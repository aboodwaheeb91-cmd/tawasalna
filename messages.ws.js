/* ── WebSocket Real-time ─────────────────────────────────────────────────── */
// ONE socket per tab: messages.html declares <meta name="tw-ws" content="page"> so the shared
// badge socket (tw_shared.js) stands down, and connectWS() closes any socket / pending reconnect
// of its own before opening a new one. Reconnect = capped exponential backoff (WS_MAX_RETRIES);
// when the cap is hit the page shows a clear notice with a manual retry (msgOnLiveLost).

var _ws             = null;    // current active socket reference
var _wsGen          = 0;       // increments on each connectWS() call — stale closures self-cancel
var _wsRetries      = 0;
var WS_MAX_RETRIES  = 5;       // reconnect attempts after a drop — then stop + notice
var _wsReady        = false;   // true only after server sends auth_ok
var _wsReconnectTimer      = null;  // active reconnect timer handle
var _wsSessionSwitchTimer  = null;  // account-switch reconnect timer (cancellable)
var _wsPendingJwt   = '';      // fresh JWT staged for next onopen auth frame (account switch)
var _wsAuthTimeoutTimer = null; // cancellable handle for the 5s client-side auth timeout

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
    el.textContent = twNotifBadgeLabel(count);   // one cap rule (tw_shared.js — HNAV-05)
    el.style.display = count > 0 ? 'inline-block' : 'none';
  });
}

// ── WebSocket connection ──────────────────────────────────────────────────

// The JWT for the auth frame: a staged session-switch token first, else the current one
// (TwAuthSync.getToken — '' when the session is not authenticated).
function _wsToken() {
  if (_wsPendingJwt) return _wsPendingJwt;
  return (typeof TwAuthSync !== 'undefined' && typeof TwAuthSync.getToken === 'function')
    ? TwAuthSync.getToken() : '';
}

// Close the current socket + cancel its timers. The caller bumps _wsGen so the closed
// socket's onclose is ignored (no reconnect from a socket we closed on purpose).
function _wsTeardown() {
  if (_wsReconnectTimer)   { clearTimeout(_wsReconnectTimer);   _wsReconnectTimer = null; }
  if (_wsAuthTimeoutTimer) { clearTimeout(_wsAuthTimeoutTimer); _wsAuthTimeoutTimer = null; }
  _wsReady = false;
  var old = _ws;
  _ws = null;
  if (old) { try { old.close(); } catch(e) {} }
}

function _wsNotify(fnName) {
  if (typeof window !== 'undefined' && typeof window[fnName] === 'function') {
    try { window[fnName](); } catch(e) { console.warn('[messages] ' + fnName + ' failed:', e); }
  }
}

