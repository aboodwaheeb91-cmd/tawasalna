// profile-v2.render.js — renderProfile, header wiring, initial fetch, Eye Button
// Depends on: profile-v2.state.js, profile-v2.utils.js, profile-v2.api.js, profile-v2.qr.js

// ── Header button wiring (once at load) ──
(function(){
  var homeBtn=document.getElementById('scHomeBtn');
  if(homeBtn) homeBtn.onclick=function(){ window.location.href='/home'; };
  var bellBtn=document.getElementById('scBellBtn');
  if(bellBtn) bellBtn.onclick=function(){ window.location.href='/notifications'; };
  var msgBtn=document.getElementById('scMsgBtn');
  if(msgBtn) msgBtn.onclick=function(){ window.location.href='/messages'; };
  var menuBtn=document.getElementById('scMenuBtn');
  if(menuBtn) menuBtn.onclick=function(){ history.back(); };
})();

// ── Main render function (Doctrine §26) ──
window.renderProfile = function renderProfile(res){
  var p = (res && res.profile) ? res.profile : {};

  // viewer_type → body class (Doctrine §22, §23)
  var _vt = res.viewer_type || 'guest';
  document.body.classList.remove('view-owner', 'public-view', 'view-guest');
  if      (_vt === 'owner')       document.body.classList.add('view-owner');
  else if (_vt === 'public-user') document.body.classList.add('public-view');
  else                            document.body.classList.add('view-guest');

  // numeric user id for Edit Modal — never use URL param directly
  window._scUserId = (p.id != null) ? p.id : null;

  // edit button — owner only, server-verified
  var editBtn = document.getElementById('scEditProfileBtn');
  if(editBtn) editBtn.style.display = (_vt === 'owner') ? 'flex' : 'none';

  // Identity
  setText('scName', p.full_name || '—');
  setText('scBio', p.bio || '');

  // Title + profession icon (Doctrine §27) — fallback = briefcase
  var titleEl = document.getElementById('scTitle');
  if(titleEl){
    var profIcon = (p.profession && p.profession.icon) ? p.profession.icon : 'briefcase';
    var titleText = (p.profession && p.profession.name_ar)
      ? p.profession.name_ar
      : (p.headline || p.title || '');
    if(titleText){
      titleEl.innerHTML = '<i data-lucide="' + profIcon + '" class="ico-sm"></i> ' + esc(titleText);
    } else {
      titleEl.textContent = '';
    }
  }

  // Store profile data for Edit Modal pre-population
  window._scProfile = p;

  // Verified badge
  if(p.is_verified){
    var vEl=document.getElementById('scVerified');
    if(vEl) vEl.style.display='inline-flex';
  }

  // Location
  var locEl=document.getElementById('scLoc');
  if(locEl && p.location){
    locEl.innerHTML = '<i data-lucide="map-pin" class="ico-sm"></i> ' + esc(p.location);
    locEl.style.display='inline-flex';
    locEl.style.alignItems='center';
    locEl.style.gap='4px';
  }

  // Age from dob
  if(p.dob){
    var birth=new Date(p.dob);
    if(!isNaN(birth.getTime())){
      var diff=Date.now()-birth.getTime();
      var age=Math.floor(diff/(365.25*24*3600*1000));
      if(age>0 && age<150){
        var ageEl=document.getElementById('scAge');
        if(ageEl){
          ageEl.innerHTML='<i data-lucide="cake" class="ico-sm"></i> ' + age + ' سنة';
          ageEl.style.display='flex';
        }
      }
    }
  }

  // Cover image — use cover_url from API if available, else keep CSS default
  var coverEl = document.getElementById('scCover');
  if(coverEl){
    if(p.cover_url){
      coverEl.style.backgroundImage = 'url(' + esc(p.cover_url) + ')';
    }
    // if no cover_url: CSS default (Cover.png) remains untouched
  }

  // Avatar image
  var av=document.getElementById('scAvatar');
  if(av && p.avatar_url){
    var img=new Image();
    img.alt='';
    img.style.cssText='width:100%;height:100%;object-fit:cover;border-radius:50%';
    img.onload=function(){ av.innerHTML=''; av.appendChild(img); };
    img.src=esc(p.avatar_url);
  }

  // Profile link row — single version using onclick (safe on re-render, Doctrine §28)
  var _profileUrl = location.origin + '/profile?id=' + encodeURIComponent(p.tw_id || _scProfileId);
  var linkRow  = document.getElementById('scLinkRow');
  var linkText = document.getElementById('scLinkText');
  var linkCopy = document.getElementById('scLinkCopy');
  if(linkRow && linkText && linkCopy){
    linkText.textContent = _profileUrl;
    linkRow.style.display = 'flex';
    linkCopy.onclick = function(){
      if(navigator.clipboard && navigator.clipboard.writeText){
        navigator.clipboard.writeText(_profileUrl)
          .then(function(){ toast('تم نسخ رابط البروفايل'); })
          .catch(function(){ toast('تعذّر نسخ الرابط'); });
      } else { toast('تعذّر نسخ الرابط'); }
    };
  }

  // QR (via profile-v2.qr.js)
  var qrEl = document.getElementById('scQr');
  if(qrEl){
    var showcaseUrl = location.origin + '/profile-showcase?id=' + encodeURIComponent(_scProfileId);
    renderQR(qrEl, showcaseUrl);
  }

  // Data arrays
  var skills = Array.isArray(p.skills) ? p.skills : [];
  var exp    = Array.isArray(p.experience) ? p.experience : [];
  var edu    = Array.isArray(p.education) ? p.education : [];

  // Stats
  setText('scStatEdu', edu.length);
  setText('scStatExp', exp.length);

  // Bio "more" button
  requestAnimationFrame(function(){
    var bioEl=document.getElementById('scBio');
    var moreBtn=document.getElementById('scBioMore');
    if(bioEl && moreBtn && bioEl.scrollHeight > bioEl.clientHeight + 2){
      moreBtn.style.display='inline-block';
    }
  });

  // Tab: About
  var aboutEl=document.getElementById('scAboutText');
  if(aboutEl) aboutEl.textContent = p.bio || 'لا توجد نبذة بعد';

  // Tab: Skills
  var skEl=document.getElementById('scSkillsPane');
  if(skEl){
    skEl.innerHTML = skills.length
      ? skills.map(function(s){
          var label=(s&&typeof s==='object')?(s.skill||''):s;
          return '<span class="sc-skill">'+esc(label)+'</span>';
        }).join('')
      : '<div class="sc-empty">لا توجد مهارات بعد</div>';
  }

  // Tab: Experience
  var expEl=document.getElementById('scExpPane');
  if(expEl){
    expEl.innerHTML = exp.length
      ? exp.map(function(e){
          var t=esc(e.title||''); var c=esc(e.company||'');
          var loc=e.location?(' · '+esc(e.location)):'';
          return '<div class="sc-item"><div class="sc-item-t">'+t+'</div>'+
            (c?'<div class="sc-item-s">'+c+loc+'</div>':'')+'</div>';
        }).join('')
      : '<div class="sc-empty">لا توجد خبرات بعد</div>';
  }

  // Tab: Education
  var eduEl=document.getElementById('scEduPane');
  if(eduEl){
    eduEl.innerHTML = edu.length
      ? edu.map(function(d){
          var inst=esc(d.institution||''); var deg=esc(d.degree||'');
          var fld=d.field?(' · '+esc(d.field)):'';
          return '<div class="sc-item"><div class="sc-item-t">'+inst+'</div>'+
            ((deg||fld)?'<div class="sc-item-s">'+deg+fld+'</div>':'')+'</div>';
        }).join('')
      : '<div class="sc-empty">لا توجد شهادات بعد</div>';
  }

  // Action buttons — onclick overwrites safely on each re-render
  var followBtn=document.getElementById('scFollowBtn');
  if(followBtn) followBtn.onclick=function(){ toast('ميزة المتابعة قريباً'); };
  var contactBtn=document.getElementById('scContactBtn');
  if(contactBtn) contactBtn.onclick=function(){ window.location.href='/messages'; };
  var fullBtn=document.getElementById('scFullBtn');
  if(fullBtn) fullBtn.onclick=function(){ window.location.href='/profile?id='+encodeURIComponent(_scProfileId); };

  // Reveal
  var ld=document.getElementById('scLoading');
  var ct=document.getElementById('scContent');
  if(ld) ld.style.display='none';
  if(ct) ct.style.display='block';

  // Render Lucide icons (retry if CDN still loading)
  if(!renderIcons()){
    var tries=0, iv=setInterval(function(){
      if(renderIcons() || ++tries>20) clearInterval(iv);
    },150);
  }

  // fitName: rAF → 50ms → 300ms (font may still be loading at rAF)
  requestAnimationFrame(function(){ fitName(); setTimeout(fitName,50); setTimeout(fitName,300); });

  // Score fetch (parallel, non-blocking)
  var numId = (p.id != null) ? p.id : _scProfileId;
  getScore(numId)
    .then(function(sc){ if(sc && typeof sc.score!=='undefined') setText('scStatScore', sc.score); })
    .catch(function(){ /* score stays — */ });
}; // end renderProfile

