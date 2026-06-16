// messages.render.js — Messenger V1 render + UI + init
// Depends on: messages.state.js, messages.api.js, messages.ws.js

// ── Helpers ──────────────────────────────────────────────────────────────

function scrollDown() {
  var msgs = document.getElementById('messages');
  if (msgs) msgs.scrollTop = msgs.scrollHeight;
}

function handleKey(e) {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); doSendMessage(); }
}

function autoResize(el) {
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 100) + 'px';
}

function toggleConvList() {
  var cl = document.getElementById('convList');
  if (cl) cl.classList.toggle('mobile-show');
}

function goHome() {
  if (_currentConvId) sendInactiveConversation(_currentConvId);
  if (!_user) { window.location.href = '/'; return; }
  var dest = _user.user_type === 'co'  ? '/company-profile?id=' + _user.id
           : _user.user_type === 'edu' ? '/edu-profile?id=' + _user.id
           : '/home';
  window.location.href = dest;
}

// ── Unread count ──────────────────────────────────────────────────────────

function loadUnreadCount() {
  if (!_user || !_user.id) return;
  apiGetUnreadCount().then(function(data) {
    var count = data.count || 0;
    var msgBn = document.querySelector('.bn:last-child .bi');
    if (msgBn && count > 0) msgBn.textContent = '💬';
  }).catch(function() {});
}

// ── Conversation list ─────────────────────────────────────────────────────

function renderConvList(convs) {
  var items = document.querySelector('.conv-items');
  if (!items) return;

  if (!convs.length) {
    if (!_currentConvId) {
      items.innerHTML = '<div class="conv-empty">لا توجد محادثات بعد</div>';
    }
    return;
  }

  var frag = '';
  convs.forEach(function(c) {
    var typeIco = c.user_type === 'co' ? '🏢' : c.user_type === 'edu' ? '🎓' : '👤';
    var name    = esc(c.full_name || 'مستخدم');
    var last    = esc((c.content || '').slice(0, 45));
    var unread  = (!c.is_read && c.sender_id !== _user.id)
                  ? '<span class="ci-badge">1</span>' : '';
    var isActive = (_currentConvId && c.other_id === _currentConvId) ? ' active' : '';
    frag += '<div class="conv-item' + isActive + '" data-uid="' + c.other_id + '">'
          + '<div class="ci-ava">' + typeIco + '</div>'
          + '<div class="ci-body">'
          + '<div class="ci-top"><span class="ci-name">' + name + '</span></div>'
          + '<div class="ci-preview">' + last + '</div>'
          + '</div>' + unread + '</div>';
  });
  items.innerHTML = frag;

  // Placeholder for conversations not yet in DB (new conv via ?with=)
  if (_currentConvId && _activeConvMeta && !items.querySelector('[data-uid="' + _currentConvId + '"]')) {
    var ph = document.createElement('div');
    ph.className = 'conv-item active';
    ph.setAttribute('data-uid', String(_activeConvMeta.id));
    ph.innerHTML = '<div class="ci-ava">' + _activeConvMeta.typeIco + '</div>'
      + '<div class="ci-body">'
      + '<div class="ci-top"><span class="ci-name">' + esc(_activeConvMeta.name) + '</span></div>'
      + '<div class="ci-preview">محادثة جديدة</div></div>';
    ph.addEventListener('click', function() {
      openConversation(_activeConvMeta.id, _activeConvMeta.name, _activeConvMeta.typeIco);
    });
    items.insertAdjacentElement('afterbegin', ph);
  }

  items.querySelectorAll('.conv-item').forEach(function(el) {
    var uid  = parseInt(el.getAttribute('data-uid'));
    var name = (el.querySelector('.ci-name') || {}).textContent || '';
    var ava  = (el.querySelector('.ci-ava')  || {}).textContent || '👤';
    el.addEventListener('click', function() { openConversation(uid, name, ava); });
  });
}

function loadConversations() {
  if (!_user || !_user.id) return;
  apiGetConversations().then(function(data) {
    renderConvList(data.conversations || []);
  }).catch(function(status) {
    console.error('[messages] loadConversations failed, status:', status);
    var items = document.querySelector('.conv-items');
    if (!items || _currentConvId) return;
    if (status === 401 || status === 403) {
      items.innerHTML = '<div class="conv-empty" style="color:rgba(239,68,68,.7)">انتهت الجلسة — أعد تسجيل الدخول</div>';
    } else if (!items.querySelector('.conv-item')) {
      // Don't overwrite a valid list on a temporary poll failure
      items.innerHTML = '<div class="conv-empty" style="color:rgba(239,68,68,.5)">تعذر تحميل المحادثات</div>';
    }
  });
}

