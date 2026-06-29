// profile-v2.api.js — fetch wrappers for Profile V2
// Depends on: profile-v2.state.js (_currentJwt)

function getProfile(id){
  return fetch('/profile/' + encodeURIComponent(id), { headers: { 'Authorization': 'Bearer ' + _currentJwt() } })
    .then(function(r){ if(!r.ok) throw new Error('profile ' + r.status); return r.json(); });
}

function getProfileMetrics(id){
  return fetch('/profile/' + encodeURIComponent(id) + '/metrics', { headers: { 'Authorization': 'Bearer ' + _currentJwt() } })
    .then(function(r){ return r.ok ? r.json() : null; });
}
window.getProfileMetrics = getProfileMetrics;

function getScore(numId){
  return fetch('/profile/' + encodeURIComponent(numId) + '/score')
    .then(function(r){ return r.ok ? r.json() : null; });
}

function getProfessions(){
  return fetch('/professions')
    .then(function(r){ return r.ok ? r.json() : []; });
}

// Guard: rejects immediately if session is gone or viewer is no longer owner
function _ownerGuard() {
  return !_currentJwt() || window._scViewerType !== 'owner';
}
var _STALE = { ok: false, data: { detail: 'session_invalid' } };

function updateProfile(uid, payload){
  if (_ownerGuard()) return Promise.reject(_STALE);
  return fetch('/profile/' + uid, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + _currentJwt() },
    body: JSON.stringify(payload)
  }).then(function(r){ return r.json().then(function(d){ return {ok: r.ok, data: d}; }); });
}

function reorderExperience(orderedIds){
  if (_ownerGuard()) return Promise.reject(_STALE);
  return fetch('/experience/reorder', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + _currentJwt() },
    body: JSON.stringify({ ordered_ids: orderedIds })
  }).then(function(r){ return r.json().then(function(d){ return { ok: r.ok, data: d }; }); });
}

function addExperience(userId, payload){
  if (_ownerGuard()) return Promise.reject(_STALE);
  return fetch('/experience/' + userId, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + _currentJwt() },
    body: JSON.stringify(payload)
  }).then(function(r){ return r.json().then(function(d){ return { ok: r.ok, data: d }; }); });
}

function updateExperience(expId, payload){
  if (_ownerGuard()) return Promise.reject(_STALE);
  return fetch('/experience/' + expId, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + _currentJwt() },
    body: JSON.stringify(payload)
  }).then(function(r){ return r.json().then(function(d){ return { ok: r.ok, data: d }; }); });
}

function deleteExperience(expId){
  if (_ownerGuard()) return Promise.reject(_STALE);
  return fetch('/experience/' + expId, {
    method: 'DELETE',
    headers: { 'Authorization': 'Bearer ' + _currentJwt() }
  }).then(function(r){ return r.json().then(function(d){ return { ok: r.ok, data: d }; }); });
}

function uploadCover(userId, dataUrl){
  if (_ownerGuard()) return Promise.reject(_STALE);
  return fetch('/upload/image', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + _currentJwt() },
    body: JSON.stringify({ user_id: userId, bucket: 'covers', filename: 'cover', data_url: dataUrl })
  }).then(function(r){ return r.json().then(function(d){ return { ok: r.ok, data: d }; }); });
}

function uploadAvatar(userId, dataUrl){
  if (_ownerGuard()) return Promise.reject(_STALE);
  return fetch('/upload/image', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + _currentJwt() },
    body: JSON.stringify({ user_id: userId, bucket: 'avatars', filename: 'avatar', data_url: dataUrl })
  }).then(function(r){ return r.json().then(function(d){ return { ok: r.ok, data: d }; }); });
}

window.addExperience    = addExperience;
window.updateExperience = updateExperience;
window.deleteExperience = deleteExperience;
window.getProfile     = getProfile;
window.getScore       = getScore;
window.getProfessions = getProfessions;
window.updateProfile  = updateProfile;
window.uploadAvatar   = uploadAvatar;
window.uploadCover    = uploadCover;

function followProfile(userId){
  return fetch('/profile/' + userId + '/follow', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + _currentJwt() }
  }).then(function(r){ return r.json().then(function(d){ return {ok: r.ok, status: r.status, data: d}; }); });
}

function unfollowProfile(userId){
  return fetch('/profile/' + userId + '/follow', {
    method: 'DELETE',
    headers: { 'Authorization': 'Bearer ' + _currentJwt() }
  }).then(function(r){ return r.json().then(function(d){ return {ok: r.ok, status: r.status, data: d}; }); });
}

window.followProfile   = followProfile;
window.unfollowProfile = unfollowProfile;

function saveProfileInterest(profileId){
  return fetch('/profile/' + profileId + '/interest', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + _currentJwt() }
  }).then(function(r){ return r.json().then(function(d){ return {ok: r.ok, status: r.status, data: d}; }); });
}

function removeProfileInterest(profileId){
  return fetch('/profile/' + profileId + '/interest', {
    method: 'DELETE',
    headers: { 'Authorization': 'Bearer ' + _currentJwt() }
  }).then(function(r){ return r.json().then(function(d){ return {ok: r.ok, status: r.status, data: d}; }); });
}

window.saveProfileInterest   = saveProfileInterest;
window.removeProfileInterest = removeProfileInterest;

function getFollowersList(profileId, limit, offset, type){
  var qs = '?limit=' + (limit || 20) + '&offset=' + (offset || 0) + '&type=' + (type || 'all');
  return fetch('/profile/' + profileId + '/followers' + qs, {
    headers: { 'Authorization': 'Bearer ' + _currentJwt() }
  }).then(function(r){ return r.json().then(function(d){ return {ok: r.ok, data: d}; }); });
}

function getFollowingList(profileId, limit, offset, type){
  var qs = '?limit=' + (limit || 20) + '&offset=' + (offset || 0) + '&type=' + (type || 'all');
  return fetch('/profile/' + profileId + '/following' + qs, {
    headers: { 'Authorization': 'Bearer ' + _currentJwt() }
  }).then(function(r){ return r.json().then(function(d){ return {ok: r.ok, data: d}; }); });
}

window.getFollowersList = getFollowersList;
window.getFollowingList = getFollowingList;

// ── Section CRUD helpers (Education, Courses, Skills, Languages, Links) ──
// All owner-only; guard runs before every call

function _scApiCall(method, path, body){
  if (_ownerGuard()) return Promise.reject(_STALE);
  var opts = { method:method, headers:{'Content-Type':'application/json', 'Authorization': 'Bearer ' + _currentJwt()} };
  if(body != null) opts.body = JSON.stringify(body);
  return fetch(path, opts)
    .then(function(r){ return r.json().then(function(d){ return {ok:r.ok, data:d}; }); });
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
