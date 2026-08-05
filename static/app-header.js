/* app-header.js — Shared App Header layout helper (VM-10 compliant)
 *
 * Layout-only: populates avatar initials/image and wires logout buttons to the
 * central twLogout() defined in tw_shared.js. No polling, no setInterval,
 * no independent session resolution, no parallel WS.
 *
 * Targets elements by data attributes:
 *   [data-ah-av]       Avatar circle: sets initials + href (if <a>)
 *   [data-ah-logout]   Logout button: delegates to window.twLogout()
 *
 * Badge and notification counts are handled by loadGlobalBadges() + Badge WS
 * in tw_shared.js — app-header.js does not touch [data-ah-notif-badge].
 *
 * Bell, message, and home navigation are plain <a href> links in the HTML.
 */

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
    av.style.display = '';
  });

  /* Logout — fail-closed: clean session before redirect regardless of which path runs */
  document.querySelectorAll('[data-ah-logout]').forEach(function(btn) {
    btn.addEventListener('click', function() {
      if (typeof window.twLogout === 'function') {
        window.twLogout();
      } else if (window.TwAuthSync && typeof TwAuthSync.invalidateSession === 'function') {
        TwAuthSync.invalidateSession('logout', { redirect: '/login' });
      } else {
        // Last-resort fallback: allowlist only — never startsWith('tw_')
        try { localStorage.removeItem('tw_jwt');  } catch(e){}
        try { localStorage.removeItem('tw_user'); } catch(e){}
        location.replace('/login');
      }
    });
  });
}