// ── Message bubble ────────────────────────────────────────────────────────

function renderMessageStatus(msg) {
  if (msg.read_at)      return '<span class="msg-status read">✓✓</span>';
  if (msg.delivered_at) return '<span class="msg-status delivered">✓✓</span>';
  return '<span class="msg-status sent">✓</span>';
}

function renderBubble(isMe, content, time, statusHtml, msgId) {
  var dir    = isMe ? 'out' : 'in';
  var idAttr = msgId ? ' data-msg-id="' + msgId + '"' : '';
  return '<div class="msg-wrap ' + dir + '"' + idAttr + '><div class="msg ' + dir + '">'
    + '<div class="msg-text">' + esc(content) + '</div>'
    + '<div class="msg-time">' + esc(time)
    + (statusHtml ? ' ' + statusHtml : '')
    + '</div></div></div>';
}

// ── Open conversation — THE ONLY ENTRY POINT ─────────────────────────────

function openConversation(otherId, name, typeIco) {
  // Signal inactive on previous conversation before switching
  if (_currentConvId && _currentConvId !== otherId) {
    sendInactiveConversation(_currentConvId);
    hideTypingBubble(_currentConvId);
  }
  _currentConvId  = otherId;
  _activeConvMeta = { id: otherId, name: name, typeIco: typeIco };
  // Signal active conversation to server (enables immediate read receipts)
  sendActiveConversation(otherId);

  document.querySelectorAll('.conv-item').forEach(function(i) { i.classList.remove('active'); });
  var activeEl = document.querySelector('[data-uid="' + otherId + '"]');
  if (activeEl) {
    activeEl.classList.add('active');
    var b = activeEl.querySelector('.ci-badge');
    if (b) b.remove();
  }

  var nameEl   = document.getElementById('chatName');
  var avaEl    = document.getElementById('chatAva');
  var statusEl = document.getElementById('chatStatus');
  if (nameEl)   nameEl.textContent   = name;
  if (avaEl)    avaEl.textContent    = typeIco;
  if (statusEl) statusEl.textContent = '';

  var viewBtn = document.getElementById('viewProfileBtn');
  if (viewBtn) viewBtn.style.display = '';

  // Show composer — only visible when a conversation is active
  var chatInput = document.getElementById('chatInput');
  if (chatInput) chatInput.style.display = '';

  var convListEl = document.getElementById('convList');
  if (convListEl) convListEl.classList.remove('mobile-show');

  var msgArea = document.getElementById('messages');
  msgArea.innerHTML = '<div style="text-align:center;padding:20px;color:var(--t3);font-size:.8rem">⏳</div>';

  apiGetMessages(otherId).then(function(data) {
    var list = data.messages || [];
    if (!list.length) {
      msgArea.innerHTML = '<div style="text-align:center;padding:30px;color:var(--t3);font-size:.8rem">ابدأ المحادثة ✉️</div>';
      loadUnreadCount();
      return;
    }
    var lastDate = '';
    msgArea.innerHTML = list.map(function(msg) {
      var isMe    = msg.sender_id === _user.id;
      var d       = new Date(msg.created_at);
      var t       = d.toLocaleTimeString('ar', { hour: '2-digit', minute: '2-digit' });
      var dateStr = d.toLocaleDateString('ar', { weekday: 'long', month: 'short', day: 'numeric' });
      var dateDiv = '';
      if (dateStr !== lastDate) {
        lastDate = dateStr;
        dateDiv = '<div class="date-divider">' + esc(dateStr) + '</div>';
      }
      var statusHtml = isMe ? renderMessageStatus(msg) : '';
      return dateDiv + renderBubble(isMe, msg.content, t, statusHtml, msg.id);
    }).join('');
    scrollDown();
    loadUnreadCount();
  }).catch(function() {
    msgArea.innerHTML = '<div style="text-align:center;color:var(--t3)">تعذر تحميل الرسائل</div>';
  });
}

