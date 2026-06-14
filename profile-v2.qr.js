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
var _QR_HIDDEN_ID  = '__qrHiddenContainer';

window._qrDownload = function(url, name){
  if(_qrDownloading) return;
  if(typeof QRCode === 'undefined'){
    if(window.toast) toast('تعذّر تحميل مكتبة QR');
    return;
  }

  _qrDownloading = true;
  var dlB = document.getElementById('scQrDownloadBtn');
  if(dlB) dlB.disabled = true;
  if(window.toast) toast('جاري تجهيز البطاقة...');

  function _release(errMsg){
    _qrDownloading = false;
    if(dlB) dlB.disabled = false;
    var hd = document.getElementById(_QR_HIDDEN_ID);
    if(hd) hd.innerHTML = '';
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

  // ── Draw card over template ──
  function _drawCard(qrCanvas, tmpl){
    var cv = document.createElement('canvas');
    cv.width = 1800; cv.height = 1800;
    var ctx = cv.getContext('2d');

    if(tmpl) ctx.drawImage(tmpl, 0, 0, 1800, 1800);
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
      var tw    = ctx.measureText(nameText).width;
      var nameX = NAME_LEFT + (availW - tw) / 2;
      var nameY = CARD_CY + fontSize * 0.35;
      ctx.save();
      ctx.fillStyle = '#ffffff';
      ctx.fillText(nameText, nameX, nameY);
      ctx.restore();
    }

    try {
      cv.toBlob(function(blob){
        try {
          if(!blob){ _release('تعذّر إنشاء الصورة'); return; }

          var twId   = (url.match(/\/u\/([^?#/]+)/) || [])[1] || 'profile';
          var dlName = 'tawasolna-qr-card-' + twId + '-' + Date.now() + '.png';

          var blobUrl = URL.createObjectURL(blob);
          var a = document.createElement('a');
          a.href     = blobUrl;
          a.download = dlName;
          document.body.appendChild(a);
          a.click();
          document.body.removeChild(a);
          setTimeout(function(){ URL.revokeObjectURL(blobUrl); }, 10000);

          if(window.toast) toast('جاري التحميل...');
        } catch(e2){
          // toBlob callback error
        } finally {
          _release(null);
        }
      }, 'image/png');
    } catch(e){
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
      _release('تعذّر توليد QR');
      return;
    }

    setTimeout(function(){
      var qrCanvas = hd.querySelector('canvas');
      _drawCard(qrCanvas, tmpl);
    }, 50);
  }

  // ── Load template then draw ──
  var _fired = false;
  function _onTemplate(tmpl){
    if(_fired) return; _fired = true;
    _generateAndDraw(tmpl);
  }

  var tmplImg = new Image();
  tmplImg.onload  = function(){ _onTemplate(tmplImg); };
  tmplImg.onerror = function(){ _release('تعذّر تحميل قالب البطاقة'); };
  setTimeout(function(){ _onTemplate(null); }, 8000);
  tmplImg.src = '/static/img/qr-card-template-ar-v2.png?v=2';
};
