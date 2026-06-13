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

  // ── Coordinates within the 1800×1800 template ──
  // White QR box: pixel-analysed bounds X=125..916, Y=393..1185
  var QR_X    = 170;   // centred in white box (centre X=520, QR half=350)
  var QR_Y    = 439;   // centred in white box (centre Y=789, QR half=350)
  var QR_SIZE = 700;

  // Profile card: teal borders at Y=1290 (top) and Y=1482 (bottom), centre Y=1390
  var NAME_X  = 1520;  // right edge — direction=rtl, textAlign=right
  var NAME_Y  = 1368;  // baseline (56px font, sits above card centre)
  var URL_X   = 155;   // left edge  — direction=ltr, textAlign=left
  var URL_Y   = 1435;  // baseline (below name, inside card)
  var PC_NAME_PX = 56;
  var PC_URL_PX  = 30; // slightly smaller so URL stays inside card width

  // ── Draw card over template ──
  function _drawCard(qrCanvas, tmpl){
    var TW = 1800, TH = 1800;
    var cv = document.createElement('canvas');
    cv.width = TW; cv.height = TH;
    var ctx = cv.getContext('2d');

    // 1. Background template
    if(tmpl) ctx.drawImage(tmpl, 0, 0, TW, TH);

    // 2. QR code inside white box (internal URL keeps ?ref=qr)
    if(qrCanvas) ctx.drawImage(qrCanvas, QR_X, QR_Y, QR_SIZE, QR_SIZE);

    // 3. Profile name — right-aligned Arabic, bold white
    ctx.save();
    ctx.direction  = 'rtl';
    ctx.textAlign  = 'right';
    ctx.font       = 'bold ' + PC_NAME_PX + 'px "Cairo","Noto Sans Arabic",Arial,sans-serif';
    ctx.fillStyle  = '#ffffff';
    ctx.fillText(name || '', NAME_X, NAME_Y);
    ctx.restore();

    // 4. Display URL — LTR, teal, no ?ref=qr
    var displayUrl = url.replace(/[?&]ref=qr$/, '');
    ctx.save();
    ctx.direction  = 'ltr';
    ctx.textAlign  = 'left';
    ctx.font       = PC_URL_PX + 'px "Cairo","Noto Sans Arabic",Arial,sans-serif';
    ctx.fillStyle  = '#00d4b4';
    ctx.fillText(displayUrl, URL_X, URL_Y);
    ctx.restore();

    // 5. Download as PNG
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
  tmplImg.src = '/static/img/qr-card-template-ar.png?v=1';
};