// ── Send message — HTTP primary, WS receive only ──────────────────────────
// HTTP is source of truth for DB save. ✓ shown ONLY after server confirms.

function doSendMessage() {
  var input = document.getElementById('msgInput');
  var text  = input ? input.value.trim() : '';
  if (!text || !_currentConvId) return;

  var sendBtn = document.querySelector('.send-btn');
  if (sendBtn) sendBtn.disabled = true;

  // Cancel debounce; notify receiver immediately so their 2.5s delayed hide starts now
  if (_typingTimer) { clearTimeout(_typingTimer); _typingTimer = null; }
  sendTypingStop(_currentConvId);

  var savedText = text;
  input.value = '';
  autoResize(input);
  var _twT0 = performance.now();

  var pid = 'pm' + Date.now();
  var msgs = document.getElementById('messages');
  var t    = new Date().toLocaleTimeString('ar', { hour: '2-digit', minute: '2-digit' });

  msgs.insertAdjacentHTML('beforeend',
    '<div id="' + pid + '" class="msg-wrap out">'
    + '<div class="msg out">'
    + '<div class="msg-text" style="opacity:.6">' + esc(savedText) + '</div>'
    + '<div class="msg-time">' + esc(t)
    + ' <span class="msg-status pending" id="' + pid + 'st">•••</span></div>'
    + '</div></div>'
  );
  scrollDown();

  apiSendMessage(_currentConvId, savedText)
    .then(function(data) {
      var msg = (data && data.message) || {};
      var el  = document.getElementById(pid);
      var realId = msg.id;
      var _srv = data && data._timing;
      twDebugLog('HTTP send', {
        net_ms:   (performance.now() - _twT0).toFixed(0),
        id:       realId || '?',
        drv:      _srv ? (_srv.driver || '?') : '?',
        srv_ms:   _srv ? _srv.total_ms       : '?',
        db_ms:    _srv ? _srv.db_ms          : '?',
        conn_ms:  _srv ? _srv.conn_ms        : '?',
        sync_ms:  _srv ? _srv.sync_set_ms    : '?',
        ins_exec: _srv ? _srv.insert_exec_ms : '?',
        ins_ms:   _srv ? _srv.insert_ms      : '?',
        upd_ms:   _srv ? _srv.update_ms      : '?',
        cnt_ms:   _srv ? _srv.count_ms       : '?',
        ws_ms:    _srv ? _srv.ws_ms          : '?'
      });
      if (el && realId) {
        el.setAttribute('data-msg-id', String(realId));
      }
      var txt = el && el.querySelector('.msg-text');
      if (txt) txt.style.opacity = '';
      // Apply any WS status_update that arrived before HTTP response
      if (realId && _pendingStatus[realId]) {
        _applyStatusToEl(el, _pendingStatus[realId]);
        delete _pendingStatus[realId];
        loadConversations();
        return;
      }
      var st  = document.getElementById(pid + 'st');
      if (st) {
        if (msg.read_at) {
          st.className = 'msg-status read'; st.textContent = '✓✓';
        } else if (msg.delivered_at) {
          st.className = 'msg-status delivered'; st.textContent = '✓✓';
        } else {
          st.className = 'msg-status sent'; st.textContent = '✓';
        }
      }
      loadConversations();
    })
    .catch(function() {
      var el = document.getElementById(pid);
      if (el) el.classList.add('msg-failed');
      var st = document.getElementById(pid + 'st');
      if (st) { st.textContent = '✗'; st.style.color = '#ef4444'; }
      var inp = document.getElementById('msgInput');
      if (inp) { inp.value = savedText; autoResize(inp); }
    })
    .finally(function() {
      if (sendBtn) sendBtn.disabled = false;
    });
}

// ── Silent message reload (receiver polling) ──────────────────────────────
// Called on interval — only refreshes if DB has more messages than shown.
// Preserves scroll position if user is not at bottom.

