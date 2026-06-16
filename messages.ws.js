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
    _ws.onclose = function() {
      if (_wsRetries < 5) { _wsRetries++; setTimeout(connectWS, _wsRetries * 2000); }
    };
    _ws.onerror = function() { _ws.close(); };
  } catch(e) {}
}
