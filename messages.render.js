// messages.render.js — Messenger V1 render + UI + init
// Depends on: messages.state.js, messages.api.js, messages.ws.js

// ── Account-type presentation (avatar/badge only — no new data, no new logic) ──
// Maps the user_type already returned by the API to a label/icon/color class.
var _TYPE_INFO = {
  co:  { label: 'شركة',       icon: '🏢', cls: 't-co'  },
  edu: { label: 'جهة تعليمية', icon: '🎓', cls: 't-edu' },
  emp: { label: 'موظف',       icon: '👤', cls: 't-emp' }
};
function typeInfo(t) { return _TYPE_INFO[t] || _TYPE_INFO.emp; }

function avatarHtml(name, avatarUrl) {
  if (avatarUrl) return '<img src="' + esc(avatarUrl) + '" alt="" loading="lazy">';
  var initial = String(name || '').trim().charAt(0) || '؟';
  return '<span class="ava-initial">' + esc(initial) + '</span>';
}

function typeBadgeHtml(type, cls) {
  var info = typeInfo(type);
  return '<span class="' + cls + ' ' + info.cls + '" title="' + info.label + '">' + info.icon + '</span>';
}

// Text-only pill badge — same identity-display convention as the followers
// list (profile-v2.css .sc-fl-type-badge): label only, no emoji, color-tinted
// background. Used for the chat header and conversation-list cards.
function typeBadgePillHtml(type) {
  var info = typeInfo(type);
  return '<span class="type-badge-pill ' + info.cls + '">' + info.label + '</span>';
}

// Per-type card accent class — namespaced "acc-*" (not "t-*") so it never
// collides with the solid-fill avatar gradient classes of the same name.
function accentClass(type) {
  return typeInfo(type).cls.replace('t-', 'acc-');
}

// Line-2 profession/specialty caption — profiles.headline (falling back to
// the older profiles.title column, same convention as profile.html /
// profile-v2.render.js: `prof.headline || prof.title`). The account type
// already shows as the line-1 badge, so when neither field is set, render
// no line at all rather than repeating the type.
function profession(c) {
  return (c && (c.headline || c.title)) || '';
}
function professionLineHtml(c) {
  var text = profession(c);
  return text ? '<div class="ci-sub">' + esc(text) + '</div>' : '';
}

function formatConvTime(iso) {
  if (!iso) return '';
  try { return new Date(iso).toLocaleTimeString('ar', { hour: '2-digit', minute: '2-digit' }); }
  catch (e) { return ''; }
}

// ── Online row (presence) ───────────────────────────────────────────────
// No client-accessible "who is online" signal exists anywhere in the
// backend today (see ARCHITECTURE.md). This renders a structurally-ready
// row — real avatar/name/type-badge — if presence data is ever supplied;
// otherwise it leaves the honest empty state already in the markup.
function renderOnlineRow(users) {
  var wrap = document.getElementById('onlineRowItems');
  if (!wrap) return;
  if (!users || !users.length) {
    wrap.innerHTML = '<div class="online-empty">لا يوجد متصلون حالياً</div>';
    return;
  }
  wrap.innerHTML = users.map(function(u) {
    var type = u.user_type || 'emp';
    var shortName = String(u.full_name || '').trim().split(' ')[0] || 'مستخدم';
    return '<div class="online-item" data-uid="' + u.id + '">'
      + '<div class="online-ava-wrap"><div class="online-ava ' + typeInfo(type).cls + '">'
      + avatarHtml(u.full_name, u.avatar_url) + '</div>'
      + '<span class="online-dot"></span>'
      + typeBadgeHtml(type, 'online-type-badge') + '</div>'
      + '<span class="online-name">' + esc(shortName) + '</span>'
      + '</div>';
  }).join('');
}

// ── Conversation list filter/search (client-side, DOM-only) ──────────────
var _convFilterMode  = 'all';
var _convSearchTerm  = '';

// Tracks whether openConversation() has already pushed the "conversation-open"
// history entry, so switching directly between conversations doesn't stack
// multiple entries (see openConversation/backToConvList/popstate below).
var _convHistoryPushed = false;

function applyConvFilter(mode) {
  _convFilterMode = mode || 'all';
  var term = _convSearchTerm.toLowerCase();
  document.querySelectorAll('.conv-item').forEach(function(el) {
    var matchesFilter = _convFilterMode !== 'unread' || !!el.querySelector('.ci-badge');
    var nameEl = el.querySelector('.ci-name');
    var prevEl = el.querySelector('.ci-preview');
    var text = ((nameEl ? nameEl.textContent : '') + ' ' + (prevEl ? prevEl.textContent : '')).toLowerCase();
    var matchesSearch = !term || text.indexOf(term) !== -1;
    el.style.display = (matchesFilter && matchesSearch) ? '' : 'none';
  });
}

