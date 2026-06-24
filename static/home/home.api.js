/* home.api.js — feed API calls for Home V2
 *
 * All requests send Authorization: Bearer <jwt> from Home.state.jwt.
 * user_id is NEVER passed as a query param — the server reads it from the token.
 *
 * loadFeed returns a Promise<Array|null>:
 *   Array  — items from the API
 *   null   — request was aborted (filter changed mid-flight); caller ignores
 *   throws — network/server error; caller shows error state
 */
(function () {
  'use strict';
  window.Home = window.Home || {};

  var FEED_URL   = '/home/feed';
  var DEFAULT_LIMIT = 30;

  window.Home.api = {
    loadFeed: function (filter, limit) {
      var state = window.Home.state;

      if (state.abortCtrl) { state.abortCtrl.abort(); }
      state.abortCtrl     = new AbortController();
      state.currentFilter = filter;
      state.loading       = true;

      var headers = {};
      if (state.jwt) headers['Authorization'] = 'Bearer ' + state.jwt;

      var url = FEED_URL
        + '?filter=' + encodeURIComponent(filter)
        + '&limit='  + (limit || DEFAULT_LIMIT);

      return fetch(url, { headers: headers, signal: state.abortCtrl.signal })
        .then(function (r) {
          if (!r.ok) throw new Error('HTTP ' + r.status);
          return r.json();
        })
        .then(function (data) {
          state.loading     = false;
          state.nextCursor  = data.next_cursor || null;
          return data.items || [];
        })
        .catch(function (err) {
          state.loading = false;
          if (err && err.name === 'AbortError') return null;
          throw err;
        });
    }
  };
}());
