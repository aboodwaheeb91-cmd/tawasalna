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
  if(window.toast) toast('جاري تجهيز البطاقة...');

  // ── Text-wrap helper (Arabic RTL safe) ──
  function _wrap(ctx, text, x, y, maxW, lineH){
    var words = text.split(' ');
    var line = '';
    var out = [];
    for(var i = 0; i < words.length; i++){
      var t = line ? line + ' ' + words[i] : words[i];
      if(ctx.measureText(t).width > maxW && line){ out.push(line); line = words[i]; }
      else { line = t; }
    }
    if(line) out.push(line);
    for(var j = 0; j < out.length; j++) ctx.fillText(out[j], x, y + j * lineH);
    return y + out.length * lineH;
  }

  // ── Draw 1080×1350 portrait card ──
  function _drawCard(qrCanvas, logo){
    var W = 1080, H = 1350;
    var cv  = document.createElement('canvas');
    cv.width = W; cv.height = H;
    var ctx = cv.getContext('2d');

    // Background
    var bg = ctx.createLinearGradient(0, 0, W * 0.8, H);
    bg.addColorStop(0, '#0d1526');
    bg.addColorStop(1, '#070b18');
    ctx.fillStyle = bg; ctx.fillRect(0, 0, W, H);

    // Accent bar
    ctx.fillStyle = '#00c896'; ctx.fillRect(0, 0, W, 7);

    // Logo (SVG aspect 3650:1100) — Y=55, generous top air
    var logoH = 68, logoW = Math.round(logoH * 3650 / 1100);
    var logoY = 55;
    if(logo){
      try { ctx.drawImage(logo, (W - logoW) / 2, logoY, logoW, logoH); }
      catch(e){ logo = null; }
    }
    if(!logo){
      ctx.save();
      ctx.direction = 'rtl'; ctx.textAlign = 'center';
      ctx.font = 'bold 62px "Cairo", Arial, sans-serif';
      ctx.fillStyle = '#ffffff';
      ctx.fillText('تواصلنا', W / 2, logoY + logoH - 6);
      ctx.restore();
    }

    // Tagline — 35px below logo bottom (Y=158)
    ctx.save();
    ctx.direction = 'rtl'; ctx.textAlign = 'center';
    ctx.font = '26px "Cairo", Arial, sans-serif';
    ctx.fillStyle = '#00d4b4';
    ctx.fillText('منصة تربط المواهب بالفرص', W / 2, 158);
    ctx.restore();

    // QR box — white fill + blue border, same 460px QR
    var qrSize = 460, pad = 26;
    var boxW   = qrSize + pad * 2;    // 512
    var boxX   = (W - boxW) / 2;      // 284
    var boxY   = 192;
    var boxBot = boxY + boxW;          // 704
    var rr     = 26;

    function _rrPath(){
      ctx.beginPath();
      ctx.moveTo(boxX + rr, boxY);
      ctx.lineTo(boxX + boxW - rr, boxY);   ctx.arcTo(boxX+boxW, boxY,    boxX+boxW, boxY+rr,   rr);
      ctx.lineTo(boxX + boxW, boxBot - rr); ctx.arcTo(boxX+boxW, boxBot,  boxX+boxW-rr, boxBot, rr);
      ctx.lineTo(boxX + rr,  boxBot);       ctx.arcTo(boxX,      boxBot,  boxX,      boxBot-rr, rr);
      ctx.lineTo(boxX,       boxY + rr);    ctx.arcTo(boxX,      boxY,    boxX+rr,   boxY,      rr);
      ctx.closePath();
    }

    ctx.fillStyle = '#ffffff'; _rrPath(); ctx.fill();
    ctx.strokeStyle = '#3b82f6'; ctx.lineWidth = 3; _rrPath(); ctx.stroke();

    if(qrCanvas) ctx.drawImage(qrCanvas, boxX + pad, boxY + pad, qrSize, qrSize);

    // Profile name — Y=784
    ctx.save();
    ctx.direction = 'rtl'; ctx.textAlign = 'center';
    ctx.font = 'bold 40px "Cairo", Arial, sans-serif';
    ctx.fillStyle = '#ffffff';
    ctx.fillText(name || '', W / 2, boxBot + 80);

    // URL — strip ?ref=qr, light blue — Y=834
    var displayUrl = url.replace(/[?&]ref=qr$/, '');
    ctx.direction = 'ltr';
    ctx.font = '21px "Cairo", Arial, sans-serif';
    ctx.fillStyle = '#60a5fa';
    ctx.fillText(displayUrl, W / 2, boxBot + 130);
    ctx.restore();

    // Marketing rounded container — Y=860, H=400, bottom=1260
    var mX = W * 0.07, mY = boxBot + 156;   // mY=860
    var mW = W * 0.86, mH = 400, mR = 20;

    ctx.save();
    ctx.fillStyle = 'rgba(37,99,255,0.10)';
    ctx.beginPath();
    ctx.moveTo(mX+mR, mY);
    ctx.lineTo(mX+mW-mR, mY);    ctx.arcTo(mX+mW, mY,    mX+mW, mY+mR,    mR);
    ctx.lineTo(mX+mW, mY+mH-mR); ctx.arcTo(mX+mW, mY+mH, mX+mW-mR, mY+mH, mR);
    ctx.lineTo(mX+mR, mY+mH);    ctx.arcTo(mX,    mY+mH, mX,    mY+mH-mR, mR);
    ctx.lineTo(mX,    mY+mR);     ctx.arcTo(mX,    mY,    mX+mR, mY,       mR);
    ctx.closePath(); ctx.fill();
    ctx.strokeStyle = 'rgba(59,130,246,0.28)'; ctx.lineWidth = 1.5; ctx.stroke();
    ctx.restore();

    // Marketing text — Y=920, 2 lines lineH=46
    ctx.save();
    ctx.direction = 'rtl'; ctx.textAlign = 'center';
    ctx.font = '27px "Cairo", Arial, sans-serif';
    ctx.fillStyle = 'rgba(255,255,255,.84)';
    _wrap(ctx,
      'أنشئ سيرتك الذاتية مجاناً، وابدأ رحلتك المهنية عبر تواصلنا',
      W / 2, mY + 60, W * 0.76, 46);  // Y=920, 966 if 2 lines

    // CTA — green, Y=1060
    ctx.font = 'bold 30px "Cairo", Arial, sans-serif';
    ctx.fillStyle = '#00c896';
    ctx.fillText('سجّل الآن على تواصلنا', W / 2, mY + 260);
    ctx.restore();

    // Outer gradient border frame (drawn last over everything)
    var bGrad = ctx.createLinearGradient(0, 0, W, H);
    bGrad.addColorStop(0,   '#2563ff');
    bGrad.addColorStop(0.5, '#00c896');
    bGrad.addColorStop(1,   '#2563ff');
    ctx.strokeStyle = bGrad;
    ctx.lineWidth   = 20;
    var fr = 16;
    ctx.beginPath();
    ctx.moveTo(fr, 0);
    ctx.lineTo(W-fr, 0);  ctx.arcTo(W, 0, W, fr,   fr);
    ctx.lineTo(W, H-fr);  ctx.arcTo(W, H, W-fr, H, fr);
    ctx.lineTo(fr, H);    ctx.arcTo(0, H, 0, H-fr, fr);
    ctx.lineTo(0, fr);    ctx.arcTo(0, 0, fr, 0,   fr);
    ctx.closePath(); ctx.stroke();

    // Download
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

  // ── Generate QR then draw ──
  function _generateAndDraw(logo){
    var tmpDiv = document.createElement('div');
    tmpDiv.style.cssText = 'position:fixed;left:-9999px;top:0;width:460px;height:460px;overflow:hidden;';
    document.body.appendChild(tmpDiv);
    try {
      new QRCode(tmpDiv, {
        text: url, width: 460, height: 460,
        colorDark: '#111111', colorLight: '#ffffff',
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
      _drawCard(qrCanvas, logo);
    }, 0);
  }

  // Load logo first (same-domain /static/33333.svg), then draw
  var _fired = false;
  function _onLogo(img){
    if(_fired) return; _fired = true;
    _generateAndDraw(img);
  }

  var logoImg = new Image();
  logoImg.onload  = function(){ _onLogo(logoImg); };
  logoImg.onerror = function(){ _onLogo(null); };
  setTimeout(function(){ _onLogo(null); }, 5000);
  logoImg.src = '/static/33333.svg';
};
