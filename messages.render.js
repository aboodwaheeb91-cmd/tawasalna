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
  }).catch(function() {});
}

// ── Message bubble ────────────────────────────────────────────────────────

function renderBubble(isMe, content, time, readIcon) {
  var dir = isMe ? 'out' : 'in';
  return '<div class="msg-wrap ' + dir + '"><div class="msg ' + dir + '">'
    + '<div class="msg-text">' + esc(content) + '</div>'
    + '<div class="msg-time">' + esc(time)
    + (readIcon ? ' <span style="font-size:.6rem;opacity:.7">' + readIcon + '</span>' : '')
    + '</div></div></div>';
}

// ── Open conversation — THE ONLY ENTRY POINT ─────────────────────────────

function openConversation(otherId, name, typeIco) {
  _currentConvId  = otherId;
  _activeConvMeta = { id: otherId, name: name, typeIco: typeIco };

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
      var readIcon = isMe ? (msg.is_read ? '✓✓' : '✓') : '';
      return dateDiv + renderBubble(isMe, msg.content, t, readIcon);
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

  var savedText = text;
  input.value = '';
  autoResize(input);

  var pid = 'pm' + Date.now();
  var msgs = document.getElementById('messages');
  var t    = new Date().toLocaleTimeString('ar', { hour: '2-digit', minute: '2-digit' });

  msgs.insertAdjacentHTML('beforeend',
    '<div id="' + pid + '" class="msg-wrap out">'
    + '<div class="msg out">'
    + '<div class="msg-text" style="opacity:.6">' + esc(savedText) + '</div>'
    + '<div class="msg-time">' + esc(t) + ' <span id="' + pid + 'st">•••</span></div>'
    + '</div></div>'
  );
  scrollDown();

  apiSendMessage(_currentConvId, savedText)
    .then(function() {
      var el  = document.getElementById(pid);
      var txt = el && el.querySelector('.msg-text');
      var st  = document.getElementById(pid + 'st');
      if (txt) txt.style.opacity = '';
      if (st)  st.textContent = '✓';
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
      var readIcon = isMe ? (msg.is_read ? '✓✓' : '✓') : '';
      return dateDiv + renderBubble(isMe, msg.content, t, readIcon);
    }).join('');
    if (atBottom) scrollDown();
    loadUnreadCount();
  }).catch(function() {});
}

// ── View conversation partner's profile ───────────────────────────────────

function viewConvProfile() {
  if (!_activeConvMeta || !_activeConvMeta.id) return;
  apiGetUser(_activeConvMeta.id).then(function(data) {
    if (data && data.tw_id) {
      window.location.href = '/u/' + data.tw_id;
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
});
