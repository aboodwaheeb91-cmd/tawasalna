// profile-v2.state.js — script-level globals for Profile V2
window.PROFILE_SHOWCASE_VERSION = "edit-modal-profession-v1";
// Always reads from localStorage so stale in-memory token is never used after
// logout or account switch in another tab (fix/profile-v2-stale-jwt-mutation-guard)
function _currentJwt() { return localStorage.getItem('tw_jwt') || ''; }
window._currentJwt = _currentJwt;
var _jwt        = _currentJwt();  // legacy alias — api.js now calls _currentJwt() directly
var _fetchOpts  = _jwt ? { headers: { 'Authorization': 'Bearer ' + _jwt } } : {};
var _scProfileId  = (window._scProfileIdFromRoute != null)
  ? String(window._scProfileIdFromRoute)
  : new URLSearchParams(location.search).get('id');
var _scProfileKey = _scProfileId;
var _scUserId     = null;