function connectWS() {
  if (!_user || !_user.id) return;

  _wsGen++;                // stale closures of the previous socket self-cancel
  _wsTeardown();           // never two sockets: close the old one + any pending reconnect
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
    _wsReady = false;
    // First message must be auth — no operational events until auth_ok received
    var jwt = _wsToken();
    _wsPendingJwt = '';  // consume the pending JWT; reconnects use the current session token
    ws.send(JSON.stringify({type: 'auth', token: jwt}));
    // Client-side auth timeout: store handle so onclose and auth_ok can cancel it
    _wsAuthTimeoutTimer = setTimeout(function() {
      _wsAuthTimeoutTimer = null;
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
        if (_wsAuthTimeoutTimer) { clearTimeout(_wsAuthTimeoutTimer); _wsAuthTimeoutTimer = null; }
        _wsRetries = 0;
        _wsReady = true;
        _wsNotify('msgOnLiveBack');
        // Signal active conversation now that the connection is authenticated
        // Hidden tab stays inactive — the server would mark incoming messages read (PR 2C)
        if (_currentConvId && !document.hidden) sendActiveConversation(_currentConvId);
        return;
      }
      // Drop all operational events until auth is confirmed
      if (!_wsReady) return;

      // Normalize to number for all id comparisons — prevents string/number mismatch
      var fromId = Number(data.from || data.from_user_id);
      var convId  = Number(_currentConvId);

      if (data.type === 'message' && fromId === convId) {
        var msgs = document.getElementById('messages');
        var t = new Date().toLocaleTimeString('ar', { hour: '2-digit', minute: '2-digit' });
        var innerHtml = '<div class="msg in">'
          + '<div class="msg-text">' + twEscHtml(data.content) + '</div>'
          + '<div class="msg-time">' + twEscHtml(t) + '</div>'
          + '</div>';
        // Cancel any pending hide timer
        if (_typingHideTimer) { clearTimeout(_typingHideTimer); _typingHideTimer = null; }
        var typingEl = document.getElementById('typing-bubble-' + fromId);
        if (typingEl) {
          // Transform typing bubble in-place — no jump, no duplicate
          typingEl.removeAttribute('id');
          typingEl.classList.remove('typing-bubble');
          typingEl.setAttribute('data-msg-id', String(data.id));
          typingEl.innerHTML = innerHtml;
        } else {
          msgs.insertAdjacentHTML('beforeend',
            '<div class="msg-wrap in" data-msg-id="' + twEscAttr(data.id) + '">' + innerHtml + '</div>'
          );
        }
        scrollDown();
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
    // Cancel auth timeout only for the connection that owns it (prevent cross-connection cancellation)
    if (ws === _ws && _wsAuthTimeoutTimer) { clearTimeout(_wsAuthTimeoutTimer); _wsAuthTimeoutTimer = null; }
    if (capturedGen !== _wsGen) return;  // superseded by newer session — ignore
    _wsReady = false;
    if (ws === _ws) _ws = null;
    // Auth/Policy close codes (4001-4007) — do not reconnect
    if (event.code >= 4001 && event.code <= 4007) return;
    if (_wsRetries < WS_MAX_RETRIES) {
      _wsRetries++;
      // Exponential backoff with jitter: 2^n seconds ± 1s, capped at 30s
      var delay = Math.min(30000, Math.pow(2, _wsRetries) * 1000 + Math.floor(Math.random() * 1000));
      _wsReconnectTimer = setTimeout(function() { _wsReconnectTimer = null; connectWS(); }, delay);
    } else {
      // Retry cap reached — stop here; the page tells the user and offers a manual retry
      _wsNotify('msgOnLiveLost');
    }
  };

  ws.onerror = function() { ws.close(); };
}

// ── TwAuthSync lifecycle — conversation socket on session change ──
// Navigation is NOT done here: twRequireAuth (messages.state.js) owns it — logout / expired /
// invalid → /login?next=/messages, account switch → reload. This handler only makes sure the
// socket never outlives the session it authenticated with.
//   Same JWT + same user + socket open/connecting → no-op (PR 2C — keeps the
//                                       conversation socket, typing and active conv)
//   No JWT / not authenticated (logout) → close socket, clear state, no reconnect
//   Different userId (account switch)   → close socket, clear state, no reconnect
//   Same userId (token refresh)         → update _jwt, reconnect WS with the new token
if (typeof TwAuthSync !== 'undefined' && TwAuthSync.onSessionChange) {
  TwAuthSync.onSessionChange(function(info) {
    // Step 0: same session and the socket is still alive → keep everything as is
    var snap0 = info && info.snapshot;
    if (info && info.jwt && info.jwt === _jwt && snap0 && snap0.isAuthenticated
        && _user && Number(snap0.userId) === Number(_user.id)
        && _ws && _ws.readyState < 2) return;

    // Step 1: Capture current user before any state mutation
    var prevUserId = _user ? Number(_user.id) : null;

    // Invalidate all active closures + close the socket and its timers
    _wsGen++;
    _wsRetries = 0;  // new session resets the retry counter
    if (_wsSessionSwitchTimer) { clearTimeout(_wsSessionSwitchTimer); _wsSessionSwitchTimer = null; }
    _wsTeardown();

    // Step 2: Current JWT — info.jwt is captured synchronously before any delay
    var capturedJwt = (info && info.jwt) || '';
    var snapshot = (info && info.snapshot)
        || (typeof TwAuthSync.getSessionSnapshot === 'function' ? TwAuthSync.getSessionSnapshot() : null);
    var newUserId = snapshot && snapshot.isAuthenticated && snapshot.userId ? Number(snapshot.userId) : null;

    // Step 3: logout / invalid / account switch → clear state, never reconnect
    if (!capturedJwt || !newUserId || (prevUserId && newUserId !== prevUserId)) {
      _jwt = '';
      _user = null;
      _currentConvId = null;
      return;
    }

    // Step 4: Same user (token refresh) → update JWT, stage for WS auth, reconnect
    _jwt = capturedJwt;
    _wsPendingJwt = capturedJwt;
    _wsSessionSwitchTimer = setTimeout(function() {
      _wsSessionSwitchTimer = null;
      if (!_user || !_user.id) return;
      connectWS();
    }, 500);
  });
}
