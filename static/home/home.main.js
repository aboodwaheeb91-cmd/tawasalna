/* home.main.js — bootstrap for Home V2
 *
 * Responsibilities: auth guard, populate state, init modules, load initial feed.
 * No business logic here — delegate to the appropriate module.
 *
 * Load order (enforced by <script> tags in home-v2.html):
 *   home.utils.js → home.state.js → home.api.js → home.cards.js →
 *   home.render.js → home.filters.js → home.nav.js →
 *   home.main.js
 */
(function () {
  'use strict';

  /* Auth guard — the shared Protected Page Guard (SHELL-09) runs before any request.
   * guest / expired / stale / invalid → /login?next=/home · logout or account switch in
   * another tab is handled by the same guard (TwAuthSync.onSessionChange). */
  var snap = twRequireAuth();
  if (!snap) return;

  document.title = twT('page.title', { page: twT('header.home') });

  /* Populate shared state — session from TwAuthSync (snapshot) + the cached profile fields */
  var u = getTwUser() || {};
  window.Home.state.user = {
    id:        Number(snap.userId),
    user_type: snap.userType,
    tw_id:     u.tw_id || ''
  };

  /* Init modules */
  window.Home.filters.init();
  window.Home.nav.init(window.Home.state.user);

  /* Static icons already in the DOM (header + bottom nav come from the unified app chrome) */
  window.Home.utils.icons(document.body);

  /* Load default feed */
  window.Home.filters.load('all');
}());
