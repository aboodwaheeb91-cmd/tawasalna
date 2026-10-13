// profile-v2.state.js — script-level globals for Profile V2
window.PROFILE_SHOWCASE_VERSION = "edit-modal-profession-v1";
// Current JWT from the session authority (TwAuthSync.getToken — '' unless authenticated), read on
// every call so a stale token is never used after logout / account switch in another tab
// (fix/profile-v2-stale-jwt-mutation-guard). Used for owner guards + the upload client only;
// HTTP calls go through twApi (PR 4.2a).
function _currentJwt() {
  return (window.TwAuthSync && typeof TwAuthSync.getToken === 'function') ? TwAuthSync.getToken() : '';
}
window._currentJwt = _currentJwt;
var _scProfileId  = (window._scProfileIdFromRoute != null)
  ? String(window._scProfileIdFromRoute)
  : new URLSearchParams(location.search).get('id');
var _scProfileKey = _scProfileId;
var _scUserId     = null;
