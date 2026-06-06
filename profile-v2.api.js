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

window.getProfile     = getProfile;
window.getScore       = getScore;
window.getProfessions = getProfessions;
window.updateProfile  = updateProfile;
