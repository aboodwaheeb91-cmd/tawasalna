// company.permissions.js — loading state + permission guards
// Load order: 3rd (after state, before render)
(function () {
  'use strict';

  function _applyLoadingState(loading) {
    document.body.classList.toggle('co-loading', loading);
  }

  window._applyLoadingState = _applyLoadingState;
}());
