// messages.api.js — Messenger V1 API layer
// Depends on: messages.state.js (_user, _jwt)

function apiGetConversations() {
  return fetch('/messages/conversations/' + _user.id, {
    headers: { 'Authorization': 'Bearer ' + _jwt }
  }).then(function(r) { return r.ok ? r.json() : Promise.reject(r.status); });
}

function apiGetMessages(otherId) {
  return fetch('/messages/' + _user.id + '/' + otherId, {
    headers: { 'Authorization': 'Bearer ' + _jwt }
  }).then(function(r) { return r.ok ? r.json() : Promise.reject(r.status); });
}

// No sender_id in body — extracted from JWT on server
function apiSendMessage(receiverId, content) {
  return fetch('/messages/send', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + _jwt },
    body: JSON.stringify({ receiver_id: receiverId, content: content })
  }).then(function(r) { return r.ok ? r.json() : Promise.reject(r.status); });
}

function apiGetUnreadCount() {
  return fetch('/messages/unread/' + _user.id, {
    headers: { 'Authorization': 'Bearer ' + _jwt }
  }).then(function(r) { return r.ok ? r.json() : Promise.reject(r.status); });
}

function apiLookupByTwId(twId) {
  return fetch('/user/lookup/' + encodeURIComponent(twId), {
    headers: { 'Authorization': 'Bearer ' + _jwt }
  }).then(function(r) { return r.ok ? r.json() : null; });
}

function apiGetUser(userId) {
  return fetch('/auth/user/' + userId, {
    headers: { 'Authorization': 'Bearer ' + _jwt }
  }).then(function(r) { return r.ok ? r.json() : null; });
}
