/* home.filters.js — filter tab wiring and feed load orchestration for Home V2
 *
 * Allowed filters (server-enforced allowlist): all / opportunities / posts / news
 * Any unknown value is coerced to "all" by the API.
 */
(function () {
  'use strict';
  window.Home = window.Home || {};

  var ALLOWED = ['all', 'opportunities', 'posts', 'news'];

  window.Home.filters = {
    /* ?f= deep link (sidebar links) — read once at load; anything outside the allowlist → 'all' */
    fromUrl: function () {
      var f = new URLSearchParams(location.search).get('f');
      return ALLOWED.indexOf(f) >= 0 ? f : 'all';
    },

    /* Marks the tab of `filter` active and loads it */
    select: function (filter) {
      document.querySelectorAll('.hw-ft').forEach(function (b) {
        b.classList.toggle('active', (b.getAttribute('data-filter') || 'all') === filter);
      });
      window.Home.filters.load(filter);
    },

    init: function () {
      document.querySelectorAll('.hw-ft').forEach(function (btn) {
        btn.addEventListener('click', function () {
          var filter = btn.getAttribute('data-filter') || 'all';
          if (filter === window.Home.state.currentFilter) return;
          window.Home.filters.select(filter);
        });
      });
      document.getElementById('hwMoreBtn').addEventListener('click', function () {
        window.Home.filters.loadMore();
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
    },

    /* «عرض المزيد» (task 8.6d-2) — next page appended · 409 feed_reset / 422 invalid_cursor → the
     * same filter from the top + a toast · any other error → message by the button, cards stay */
    loadMore: function () {
      var state  = window.Home.state;
      var render = window.Home.render;
      var filter = state.currentFilter;
      if (!state.nextCursor || state.loading || state.loadingMore) return;
      render.moreLoading();
      window.Home.api.loadMore(filter)
        .then(function (items) {
          if (items === null) return;
          render.renderFeed(items, filter, true);
        })
        .catch(function (err) {
          if (state.currentFilter !== filter) return;
          if (err && err.reset) {
            showToast(twT('home.more.reset'), 'info');
            window.Home.filters.load(filter);
            return;
          }
          render.moreError();
        });
    }
  };
}());
