// profile-v2.state.js — script-level globals for Profile V2
window.PROFILE_SHOWCASE_VERSION = "edit-modal-profession-v1";
var _jwt        = localStorage.getItem('tw_jwt') || '';
var _fetchOpts  = _jwt ? { headers: { 'Authorization': 'Bearer ' + _jwt } } : {};
var _scProfileId  = new URLSearchParams(location.search).get('id');
var _scProfileKey = _scProfileId;
var _scUserId     = null;
