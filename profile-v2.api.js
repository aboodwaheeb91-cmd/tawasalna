// profile-v2.api.js — fetch wrappers for Profile V2
// Depends on: profile-v2.state.js (_jwt, _fetchOpts)

function getProfile(id){
  return fetch('/profile/' + encodeURIComponent(id), _fetchOpts)
    .then(function(r){ if(!r.ok) throw new Error('profile ' + r.status); return r.json(); });
}

function getScore(numId){
  return fetch('/profile/' + encodeURIComponent(numId) + '/score')
    .then(function(r){ return r.ok ? r.json() : null; });
}

function getProfessions(){
  return fetch('/professions')
    .then(function(r){ return r.ok ? r.json() : []; });
}

function updateProfile(uid, payload){
  return fetch('/profile/' + uid, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + (_jwt || '') },
    body: JSON.stringify(payload)
  }).then(function(r){ return r.json().then(function(d){ return {ok: r.ok, data: d}; }); });
}

function addExperience(userId, payload){
  return fetch('/experience/' + userId, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + (_jwt || '') },
    body: JSON.stringify(payload)
  }).then(function(r){ return r.json().then(function(d){ return { ok: r.ok, data: d }; }); });
}

function updateExperience(expId, payload){
  return fetch('/experience/' + expId, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + (_jwt || '') },
    body: JSON.stringify(payload)
  }).then(function(r){ return r.json().then(function(d){ return { ok: r.ok, data: d }; }); });
}

function deleteExperience(expId){
  return fetch('/experience/' + expId, {
    method: 'DELETE',
    headers: { 'Authorization': 'Bearer ' + (_jwt || '') }
  }).then(function(r){ return r.json().then(function(d){ return { ok: r.ok, data: d }; }); });
}

function uploadCover(userId, dataUrl, jwt){
  return fetch('/upload/image', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + (jwt || _jwt || '') },
    body: JSON.stringify({ user_id: userId, bucket: 'covers', filename: 'cover', data_url: dataUrl })
  }).then(function(r){ return r.json().then(function(d){ return { ok: r.ok, data: d }; }); });
}

function uploadAvatar(userId, dataUrl, jwt){
  return fetch('/upload/image', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + (jwt || _jwt || '') },
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