// ── Initial load ──
(function(){
  if(!_scProfileId){
    var ld=document.getElementById('scLoading');
    if(ld) ld.textContent='لا يوجد معرّف ملف';
    return;
  }
  getProfile(_scProfileId)
    .then(window.renderProfile)
    .catch(function(){
      var ld=document.getElementById('scLoading');
      if(ld) ld.textContent='تعذّر تحميل الملف';
    });
})();

// ── Preview Eye Button (Doctrine §24) ──
(function(){
  var eyeWrap = document.getElementById('scEyeWrap');
  var eyeBtn  = document.getElementById('scEyeBtn');
  var eyeMenu = document.getElementById('scEyeMenu');
  if(!eyeBtn || !eyeMenu) return;

  eyeBtn.addEventListener('click', function(e){
    e.stopPropagation();
    eyeMenu.classList.toggle('open');
  });

  document.getElementById('scPreviewPublic').addEventListener('click', function(){
    document.body.classList.remove('preview-guest');
    document.body.classList.add('preview-public-user');
    eyeMenu.classList.remove('open');
  });

  document.getElementById('scPreviewGuest').addEventListener('click', function(){
    document.body.classList.remove('preview-public-user');
    document.body.classList.add('preview-guest');
    eyeMenu.classList.remove('open');
  });

  document.getElementById('scPreviewEnd').addEventListener('click', function(){
    document.body.classList.remove('preview-public-user', 'preview-guest');
    eyeMenu.classList.remove('open');
  });

  document.addEventListener('click', function(e){
    if(eyeWrap && !eyeWrap.contains(e.target)) eyeMenu.classList.remove('open');
  });
})();
