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

// Export QR card as 1080×1080 PNG — fully local, no cross-origin, works on Chrome Android.
window._qrDownload = function(url, name){
  if(typeof QRCode === 'undefined'){
    if(window.toast) toast('تعذّر تحميل مكتبة QR');
    return;
  }
  if(window.toast) toast('جاري تجهيز البطاقة...');

  // ── Text-wrap helper (Arabic RTL safe) ──
  function _wrap(ctx, text, x, y, maxW, lineH){
    var words = text.split(' ');
    var line = '', out = [];
    for(var i = 0; i < words.length; i++){
      var t = line ? line + ' ' + words[i] : words[i];
      if(ctx.measureText(t).width > maxW && line){ out.push(line); line = words[i]; }
      else { line = t; }
    }
    if(line) out.push(line);
    for(var j = 0; j < out.length; j++) ctx.fillText(out[j], x, y + j * lineH);
    return y + out.length * lineH;
  }

  // ── Draw 1080×1080 two-column card ──
  function _drawCard(qrCanvas, logo){
    var W = 1080, H = 1080;
    var cv = document.createElement('canvas');
    cv.width = W; cv.height = H;
    var ctx = cv.getContext('2d');

    // Rounded rect path helper
    function _rr(x, y, w, h, r){
      ctx.beginPath();
      ctx.moveTo(x+r,y); ctx.lineTo(x+w-r,y); ctx.arcTo(x+w,y,x+w,y+r,r);
      ctx.lineTo(x+w,y+h-r); ctx.arcTo(x+w,y+h,x+w-r,y+h,r);
      ctx.lineTo(x+r,y+h); ctx.arcTo(x,y+h,x,y+h-r,r);
      ctx.lineTo(x,y+r); ctx.arcTo(x,y,x+r,y,r);
      ctx.closePath();
    }

    // Background
    ctx.fillStyle = '#080f1e';
    ctx.fillRect(0, 0, W, H);

    // Dotted grid (very subtle)
    ctx.save();
    ctx.fillStyle = 'rgba(37,99,255,0.08)';
    for(var gy = 20; gy < H; gy += 40){
      for(var gx = 20; gx < W; gx += 40){
        ctx.beginPath(); ctx.arc(gx, gy, 1.5, 0, Math.PI*2); ctx.fill();
      }
    }
    ctx.restore();

    // Outer gradient border (12px, not too thick)
    var bGrad = ctx.createLinearGradient(0, 0, W, H);
    bGrad.addColorStop(0, '#2563ff');
    bGrad.addColorStop(0.5, '#00c896');
    bGrad.addColorStop(1, '#2563ff');
    ctx.strokeStyle = bGrad; ctx.lineWidth = 12;
    _rr(6, 6, W-12, H-12, 22); ctx.stroke();

    // Accent bar
    ctx.fillStyle = '#00c896'; ctx.fillRect(0, 0, W, 5);

    // Logo (SVG aspect 3650:1100)
    var lH = 58, lW = Math.round(lH * 3650 / 1100), lY = 24;
    if(logo){ try{ ctx.drawImage(logo, (W-lW)/2, lY, lW, lH); }catch(e){ logo = null; } }
    if(!logo){
      ctx.save(); ctx.direction='rtl'; ctx.textAlign='center';
      ctx.font = 'bold 54px "Cairo",Arial,sans-serif'; ctx.fillStyle='#fff';
      ctx.fillText('تواصلنا', W/2, lY+lH-4); ctx.restore();
    }

    // Tagline (small, below logo)
    ctx.save(); ctx.direction='rtl'; ctx.textAlign='center';
    ctx.font = '20px "Cairo",Arial,sans-serif'; ctx.fillStyle='#00d4b4';
    ctx.fillText('منصة تربط المواهب بالفرص', W/2, 100); ctx.restore();

    // Divider
    var dg = ctx.createLinearGradient(40, 0, W-40, 0);
    dg.addColorStop(0, 'transparent');
    dg.addColorStop(0.25, 'rgba(37,99,255,.55)');
    dg.addColorStop(0.75, 'rgba(0,200,150,.55)');
    dg.addColorStop(1, 'transparent');
    ctx.strokeStyle = dg; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(40, 116); ctx.lineTo(W-40, 116); ctx.stroke();

    // ── QR box (left column) ──
    // qrSize=450 drawn from generated 460px QR → 98% scale, readable
    var qrSize = 450, qrPad = 24;
    var qBoxW = qrSize + qrPad*2;  // 498
    var qBoxX = 36, qBoxY = 130;
    var qBoxBot = qBoxY + qBoxW;   // 628

    ctx.save(); ctx.shadowColor='rgba(59,130,246,.65)'; ctx.shadowBlur=28;
    ctx.fillStyle='#fff'; _rr(qBoxX, qBoxY, qBoxW, qBoxW, 20); ctx.fill(); ctx.restore();
    ctx.strokeStyle='#3b82f6'; ctx.lineWidth=3;
    _rr(qBoxX, qBoxY, qBoxW, qBoxW, 20); ctx.stroke();
    if(qrCanvas) ctx.drawImage(qrCanvas, qBoxX+qrPad, qBoxY+qrPad, qrSize, qrSize);

    // ── Right column ──
    var rx = qBoxX + qBoxW + 14;   // 548
    var rw = W - rx - 36;           // 496  (right margin 36px)

    // Title — "منصة تربط" teal, "المواهب بالفرص" white (two lines, large)
    ctx.save(); ctx.direction='rtl'; ctx.textAlign='right';
    ctx.font = 'bold 36px "Cairo",Arial,sans-serif'; ctx.fillStyle='#00d4b4';
    ctx.fillText('منصة تربط', rx+rw, 170); ctx.restore();

    ctx.save(); ctx.direction='rtl'; ctx.textAlign='right';
    ctx.font = 'bold 36px "Cairo",Arial,sans-serif'; ctx.fillStyle='#ffffff';
    ctx.fillText('المواهب بالفرص', rx+rw, 212); ctx.restore();

    ctx.save(); ctx.direction='rtl'; ctx.textAlign='right';
    ctx.font = '17px "Cairo",Arial,sans-serif'; ctx.fillStyle='rgba(0,212,180,.72)';
    ctx.fillText('في تواصلنا، منصتك للنجاح', rx+rw, 238); ctx.restore();

    // Sub-divider
    ctx.save(); ctx.strokeStyle='rgba(0,212,180,.22)'; ctx.lineWidth=1;
    ctx.beginPath(); ctx.moveTo(rx, 254); ctx.lineTo(rx+rw, 254); ctx.stroke(); ctx.restore();

    // Bullets (user-specified text, 18px to fit in ~496px column)
    var bullets = [
      { c:'#00c896', t:'انضم إلى مجتمع المحترفين واكتشف فرصاً تناسب طموحاتك' },
      { c:'#3b82f6', t:'أنشئ ملفك المهني باحترافية وسهولة' },
      { c:'#8b5cf6', t:'اكتشف فرص عمل تناسب خبراتك' },
      { c:'#f59e0b', t:'طوّر مهاراتك وانطلق نحو مستقبل أفضل' }
    ];
    var bStart = 266, bH = 88;
    // last bullet bottom: 266 + 4*88 = 618 < 628=qBoxBot ✓

    bullets.forEach(function(b, i){
      var by = bStart + i * bH;
      var icX = rx + rw - 16, icY = by + 44;
      // Colored icon circle
      ctx.save(); ctx.fillStyle=b.c; ctx.shadowColor=b.c; ctx.shadowBlur=10;
      ctx.beginPath(); ctx.arc(icX, icY, 13, 0, Math.PI*2); ctx.fill(); ctx.restore();
      // Checkmark inside
      ctx.save(); ctx.strokeStyle='#fff'; ctx.lineWidth=2.2; ctx.lineCap='round'; ctx.lineJoin='round';
      ctx.beginPath();
      ctx.moveTo(icX-6, icY); ctx.lineTo(icX-1, icY+5); ctx.lineTo(icX+7, icY-5);
      ctx.stroke(); ctx.restore();
      // Bullet text (right-aligned, RTL, 18px)
      ctx.save(); ctx.direction='rtl'; ctx.textAlign='right';
      ctx.font = '18px "Cairo",Arial,sans-serif'; ctx.fillStyle='rgba(255,255,255,.88)';
      ctx.fillText(b.t, icX-28, icY+6); ctx.restore();
      // Row separator
      if(i < 3){
        ctx.save(); ctx.strokeStyle='rgba(255,255,255,.07)'; ctx.lineWidth=1;
        ctx.beginPath(); ctx.moveTo(rx, by+bH-5); ctx.lineTo(rx+rw, by+bH-5); ctx.stroke(); ctx.restore();
      }
    });

    // ── Profile card ──
    var pcY = qBoxBot + 30;   // 658
    var pcX = 36, pcW = W-72, pcH = 90, pcR = 16;
    ctx.save(); ctx.fillStyle='rgba(37,99,255,.10)'; ctx.strokeStyle='rgba(59,130,246,.28)'; ctx.lineWidth=1.5;
    _rr(pcX, pcY, pcW, pcH, pcR); ctx.fill(); ctx.stroke(); ctx.restore();

    // Person icon (LEFT side — matching reference)
    var icCX = pcX + 46, icCY = pcY + pcH/2;
    ctx.save(); ctx.fillStyle='#2563ff'; ctx.shadowColor='rgba(37,99,255,.8)'; ctx.shadowBlur=14;
    ctx.beginPath(); ctx.arc(icCX, icCY, 28, 0, Math.PI*2); ctx.fill(); ctx.restore();
    ctx.save(); ctx.fillStyle='#fff';
    ctx.beginPath(); ctx.arc(icCX, icCY-8, 8, 0, Math.PI*2); ctx.fill();
    ctx.beginPath(); ctx.arc(icCX, icCY+12, 12, Math.PI, 0); ctx.fill(); ctx.restore();

    // Name (right-aligned, Arabic)
    ctx.save(); ctx.direction='rtl'; ctx.textAlign='right';
    ctx.font = 'bold 26px "Cairo",Arial,sans-serif'; ctx.fillStyle='#fff';
    ctx.fillText(name||'', pcX+pcW-22, pcY+32); ctx.restore();

    // URL display (LTR, teal, starts after icon)
    var displayUrl = url.replace(/[?&]ref=qr$/, '');
    ctx.save(); ctx.direction='ltr'; ctx.textAlign='left';
    ctx.font = '16px "Cairo",Arial,sans-serif'; ctx.fillStyle='#60a5fa';
    ctx.fillText(displayUrl, icCX+38, pcY+60); ctx.restore();

    // ── Marketing strip (thin, not big box) ──
    var stY = pcY + pcH + 20;  // 768
    ctx.save(); ctx.fillStyle='rgba(255,255,255,.05)'; ctx.strokeStyle='rgba(255,255,255,.10)'; ctx.lineWidth=1;
    _rr(36, stY, W-72, 58, 14); ctx.fill(); ctx.stroke(); ctx.restore();
    ctx.save(); ctx.direction='rtl'; ctx.textAlign='center';
    ctx.font = '18px "Cairo",Arial,sans-serif'; ctx.fillStyle='rgba(255,255,255,.80)';
    ctx.fillText('أنشئ سيرتك الذاتية مجاناً، وابدأ رحلتك المهنية عبر تواصلنا', W/2, stY+36); ctx.restore();

    // ── CTA button (close to strip) ──
    var btnY = stY + 58 + 18;  // 844
    var btnW = 370, btnH = 58, btnX = (W-370)/2, btnR = 29;
    var btnG = ctx.createLinearGradient(btnX, 0, btnX+btnW, 0);
    btnG.addColorStop(0, '#00c896'); btnG.addColorStop(1, '#2563ff');
    ctx.save(); ctx.fillStyle=btnG; ctx.shadowColor='rgba(0,200,150,.45)'; ctx.shadowBlur=20;
    _rr(btnX, btnY, btnW, btnH, btnR); ctx.fill(); ctx.restore();
    ctx.save(); ctx.direction='rtl'; ctx.textAlign='center';
    ctx.font = 'bold 23px "Cairo",Arial,sans-serif'; ctx.fillStyle='#fff';
    ctx.fillText('سجّل الآن على تواصلنا', W/2, btnY+38); ctx.restore();
    // Arrow on button left (RTL trailing edge)
    ctx.save(); ctx.strokeStyle='rgba(255,255,255,.72)'; ctx.lineWidth=2.5; ctx.lineCap='round'; ctx.lineJoin='round';
    var ax = btnX+26, ay = btnY+btnH/2;
    ctx.beginPath(); ctx.moveTo(ax+7,ay-7); ctx.lineTo(ax,ay); ctx.lineTo(ax+7,ay+7); ctx.stroke(); ctx.restore();

    // Hint + watermark (compact)
    ctx.save(); ctx.direction='rtl'; ctx.textAlign='center';
    ctx.font = '15px "Cairo",Arial,sans-serif'; ctx.fillStyle='rgba(255,255,255,.32)';
    ctx.fillText('امسح QR أو انقر لمشاركة البروفايل', W/2, btnY+btnH+24); ctx.restore();

    ctx.save(); ctx.direction='ltr'; ctx.textAlign='center';
    ctx.font = '13px "Cairo",Arial,sans-serif'; ctx.fillStyle='rgba(255,255,255,.17)';
    ctx.fillText('tawasolna.com', W/2, btnY+btnH+46); ctx.restore();

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