function reloadMessagesQuiet() {
  if (!_currentConvId) return;
  apiGetMessages(_currentConvId).then(function(data) {
    var list = data.messages || [];
    var msgs = document.getElementById('messages');
    if (!msgs) return;
    var current = msgs.querySelectorAll('.msg-wrap').length;
    if (list.length <= current) return;
    var atBottom = (msgs.scrollHeight - msgs.scrollTop - msgs.clientHeight) < 80;
    var lastDate = '';
    msgs.innerHTML = list.map(function(msg) {
      var isMe    = msg.sender_id === _user.id;
      var d       = new Date(msg.created_at);
      var t       = d.toLocaleTimeString('ar', { hour: '2-digit', minute: '2-digit' });
      var dateStr = d.toLocaleDateString('ar', { weekday: 'long', month: 'short', day: 'numeric' });
      var dateDiv = '';
      if (dateStr !== lastDate) {
        lastDate = dateStr;
        dateDiv = '<div class="date-divider">' + esc(dateStr) + '</div>';
      }
      var statusHtml = isMe ? renderMessageStatus(msg) : '';
      return dateDiv + renderBubble(isMe, msg.content, t, statusHtml, msg.id);
    }).join('');
    if (atBottom) scrollDown();
    loadUnreadCount();
  }).catch(function() {});
}

// ── View conversation partner's profile ───────────────────────────────────

function viewConvProfile() {
  if (!_activeConvMeta || !_activeConvMeta.id) return;
  apiGetUser(_activeConvMeta.id).then(function(data) {
    var tw = data && data.user && data.user.tw_id;
    if (tw) {
      window.location.href = '/u/' + tw;
    } else {
      showToast('تعذر فتح الملف الشخصي', 'error');
    }
  }).catch(function() { showToast('تعذر فتح الملف الشخصي', 'error'); });
}

// ── ?with= deep-link handler ──────────────────────────────────────────────

function handleWithParam(twId) {
  apiLookupByTwId(twId).then(function(data) {
    if (!data || !data.id) {
      document.getElementById('messages').innerHTML =
        '<div style="text-align:center;padding:30px;color:var(--t3)">تعذر فتح المحادثة</div>';
    } else {
      var typeIco   = data.user_type === 'co' ? '🏢' : data.user_type === 'edu' ? '🎓' : '👤';
      var convItems = document.querySelector('.conv-items');
      var ph = document.createElement('div');
      ph.className = 'conv-item';
      ph.setAttribute('data-uid', String(data.id));
      ph.innerHTML = '<div class="ci-ava">' + typeIco + '</div>'
        + '<div class="ci-body"><div class="ci-top"><span class="ci-name">'
        + esc(data.full_name || 'مستخدم') + '</span></div></div>';
      if (convItems) convItems.insertAdjacentElement('afterbegin', ph);
      openConversation(data.id, data.full_name || 'مستخدم', typeIco);
      history.replaceState(null, '', '/messages');
    }
    // loadConversations runs AFTER _currentConvId is set → active state preserved
    loadConversations();
  }).catch(function() {
    document.getElementById('messages').innerHTML =
      '<div style="text-align:center;padding:30px;color:var(--t3)">تعذر فتح المحادثة</div>';
    loadConversations();
  });
}

// ── Init ──────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', function() {
  var withParam = new URLSearchParams(location.search).get('with');
  if (withParam && _user && _user.id) {
    handleWithParam(withParam);
  } else {
    // Mobile: .conv-list is display:none by default (CSS). Show it immediately
    // so the user sees conversations as the landing view, not just "اختر محادثة".
    // On desktop this has no visual effect (conv-list is always visible).
    var convListEl = document.getElementById('convList');
    if (convListEl) convListEl.classList.add('mobile-show');
    loadConversations();
  }
  loadUnreadCount();
  connectWS();
  // Poll every 10s: conversations list + active conversation messages.
  // Required because HTTP send does not push to receiver via WS.
  setInterval(function() {
    loadConversations();
    reloadMessagesQuiet();
  }, 10000);

  // Typing indicator: debounced WS typing events
  var msgInput = document.getElementById('msgInput');
  if (msgInput) {
    msgInput.addEventListener('input', function() {
      autoResize(this);
      if (!_currentConvId) return;
      if (_typingTimer) clearTimeout(_typingTimer);
      sendTyping(_currentConvId);
      _typingTimer = setTimeout(function() {
        sendTypingStop(_currentConvId);
        _typingTimer = null;
      }, 1800);
    });
  }

  // Signal inactive conversation on page leave
  window.addEventListener('beforeunload', function() {
    if (_currentConvId) sendInactiveConversation(_currentConvId);
  });
});
