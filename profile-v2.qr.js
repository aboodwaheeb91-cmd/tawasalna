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

// Export QR card as 1080×1350 PNG — fully local, no cross-origin, works on Chrome Android.
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

  // ── Draw 1080×1350 two-column card ──
  function _drawCard(qrCanvas, logo){
    var W = 1080, H = 1350;
    var cv  = document.createElement('canvas');
    cv.width = W; cv.height = H;
    var ctx = cv.getContext('2d');

    // Rounded rect path helper
    function _rr(x, y, w, h, r){
      ctx.beginPath();
      ctx.moveTo(x+r, y);
      ctx.lineTo(x+w-r, y);    ctx.arcTo(x+w, y,   x+w, y+r,   r);
      ctx.lineTo(x+w, y+h-r);  ctx.arcTo(x+w, y+h, x+w-r, y+h, r);
      ctx.lineTo(x+r, y+h);    ctx.arcTo(x,   y+h, x,   y+h-r, r);
      ctx.lineTo(x,   y+r);    ctx.arcTo(x,   y,   x+r, y,     r);
      ctx.closePath();
    }

    // Background
    ctx.fillStyle = '#080f1e';
    ctx.fillRect(0, 0, W, H);

    // Dotted grid
    ctx.save();
    ctx.fillStyle = 'rgba(37,99,255,0.11)';
    for(var gy = 20; gy < H; gy += 40){
      for(var gx = 20; gx < W; gx += 40){
        ctx.beginPath(); ctx.arc(gx, gy, 1.5, 0, Math.PI*2); ctx.fill();
      }
    }
    ctx.restore();

    // Outer gradient border
    var bGrad = ctx.createLinearGradient(0, 0, W, H);
    bGrad.addColorStop(0,   '#2563ff');
    bGrad.addColorStop(0.5, '#00c896');
    bGrad.addColorStop(1,   '#2563ff');
    ctx.strokeStyle = bGrad; ctx.lineWidth = 16;
    _rr(8, 8, W-16, H-16, 20); ctx.stroke();

    // Accent bar
    ctx.fillStyle = '#00c896'; ctx.fillRect(0, 0, W, 6);

    // Logo (SVG aspect 3650:1100)
    var logoH = 60, logoW = Math.round(logoH * 3650 / 1100);
    var logoY = 24;
    if(logo){
      try { ctx.drawImage(logo, (W-logoW)/2, logoY, logoW, logoH); }
      catch(e){ logo = null; }
    }
    if(!logo){
      ctx.save(); ctx.direction='rtl'; ctx.textAlign='center';
      ctx.font = 'bold 56px "Cairo",Arial,sans-serif'; ctx.fillStyle='#ffffff';
      ctx.fillText('تواصلنا', W/2, logoY+logoH-4); ctx.restore();
    }

    // Tagline
    ctx.save(); ctx.direction='rtl'; ctx.textAlign='center';
    ctx.font = '22px "Cairo",Arial,sans-serif'; ctx.fillStyle='#00d4b4';
    ctx.fillText('منصة تربط المواهب بالفرص', W/2, 108); ctx.restore();

    // Divider
    var dg = ctx.createLinearGradient(40, 0, W-40, 0);
    dg.addColorStop(0, 'transparent'); dg.addColorStop(0.25, 'rgba(37,99,255,0.6)');
    dg.addColorStop(0.75, 'rgba(0,200,150,0.6)'); dg.addColorStop(1, 'transparent');
    ctx.strokeStyle = dg; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(40, 126); ctx.lineTo(W-40, 126); ctx.stroke();

    // ── QR box (left column) ──
    var qrSize = 420, qrPad = 22;
    var qBoxW   = qrSize + qrPad*2;   // 464
    var qBoxX   = 40, qBoxY = 142;
    var qBoxBot = qBoxY + qBoxW;       // 606

    // Glow
    ctx.save(); ctx.shadowColor='rgba(59,130,246,0.6)'; ctx.shadowBlur=32;
    ctx.fillStyle='#ffffff'; _rr(qBoxX, qBoxY, qBoxW, qBoxW, 20); ctx.fill(); ctx.restore();
    // Blue border
    ctx.strokeStyle='#3b82f6'; ctx.lineWidth=3;
    _rr(qBoxX, qBoxY, qBoxW, qBoxW, 20); ctx.stroke();
    // QR image
    if(qrCanvas) ctx.drawImage(qrCanvas, qBoxX+qrPad, qBoxY+qrPad, qrSize, qrSize);

    // ── Right column ──
    var rx = 524, rw = 516;   // X=524..1040

    // Column heading
    ctx.save(); ctx.direction='rtl'; ctx.textAlign='right';
    ctx.font = 'bold 27px "Cairo",Arial,sans-serif'; ctx.fillStyle='#ffffff';
    ctx.fillText('ابنِ سيرتك المهنية مجاناً', rx+rw, 176); ctx.restore();

    ctx.save(); ctx.direction='rtl'; ctx.textAlign='right';
    ctx.font = '20px "Cairo",Arial,sans-serif'; ctx.fillStyle='rgba(0,212,180,0.9)';
    ctx.fillText('على تواصلنا — منصتك للنجاح', rx+rw, 212); ctx.restore();

    // Sub-divider
    ctx.save(); ctx.strokeStyle='rgba(0,212,180,0.25)'; ctx.lineWidth=1;
    ctx.beginPath(); ctx.moveTo(rx, 226); ctx.lineTo(rx+rw, 226); ctx.stroke(); ctx.restore();

    // Bullet points (icon + text, RTL: icon on right)
    var bullets = [
      { color:'#00c896', text:'بروفايل احترافي مجاني وسهل' },
      { color:'#3b82f6', text:'توثيق شهاداتك ومؤهلاتك' },
      { color:'#8b5cf6', text:'تواصل مع أفضل الشركات' },
      { color:'#f59e0b', text:'ابدأ مسيرتك المهنية اليوم' }
    ];
    var bStartY = 236, bH = 90;

    bullets.forEach(function(b, i){
      var by  = bStartY + i * bH;
      var icX = rx+rw-18, icY = by+40;
      // Colored circle icon
      ctx.save(); ctx.fillStyle=b.color; ctx.shadowColor=b.color; ctx.shadowBlur=12;
      ctx.beginPath(); ctx.arc(icX, icY, 15, 0, Math.PI*2); ctx.fill(); ctx.restore();
      // Checkmark inside
      ctx.save(); ctx.strokeStyle='#ffffff'; ctx.lineWidth=2.5; ctx.lineCap='round'; ctx.lineJoin='round';
      ctx.beginPath();
      ctx.moveTo(icX-8, icY); ctx.lineTo(icX-3, icY+6); ctx.lineTo(icX+7, icY-6);
      ctx.stroke(); ctx.restore();
      // Bullet text
      ctx.save(); ctx.direction='rtl'; ctx.textAlign='right';
      ctx.font='23px "Cairo",Arial,sans-serif'; ctx.fillStyle='rgba(255,255,255,0.9)';
      ctx.fillText(b.text, icX-30, icY+8); ctx.restore();
      // Row separator (not after last)
      if(i < 3){
        ctx.save(); ctx.strokeStyle='rgba(255,255,255,0.07)'; ctx.lineWidth=1;
        ctx.beginPath(); ctx.moveTo(rx, by+bH-4); ctx.lineTo(rx+rw, by+bH-4); ctx.stroke(); ctx.restore();
      }
    });

    // ── Profile card ──
    var pcY = qBoxBot + 44;   // 650
    var pcX = 40, pcW = W-80, pcH = 92, pcR = 18;
    ctx.save(); ctx.fillStyle='rgba(37,99,255,0.10)';
    ctx.strokeStyle='rgba(59,130,246,0.28)'; ctx.lineWidth=1.5;
    _rr(pcX, pcY, pcW, pcH, pcR); ctx.fill(); ctx.stroke(); ctx.restore();

    // Person icon (circle with head+body)
    var icCX = pcX+pcW-48, icCY = pcY+pcH/2;
    ctx.save(); ctx.fillStyle='#2563ff'; ctx.shadowColor='#2563ff'; ctx.shadowBlur=14;
    ctx.beginPath(); ctx.arc(icCX, icCY, 30, 0, Math.PI*2); ctx.fill(); ctx.restore();
    ctx.save(); ctx.fillStyle='#ffffff';
    ctx.beginPath(); ctx.arc(icCX, icCY-9, 9, 0, Math.PI*2); ctx.fill();
    ctx.beginPath(); ctx.arc(icCX, icCY+14, 14, Math.PI, 0); ctx.fill(); ctx.restore();

    // Name
    ctx.save(); ctx.direction='rtl'; ctx.textAlign='right';
    ctx.font='bold 29px "Cairo",Arial,sans-serif'; ctx.fillStyle='#ffffff';
    ctx.fillText(name||'', icCX-52, pcY+36); ctx.restore();

    // Display URL (no ?ref=qr)
    var displayUrl = url.replace(/[?&]ref=qr$/, '');
    ctx.save(); ctx.direction='ltr'; ctx.textAlign='right';
    ctx.font='19px "Cairo",Arial,sans-serif'; ctx.fillStyle='#60a5fa';
    ctx.fillText(displayUrl, icCX-52, pcY+65); ctx.restore();

    // ── Marketing block ──
    var mbY = pcY + pcH + 38;  // 780
    var mbX = 40, mbW = W-80, mbH = 460, mbR = 22;
    ctx.save(); ctx.fillStyle='rgba(37,99,255,0.08)';
    ctx.strokeStyle='rgba(59,130,246,0.20)'; ctx.lineWidth=1.5;
    _rr(mbX, mbY, mbW, mbH, mbR); ctx.fill(); ctx.stroke(); ctx.restore();

    // Marketing title
    ctx.save(); ctx.direction='rtl'; ctx.textAlign='center';
    ctx.font='bold 30px "Cairo",Arial,sans-serif'; ctx.fillStyle='#ffffff';
    ctx.fillText('ابدأ رحلتك المهنية الآن', W/2, mbY+58); ctx.restore();

    // Marketing body text (wrapped)
    ctx.save(); ctx.direction='rtl'; ctx.textAlign='center';
    ctx.font='23px "Cairo",Arial,sans-serif'; ctx.fillStyle='rgba(255,255,255,0.75)';
    _wrap(ctx, 'أنشئ سيرتك الذاتية المجانية، احصل على توثيق مؤهلاتك، وتواصل مع الشركات الكبرى',
      W/2, mbY+104, W*0.78, 40);
    ctx.restore();

    // CTA button (green→blue gradient)
    var btnW = 400, btnH = 64, btnX = (W-400)/2, btnY = mbY+240, btnR = 32;
    var btnG = ctx.createLinearGradient(btnX, 0, btnX+btnW, 0);
    btnG.addColorStop(0, '#00c896'); btnG.addColorStop(1, '#2563ff');
    ctx.save(); ctx.fillStyle=btnG; ctx.shadowColor='rgba(0,200,150,0.55)'; ctx.shadowBlur=26;
    _rr(btnX, btnY, btnW, btnH, btnR); ctx.fill(); ctx.restore();
    ctx.save(); ctx.direction='rtl'; ctx.textAlign='center';
    ctx.font='bold 27px "Cairo",Arial,sans-serif'; ctx.fillStyle='#ffffff';
    ctx.fillText('سجّل الآن على تواصلنا', W/2, btnY+41); ctx.restore();

    // Scan hint
    ctx.save(); ctx.direction='rtl'; ctx.textAlign='center';
    ctx.font='20px "Cairo",Arial,sans-serif'; ctx.fillStyle='rgba(255,255,255,0.45)';
    ctx.fillText('امسح رمز QR للانضمام أو مشاركة البروفايل', W/2, mbY+344); ctx.restore();

    // Domain watermark
    ctx.save(); ctx.direction='ltr'; ctx.textAlign='center';
    ctx.font='17px "Cairo",Arial,sans-serif'; ctx.fillStyle='rgba(255,255,255,0.25)';
    ctx.fillText('tawasolna.com', W/2, mbY+mbH-22); ctx.restore();

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
