/* home.api.js — API calls for Home V2 (all through twApi — CLAUDE.md → API Client Rule)
 *
 * user_id is NEVER passed as a query param to /home/feed — the server reads it from the token.
 *
 * loadFeed / loadMore return a Promise<Array|null>:
 *   Array  — items from the API
 *   null   — request was aborted (filter changed mid-flight); caller ignores
 *   throws — network/server error; caller shows error state
 *            (loadMore: err.reset = true on 409 feed_reset / 422 invalid_cursor → reload from the top)
 * One AbortController for both: a new loadFeed (filter change) aborts a loadMore in flight and
 * clears the cursor (task 8.6d-2).
 */
(function () {
  'use strict';
  window.Home = window.Home || {};

  var FEED_URL      = '/home/feed';
  var DEFAULT_LIMIT = 30;

  window.Home.api = {
    loadFeed: function (filter, limit) {
      var state = window.Home.state;

      if (state.abortCtrl) { state.abortCtrl.abort(); }
      var ctrl            = new AbortController();
      state.abortCtrl     = ctrl;
      state.currentFilter = filter;
      state.loading       = true;
      state.loadingMore   = false;
      state.nextCursor    = null;

      var url = FEED_URL
        + '?filter=' + encodeURIComponent(filter)
        + '&limit='  + (limit || DEFAULT_LIMIT);

      return twApi(url, { signal: ctrl.signal }).then(function (res) {
        if (ctrl.signal.aborted || state.abortCtrl !== ctrl) return null;
        state.loading = false;
        if (!res.ok) throw new Error('HTTP ' + res.status);
        var data = res.data || {};
        state.nextCursor = data.next_cursor || null;
        return data.items || [];
      });
    },

    /* Next page of the current filter (GET /home/feed?cursor=next_cursor — task 8.6d-2).
     * null without a request when there is no cursor / a load is running / the filter changed. */
    loadMore: function (filter) {
      var state = window.Home.state;
      if (!state.nextCursor || state.loading || state.loadingMore || filter !== state.currentFilter) {
        return Promise.resolve(null);
      }
      var ctrl          = new AbortController();
      state.abortCtrl   = ctrl;
      state.loadingMore = true;

      var url = FEED_URL
        + '?filter=' + encodeURIComponent(filter)
        + '&limit='  + DEFAULT_LIMIT
        + '&cursor=' + encodeURIComponent(state.nextCursor);

      return twApi(url, { signal: ctrl.signal }).then(function (res) {
        if (ctrl.signal.aborted || state.abortCtrl !== ctrl) return null;
        state.loadingMore = false;
        if (!res.ok) {
          var g   = res.error && res.error.generalError;
          var err = new Error('HTTP ' + res.status);
          err.reset = (res.status === 409 && !!g && g.code === 'feed_reset')
                   || (res.status === 422 && !!g && g.code === 'invalid_cursor');
          throw err;
        }
        var data = res.data || {};
        state.nextCursor = data.next_cursor || null;
        return data.items || [];
      });
    },

    /* Profile completion score (emp) — GET /profile/{id}/score → { score, tips, level } | null */
    loadScore: function (userId) {
      return twApi('/profile/' + encodeURIComponent(userId) + '/score').then(function (res) {
        return (res.ok && res.data && typeof res.data.score === 'number') ? res.data : null;
      });
    },

    /* Active jobs of the signed-in company — GET /company/jobs (JWT owner) → number | null */
    loadActiveJobsCount: function () {
      return twApi('/company/jobs?view=active').then(function (res) {
        if (!res.ok || !res.data || !Array.isArray(res.data.jobs)) return null;
        return res.data.jobs.filter(function (j) { return j.effective_status === 'active'; }).length;
      });
    }
  };
}());
