/* ── WebSocket Real-time ───────────────────────────────────────────────────
 * Security Debt (P0): /ws/{user_id} accepts any user_id from URL with no
 * JWT verification. Fix deferred to Step 3 — WebSocket Security Hardening.
 * ───────────────────────────────────────────────────────────────────────── */

var _ws = null;
var _wsRetries = 0;

function connectWS() {
  if (!_user || !_user.id) return;
  var protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  var wsUrl = protocol + '//' + window.location.host + '/ws/' + _user.id;
  try {
    _ws = new WebSocket(wsUrl);
    _ws.onopen = function() { _wsRetries = 0; };
    _ws.onmessage = function(e) {
      try {
        var data = JSON.parse(e.data);
        if (data.type === 'message' && data.from === _currentConvId) {
          var msgs = document.getElementById('messages');
          var t = new Date().toLocaleTimeString('ar', { hour: '2-digit', minute: '2-digit' });
          msgs.insertAdjacentHTML('beforeend',
            '<div class="msg-wrap in"><div class="msg in">'
            + '<div class="msg-text">' + esc(data.content) + '</div>'
            + '<div class="msg-time">' + esc(t) + '</div>'
            + '</div></div>'
          );
          scrollDown();
        }
        if (data.type === 'message') loadConversations();
      } catch(ex) {}
    };
    _ws.onclose = function() {
      if (_wsRetries < 5) { _wsRetries++; setTimeout(connectWS, _wsRetries * 2000); }
    };
    _ws.onerror = function() { _ws.close(); };
  } catch(e) {}
}
