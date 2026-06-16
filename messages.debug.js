// messages.debug.js — Mobile timing debug panel (?debug=1 only)
// Safe to delete entirely after diagnosis. Zero DB writes. Zero token exposure.

var _twDebugMode = new URLSearchParams(location.search).get('debug') === '1';
var _twDebugLog  = [];   // Ring buffer — last 10 entries

function twDebugLog(label, data) {
  if (!_twDebugMode) return;
  _twDebugLog.push({ ms: performance.now().toFixed(0), label: label, data: data });
  if (_twDebugLog.length > 10) _twDebugLog.shift();
  _twDebugRender();
}

function _twDebugRender() {
  var body = document.getElementById('tw-dbg-body');
  if (!body) return;
  var html = '';
  _twDebugLog.slice().reverse().forEach(function(e) {
    var parts = Object.keys(e.data).map(function(k) { return k + ':' + e.data[k]; });
    html += '<div style="border-top:1px solid rgba(255,255,255,.07);padding:3px 0;line-height:1.5">'
      + '<span style="color:rgba(255,255,255,.28);font-size:.57rem">+' + e.ms + 'ms&nbsp;</span>'
      + '<span style="color:#fbbf24;font-weight:700">' + e.label + '&nbsp;</span>'
      + '<span style="color:rgba(255,255,255,.78)">' + parts.join(' ') + '</span>'
      + '</div>';
  });
  body.innerHTML = html || '<div style="color:rgba(255,255,255,.28)">إرسل رسالة لرؤية القياسات...</div>';
}

document.addEventListener('DOMContentLoaded', function() {
  if (!_twDebugMode) return;

  // ── Container: fixed above the composer, grows upward ─────────────────
  // bottom = composer height (~74px) + safe-area + gap
  // The container's bottom edge sits above the composer — never overlaps it.
  var container = document.createElement('div');
  container.id = 'tw-dbg-container';
  container.style.cssText = [
    'position:fixed',
    'bottom:calc(74px + env(safe-area-inset-bottom,0px) + 6px)',
    'right:12px',
    'z-index:9998',
    'display:flex',
    'flex-direction:column',
    'align-items:flex-end',
    'gap:5px',
    'font-family:monospace',
    'font-size:.65rem',
    'direction:ltr',
    'pointer-events:none'   // container itself is click-through
  ].join(';');

  // ── Panel (hidden by default) ──────────────────────────────────────────
  var panel = document.createElement('div');
  panel.style.cssText = [
    'display:none',
    'flex-direction:column',
    'background:rgba(4,8,18,.97)',
    'border:1px solid rgba(0,200,150,.35)',
    'border-radius:10px',
    'width:min(320px,calc(100vw - 24px))',
    'max-height:35vh',
    'overflow:hidden',
    'pointer-events:auto'
  ].join(';');

  var pHead = document.createElement('div');
  pHead.style.cssText = 'display:flex;align-items:center;gap:6px;padding:5px 8px;border-bottom:1px solid rgba(0,200,150,.18);flex-shrink:0';

  var pTitle = document.createElement('span');
  pTitle.textContent = '⏱ TW Debug';
  pTitle.style.cssText = 'color:#00c896;font-weight:700;flex:1';

  var pMeta = document.createElement('span');
  pMeta.textContent = 'last 10';
  pMeta.style.cssText = 'color:rgba(255,255,255,.28);font-size:.57rem';

  var closeBtn = document.createElement('button');
  closeBtn.textContent = '✕';
  closeBtn.style.cssText = 'background:none;border:none;color:rgba(255,255,255,.4);cursor:pointer;padding:0;font-size:.8rem;line-height:1';

  pHead.appendChild(pTitle);
  pHead.appendChild(pMeta);
  pHead.appendChild(closeBtn);

  var pBody = document.createElement('div');
  pBody.id = 'tw-dbg-body';
  pBody.style.cssText = 'padding:5px 8px;overflow-y:auto;flex:1;color:rgba(255,255,255,.8);min-height:44px';
  pBody.innerHTML = '<div style="color:rgba(255,255,255,.28)">إرسل رسالة لرؤية القياسات...</div>';

  panel.appendChild(pHead);
  panel.appendChild(pBody);

  // ── Toggle pill ────────────────────────────────────────────────────────
  var pill = document.createElement('button');
  pill.textContent = '⏱ Debug';
  pill.style.cssText = [
    'background:rgba(0,200,150,.85)',
    'color:#0d1a2e',
    'border:none',
    'border-radius:14px',
    'padding:5px 12px',
    'font-weight:700',
    'cursor:pointer',
    'white-space:nowrap',
    'box-shadow:0 2px 8px rgba(0,0,0,.4)',
    'pointer-events:auto'
  ].join(';');

  // Panel first (appears above pill), pill second (stays at bottom)
  container.appendChild(panel);
  container.appendChild(pill);
  document.body.appendChild(container);

  function expand() {
    panel.style.display = 'flex';
    pill.style.display = 'none';
  }
  function collapse() {
    panel.style.display = 'none';
    pill.style.display = '';
  }

  pill.addEventListener('click', expand);
  closeBtn.addEventListener('click', collapse);
});
