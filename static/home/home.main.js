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

  /* Auth guard — must run before any module touches the DOM */
  var _u = null, _jwt = '';
  try {
    _u   = JSON.parse(localStorage.getItem('tw_user') || 'null');
    _jwt = localStorage.getItem('tw_jwt') || '';
  } catch (e) {}
  if (!_u || !_u.id) { location.replace('/login'); return; }

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
