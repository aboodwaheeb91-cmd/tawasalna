/* app-header.js — Shared App Header initializer
 *
 * Call initAppHeader(user) once after the auth guard has verified the user.
 * `user` is the object from localStorage tw_user.
 *
 * Targets elements by data attributes — no IDs assumed:
 *   [data-ah-av]           Avatar circle: sets initials + href (if <a>)
 *   [data-ah-logout]       Logout button: clears tw_* localStorage keys → /login
 *   [data-ah-notif-badge]  Notification unread count badge span
 *
 * Bell, message, and home navigation are plain <a href> links in the HTML —
 * they need no JS binding for navigation.
 *
 * Pages that load this script but do NOT call initAppHeader() explicitly
 * are handled by the DOMContentLoaded auto-init below — they only need
 * [data-ah-notif-badge] in the DOM and tw_user / tw_jwt in localStorage.
 */

var _ahPollStarted = false; /* guard: prevent double setInterval */

function initAppHeader(user) {
  if (!user) return;
  var initial = (user.full_name || user.name || '?').charAt(0).toUpperCase();

  /* Avatar — show only for authenticated users; hidden by default in HTML */
  document.querySelectorAll('[data-ah-av]').forEach(function(av) {
    if (user.avatar_url) {
      var img = document.createElement('img');
      img.src = user.avatar_url;
      img.alt = '';
      av.textContent = '';
      av.appendChild(img);
    } else {
      av.textContent = initial;
    }
    if (av.tagName === 'A') {
      if (user.user_type === 'emp') {
        av.href = user.tw_id ? '/u/' + user.tw_id : '/profile';
      } else if (user.user_type === 'co') {
        av.href = user.tw_id ? '/u/' + user.tw_id : '/company-profile';
      } else if (user.user_type === 'edu') {
        av.href = '/edu-profile';
      }
    }
    av.title = user.full_name || '';
    av.style.display = '';  /* un-hide: only reaches here when user is authenticated */
  });

  /* Logout */
  document.querySelectorAll('[data-ah-logout]').forEach(function(btn) {
    btn.addEventListener('click', function() {
      try {
        Object.keys(localStorage)
          .filter(function(k) { return k.startsWith('tw_'); })
          .forEach(function(k) { localStorage.removeItem(k); });
      } catch (e) {}
      location.replace('/login');
    });
  });

  /* Phase 10: Unread notification badge */
  _pollUnreadBadge(user);
}

function _pollUnreadBadge(user) {
  if (_ahPollStarted) return;
  var jwt = localStorage.getItem('tw_jwt') || '';
  if (!jwt || !user || !user.id) return;
  var badge = document.querySelector('[data-ah-notif-badge]');
  if (!badge) return;

  _ahPollStarted = true;
  var uid = user.id;
  var bellWrap = badge.parentElement; /* wrapper that holds bell icon + badge */

  function _fetchCount() {
    fetch('/notifications/' + uid + '/unread-count', {
      headers: { 'Authorization': 'Bearer ' + jwt }
    })
    .then(function(r) { return r.ok ? r.json() : null; })
    .then(function(d) {
      if (!d || !d.ok) return;
      var count = (d.data && d.data.count) || 0;
      if (count > 0) {
        badge.textContent = count > 99 ? '99+' : String(count);
        badge.style.display = 'inline-flex';
        if (bellWrap) bellWrap.classList.add('ah-bell--active');
      } else {
        badge.textContent = '';
        badge.style.display = 'none';
        if (bellWrap) bellWrap.classList.remove('ah-bell--active');
      }
    })
    .catch(function() {});
  }

  _fetchCount();
  setInterval(_fetchCount, 60000);
}

/* Auto-init: pages that load app-header.js without calling initAppHeader() explicitly.
   Reads tw_user from localStorage. Only activates when [data-ah-notif-badge] is in the DOM. */
document.addEventListener('DOMContentLoaded', function() {
  if (_ahPollStarted) return;
  if (!document.querySelector('[data-ah-notif-badge]')) return;
  try {
    var u = JSON.parse(localStorage.getItem('tw_user') || 'null');
    if (u && u.id) _pollUnreadBadge(u);
  } catch (e) {}
});
