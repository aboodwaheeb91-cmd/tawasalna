/* app-header.js — Shared App Header initializer
 *
 * Call initAppHeader(user) once after the auth guard has verified the user.
 * `user` is the object from localStorage tw_user.
 *
 * Targets elements by data attributes — no IDs assumed:
 *   [data-ah-av]      Avatar circle: sets initials + href (if <a>)
 *   [data-ah-logout]  Logout button: clears tw_* localStorage keys → /login
 *
 * Bell, message, and home navigation are plain <a href> links in the HTML —
 * they need no JS binding. Page-specific badge counts are handled per-page.
 */
function initAppHeader(user) {
  if (!user) return;
  var initial = (user.full_name || user.name || '?').charAt(0).toUpperCase();

  /* Avatar — set initials; if <a>, set profile href */
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
        av.href = '/company-profile';
      } else if (user.user_type === 'edu') {
        av.href = '/edu-profile';
      }
    }
    av.title = user.full_name || '';
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
}
