/* home.main.js — bootstrap for Home V2
 *
 * Responsibilities: auth guard, populate state, init modules, load initial feed.
 * No business logic here — delegate to the appropriate module.
 *
 * Load order (enforced by <script> tags in home-v2.html):
 *   home.utils.js → home.state.js → home.api.js → home.cards.js →
 *   home.render.js → home.filters.js → home.header.js → home.nav.js →
 *   home.main.js
 */
(function () {
  'use strict';

  /* Auth guard — must run before any module touches the DOM.
   * Decides from TwAuthSync.getSessionSnapshot() only — never tw_user alone.
   * expired / stale / invalid → invalidate the session, then /login.
   * guest or TwAuthSync missing → /login (fail-closed). */
  var _snap = (window.TwAuthSync && typeof TwAuthSync.getSessionSnapshot === 'function')
    ? TwAuthSync.getSessionSnapshot() : null;
  if (!_snap || !_snap.isAuthenticated) {
    if (_snap && _snap.state !== 'guest') TwAuthSync.invalidateSession('home_guard');
    location.replace('/login');
    return;
  }
  var _u = getTwUser(), _jwt = '';
  try { _jwt = localStorage.getItem('tw_jwt') || ''; } catch (e) {}

  /* Populate shared state */
  window.Home.state.user = _u;
  window.Home.state.jwt  = _jwt;

  /* Init modules */
  window.Home.header.init();
  window.Home.filters.init();
  window.Home.nav.init(_u);

  /* Render initial Lucide icons already in the DOM (header, bottom nav) */
  window.Home.utils.icons();

  /* Load default feed */
  window.Home.filters.load('all');
}());
