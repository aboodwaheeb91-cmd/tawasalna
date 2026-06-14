// profile-v2.qr.js — QR rendering + modal for Profile V2
// Uses api.qrserver.com — external service, replaceable with local lib later.
// QR is clean (no logo overlay inside it). Logo lives in the modal card.

function _qrSrc(url, size){
  return 'https://api.qrserver.com/v1/create-qr-code/?size=' + size + 'x' + size
    + '&qzone=4&color=111111&bgcolor=ffffff&data=' + encodeURIComponent(url);
}

function renderQR(el, profileUrl){
  if(!el) return;
  el.innerHTML = '<div class="sc-qr-inner">'
    + '<img src="' + _qrSrc(profileUrl, 140) + '" alt="رمز QR" loading="lazy">'
    + '</div>';
}
window.renderQR = renderQR;

function openQRModal(profileUrl, profileName){
  var m = document.getElementById('scQrModal');
  if(!m) return;
  var imgEl  = document.getElementById('scQrModalImg');
  var nameEl = document.getElementById('scQrModalName');
  var urlEl  = document.getElementById('scQrModalLink');
  var shareB = document.getElementById('scQrShareBtn');
  var dlB    = document.getElementById('scQrDownloadBtn');
  if(imgEl)  imgEl.src             = _qrSrc(profileUrl, 260);
  if(nameEl) nameEl.textContent    = profileName || '';
  if(urlEl)  urlEl.textContent     = profileUrl;
  if(shareB) shareB.onclick = function(){ window._qrShare(profileUrl, profileName); };
  if(dlB)    dlB.onclick    = function(){ window._qrDownload(profileUrl, profileName); };
  m.style.display = 'flex';
  document.body.style.overflow = 'hidden';
}
window.openQRModal = openQRModal;

function closeQRModal(){
  var m = document.getElementById('scQrModal');
  if(m) m.style.display = 'none';
  document.body.style.overflow = '';
}
window.closeQRModal = closeQRModal;

window._qrCopyLink = function(url){
  if(!url) return;
  function _fallback(){
    var ta = document.createElement('textarea');
    ta.value = url; ta.style.cssText = 'position:fixed;opacity:0;top:0;left:0';
    document.body.appendChild(ta); ta.select();
    try{ document.execCommand('copy'); if(window.toast) toast('تم نسخ الرابط'); }
    catch(e){ if(window.toast) toast('تعذّر النسخ'); }
    document.body.removeChild(ta);
  }
  if(navigator.clipboard && navigator.clipboard.writeText){
    navigator.clipboard.writeText(url)
      .then(function(){ if(window.toast) toast('تم نسخ الرابط'); })
      .catch(_fallback);
  } else { _fallback(); }
};

window._qrShare = function(url, name){
  if(navigator.share){
    navigator.share({
      title: (name || 'بروفايل') + ' — تواصلنا',
      text:  'تعرّف على ' + (name || 'هذا الشخص') + ' على تواصلنا',
      url:   url
    }).catch(function(){});
  } else {
    window._qrCopyLink(url);
  }
};

// Export QR card using fixed Arabic template (qr-card-template-ar-v2.png).
// Template is 1800×1800. QR and profile name are composited on top.
var _qrDownloading = false;
var _qrWatchdog    = null;   // safety timeout — releases lock if flow never completes
var _QR_HIDDEN_ID  = '__qrHiddenContainer';
var _qrClickCount  = 0;

