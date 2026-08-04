/* ── WebSocket Real-time ─────────────────────────────────────────────────── */

var _ws             = null;    // current active socket reference
var _wsGen          = 0;       // increments on each connectWS() call — stale closures self-cancel
var _wsRetries      = 0;
var _wsReady        = false;   // true only after server sends auth_ok
var _wsReconnectTimer      = null;  // active reconnect timer handle
var _wsSessionSwitchTimer  = null;  // account-switch reconnect timer (cancellable)
var _wsPendingJwt   = '';      // fresh JWT staged for next onopen auth frame (account switch)

// ── Active conversation signalling ───────────────────────────────────────

function sendActiveConversation(otherId) {
  if (_wsReady && _ws && _ws.readyState === WebSocket.OPEN)
    _ws.send(JSON.stringify({type: 'active_conversation', other_id: otherId}));
}

function sendInactiveConversation(otherId) {
  if (_wsReady && _ws && _ws.readyState === WebSocket.OPEN)
    _ws.send(JSON.stringify({type: 'inactive_conversation', other_id: otherId}));
}

// ── Typing events ──────────────────────────────────────────────────────────

function sendTyping(toUserId) {
  if (_wsReady && _ws && _ws.readyState === WebSocket.OPEN)
    _ws.send(JSON.stringify({type: 'typing', to_user_id: toUserId}));
}

function sendTypingStop(toUserId) {
  if (_wsReady && _ws && _ws.readyState === WebSocket.OPEN)
    _ws.send(JSON.stringify({type: 'typing_stop', to_user_id: toUserId}));
}

// ── Typing bubble (in-chat) ───────────────────────────────────────────────

function showTypingBubble(fromId) {
  var msgs = document.getElementById('messages');
  if (!msgs) return;
  if (!document.getElementById('typing-bubble-' + fromId)) {
    msgs.insertAdjacentHTML('beforeend',
      '<div id="typing-bubble-' + fromId + '" class="msg-wrap in typing-bubble">'
      + '<div class="msg in"><div class="msg-text typing-dots">'
      + '<span></span><span></span><span></span>'
      + '</div></div></div>'
    );
    scrollDown();
  }
  // Failsafe: hide after 5s if no typing_stop or message arrives
  _scheduleHideTypingBubble(fromId, 5000);
}

function hideTypingBubble(fromId) {
  if (_typingHideTimer) { clearTimeout(_typingHideTimer); _typingHideTimer = null; }
  var el = document.getElementById('typing-bubble-' + fromId);
  if (el) el.remove();
}

function _scheduleHideTypingBubble(fromId, ms) {
  if (_typingHideTimer) clearTimeout(_typingHideTimer);
  _typingHideTimer = setTimeout(function() { hideTypingBubble(fromId); }, ms);
}

// ── Status update helper ──────────────────────────────────────────────────

function _applyStatusToEl(el, status) {
  var st = el.querySelector('.msg-status');
  if (!st) return;
  if (status === 'read') {
    st.className = 'msg-status read';
    st.textContent = '✓✓';
  } else if (status === 'delivered') {
    st.className = 'msg-status delivered';
    st.textContent = '✓✓';
  }
}

function updateMessageStatus(data) {
  var status = data.status;
  var ids = data.ids || (data.id != null ? [data.id] : []);
  twDebugLog('status_update', { status: status, ids: ids.join(',') });
  ids.forEach(function(id) {
    var el = document.querySelector('[data-msg-id="' + id + '"]');
    if (el) {
      _applyStatusToEl(el, status);
    } else {
      // WS event arrived before HTTP ack set data-msg-id — stash for later
      _pendingStatus[id] = status;
    }
  });
}

// ── Badge update ──────────────────────────────────────────────────────────

function applyMsgBadge(count) {
  document.querySelectorAll('[data-badge="msgs"]').forEach(function(el) {
    el.textContent = count > 9 ? '9+' : String(count);
    el.style.display = count > 0 ? 'inline-block' : 'none';
  });
}

// ── WebSocket connection ──────────────────────────────────────────────────

