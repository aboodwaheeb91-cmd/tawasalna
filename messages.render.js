// messages.render.js — Messenger V1 render + UI + init
// Depends on: messages.state.js, messages.api.js, messages.ws.js

// ── Account-type presentation (avatar/badge only — no new data, no new logic) ──
// Maps the user_type already returned by the API to a label key (GLOSSARY) + color class.
var _TYPE_INFO = {
  co:  { key: 'account.type.co',  cls: 't-co'  },
  edu: { key: 'account.type.edu', cls: 't-edu' },
  emp: { key: 'account.type.emp', cls: 't-emp' }
};
function typeInfo(t) {
  var info = _TYPE_INFO[t] || _TYPE_INFO.emp;
  return { label: twT(info.key), cls: info.cls };
}

// DS-IMAGE: one avatar renderer (twAvatarHtml — URL checked by twSafeImageUrl, letter fallback)
function avatarHtml(name, avatarUrl, type) {
  return twAvatarHtml({ full_name: name || '', avatar_url: avatarUrl || '', user_type: type || 'emp' }, 'md');
}

// Text-only pill badge — same identity-display convention as the followers
// list (profile-v2.css .sc-fl-type-badge): label only, no emoji, color-tinted
// background. Used for the chat header and conversation-list cards.
function typeBadgePillHtml(type) {
  var info = typeInfo(type);
  return '<span class="type-badge-pill ' + info.cls + '">' + twEscHtml(info.label) + '</span>';
}

// Per-type card accent class — namespaced "acc-*" (not "t-*") so it never
// collides with the solid-fill avatar gradient classes of the same name.
function accentClass(type) {
  return typeInfo(type).cls.replace('t-', 'acc-');
}

// Line-2 profession/specialty caption — profiles.headline (falling back to
// the older profiles.title column, same convention as
// profile-v2.render.js: `prof.headline || prof.title`). The account type
// already shows as the line-1 badge, so when neither field is set, render
// no line at all rather than repeating the type.
function profession(c) {
  return (c && (c.headline || c.title)) || '';
}
function professionLineHtml(c) {
  var text = profession(c);
  return text ? '<div class="ci-sub">' + twEscHtml(text) + '</div>' : '';
}

