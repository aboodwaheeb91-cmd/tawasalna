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
        homeBtn.addEventListener('click', function () {
          window.scrollTo({ top: 0, behavior: 'smooth' });
        });
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
