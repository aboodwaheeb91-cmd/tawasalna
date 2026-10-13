// profile-v2.api.js — API wrappers for Profile V2 — all through twApi (PR 4.2a · API Client Rule)
// Depends on: tw_shared.js (twApi), profile-v2.state.js (_currentJwt — owner guard only)

// Mutation result shape kept for the section modules: {ok, status, data: <parsed body or {}>}.
function _scRes(r){ return { ok: r.ok, status: r.status, data: r.raw || {}, error: r.error }; }

// Profile load → parsed body; failure rejects with an Error carrying .status (0 = network /
// timeout, 404 = no such profile) so the page can show the right error state.
function getProfile(id){
  return twApi('/profile/' + encodeURIComponent(id)).then(function(r){
    if(!r.ok){ var e = new Error('profile ' + r.status); e.status = r.status; throw e; }
    return r.raw;
  });
}

// Owner-only hydration: fetches /full to get phone/dob/email for the edit modal.
// Never called for visitors — only when window._scViewerType === 'owner'.
function getOwnerProfile(id){
  return twApi('/profile/' + encodeURIComponent(id) + '/full').then(function(r){
    if(!r.ok) throw new Error('owner_profile ' + r.status);
    return r.raw;
  });
}

function getProfileMetrics(id){
  return twApi('/profile/' + encodeURIComponent(id) + '/metrics')
    .then(function(r){ return r.ok ? r.raw : null; });
}
window.getProfileMetrics = getProfileMetrics;

// Canonical completion score (server.py PROFILE_SCORE_ITEMS) → {score, level} for everyone;
// + {tips, items} only when the JWT is the owner's (PROFILE-DATA-VISIBILITY → Completion score) | null
function getScore(numId){
  return twApi('/profile/' + encodeURIComponent(numId) + '/score')
    .then(function(r){ return (r.ok && r.raw && typeof r.raw.score === 'number') ? r.raw : null; });
}

function getProfessions(){
  return twApi('/professions', { auth: false })
    .then(function(r){ return (r.ok && Array.isArray(r.raw)) ? r.raw : []; });
}

// Guard: rejects immediately if session is gone or viewer is no longer owner
function _ownerGuard() {
  return !_currentJwt() || window._scViewerType !== 'owner';
}
var _STALE = { ok: false, data: { detail: 'session_invalid' } };

function updateProfile(uid, payload){
  if (_ownerGuard()) return Promise.reject(_STALE);
  return twApi('/profile/' + uid, { method: 'PUT', body: payload }).then(_scRes);
}

function reorderExperience(orderedIds){
  if (_ownerGuard()) return Promise.reject(_STALE);
  return twApi('/experience/reorder', { method: 'PUT', body: { ordered_ids: orderedIds } }).then(_scRes);
}

function addExperience(userId, payload){
  if (_ownerGuard()) return Promise.reject(_STALE);
  return twApi('/experience/' + userId, { method: 'POST', body: payload }).then(_scRes);
}

function updateExperience(expId, payload){
  if (_ownerGuard()) return Promise.reject(_STALE);
  return twApi('/experience/' + expId, { method: 'PUT', body: payload }).then(_scRes);
}

function deleteExperience(expId){
  if (_ownerGuard()) return Promise.reject(_STALE);
  return twApi('/experience/' + expId, { method: 'DELETE' }).then(_scRes);
}

function uploadCover(userId, dataUrl){
  if (_ownerGuard()) return Promise.reject(_STALE);
  return TW.uploadImage({ kind: 'employee-cover', dataUrl: dataUrl, jwt: _currentJwt() });
}

function uploadAvatar(userId, dataUrl){
  if (_ownerGuard()) return Promise.reject(_STALE);
  return TW.uploadImage({ kind: 'employee-avatar', dataUrl: dataUrl, jwt: _currentJwt() });
}