function initConvFilters() {
  var box = document.getElementById('convFilters');
  if (!box) return;
  box.querySelectorAll('.cf-chip').forEach(function(chip) {
    chip.addEventListener('click', function() {
      box.querySelectorAll('.cf-chip').forEach(function(c) { c.classList.remove('active'); });
      chip.classList.add('active');
      applyConvFilter(chip.getAttribute('data-filter'));
    });
  });
}

function initConvSearch() {
  var input = document.getElementById('convSearch');
  if (!input) return;
  input.addEventListener('input', function() {
    _convSearchTerm = input.value.trim();
    applyConvFilter(_convFilterMode);
  });
}

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

// ── Header ☰ menu dropdown — shared Global Header Menu (tw_shared.js); see
// ARCHITECTURE.md "Global Header Menu Contract". "messages" marks "الرسائل"
// as the current/disabled page since this IS the messages page. ──
if (typeof initGlobalHeaderMenu === 'function') {
  initGlobalHeaderMenu('scMenuBtn', 'scMenuDropdown', 'messages');
}
// Run the same open-conversation cleanup the dedicated home/profile buttons
// already do (sendInactiveConversation over the existing WS) before ANY
// shared-menu link navigates away from this page.
window.twBeforeHeaderNav = function() {
  if (_currentConvId) sendInactiveConversation(_currentConvId);
};

// ── Chat-options menu dropdown (beside the conversation avatar) — same
// toggle/outside-click pattern as the header menu above, separate ids ──
function toggleChatMenu(e) {
  if (e) e.stopPropagation();
  var dd = document.getElementById('chMenuDropdown');
  if (dd) dd.classList.toggle('open');
}
document.addEventListener('click', function(e) {
  var wrap = document.getElementById('chMenuWrap');
  var dd = document.getElementById('chMenuDropdown');
  if (wrap && dd && !wrap.contains(e.target)) dd.classList.remove('open');
});

// ── Unified header nav buttons (.sc-header, Profile V2 source) — type-aware
// since messages.html is shared by emp/co/edu, unlike profile-showcase.html
// which always goes to /home regardless of account type ──
function goMessengerHome() {
  if (_currentConvId) sendInactiveConversation(_currentConvId);
  if (!_user) { window.location.href = '/'; return; }
  var dest = _user.user_type === 'co'  ? '/company'
           : _user.user_type === 'edu' ? '/edu'
           : '/home';
  window.location.href = dest;
}

function goMessengerProfile() {
  if (_currentConvId) sendInactiveConversation(_currentConvId);
  if (!_user) { window.location.href = '/'; return; }
  window.location.href = _user.tw_id ? '/u/' + _user.tw_id : '/profile';
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
    var type    = c.user_type || 'emp';
    var name    = esc(c.full_name || 'مستخدم');
    var last    = esc((c.content || '').slice(0, 45));
    var time    = esc(formatConvTime(c.created_at));
    var unreadCount = c.unread_count || 0;
    var unreadCls   = unreadCount > 0 ? ' unread' : '';
    var unread  = unreadCount > 0
                  ? '<span class="ci-badge">' + (unreadCount > 99 ? '99+' : unreadCount) + '</span>' : '';
    var isActive = (_currentConvId && c.other_id === _currentConvId) ? ' active' : '';
    var avatarUrl = c.avatar_url || '';
    frag += '<div class="conv-item ' + accentClass(type) + isActive + unreadCls + '" data-uid="' + c.other_id
          + '" data-type="' + type + '" data-avatar="' + esc(avatarUrl)
          + '" data-headline="' + esc(profession(c)) + '">'
          + '<div class="ci-ava-wrap"><div class="ci-ava ' + typeInfo(type).cls + '">'
          + avatarHtml(c.full_name, avatarUrl) + '</div></div>'
          + '<div class="ci-body">'
          + '<div class="ci-name-row"><span class="ci-name">' + name + '</span>' + typeBadgePillHtml(type) + '</div>'
          + professionLineHtml(c)
          + '<div class="ci-preview">' + last + '</div>'
          + '</div>'
          + '<div class="ci-aside"><span class="ci-time">' + time + '</span>' + unread + '</div>'
          + '</div>';
  });
  items.innerHTML = frag;

  // Placeholder for conversations not yet in DB (new conv via ?with=)
  if (_currentConvId && _activeConvMeta && !items.querySelector('[data-uid="' + _currentConvId + '"]')) {
    var phType = _activeConvMeta.type || 'emp';
    var ph = document.createElement('div');
    ph.className = 'conv-item ' + accentClass(phType) + ' active';
    ph.setAttribute('data-uid', String(_activeConvMeta.id));
    ph.innerHTML = '<div class="ci-ava-wrap"><div class="ci-ava ' + typeInfo(phType).cls + '">'
      + avatarHtml(_activeConvMeta.name, _activeConvMeta.avatarUrl) + '</div></div>'
      + '<div class="ci-body">'
      + '<div class="ci-name-row"><span class="ci-name">' + esc(_activeConvMeta.name) + '</span>' + typeBadgePillHtml(phType) + '</div>'
      + '<div class="ci-preview">محادثة جديدة</div></div>';
    ph.addEventListener('click', function() {
      openConversation(_activeConvMeta.id, _activeConvMeta.name, _activeConvMeta.type, _activeConvMeta.avatarUrl, _activeConvMeta.headline);
    });
    items.insertAdjacentElement('afterbegin', ph);
  }

  items.querySelectorAll('.conv-item').forEach(function(el) {
    var uid       = parseInt(el.getAttribute('data-uid'));
    var name      = (el.querySelector('.ci-name') || {}).textContent || '';
    var type      = el.getAttribute('data-type') || 'emp';
    var avatarUrl = el.getAttribute('data-avatar') || '';
    var headline  = el.getAttribute('data-headline') || '';
    el.addEventListener('click', function() { openConversation(uid, name, type, avatarUrl, headline); });
  });

  applyConvFilter(_convFilterMode);
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

