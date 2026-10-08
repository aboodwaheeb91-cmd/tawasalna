// messages.state.js — Messenger V1 state globals
// Protected page guard (SHELL-09): twRequireAuth decides from the TwAuthSync snapshot only —
// guest / expired / stale → /login?next=/messages; logout or account switch in another tab →
// the same guard redirects / reloads. Nothing below runs a request while _user is null.
var _session = twRequireAuth();
var _user = _session ? { id: Number(_session.userId), user_type: _session.userType } : null;
var _jwt  = _session ? TwAuthSync.getToken() : '';   // WS auth frame only — HTTP goes through twApi

var _currentConvId  = null; // numeric user id of open conversation partner
var _activeConvMeta = null; // {id, name, typeIco} — survives conv-list refresh
var _pendingStatus  = {};   // {msg_id → 'delivered'|'read'} for WS events arriving before HTTP ack

var _typingTimer     = null;  // debounce: send typing_stop after idle
var _typingThrottle  = null;  // throttle: limit typing events to ≤1 per 1500ms
var _typingHideTimer = null;  // auto-hide typing indicator after 3s
