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

// Export QR card using fixed Arabic template (qr-card-template-ar.png).
// Template is 1800×1800. QR and profile text are composited on top.
window._qrDownload = function(url, name){
  if(typeof QRCode === 'undefined'){
    if(window.toast) toast('تعذّر تحميل مكتبة QR');
    return;
  }
  if(window.toast) toast('جاري تجهيز البطاقة...');

  // ── Coordinates within the 1800×1800 template (v2 Canva design) ──
  // White QR box: pixel-analysed X=125..916, Y=393..1185, centre (520,789)
  var QR_X    = 170;
  var QR_Y    = 439;
  var QR_SIZE = 700;

  // Name card: teal borders Y=1340 (top) / Y=1484 (bottom), centre Y=1412
  // Safe text zone X=120..1620 (person icon sits at ~X=1660..1740)
  var CARD_CY     = 1412;
  var NAME_LEFT   = 120;
  var NAME_RIGHT  = 1620;
  var NAME_MAX_PX = 68;   // start size; auto-fit shrinks until text fits
  var NAME_MIN_PX = 28;

  // ── Draw card over template ──
  function _drawCard(qrCanvas, tmpl){
    var TW = 1800, TH = 1800;
    var cv = document.createElement('canvas');
    cv.width = TW; cv.height = TH;
    var ctx = cv.getContext('2d');

    // 1. Background template (already contains URL, CTA, logo)
    if(tmpl) ctx.drawImage(tmpl, 0, 0, TW, TH);

    // 2. QR code inside white placeholder box
    if(qrCanvas) ctx.drawImage(qrCanvas, QR_X, QR_Y, QR_SIZE, QR_SIZE);

    // 3. Profile name — auto-fit, centred in name card, white bold
    var nameText = (name || '').trim();
    if(nameText){
      var availW = NAME_RIGHT - NAME_LEFT;
      var fontSize = NAME_MAX_PX;
      ctx.font = 'bold ' + fontSize + 'px "Cairo","Noto Sans Arabic",Arial,sans-serif';
      while(fontSize > NAME_MIN_PX && ctx.measureText(nameText).width > availW){
        fontSize -= 2;
        ctx.font = 'bold ' + fontSize + 'px "Cairo","Noto Sans Arabic",Arial,sans-serif';
      }
      var tw = ctx.measureText(nameText).width;
      var nameX = NAME_LEFT + (availW - tw) / 2;   // centred horizontally
      var nameY = CARD_CY + fontSize * 0.35;        // optically centred vertically
      ctx.save();
      ctx.fillStyle = '#ffffff';
      ctx.fillText(nameText, nameX, nameY);
      ctx.restore();
    }

    // 4. Download as PNG
    cv.toBlob(function(blob){
      if(!blob){ if(window.toast) toast('تعذّر إنشاء الصورة'); return; }
      var dlName = (name ? name.replace(/\s+/g, '_') : 'profile') + '_tawasolna_qr.png';
      var a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = dlName;
      document.body.appendChild(a); a.click(); document.body.removeChild(a);
      setTimeout(function(){ URL.revokeObjectURL(a.href); }, 2000);
      if(window.toast) toast('جاري التحميل...');
    }, 'image/png');
  }

  // ── Generate QR at same size as draw target for sharpest output ──
  function _generateAndDraw(tmpl){
    var tmpDiv = document.createElement('div');
    tmpDiv.style.cssText = 'position:fixed;left:-9999px;top:0;width:' + QR_SIZE + 'px;height:' + QR_SIZE + 'px;overflow:hidden;';
    document.body.appendChild(tmpDiv);
    try {
      new QRCode(tmpDiv, {
        text:         url,
        width:        QR_SIZE,
        height:       QR_SIZE,
        colorDark:    '#111111',
        colorLight:   '#ffffff',
        correctLevel: QRCode.CorrectLevel.H
      });
    } catch(e) {
      document.body.removeChild(tmpDiv);
      if(window.toast) toast('تعذّر توليد QR');
      return;
    }
    setTimeout(function(){
      var qrCanvas = tmpDiv.querySelector('canvas');
      document.body.removeChild(tmpDiv);
      _drawCard(qrCanvas, tmpl);
    }, 0);
  }

  // ── Load template then draw ──
  // Served via /static/qr-card-template-ar.png (same-domain, no CORS)
  var _fired = false;
  function _onTemplate(tmpl){
    if(_fired) return; _fired = true;
    _generateAndDraw(tmpl);
  }

  var tmplImg = new Image();
  tmplImg.onload  = function(){ _onTemplate(tmplImg); };
  tmplImg.onerror = function(){
    if(window.toast) toast('تعذّر تحميل قالب البطاقة');
  };
  setTimeout(function(){ _onTemplate(null); }, 8000);
  tmplImg.src = '/static/img/qr-card-template-ar-v2.png?v=2';
};