function openConversation(otherId, name, type, avatarUrl, headline) {
  // Signal inactive on previous conversation before switching
  if (_currentConvId && _currentConvId !== otherId) {
    sendInactiveConversation(_currentConvId);
    hideTypingBubble(_currentConvId);
  }
  // One history entry marks "a conversation is open" so the phone/browser
  // back button has something to pop back from (see popstate handler below).
  // Switching directly between conversations must not stack more entries.
  if (!_convHistoryPushed) {
    history.pushState({ twConvOpen: true }, '', '/messages');
    _convHistoryPushed = true;
  }
  type = type || 'emp';
  _currentConvId  = otherId;
  _activeConvMeta = { id: otherId, name: name, type: type, avatarUrl: avatarUrl, headline: headline || '' };
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
  var badgeEl  = document.getElementById('chatTypeBadge');
  var statusEl = document.getElementById('chatStatus');
  if (nameEl) nameEl.textContent = name;
  if (avaEl) {
    avaEl.className = 'ch-ava ' + typeInfo(type).cls;
    avaEl.innerHTML = avatarHtml(name, avatarUrl);
  }
  if (badgeEl) {
    var info = typeInfo(type);
    badgeEl.textContent = info.label;
    badgeEl.className   = 'type-badge-pill ' + info.cls;
    badgeEl.style.display = '';
  }
  // Profession/specialty caption — profiles.headline/title, passed in from
  // the card's data-headline attribute. The account type already shows as
  // the badge next to the name, so when there's no profession text, leave
  // this empty rather than repeat it; CSS collapses the empty line
  // (.ch-role:empty) so no gap is left under the name.
  var roleEl = document.getElementById('chatRole');
  if (roleEl) roleEl.textContent = headline || '';
  // No real presence/online signal is exposed by the backend to other users.
  // Kept ready (text set) but hidden via CSS (.ch-status{display:none}) so
  // the header never shows an invented/placeholder activity line.
  if (statusEl) statusEl.textContent = 'آخر نشاط غير متاح';

  var menuBtn = document.getElementById('chMenuBtn');
  if (menuBtn) menuBtn.style.display = '';
  var backArrow = document.getElementById('chBackArrow');
  if (backArrow) backArrow.style.display = '';

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
  // Keep keyboard open on mobile: restore focus before the browser has a chance to close it
  requestAnimationFrame(function() { input.focus({ preventScroll: true }); });
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
      if (inp) {
        inp.value = savedText;
        autoResize(inp);
        requestAnimationFrame(function() { inp.focus({ preventScroll: true }); });
      }
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

function copyConvProfileLink() {
  if (!_activeConvMeta || !_activeConvMeta.id) return;
  var dd = document.getElementById('chMenuDropdown');
  if (dd) dd.classList.remove('open');
  apiGetUser(_activeConvMeta.id).then(function(data) {
    var tw = data && data.user && data.user.tw_id;
    if (!tw) { showToast('تعذر نسخ الرابط', 'error'); return; }
    var url = window.location.origin + '/u/' + tw;
    navigator.clipboard.writeText(url)
      .then(function() { showToast('تم نسخ رابط الملف', 'success'); })
      .catch(function() { showToast('تعذر نسخ الرابط', 'error'); });
  }).catch(function() { showToast('تعذر نسخ الرابط', 'error'); });
}

// ── Exit conversation back to the conversation list ───────────────────────
// closeConversationUI() does the DOM/state reset only — no history mutation —
// so it can be reused by both the explicit on-screen back action and the
// popstate handler (phone/browser back), which already moved the history
// pointer itself and must not have a second entry pushed on top of it.
function closeConversationUI() {
  if (_currentConvId) {
    sendInactiveConversation(_currentConvId);
    hideTypingBubble(_currentConvId);
  }
  _currentConvId  = null;
  _activeConvMeta = null;

  document.querySelectorAll('.conv-item').forEach(function(i) { i.classList.remove('active'); });

  var dd = document.getElementById('chMenuDropdown');
  if (dd) dd.classList.remove('open');
  var menuBtn = document.getElementById('chMenuBtn');
  if (menuBtn) menuBtn.style.display = 'none';
  var backArrow = document.getElementById('chBackArrow');
  if (backArrow) backArrow.style.display = 'none';
  var nameEl   = document.getElementById('chatName');
  if (nameEl) nameEl.textContent = 'اختر محادثة';
  var avaEl    = document.getElementById('chatAva');
  if (avaEl) { avaEl.className = 'ch-ava'; avaEl.innerHTML = '💬'; }
  var badgeEl  = document.getElementById('chatTypeBadge');
  if (badgeEl) { badgeEl.style.display = 'none'; badgeEl.textContent = ''; badgeEl.className = 'type-badge-pill'; }
  var roleEl   = document.getElementById('chatRole');
  if (roleEl) roleEl.textContent = '';
  var statusEl = document.getElementById('chatStatus');
  if (statusEl) statusEl.textContent = '';

  var chatInput = document.getElementById('chatInput');
  if (chatInput) chatInput.style.display = 'none';
  var msgArea = document.getElementById('messages');
  if (msgArea) msgArea.innerHTML = '<div class="empty-chat"><span class="ei">💬</span><p>اختر محادثة للبدء</p></div>';

  var convListEl = document.getElementById('convList');
  if (convListEl) convListEl.classList.add('mobile-show');
}

// Explicit on-screen action (back-arrow beside the name, or the menu's
// "الرجوع لقائمة الرسائل"). Uses replaceState — not pushState, not
// history.back() — so the "conversation-open" entry that openConversation()
// pushed is overwritten in place rather than stacked on top of or popped
// from; history.length is unchanged either way, never broken.
function backToConvList() {
  closeConversationUI();
  _convHistoryPushed = false;
  history.replaceState(null, '', '/messages');
}

// Phone/browser back button while a conversation is open: openConversation()
// already pushed a { twConvOpen: true } entry, so the native back action
// fires popstate and lands on the entry beneath it (no twConvOpen flag).
// We close the conversation UI in place and pin the URL to /messages —
// never letting the user leave the messages page from inside a conversation.
window.addEventListener('popstate', function(e) {
  var landedOnConvState = e.state && e.state.twConvOpen;
  if (!landedOnConvState && _currentConvId) {
    closeConversationUI();
    _convHistoryPushed = false;
    if (location.pathname + location.search !== '/messages') {
      history.replaceState(null, '', '/messages');
    }
  }
});

// ── ?with= deep-link handler ──────────────────────────────────────────────

function handleWithParam(twId) {
  apiLookupByTwId(twId).then(function(data) {
    if (!data || !data.id) {
      document.getElementById('messages').innerHTML =
        '<div style="text-align:center;padding:30px;color:var(--t3)">تعذر فتح المحادثة</div>';
    } else {
      var type      = data.user_type || 'emp';
      var convItems = document.querySelector('.conv-items');
      var ph = document.createElement('div');
      ph.className = 'conv-item ' + accentClass(type);
      ph.setAttribute('data-uid', String(data.id));
      ph.innerHTML = '<div class="ci-ava-wrap"><div class="ci-ava ' + typeInfo(type).cls + '">'
        + avatarHtml(data.full_name, '') + '</div></div>'
        + '<div class="ci-body"><div class="ci-name-row"><span class="ci-name">'
        + esc(data.full_name || 'مستخدم') + '</span>' + typeBadgePillHtml(type) + '</div></div>';
      if (convItems) convItems.insertAdjacentElement('afterbegin', ph);
      openConversation(data.id, data.full_name || 'مستخدم', type, '');
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
  initConvFilters();
  initConvSearch();
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

  // Prevent send button from stealing focus (keeps mobile keyboard open).
  // pointerdown preventDefault blocks focus transfer; click still fires and sends.
  var sendBtnEl = document.querySelector('.send-btn');
  if (sendBtnEl) {
    sendBtnEl.addEventListener('pointerdown', function(e) { e.preventDefault(); });
  }

  // Signal inactive conversation on page leave
  window.addEventListener('beforeunload', function() {
    if (_currentConvId) sendInactiveConversation(_currentConvId);
  });
});