window._qrDownload = function(url, name){
  _qrClickCount++;
  var _n = _qrClickCount;
  console.log('[QR Download] start #' + _n + ' | lock=' + _qrDownloading);

  if(_qrDownloading){
    console.log('[QR Download] locked — skip #' + _n);
    return;
  }
  if(typeof QRCode === 'undefined'){
    if(window.toast) toast('تعذّر تحميل مكتبة QR');
    return;
  }

  // ── Acquire lock ──
  _qrDownloading = true;
  clearTimeout(_qrWatchdog);   // cancel any stale watchdog from previous call
  var dlB = document.getElementById('scQrDownloadBtn');
  if(dlB) dlB.disabled = true;
  if(window.toast) toast('جاري تجهيز البطاقة...');

  // ── Watchdog: auto-release after 15 s if flow never completes ──
  _qrWatchdog = setTimeout(function(){
    console.log('[QR Download] watchdog release #' + _n);
    _release(null);
  }, 15000);

  // ── _release: single choke-point, idempotent ──
  function _release(errMsg){
    if(!_qrDownloading) return;   // already released — safe to call twice
    clearTimeout(_qrWatchdog);
    _qrWatchdog   = null;
    _qrDownloading = false;
    if(dlB) dlB.disabled = false;
    var hd = document.getElementById(_QR_HIDDEN_ID);
    if(hd) hd.innerHTML = '';
    console.log('[QR Download] release #' + _n + ' | err=' + (errMsg || 'null'));
    if(errMsg && window.toast) toast(errMsg);
  }

  // ── Coordinates within the 1800×1800 template (v2 Canva design) ──
  var QR_X    = 170;
  var QR_Y    = 439;
  var QR_SIZE = 700;

  var CARD_CY     = 1412;
  var NAME_LEFT   = 120;
  var NAME_RIGHT  = 1620;
  var NAME_MAX_PX = 68;
  var NAME_MIN_PX = 28;

  // ── Draw card ──
  function _drawCard(qrCanvas, tmpl){
    var cv = document.createElement('canvas');
    cv.width = 1800; cv.height = 1800;
    var ctx = cv.getContext('2d');

    if(tmpl)     ctx.drawImage(tmpl,     0,    0,    1800, 1800);
    if(qrCanvas) ctx.drawImage(qrCanvas, QR_X, QR_Y, QR_SIZE, QR_SIZE);

    var nameText = (name || '').trim();
    if(nameText){
      var availW   = NAME_RIGHT - NAME_LEFT;
      var fontSize = NAME_MAX_PX;
      ctx.font = 'bold ' + fontSize + 'px "Cairo","Noto Sans Arabic",Arial,sans-serif';
      while(fontSize > NAME_MIN_PX && ctx.measureText(nameText).width > availW){
        fontSize -= 2;
        ctx.font = 'bold ' + fontSize + 'px "Cairo","Noto Sans Arabic",Arial,sans-serif';
      }
      var tw = ctx.measureText(nameText).width;
      ctx.save();
      ctx.fillStyle = '#ffffff';
      ctx.fillText(nameText, NAME_LEFT + (availW - tw) / 2, CARD_CY + fontSize * 0.35);
      ctx.restore();
    }

    try {
      cv.toBlob(function(blob){
        console.log('[QR Download] blob ready #' + _n + ' | size=' + (blob ? blob.size : 'null'));
        try {
          if(!blob){ _release('تعذّر إنشاء الصورة'); return; }

          var twId   = (url.match(/\/u\/([^?#/]+)/) || [])[1] || 'profile';
          var dlName = 'tawasolna-qr-card-' + twId + '-' + Date.now() + '.png';
          var blobUrl = URL.createObjectURL(blob);

          var a = document.createElement('a');
          a.style.display = 'none';
          a.href     = blobUrl;
          a.download = dlName;
          document.body.appendChild(a);
          a.click();
          console.log('[QR Download] a.click #' + _n + ' | file=' + dlName);

          // Cleanup: remove anchor after 500ms, revoke URL after 10s
          setTimeout(function(){ if(a.parentNode) a.parentNode.removeChild(a); }, 500);
          setTimeout(function(){ URL.revokeObjectURL(blobUrl); }, 10000);

          if(window.toast) toast('جاري التحميل...');
        } catch(e2){
          console.log('[QR Download] error in blob cb #' + _n + ': ' + e2);
        } finally {
          // Release immediately after a.click() — do NOT wait for browser download event
          _release(null);
        }
      }, 'image/png');
    } catch(e){
      console.log('[QR Download] toBlob threw #' + _n + ': ' + e);
      _release('تعذّر إنشاء الصورة');
    }
  }

  // ── Generate QR then draw ──
  function _generateAndDraw(tmpl){
    var hd = document.getElementById(_QR_HIDDEN_ID);
    if(!hd){
      hd = document.createElement('div');
      hd.id = _QR_HIDDEN_ID;
      hd.style.cssText = 'position:fixed;left:-9999px;top:0;width:' + QR_SIZE + 'px;height:' + QR_SIZE + 'px;overflow:hidden;';
      document.body.appendChild(hd);
    }
    hd.innerHTML = '';

    try {
      new QRCode(hd, {
        text:         url,
        width:        QR_SIZE,
        height:       QR_SIZE,
        colorDark:    '#111111',
        colorLight:   '#ffffff',
        correctLevel: QRCode.CorrectLevel.H
      });
    } catch(e){
      console.log('[QR Download] QRCode failed #' + _n + ': ' + e);
      _release('تعذّر توليد QR');
      return;
    }

    setTimeout(function(){
      var qrCanvas = hd.querySelector('canvas');
      console.log('[QR Download] canvas #' + _n + ': ' + (qrCanvas ? 'ok w=' + qrCanvas.width : 'NOT FOUND'));
      _drawCard(qrCanvas, tmpl);
    }, 50);
  }

  // ── Load template then draw ──
  var _fired = false;
  function _onTemplate(tmpl){ if(_fired) return; _fired = true; _generateAndDraw(tmpl); }

  var tmplImg = new Image();
  tmplImg.onload  = function(){ console.log('[QR Download] template ok #' + _n); _onTemplate(tmplImg); };
  tmplImg.onerror = function(){ console.log('[QR Download] template err #' + _n); _release('تعذّر تحميل قالب البطاقة'); };
  setTimeout(function(){ console.log('[QR Download] template timeout #' + _n); _onTemplate(null); }, 8000);
  tmplImg.src = '/static/img/qr-card-template-ar-v2.png?v=2';
};
