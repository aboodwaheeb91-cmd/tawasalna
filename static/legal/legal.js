// static/legal/legal.js — /privacy + /terms (task terms · SYSTEMS_INDEX §1d)
//   public pages (no twRequireAuth) · every text is a twT key (legal.*) on the page itself;
//   this only sets the tab title from <body data-tw-legal-title> and draws the icons.
(function () {
  'use strict';
  var key = document.body.getAttribute('data-tw-legal-title');
  if (key) document.title = twT('page.title', { page: twT(key) });
  twTApply(document.body);
  twIcon.hydrate(document.body);
})();
