// messages.debug.js — Mobile timing debug panel
// Activated only when ?debug=1 is in the URL.
// Safe to delete entirely after diagnosis.
// Never stores data in DB. Never logs tokens or message content.

var _twDebugMode = new URLSearchParams(location.search).get('debug') === '1';
var _twDebugLog  = [];   // Ring buffer — last 10 entries

function twDebugLog(label, data) {
  var ms = performance.now().toFixed(0);
  if (_twDebugMode) {
    _twDebugLog.push({ ms: ms, label: label, data: data });
    if (_twDebugLog.length > 10) _twDebugLog.shift();
    _twDebugRender();
  }
}

function _twDebugRender() {
  var panel = document.getElementById('tw-debug-panel-body');
  if (!panel) return;
  var html = '';
  _twDebugLog.slice().reverse().forEach(function(e) {
    var d = e.data;
    var parts = [];
    Object.keys(d).forEach(function(k) { parts.push(k + ':' + d[k]); });
    html += '<div style="border-top:1px solid rgba(255,255,255,.08);padding:3px 0;line-height:1.4">'
      + '<span style="color:rgba(255,255,255,.35);font-size:.58rem">+' + e.ms + 'ms&nbsp;</span>'
      + '<span style="color:#fbbf24">' + e.label + '&nbsp;</span>'
      + '<span style="color:rgba(255,255,255,.8)">' + parts.join(' ') + '</span>'
      + '</div>';
  });
  panel.innerHTML = html || '<div style="color:rgba(255,255,255,.35)">إرسل رسالة لرؤية القياسات...</div>';
}

document.addEventListener('DOMContentLoaded', function() {
  if (!_twDebugMode) return;

  var wrap = document.createElement('div');
  wrap.id = 'tw-debug-panel';
  wrap.style.cssText = [
    'position:fixed', 'bottom:0', 'left:0', 'right:0', 'z-index:9999',
    'background:rgba(4,8,18,.97)', 'border-top:2px solid #00c896',
    'font-family:monospace', 'font-size:.65rem', 'direction:ltr',
    'color:rgba(255,255,255,.85)', 'max-height:44vh', 'overflow:hidden',
    'display:flex', 'flex-direction:column'
  ].join(';');

  var header = document.createElement('div');
  header.style.cssText = 'display:flex;align-items:center;justify-content:space-between;padding:6px 10px;flex-shrink:0;border-bottom:1px solid rgba(0,200,150,.25)';
  header.innerHTML = '<span style="color:#00c896;font-weight:700">⏱ TW Debug</span>'
    + '<span style="color:rgba(255,255,255,.4);font-size:.58rem">?debug=1 · last 10</span>';

  var closeBtn = document.createElement('button');
  closeBtn.textContent = '✕';
  closeBtn.style.cssText = 'background:none;border:none;color:rgba(255,255,255,.5);font-size:.85rem;cursor:pointer;padding:0 0 0 8px;line-height:1';
  closeBtn.onclick = function() { wrap.remove(); };
  header.appendChild(closeBtn);

  var body = document.createElement('div');
  body.id = 'tw-debug-panel-body';
  body.style.cssText = 'padding:6px 10px;overflow-y:auto;flex:1';
  body.innerHTML = '<div style="color:rgba(255,255,255,.35)">إرسل رسالة لرؤية القياسات...</div>';

  wrap.appendChild(header);
  wrap.appendChild(body);
  document.body.appendChild(wrap);
});
