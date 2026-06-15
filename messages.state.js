// messages.state.js — Messenger V1 state globals
var _user = null;
try { _user = JSON.parse(localStorage.getItem('tw_user')); } catch(e){}
if (!_user || !_user.id) { window.location.href = '/'; }

var _jwt = localStorage.getItem('tw_jwt') || '';
var _currentConvId  = null; // numeric user id of open conversation partner
var _activeConvMeta = null; // {id, name, typeIco} — survives conv-list refresh
var _pendingStatus  = {};   // {msg_id → 'delivered'|'read'} for WS events arriving before HTTP ack

function esc(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;')
    .replace(/</g,  '&lt;')
    .replace(/>/g,  '&gt;')
    .replace(/"/g,  '&quot;')
    .replace(/'/g,  '&#39;');
}