function convTimeLabel(iso) {
  if (!iso) return '';
  try { return new Date(iso).toLocaleTimeString('ar', { hour: '2-digit', minute: '2-digit' }); }
  catch (e) { return ''; }
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

// ── Header = unified app chrome (tw_shared.js twMountAppChrome — HEADER-NAV.md). ──
// Run the open-conversation cleanup (sendInactiveConversation over the existing WS)
// before ANY header / menu link navigates away from this page.
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

// ── Unread count ──────────────────────────────────────────────────────────

function loadUnreadCount() {
  if (!_user || !_user.id) return;
  apiGetUnreadCount().then(function(data) {
    applyMsgBadge(data.count || 0);   // header msgs badge (messages.ws.js — one cap rule)
  }).catch(function(status) { console.warn('[messages] unread count failed, status:', status); });
}

// ── Conversation list ─────────────────────────────────────────────────────

function renderConvList(convs) {
  var items = document.querySelector('.conv-items');
  if (!items) return;

  if (!convs.length) {
    if (!_currentConvId) {
      items.innerHTML = '<div class="conv-empty">' + twEscHtml(twT('msg.empty_list')) + '</div>';
    }
    return;
  }

  var frag = '';
  convs.forEach(function(c) {
    var type    = c.user_type || 'emp';
    var name    = twEscHtml(c.full_name || twT('msg.user_fallback'));
    var last    = twEscHtml((c.content || '').slice(0, 45));
    var time    = twEscHtml(convTimeLabel(c.created_at));
    var unreadCount = c.unread_count || 0;
    var unreadCls   = unreadCount > 0 ? ' unread' : '';
    var unread  = unreadCount > 0
                  ? '<span class="ci-badge">' + twEscHtml(twNotifBadgeLabel(unreadCount)) + '</span>' : '';
    var isActive = (_currentConvId && c.other_id === _currentConvId) ? ' active' : '';
    var avatarUrl = c.avatar_url || '';
    frag += '<div class="conv-item ' + accentClass(type) + isActive + unreadCls + '" data-uid="' + twEscAttr(c.other_id)
          + '" data-type="' + twEscAttr(type) + '" data-avatar="' + twEscAttr(avatarUrl)
          + '" data-headline="' + twEscAttr(profession(c))
          + '" data-twid="' + twEscAttr(c.tw_id || '') + '">'
          + '<div class="ci-ava-wrap"><div class="ci-ava">'
          + avatarHtml(c.full_name, avatarUrl, type) + '</div></div>'
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
  // All metadata set as data-* attributes so the single general loop below handles the click.
  // No explicit addEventListener here — avoids double-listener when the loop iterates this card.
  if (_currentConvId && _activeConvMeta && !items.querySelector('[data-uid="' + _currentConvId + '"]')) {
    var phType = _activeConvMeta.type || 'emp';
    var ph = document.createElement('div');
    ph.className = 'conv-item ' + accentClass(phType) + ' active';
    ph.setAttribute('data-uid',      String(_activeConvMeta.id));
    ph.setAttribute('data-type',     phType);
    ph.setAttribute('data-avatar',   _activeConvMeta.avatarUrl || '');
    ph.setAttribute('data-headline', _activeConvMeta.headline  || '');
    ph.setAttribute('data-twid',     _activeConvMeta.twId      || '');
    ph.innerHTML = '<div class="ci-ava-wrap"><div class="ci-ava">'
      + avatarHtml(_activeConvMeta.name, _activeConvMeta.avatarUrl, phType) + '</div></div>'
      + '<div class="ci-body">'
      + '<div class="ci-name-row"><span class="ci-name">' + twEscHtml(_activeConvMeta.name) + '</span>' + typeBadgePillHtml(phType) + '</div>'
      + '<div class="ci-preview">' + twEscHtml(twT('msg.new_conv')) + '</div></div>';
    items.insertAdjacentElement('afterbegin', ph);
  }

  items.querySelectorAll('.conv-item').forEach(function(el) {
    var uid       = parseInt(el.getAttribute('data-uid'));
    var name      = (el.querySelector('.ci-name') || {}).textContent || '';
    var type      = el.getAttribute('data-type') || 'emp';
    var avatarUrl = el.getAttribute('data-avatar') || '';
    var headline  = el.getAttribute('data-headline') || '';
    var twId      = el.getAttribute('data-twid') || '';
    el.addEventListener('click', function() { openConversation(uid, name, type, avatarUrl, headline, twId); });
  });

  applyConvFilter(_convFilterMode);
}

// Request ordering: every list load gets a sequence number; only the newest response
// may render, so a slow older response never overwrites a newer list.
var _convSeq = 0;

// Retry limit: the 10s poll stops after MSG_MAX_FAILS consecutive failures and the page
// says so (connection notice + manual retry) instead of retrying forever.
var MSG_MAX_FAILS = 3;
var _convFails = 0;

function loadConversations() {
  if (!_user || !_user.id) return Promise.resolve(false);
  var seq = ++_convSeq;
  return apiGetConversations().then(function(data) {
    if (seq !== _convSeq) return true;           // superseded by a newer load
    _convFails = 0;
    msgHideConnBar('offline');
    // the socket may still be given up — keep saying so once the bigger notice is gone
    if (!_ws && _wsRetries >= WS_MAX_RETRIES) msgShowConnBar('live');
    renderConvList(data.conversations || []);
    return true;
  }).catch(function(status) {
    if (seq !== _convSeq) return false;
    console.error('[messages] loadConversations failed, status:', status);
    _convFails++;
    var items = document.querySelector('.conv-items');
    // Don't overwrite a valid list on a temporary poll failure
    if (items && !_currentConvId && !items.querySelector('.conv-item')) {
      items.innerHTML = '<div class="conv-empty conv-empty--error">' + twEscHtml(twT('msg.list_error')) + '</div>';
    }
    if (_convFails >= MSG_MAX_FAILS) {
      _stopMsgPoll();
      msgShowConnBar('offline');
    }
    return false;
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
  var idAttr = msgId ? ' data-msg-id="' + twEscAttr(msgId) + '"' : '';
  return '<div class="msg-wrap ' + dir + '"' + idAttr + '><div class="msg ' + dir + '">'
    + '<div class="msg-text">' + twEscHtml(content) + '</div>'
    + '<div class="msg-time">' + twEscHtml(time)
    + (statusHtml ? ' ' + statusHtml : '')
    + '</div></div></div>';
}

// One thread renderer (open + quiet reload) — date dividers + bubbles.
function renderThreadHtml(list) {
  var lastDate = '';
  var me = Number(_user && _user.id);
  return list.map(function(msg) {
    var isMe    = Number(msg.sender_id) === me;
    var d       = new Date(msg.created_at);
    var t       = d.toLocaleTimeString('ar', { hour: '2-digit', minute: '2-digit' });
    var dateStr = d.toLocaleDateString('ar', { weekday: 'long', month: 'short', day: 'numeric' });
    var dateDiv = '';
    if (dateStr !== lastDate) {
      lastDate = dateStr;
      dateDiv = '<div class="date-divider">' + twEscHtml(dateStr) + '</div>';
    }
    var statusHtml = isMe ? renderMessageStatus(msg) : '';
    return dateDiv + renderBubble(isMe, msg.content, t, statusHtml, msg.id);
  }).join('');
}

function threadNoteHtml(key) {
  return '<div class="msg-note">' + twEscHtml(twT(key)) + '</div>';
}

// Thread ordering: each load is tied to the conversation it was made for + a sequence
// number. A response for another conversation, or older than the latest open, is dropped.
var _threadSeq = 0;

// ── Chat header schedule button (PR 3.10) ─────────────────────────────────
// twScheduleButton decides visibility itself (tw-schedule.js — company viewer + emp other side,
// not self); a person who is not yet a candidate is shortlisted by the server on save (§75).
function _renderChatSchedule(otherId, name, type) {
  var slot = document.getElementById('chatSchedSlot');
  if (!slot) return;
  slot.innerHTML = '';
  if (!otherId || !window.twScheduleButton) return;
  var btn = twScheduleButton({ candidateId: otherId, candidateName: name, candidateType: type });
  if (btn) slot.appendChild(btn);
}

// ── Open conversation — THE ONLY ENTRY POINT ─────────────────────────────

function openConversation(otherId, name, type, avatarUrl, headline, twId) {
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
  _activeConvMeta = { id: otherId, name: name, type: type, avatarUrl: avatarUrl, headline: headline || '', twId: twId || '' };
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
    avaEl.innerHTML = avatarHtml(name, avatarUrl, type);
  }
  if (badgeEl) {
    var info = typeInfo(type);
    badgeEl.textContent = info.label;
    badgeEl.className   = 'type-badge-pill ' + info.cls;
    badgeEl.hidden = false;
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
  if (statusEl) statusEl.textContent = twT('msg.last_seen_na');

  var menuBtn = document.getElementById('chMenuBtn');
  if (menuBtn) menuBtn.hidden = false;
  var backArrow = document.getElementById('chBackArrow');
  if (backArrow) backArrow.hidden = false;

  // Schedule Interview (PR 3.10 — shared tw-schedule.js): only for a company talking to an emp
  _renderChatSchedule(otherId, name, type);

  // Show composer — only visible when a conversation is active
  var chatInput = document.getElementById('chatInput');
  if (chatInput) chatInput.hidden = false;

  var convListEl = document.getElementById('convList');
  if (convListEl) convListEl.classList.remove('mobile-show');

  var msgArea = document.getElementById('messages');
  msgArea.innerHTML = threadNoteHtml('msg.loading');

  var seq = ++_threadSeq;
  apiGetMessages(otherId).then(function(data) {
    if (seq !== _threadSeq || _currentConvId !== otherId) return;   // stale response
    var list = data.messages || [];
    msgArea.innerHTML = list.length ? renderThreadHtml(list) : threadNoteHtml('msg.thread_empty');
    if (list.length) scrollDown();
    loadUnreadCount();
  }).catch(function(status) {
    if (seq !== _threadSeq || _currentConvId !== otherId) return;
    console.error('[messages] load thread failed, status:', status);
    msgArea.innerHTML = threadNoteHtml('msg.thread_error');
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
  var sendConvId = _currentConvId;

  // Cancel debounce + throttle; notify receiver immediately so their 2.5s delayed hide starts now
  if (_typingTimer)    { clearTimeout(_typingTimer);    _typingTimer    = null; }
  if (_typingThrottle) { clearTimeout(_typingThrottle); _typingThrottle = null; }
  sendTypingStop(_currentConvId);

  var savedText = text;
  input.value = '';
  autoResize(input);
  // Keep keyboard open on mobile: restore focus before the browser has a chance to close it
  requestAnimationFrame(function() { input.focus({ preventScroll: true }); });

  var pid = 'pm' + Date.now();
  var msgs = document.getElementById('messages');
  var t    = new Date().toLocaleTimeString('ar', { hour: '2-digit', minute: '2-digit' });

  msgs.insertAdjacentHTML('beforeend',
    '<div id="' + pid + '" class="msg-wrap out is-pending">'
    + '<div class="msg out">'
    + '<div class="msg-text">' + twEscHtml(savedText) + '</div>'
    + '<div class="msg-time">' + twEscHtml(t)
    + ' <span class="msg-status pending" id="' + pid + 'st">•••</span></div>'
    + '</div></div>'
  );
  scrollDown();

  apiSendMessage(sendConvId, savedText)
    .then(function(data) {
      var msg = (data && data.message) || {};
      var el  = document.getElementById(pid);
      var realId = msg.id;
      if (el && realId) {
        el.setAttribute('data-msg-id', String(realId));
      }
      if (el) el.classList.remove('is-pending');
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
    .catch(function(status) {
      console.error('[messages] send failed, status:', status);
      var el = document.getElementById(pid);
      if (el) { el.classList.remove('is-pending'); el.classList.add('msg-failed'); }
      var st = document.getElementById(pid + 'st');
      if (st) { st.className = 'msg-status failed'; st.textContent = '✗'; }
      showToast(twT('msg.send_failed'), 'error');
      var inp = document.getElementById('msgInput');
      // Give the text back only if the user is still in the same conversation
      if (inp && _currentConvId === sendConvId) {
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

// @vm-extract-begin: msg-poll
var _msgPollTimer = null;
function _msgPollTick() {
  loadConversations();
  reloadMessagesQuiet();
}
function _startMsgPoll() {
  if (_msgPollTimer || document.hidden) return;
  _msgPollTimer = setInterval(_msgPollTick, 10000);
}
function _stopMsgPoll() {
  if (_msgPollTimer) { clearInterval(_msgPollTimer); _msgPollTimer = null; }
}
// @vm-extract-end: msg-poll

function reloadMessagesQuiet() {
  // Hidden tab never fetches the open conversation — GET /messages marks it read (PR 2C)
  if (!_currentConvId || document.hidden) return;
  var convId = _currentConvId;
  var seq = _threadSeq;   // a newer openConversation() bumps it → this response is dropped
  apiGetMessages(convId).then(function(data) {
    if (seq !== _threadSeq || _currentConvId !== convId) return;   // stale response
    var list = data.messages || [];
    var msgs = document.getElementById('messages');
    if (!msgs) return;
    var current = msgs.querySelectorAll('.msg-wrap').length;
    if (list.length <= current) return;
    var atBottom = (msgs.scrollHeight - msgs.scrollTop - msgs.clientHeight) < 80;
    msgs.innerHTML = renderThreadHtml(list);
    if (atBottom) scrollDown();
    loadUnreadCount();
  }).catch(function(status) { console.warn('[messages] quiet reload failed, status:', status); });
}

// ── View conversation partner's profile ───────────────────────────────────

function viewConvProfile() {
  if (!_activeConvMeta || !_activeConvMeta.id) return;
  var tw = _activeConvMeta.twId;
  if (tw) {
    window.location.href = '/u/' + encodeURIComponent(tw);
  } else {
    showToast(twT('msg.profile_failed'), 'error');
  }
}

function copyConvProfileLink() {
  if (!_activeConvMeta || !_activeConvMeta.id) return;
  var dd = document.getElementById('chMenuDropdown');
  if (dd) dd.classList.remove('open');
  var tw = _activeConvMeta.twId;
  if (!tw) { showToast(twT('msg.copy_failed'), 'error'); return; }
  var url = window.location.origin + '/u/' + encodeURIComponent(tw);
  navigator.clipboard.writeText(url)
    .then(function() { showToast(twT('msg.copied'), 'success'); })
    .catch(function() { showToast(twT('msg.copy_failed'), 'error'); });
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
  // Clear typing timers so the old conversation's pending events don't fire
  if (_typingTimer)    { clearTimeout(_typingTimer);    _typingTimer    = null; }
  if (_typingThrottle) { clearTimeout(_typingThrottle); _typingThrottle = null; }
  _currentConvId  = null;
  _activeConvMeta = null;

  document.querySelectorAll('.conv-item').forEach(function(i) { i.classList.remove('active'); });

  var dd = document.getElementById('chMenuDropdown');
  if (dd) dd.classList.remove('open');
  var menuBtn = document.getElementById('chMenuBtn');
  if (menuBtn) menuBtn.hidden = true;
  var backArrow = document.getElementById('chBackArrow');
  if (backArrow) backArrow.hidden = true;
  _renderChatSchedule(null);
  var nameEl   = document.getElementById('chatName');
  if (nameEl) nameEl.textContent = twT('msg.pick');
  var avaEl    = document.getElementById('chatAva');
  if (avaEl) avaEl.innerHTML = twIcon('messages');
  var badgeEl  = document.getElementById('chatTypeBadge');
  if (badgeEl) { badgeEl.hidden = true; badgeEl.textContent = ''; badgeEl.className = 'type-badge-pill'; }
  var roleEl   = document.getElementById('chatRole');
  if (roleEl) roleEl.textContent = '';
  var statusEl = document.getElementById('chatStatus');
  if (statusEl) statusEl.textContent = '';

  var chatInput = document.getElementById('chatInput');
  if (chatInput) chatInput.hidden = true;
  var msgArea = document.getElementById('messages');
  if (msgArea) msgArea.innerHTML = emptyChatHtml();

  var convListEl = document.getElementById('convList');
  if (convListEl) convListEl.classList.add('mobile-show');
}

function emptyChatHtml() {
  return '<div class="empty-chat"><span class="ei">' + twIcon('messages') + '</span><p>'
    + twEscHtml(twT('msg.pick_hint')) + '</p></div>';
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
      document.getElementById('messages').innerHTML = threadNoteHtml('msg.open_failed');
    } else {
      var type      = data.user_type || 'emp';
      var name      = data.full_name || twT('msg.user_fallback');
      var convItems = document.querySelector('.conv-items');
      var ph = document.createElement('div');
      ph.className = 'conv-item ' + accentClass(type);
      ph.setAttribute('data-uid',      String(data.id));
      ph.setAttribute('data-type',     type);
      ph.setAttribute('data-avatar',   '');
      ph.setAttribute('data-headline', '');
      ph.setAttribute('data-twid',     data.tw_id || twId || '');
      ph.innerHTML = '<div class="ci-ava-wrap"><div class="ci-ava">'
        + avatarHtml(name, '', type) + '</div></div>'
        + '<div class="ci-body"><div class="ci-name-row"><span class="ci-name">'
        + twEscHtml(name) + '</span>' + typeBadgePillHtml(type) + '</div></div>';
      if (convItems) convItems.insertAdjacentElement('afterbegin', ph);
      openConversation(Number(data.id), name, type, '', '', data.tw_id || twId);
    }
    // loadConversations runs AFTER _currentConvId is set → active state preserved
    loadConversations();
  }).catch(function(e) {
    console.error('[messages] ?with= lookup failed:', e);
    document.getElementById('messages').innerHTML = threadNoteHtml('msg.open_failed');
    loadConversations();
  });
}

// ── Connection notice (retry limit reached) ───────────────────────────────
// 'offline' = the HTTP poll stopped after MSG_MAX_FAILS failures; 'live' = the socket gave up
// after WS_MAX_RETRIES reconnects (messages still arrive by the 10s poll). One bar, one retry.
var _connBarKind = '';
function msgShowConnBar(kind) {
  var bar = document.getElementById('msgConnBar');
  var txt = document.getElementById('msgConnText');
  if (!bar || !txt) return;
  if (_connBarKind === 'offline' && kind === 'live') return;   // the bigger problem stays shown
  _connBarKind = kind;
  bar.setAttribute('data-kind', kind);
  txt.textContent = twT(kind === 'offline' ? 'msg.offline' : 'msg.live_lost');
  bar.hidden = false;
}
function msgHideConnBar(kind) {
  if (kind && _connBarKind !== kind) return;
  var bar = document.getElementById('msgConnBar');
  if (bar) bar.hidden = true;
  _connBarKind = '';
}
// messages.ws.js hooks (called through _wsNotify)
window.msgOnLiveLost = function() { msgShowConnBar('live'); };
window.msgOnLiveBack = function() { msgHideConnBar('live'); };

// Manual retry: reset both limits, reload now, restart the poll and the socket if it is down.
function msgRetryConnection() {
  _convFails = 0;
  _wsRetries = 0;
  msgHideConnBar();
  loadConversations().then(function(ok) { if (ok) _startMsgPoll(); });
  reloadMessagesQuiet();
  if (!_ws || _ws.readyState > 1) connectWS();
}

// ── Init ──────────────────────────────────────────────────────────────────

// One delegated click handler for the page's static buttons (no inline onclick)
var _MSG_ACTIONS = {
  menu:    function(e) { toggleChatMenu(e); },
  profile: function() { viewConvProfile(); },
  copy:    function() { copyConvProfileLink(); },
  back:    function() { backToConvList(); },
  send:    function() { doSendMessage(); },
  retry:   function() { msgRetryConnection(); }
};

document.addEventListener('DOMContentLoaded', function() {
  if (!_user || !_user.id) return;   // twRequireAuth is already redirecting
  document.title = twT('page.title', { page: twT('msg.title') });
  twIcon.hydrate(document.body);     // static <i data-tw-icon> placeholders (DS-ICON)
  var msgArea0 = document.getElementById('messages');
  if (msgArea0 && !msgArea0.firstChild) msgArea0.innerHTML = emptyChatHtml();
  document.addEventListener('click', function(e) {
    var btn = e.target.closest && e.target.closest('[data-msg-act]');
    if (!btn || btn.disabled) return;
    var fn = _MSG_ACTIONS[btn.getAttribute('data-msg-act')];
    if (fn) fn(e);
  });

  var withParam = new URLSearchParams(location.search).get('with');
  if (withParam) {
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
  // Visible pages only (PR 2C): GET /messages marks messages read, so a hidden tab
  // must not poll — and tells the server the conversation is inactive meanwhile.
  _startMsgPoll();
  document.addEventListener('visibilitychange', function() {
    if (document.hidden) {
      _stopMsgPoll();
      if (_currentConvId) sendInactiveConversation(_currentConvId);
    } else {
      if (_currentConvId) sendActiveConversation(_currentConvId);
      _msgPollTick();
      _startMsgPoll();
    }
  });

  // Typing indicator: throttled + debounced WS typing events.
  // Throttle sends typing at most once per 1500ms to stay well under the server
  // rate limit (10/10s). Debounce sends typing_stop 1800ms after the last keystroke.
  var msgInput = document.getElementById('msgInput');
  if (msgInput) {
    msgInput.addEventListener('keydown', handleKey);
    msgInput.addEventListener('input', function() {
      autoResize(this);
      if (!_currentConvId) return;
      // Reset stop-debounce on every keystroke
      if (_typingTimer) { clearTimeout(_typingTimer); _typingTimer = null; }
      // Throttle: send typing only if not in cooldown
      if (!_typingThrottle) {
        sendTyping(_currentConvId);
        _typingThrottle = setTimeout(function() { _typingThrottle = null; }, 1500);
      }
      // Debounce: schedule typing_stop and reset throttle 1800ms after last keystroke
      _typingTimer = setTimeout(function() {
        sendTypingStop(_currentConvId);
        _typingTimer    = null;
        _typingThrottle = null;
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
