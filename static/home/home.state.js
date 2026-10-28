/* home.state.js — shared runtime state for Home V2
 *
 * Single source of truth for all modules. Never read localStorage
 * directly in any module — the session comes from twRequireAuth (home.main.js)
 * and every request goes through twApi (auth headers added there).
 *
 * Cursor pagination (task 8.6d-1 server · 8.6d-2 page):
 *   GET /home/feed → { items: [...], next_cursor: "<opaque signed string>" | null }
 *   «عرض المزيد» sends ?cursor=<next_cursor> (Home.api.loadMore); null = end of the feed.
 *   seen = "type:id" of every card on screen — duplicate guard for appended pages.
 */
(function () {
  'use strict';
  window.Home = window.Home || {};

  window.Home.state = {
    user:          null,   // { id, user_type, tw_id } — set by home.main.js
    currentFilter: 'all',
    loading:       false,
    loadingMore:   false,
    abortCtrl:     null,
    nextCursor:    null,
    seen:          {}
  };
}());
