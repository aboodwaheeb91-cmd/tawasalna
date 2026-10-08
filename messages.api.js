// messages.api.js — Messenger V1 API layer
// Depends on: tw_shared.js (twApi), messages.state.js (_user)
// Every request goes through twApi (JWT header, timeout, 401 → TwAuthSync.invalidateSession).

// Guard: block API calls when the session is no longer the one this page was opened with.
// Reads the TwAuthSync snapshot at call time (it cross-checks tw_jwt against tw_user), so
// during an account switch Account A's in-memory _user cannot send a request with Account B's
// session while the reload is pending.
function _isMessagesAuthValid() {
  if (!_user || !_user.id) return false;
  if (typeof TwAuthSync === 'undefined' || typeof TwAuthSync.getSessionSnapshot !== 'function') return false;
  var snap = TwAuthSync.getSessionSnapshot();
  return !!(snap && snap.isAuthenticated && Number(snap.userId) === Number(_user.id));
}

// twApi result → data on success; rejects with the HTTP status (0 = network / timeout).
function _msgApi(path, opts) {
  if (!_isMessagesAuthValid()) return Promise.reject('unauthenticated');
  return twApi(path, opts).then(function(res) {
    return res.ok ? (res.data || {}) : Promise.reject(res.status);
  });
}

function apiGetConversations() {
  return _msgApi('/messages/conversations/' + _user.id);
}

function apiGetMessages(otherId) {
  return _msgApi('/messages/' + _user.id + '/' + otherId);
}

// No sender_id in body — extracted from JWT on server
function apiSendMessage(receiverId, content) {
  return _msgApi('/messages/send', { method: 'POST', body: { receiver_id: receiverId, content: content } });
}

function apiGetUnreadCount() {
  return _msgApi('/messages/unread/' + _user.id);
}

function apiLookupByTwId(twId) {
  if (!_isMessagesAuthValid()) return Promise.resolve(null);
  return twApi('/user/lookup/' + encodeURIComponent(twId)).then(function(res) {
    return res.ok ? res.data : null;
  });
}
