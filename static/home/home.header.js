/* home.header.js — header button wiring for Home V2
 *
 * Handles: home button (scroll-to-top), menu dropdown toggle,
 * outside-click close, and logout.
 * No feed logic here.
 */
(function () {
  'use strict';
  window.Home = window.Home || {};

  window.Home.header = {
    init: function () {
      var homeBtn = document.getElementById('hwHomeBtn');
      if (homeBtn) {
        var user = window.Home.state.user || {};
        var type = user.user_type || 'emp';
        var profileUrl = type === 'co'  ? (user.tw_id ? '/u/' + user.tw_id : '/company-profile')
                       : type === 'edu' ? '/edu-profile'
                       : user.tw_id    ? '/u/' + user.tw_id
                       : '/profile';
        homeBtn.addEventListener('click', function () {
          location.href = profileUrl;
        });
        homeBtn.title = 'ملفي';
      }

      var menuBtn  = document.getElementById('hwMenuBtn');
      var menuDrop = document.getElementById('hwMenuDropdown');
      if (menuBtn && menuDrop) {
        menuBtn.addEventListener('click', function (e) {
          e.stopPropagation();
          menuDrop.classList.toggle('open');
        });
        document.addEventListener('click', function (e) {
          if (menuDrop.classList.contains('open') && !menuDrop.contains(e.target)) {
            menuDrop.classList.remove('open');
          }
        });
      }

      var logoutBtn = document.getElementById('hwLogoutBtn');
      if (logoutBtn) {
        logoutBtn.addEventListener('click', function () {
          try {
            Object.keys(localStorage)
              .filter(function (k) { return k.startsWith('tw_'); })
              .forEach(function (k) { localStorage.removeItem(k); });
          } catch (e) {}
          location.replace('/login');
        });
      }
    }
  };
}());
