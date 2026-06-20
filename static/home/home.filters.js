/* home.filters.js — filter tab wiring and feed load orchestration for Home V2
 *
 * Allowed filters (server-enforced allowlist): all / opportunities / posts / news
 * Any unknown value is coerced to "all" by the API.
 */
(function () {
  'use strict';
  window.Home = window.Home || {};

  window.Home.filters = {
    init: function () {
      document.querySelectorAll('.hw-ft').forEach(function (btn) {
        btn.addEventListener('click', function () {
          var filter = btn.getAttribute('data-filter') || 'all';
          if (filter === window.Home.state.currentFilter) return;
          document.querySelectorAll('.hw-ft').forEach(function (b) { b.classList.remove('active'); });
          btn.classList.add('active');
          window.Home.filters.load(filter);
        });
      });
    },

    load: function (filter) {
      var render = window.Home.render;
      render.showSkeleton();
      window.Home.api.loadFeed(filter)
        .then(function (items) {
          if (items === null) return;
          render.renderFeed(items, filter);
        })
        .catch(function () {
          render.showError(function () { window.Home.filters.load(filter); });
        });
    }
  };
}());