window.addExperience    = addExperience;
window.updateExperience = updateExperience;
window.deleteExperience = deleteExperience;
window.getProfile      = getProfile;
window.getOwnerProfile = getOwnerProfile;
window.getScore       = getScore;
window.getProfessions = getProfessions;
window.updateProfile  = updateProfile;
window.uploadAvatar   = uploadAvatar;
window.uploadCover    = uploadCover;

// Follow System (SYSTEMS_INDEX §20 · PR 3.5) — one endpoint for every account type, via twApi.
// Result: {ok, status, data:{is_following, followers_count}, error}.
function followProfile(userId){
  return twApi('/profile/' + encodeURIComponent(userId) + '/follow', { method: 'POST' });
}

function unfollowProfile(userId){
  return twApi('/profile/' + encodeURIComponent(userId) + '/follow', { method: 'DELETE' });
}

window.followProfile   = followProfile;
window.unfollowProfile = unfollowProfile;

function saveProfileInterest(profileId){
  return twApi('/profile/' + profileId + '/interest', { method: 'POST' }).then(_scRes);
}

function removeProfileInterest(profileId){
  return twApi('/profile/' + profileId + '/interest', { method: 'DELETE' }).then(_scRes);
}

window.saveProfileInterest   = saveProfileInterest;
window.removeProfileInterest = removeProfileInterest;

function saveCandidateToCompany(profileId){
  return twApi('/company/saved-candidates/' + profileId, { method: 'POST' }).then(_scRes);
}

function removeCandidateFromCompany(profileId){
  return twApi('/company/saved-candidates/' + profileId, { method: 'DELETE' }).then(_scRes);
}

window.saveCandidateToCompany   = saveCandidateToCompany;
window.removeCandidateFromCompany = removeCandidateFromCompany;

function _followListQs(limit, offset, type){
  return '?limit=' + (limit || 20) + '&offset=' + (offset || 0) + '&type=' + encodeURIComponent(type || 'all');
}

function getFollowersList(profileId, limit, offset, type){
  return twApi('/profile/' + encodeURIComponent(profileId) + '/followers' + _followListQs(limit, offset, type));
}

function getFollowingList(profileId, limit, offset, type){
  return twApi('/profile/' + encodeURIComponent(profileId) + '/following' + _followListQs(limit, offset, type));
}

window.getFollowersList = getFollowersList;
window.getFollowingList = getFollowingList;

// ── Section CRUD helpers (Education, Courses, Skills, Languages, Links) ──
// All owner-only; guard runs before every call

function _scApiCall(method, path, body){
  if (_ownerGuard()) return Promise.reject(_STALE);
  var opts = { method: method };
  if(body != null) opts.body = body;
  return twApi(path, opts).then(_scRes);
}

function addEdu(userId, payload)    { return _scApiCall('POST',  '/education/'+userId, payload); }
function updateEdu(id, payload)     { return _scApiCall('PUT',   '/education/'+id,     payload); }
function deleteEdu(id)              { return _scApiCall('DELETE', '/education/'+id,     null);    }

function addCourse(userId, payload) { return _scApiCall('POST',  '/course/'+userId, payload); }
function updateCourse(id, payload)  { return _scApiCall('PUT',   '/course/'+id,     payload); }
function deleteCourse(id)           { return _scApiCall('DELETE', '/course/'+id,     null);    }

function addSkill(userId, payload)  { return _scApiCall('POST',  '/skills/'+userId, payload); }
function deleteSkill(id)            { return _scApiCall('DELETE', '/skills/'+id,     null);    }

function addLang(userId, payload)   { return _scApiCall('POST',  '/langs/'+userId, payload); }
function deleteLang(id)             { return _scApiCall('DELETE', '/langs/'+id,     null);    }

function addLink(userId, payload)   { return _scApiCall('POST',  '/links/'+userId, payload); }
function deleteLink(id)             { return _scApiCall('DELETE', '/links/'+id,     null);    }
