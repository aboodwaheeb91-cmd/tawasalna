/* home.header.js — header button wiring for Home V2
 *
 * Handles: home button (profile nav).
 * Menu toggle + logout are delegated to initGlobalHeaderMenu (tw_shared.js).
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

      if (window.initGlobalHeaderMenu) {
        initGlobalHeaderMenu('hwMenuBtn', 'hwMenuDropdown');
      }
    }
  };
}());