function connectWS() {
  if (!_user || !_user.id) return;

  _wsGen++;
  var capturedGen = _wsGen;
  var capturedUid = Number(_user.id);

  var protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  var wsUrl = protocol + '//' + window.location.host + '/ws/' + _user.id;
  var ws;
  try { ws = new WebSocket(wsUrl); } catch(e) { return; }
  _ws = ws;
  _wsReady = false;

  ws.onopen = function() {
    if (capturedGen !== _wsGen || ws !== _ws) { ws.close(); return; }
    _wsRetries = 0;
    _wsReady = false;
    // First message must be auth — no operational events until auth_ok received
    var jwt = _wsPendingJwt || (typeof localStorage !== 'undefined' && localStorage.getItem('tw_jwt')) || '';
    _wsPendingJwt = '';  // consume the pending JWT; fall back to localStorage on reconnects
    ws.send(JSON.stringify({type: 'auth', token: jwt}));
    // Client-side auth timeout: if server hasn't confirmed auth in 5s, close
    setTimeout(function() {
      if (capturedGen === _wsGen && ws === _ws && !_wsReady) {
        ws.close(1000, 'auth_timeout');
      }
    }, 5000);
  };

  ws.onmessage = function(e) {
    // Stale-connection guards: generation and socket identity
    if (capturedGen !== _wsGen || ws !== _ws) return;
    try {
      var data = JSON.parse(e.data);

      // Auth handshake — must be first exchange
      if (data.type === 'auth_ok') {
        // Validate server echoed the correct user_id
        if (Number(data.user_id) !== capturedUid) {
          // Mismatch: advance generation so stale closures self-cancel, close with Forbidden
          _wsGen++;
          _wsReady = false;
          ws.close(4003);
          return;
        }
        _wsReady = true;
        // Signal active conversation now that the connection is authenticated
        if (_currentConvId) sendActiveConversation(_currentConvId);
        return;
      }
      // Drop all operational events until auth is confirmed
      if (!_wsReady) return;

      // Normalize to number for all id comparisons — prevents string/number mismatch
      var fromId = Number(data.from || data.from_user_id);
      var convId  = Number(_currentConvId);

      if (data.type === 'message' && fromId === convId) {
        var _twRx = performance.now();
        var msgs = document.getElementById('messages');
        var t = new Date().toLocaleTimeString('ar', { hour: '2-digit', minute: '2-digit' });
        var innerHtml = '<div class="msg in">'
          + '<div class="msg-text">' + esc(data.content) + '</div>'
          + '<div class="msg-time">' + esc(t) + '</div>'
          + '</div>';
        // Cancel any pending hide timer
        if (_typingHideTimer) { clearTimeout(_typingHideTimer); _typingHideTimer = null; }
        var typingEl = document.getElementById('typing-bubble-' + fromId);
        if (typingEl) {
          // Transform typing bubble in-place — no jump, no duplicate
          typingEl.removeAttribute('id');
          typingEl.classList.remove('typing-bubble');
          typingEl.setAttribute('data-msg-id', data.id);
          typingEl.innerHTML = innerHtml;
        } else {
          msgs.insertAdjacentHTML('beforeend',
            '<div class="msg-wrap in" data-msg-id="' + data.id + '">' + innerHtml + '</div>'
          );
        }
        scrollDown();
        twDebugLog('WS→DOM', { ms: (performance.now() - _twRx).toFixed(0), id: data.id, from: fromId, via: typingEl ? 'transform' : 'append' });
      }

      if (data.type === 'message') {
        loadConversations();
      }

      if (data.type === 'status_update') {
        updateMessageStatus(data);
      }

      if (data.type === 'typing' && fromId === convId) {
        showTypingBubble(fromId);
      }

      if (data.type === 'typing_stop' && fromId === convId) {
        // Delay hide 2.5s — lets the bubble linger naturally after typing stops
        _scheduleHideTypingBubble(fromId, 2500);
      }

      if (data.type === 'badge_update' && data.badge === 'messages') {
        applyMsgBadge(data.count || 0);
      }

    } catch(ex) {}
  };

  ws.onclose = function(event) {
    if (capturedGen !== _wsGen) return;  // superseded by newer session — ignore
    _wsReady = false;
    if (ws === _ws) _ws = null;
    // Auth/Policy close codes (4001-4007) — do not reconnect
    if (event.code >= 4001 && event.code <= 4007) return;
    if (_wsRetries < 5) {
      _wsRetries++;
      // Exponential backoff with jitter: 2^n seconds ± 1s, capped at 30s
      var delay = Math.min(30000, Math.pow(2, _wsRetries) * 1000 + Math.floor(Math.random() * 1000));
      _wsReconnectTimer = setTimeout(connectWS, delay);
    }
  };

  ws.onerror = function() { ws.close(); };
}

// ── TwAuthSync lifecycle — close socket on logout or account-switch ───────
// TwAuthSync fires when tw_jwt changes in any tab or on page focus/visibility.
if (typeof TwAuthSync !== 'undefined' && TwAuthSync.onSessionChange) {
  TwAuthSync.onSessionChange(function(info) {
    // Invalidate all active closures by advancing the generation counter
    _wsGen++;
    _wsReady = false;
    if (_wsReconnectTimer) { clearTimeout(_wsReconnectTimer); _wsReconnectTimer = null; }
    if (_wsSessionSwitchTimer) { clearTimeout(_wsSessionSwitchTimer); _wsSessionSwitchTimer = null; }
    var sock = _ws;
    _ws = null;
    if (sock) { try { sock.close(); } catch(e) {} }
    // Reconnect on account-switch (new JWT exists); stay disconnected on logout
    if (info && info.jwt) {
      _wsSessionSwitchTimer = setTimeout(function() {
        _wsSessionSwitchTimer = null;
        // Read fresh session — prefer V2 getSessionSnapshot() over stale localStorage
        var snapshot = (typeof TwAuthSync !== 'undefined' && typeof TwAuthSync.getSessionSnapshot === 'function')
            ? TwAuthSync.getSessionSnapshot() : null;
        var freshUser = null, freshJwt = '';
        if (snapshot) {
          if (!snapshot.isAuthenticated) return;
          freshUser = { id: snapshot.userId };
          freshJwt  = snapshot.jwt || '';
        } else {
          try { freshUser = JSON.parse((typeof localStorage !== 'undefined' && localStorage.getItem('tw_user')) || 'null'); } catch(e) {}
          freshJwt = (typeof localStorage !== 'undefined' && localStorage.getItem('tw_jwt')) || '';
        }
        if (!freshUser || !freshUser.id || !freshJwt) return;
        _user = freshUser;
        _wsPendingJwt = freshJwt;  // stage fresh JWT for onopen auth frame
        connectWS();
      }, 500);
    }
  });
}
