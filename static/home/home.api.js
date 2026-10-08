/* home.api.js — API calls for Home V2 (all through twApi — CLAUDE.md → API Client Rule)
 *
 * user_id is NEVER passed as a query param to /home/feed — the server reads it from the token.
 *
 * loadFeed returns a Promise<Array|null>:
 *   Array  — items from the API
 *   null   — request was aborted (filter changed mid-flight); caller ignores
 *   throws — network/server error; caller shows error state
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

      var url = FEED_URL
        + '?filter=' + encodeURIComponent(filter)
        + '&limit='  + (limit || DEFAULT_LIMIT);

      return twApi(url, { signal: ctrl.signal }).then(function (res) {
        if (ctrl.signal.aborted) return null;
        state.loading = false;
        if (!res.ok) throw new Error('HTTP ' + res.status);
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
