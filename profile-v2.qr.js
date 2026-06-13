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

// Export QR card as 1080x1080 PNG — fully local, no cross-origin, works on Chrome Android.
window._qrDownload = function(url, name){
  if(typeof QRCode === 'undefined'){
    if(window.toast) toast('تعذّر تحميل مكتبة QR');
    return;
  }

  // 1. Render QR into a hidden div using qrcodejs (local, no network call)
  var tmpDiv = document.createElement('div');
  tmpDiv.style.cssText = 'position:fixed;left:-9999px;top:0;width:540px;height:540px;overflow:hidden;';
  document.body.appendChild(tmpDiv);
  try {
    new QRCode(tmpDiv, {
      text: url,
      width: 540, height: 540,
      colorDark: '#111111', colorLight: '#ffffff',
      correctLevel: QRCode.CorrectLevel.H
    });
  } catch(e) {
    document.body.removeChild(tmpDiv);
    if(window.toast) toast('تعذّر توليد QR');
    return;
  }

  // qrcodejs draws synchronously for canvas — setTimeout(0) as safety net
  setTimeout(function(){
    var qrCanvas = tmpDiv.querySelector('canvas');
    document.body.removeChild(tmpDiv);

    // 2. Build 1080x1080 export canvas
    var W = 1080, H = 1080;
    var cv  = document.createElement('canvas');
    cv.width = W; cv.height = H;
    var ctx = cv.getContext('2d');

    // Background
    var bg = ctx.createLinearGradient(0, 0, W * 0.8, H);
    bg.addColorStop(0, '#0d1526');
    bg.addColorStop(1, '#070b18');
    ctx.fillStyle = bg;
    ctx.fillRect(0, 0, W, H);

    // Top green accent
    ctx.fillStyle = '#00c896';
    ctx.fillRect(0, 0, W, 6);

    // White rounded box for QR
    var qrSize = 540, pad = 28;
    var boxW   = qrSize + pad * 2;                 // 596
    var boxX   = (W - boxW) / 2;                   // 242
    var boxY   = 205;
    var r      = 28;
    ctx.fillStyle = '#ffffff';
    ctx.beginPath();
    ctx.moveTo(boxX + r, boxY);
    ctx.lineTo(boxX + boxW - r, boxY);           ctx.arcTo(boxX+boxW, boxY,    boxX+boxW, boxY+r,    r);
    ctx.lineTo(boxX + boxW, boxY+boxW-r);        ctx.arcTo(boxX+boxW, boxY+boxW, boxX+boxW-r, boxY+boxW, r);
    ctx.lineTo(boxX + r, boxY+boxW);             ctx.arcTo(boxX, boxY+boxW, boxX, boxY+boxW-r, r);
    ctx.lineTo(boxX, boxY + r);                  ctx.arcTo(boxX, boxY, boxX+r, boxY, r);
    ctx.closePath();
    ctx.fill();

    // QR image inside box
    if(qrCanvas) ctx.drawImage(qrCanvas, boxX + pad, boxY + pad, qrSize, qrSize);

    var boxBottom = boxY + boxW;  // 801

    // Arabic brand text (RTL)
    ctx.save();
    ctx.direction   = 'rtl';
    ctx.textAlign   = 'center';
    ctx.textBaseline = 'alphabetic';

    ctx.font      = 'bold 68px "Cairo", Arial, sans-serif';
    ctx.fillStyle = '#ffffff';
    ctx.fillText('تواصلنا', W / 2, 115);

    ctx.font      = '30px "Cairo", Arial, sans-serif';
    ctx.fillStyle = 'rgba(255,255,255,.42)';
    ctx.fillText('منصة تربط المواهب بالفرص', W / 2, 168);

    ctx.font      = 'bold 42px "Cairo", Arial, sans-serif';
    ctx.fillStyle = '#ffffff';
    ctx.fillText(name || '', W / 2, boxBottom + 82);

    ctx.restore();

    // URL — LTR
    ctx.save();
    ctx.direction    = 'ltr';
    ctx.textAlign    = 'center';
    ctx.textBaseline = 'alphabetic';
    ctx.font         = '22px "Cairo", Arial, sans-serif';
    ctx.fillStyle    = 'rgba(255,255,255,.32)';
    ctx.fillText(url, W / 2, boxBottom + 135);
    ctx.restore();

    // 3. Download as PNG blob — works on Chrome Android
    cv.toBlob(function(blob){
      if(!blob){ if(window.toast) toast('تعذّر إنشاء الصورة'); return; }
      var dlName = (name ? name.replace(/\s+/g, '_') : 'profile') + '_tawasolna_qr.png';
      var a = document.createElement('a');
      a.href     = URL.createObjectURL(blob);
      a.download = dlName;
      document.body.appendChild(a); a.click(); document.body.removeChild(a);
      setTimeout(function(){ URL.revokeObjectURL(a.href); }, 2000);
      if(window.toast) toast('جاري التحميل...');
    }, 'image/png');

  }, 0);
};
