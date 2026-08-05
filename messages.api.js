// messages.api.js — Messenger V1 API layer
// Depends on: messages.state.js (_user, _jwt)

// Read JWT at call time — immune to stale in-memory state after session changes
function getMessagesJwt() {
  return (typeof localStorage !== 'undefined' && localStorage.getItem('tw_jwt')) || '';
}

// Guard: block API calls when session is no longer valid.
// Triple-layer: (1) in-memory _user.id; (2) localStorage JWT; (3) localStorage tw_user.id
// matches _user.id; (4) optional snapshot isAuthenticated + userId match.
// Closes the account-switch race window: Account A cannot send HTTP requests
// using Account B's JWT while window.location.reload() is pending.
function _isMessagesAuthValid() {
  if (!_user || !_user.id) return false;
  if (!getMessagesJwt()) return false;
  // Read tw_user from localStorage at call time — immune to stale in-memory state
  var currentStoredUser = null;
  try {
    currentStoredUser = JSON.parse(
      (typeof localStorage !== 'undefined' && localStorage.getItem('tw_user')) || 'null'
    );
  } catch(e) {}
  if (!currentStoredUser || !currentStoredUser.id) return false;
  if (Number(currentStoredUser.id) !== Number(_user.id)) return false;
  if (typeof TwAuthSync !== 'undefined' && typeof TwAuthSync.getSessionSnapshot === 'function') {
    var snap = TwAuthSync.getSessionSnapshot();
    if (snap) {
      if (!snap.isAuthenticated) return false;
      if (snap.userId && Number(snap.userId) !== Number(_user.id)) return false;
    }
  }
  return true;
}

function apiGetConversations() {
  if (!_isMessagesAuthValid()) return Promise.reject('unauthenticated');
  return fetch('/messages/conversations/' + _user.id, {
    headers: { 'Authorization': 'Bearer ' + getMessagesJwt() }
  }).then(function(r) { return r.ok ? r.json() : Promise.reject(r.status); });
}

function apiGetMessages(otherId) {
  if (!_isMessagesAuthValid()) return Promise.reject('unauthenticated');
  return fetch('/messages/' + _user.id + '/' + otherId, {
    headers: { 'Authorization': 'Bearer ' + getMessagesJwt() }
  }).then(function(r) { return r.ok ? r.json() : Promise.reject(r.status); });
}

// No sender_id in body — extracted from JWT on server
function apiSendMessage(receiverId, content) {
  if (!_isMessagesAuthValid()) return Promise.reject('unauthenticated');
  return fetch('/messages/send', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + getMessagesJwt() },
    body: JSON.stringify({ receiver_id: receiverId, content: content })
  }).then(function(r) { return r.ok ? r.json() : Promise.reject(r.status); });
}

function apiGetUnreadCount() {
  if (!_isMessagesAuthValid()) return Promise.reject('unauthenticated');
  return fetch('/messages/unread/' + _user.id, {
    headers: { 'Authorization': 'Bearer ' + getMessagesJwt() }
  }).then(function(r) { return r.ok ? r.json() : Promise.reject(r.status); });
}

function apiLookupByTwId(twId) {
  if (!_isMessagesAuthValid()) return Promise.resolve(null);
  return fetch('/user/lookup/' + encodeURIComponent(twId), {
    headers: { 'Authorization': 'Bearer ' + getMessagesJwt() }
  }).then(function(r) { return r.ok ? r.json() : null; });
}

function apiGetUser(userId) {
  if (!_isMessagesAuthValid()) return Promise.resolve(null);
  return fetch('/auth/user/' + userId, {
    headers: { 'Authorization': 'Bearer ' + getMessagesJwt() }
  }).then(function(r) { return r.ok ? r.json() : null; });
}
