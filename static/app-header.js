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
  /* twSafeImageUrl / twAccountHref come from tw_shared.js (§54 / Auth Gateway rule 3) —
     never copied here. Called at init time, so load order vs tw_shared.js does not matter.
     Page without tw_shared.js (job-detail: no [data-ah-av] in its HTML) → fail-closed:
     no image (initials), account link → /login (the gateway resolves an active session). */
  var safeAvatar = (typeof twSafeImageUrl === 'function') ? twSafeImageUrl(user.avatar_url) : '';
  var accountHref = (typeof twAccountHref === 'function') ? twAccountHref(user) : '/login';
  document.querySelectorAll('[data-ah-av]').forEach(function(av) {
    if (safeAvatar) {
      var img = document.createElement('img');
      img.src = safeAvatar;
      img.alt = '';
      av.textContent = '';
      av.appendChild(img);
    } else {
      av.textContent = initial;
    }
    if (av.tagName === 'A') {
      av.href = accountHref;
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
