/* ── WebSocket Real-time ───────────────────────────────────────────────────
 * Security Debt (P0): /ws/{user_id} accepts any user_id from URL with no
 * JWT verification. Fix deferred to Step 3 — WebSocket Security Hardening.
 * ───────────────────────────────────────────────────────────────────────── */

var _ws = null;
var _wsRetries = 0;

// ── Active conversation signalling ───────────────────────────────────────

function sendActiveConversation(otherId) {
  if (_ws && _ws.readyState === WebSocket.OPEN)
    _ws.send(JSON.stringify({type: 'active_conversation', other_id: otherId}));
}

function sendInactiveConversation(otherId) {
  if (_ws && _ws.readyState === WebSocket.OPEN)
    _ws.send(JSON.stringify({type: 'inactive_conversation', other_id: otherId}));
}

// ── Typing events ──────────────────────────────────────────────────────────

function sendTyping(toUserId) {
  if (_ws && _ws.readyState === WebSocket.OPEN)
    _ws.send(JSON.stringify({type: 'typing', to_user_id: toUserId}));
}

function sendTypingStop(toUserId) {
  if (_ws && _ws.readyState === WebSocket.OPEN)
    _ws.send(JSON.stringify({type: 'typing_stop', to_user_id: toUserId}));
}

// ── Typing indicator UI ───────────────────────────────────────────────────

function showTypingIndicator() {
  var st = document.getElementById('chatStatus');
  if (st) st.textContent = 'يكتب الآن...';
  if (_typingHideTimer) clearTimeout(_typingHideTimer);
  _typingHideTimer = setTimeout(hideTypingIndicator, 3000);
}

function hideTypingIndicator() {
  if (_typingHideTimer) { clearTimeout(_typingHideTimer); _typingHideTimer = null; }
  var st = document.getElementById('chatStatus');
  if (st) st.textContent = '';
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
    el.textContent = count > 9 ? '9+' : String(count);
    el.style.display = count > 0 ? 'inline-block' : 'none';
  });
}

// ── WebSocket connection ──────────────────────────────────────────────────

function connectWS() {
  if (!_user || !_user.id) return;
  var protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  var wsUrl = protocol + '//' + window.location.host + '/ws/' + _user.id;
  try {
    _ws = new WebSocket(wsUrl);
    _ws.onopen = function() {
      _wsRetries = 0;
      // If a conversation was opened before WS connected (e.g. ?with= deep-link), signal it now
      if (_currentConvId) sendActiveConversation(_currentConvId);
    };
    _ws.onmessage = function(e) {
      try {
        var data = JSON.parse(e.data);

        if (data.type === 'message' && data.from === _currentConvId) {
          // New incoming message in active conversation — append it
          var msgs = document.getElementById('messages');
          var t = new Date().toLocaleTimeString('ar', { hour: '2-digit', minute: '2-digit' });
          msgs.insertAdjacentHTML('beforeend',
            '<div class="msg-wrap in" data-msg-id="' + data.id + '"><div class="msg in">'
            + '<div class="msg-text">' + esc(data.content) + '</div>'
            + '<div class="msg-time">' + esc(t) + '</div>'
            + '</div></div>'
          );
          scrollDown();
          // Hide typing indicator when message arrives
          hideTypingIndicator();
        }

        if (data.type === 'message') {
          loadConversations();
        }

        if (data.type === 'status_update') {
          updateMessageStatus(data);
        }

        if (data.type === 'typing' && data.from_user_id === _currentConvId) {
          showTypingIndicator();
        }

        if (data.type === 'typing_stop' && data.from_user_id === _currentConvId) {
          hideTypingIndicator();
        }

        if (data.type === 'badge_update' && data.badge === 'messages') {
          applyMsgBadge(data.count || 0);
        }

      } catch(ex) {}
    };
    _ws.onclose = function() {
      if (_wsRetries < 5) { _wsRetries++; setTimeout(connectWS, _wsRetries * 2000); }
    };
    _ws.onerror = function() { _ws.close(); };
  } catch(e) {}
}
