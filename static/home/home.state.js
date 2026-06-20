/* home.state.js — shared runtime state for Home V2
 *
 * Single source of truth for all modules. Never read localStorage
 * directly in any other module — read from Home.state.user/jwt instead.
 *
 * Cursor pagination contract (not yet active):
 *   API will return { items: [...], next_cursor: "<opaque string>" | null }
 *   On load-more, client sends ?cursor=<next_cursor>.
 *   Current API uses ?limit only; nextCursor is reserved and always null today.
 */
(function () {
  'use strict';
  window.Home = window.Home || {};

  window.Home.state = {
    user:          null,
    jwt:           '',
    currentFilter: 'all',
    loading:       false,
    abortCtrl:     null,
    nextCursor:    null
  };
}());
