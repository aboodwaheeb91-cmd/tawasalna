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

// ── Experience HTML builder (shared with profile-v2.exp.js) ──
window._buildExpHTML = function(exp, isOwner){
  var addBtn = isOwner
    ? '<button class="sc-section-add owner-only" onclick="window._expOpenAdd()">'
      + '<svg class="ico-sm" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>'
      + ' إضافة خبرة</button>'
    : '';
  if(!exp.length) return addBtn + '<div class="sc-empty">لا توجد خبرات بعد</div>';
  var n = exp.length;
  var icoPin = '<svg class="sc-exp-ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>';
  var icoCal = '<svg class="sc-exp-ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>';
  return addBtn + '<div class="sc-exp-list">' + exp.map(function(e, i){
    var t    = esc(e.title   || '');
    var c    = esc(e.company || '');
    var loc  = e.location ? esc(e.location) : '';
    var dateStr = e.start_date
      ? esc(e.start_date) + (!e.is_current && e.end_date ? ' — ' + esc(e.end_date) : '')
      : '';
    var desc = e.description ? esc(e.description) : '';
    var meta = '';
    if(loc || dateStr || e.is_current){
      meta = '<div class="sc-exp-meta">';
      if(loc)          meta += '<span class="sc-exp-meta-item">'+icoPin+loc+'</span>';
      if(dateStr)      meta += '<span class="sc-exp-meta-item">'+icoCal+dateStr+'</span>';
      if(e.is_current) meta += '<span class="sc-exp-current">حتى الآن</span>';
      meta += '</div>';
    }
    var upDis = (i === 0)     ? ' disabled' : '';
    var dnDis = (i === n - 1) ? ' disabled' : '';
    var actions = isOwner
      ? '<div class="sc-exp-menu-wrap owner-only">'
        +'<button class="sc-exp-menu-btn" onclick="window._expMenuToggle(this)" title="خيارات">'
        +'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="5" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="12" cy="19" r="1"/></svg>'
        +'</button>'
        +'<div class="sc-exp-menu">'
        +'<button class="sc-exp-menu-item" data-exp-id="'+e.id+'" onclick="window._expOpenEdit(this.dataset.expId);window._expMenuClose()">'
        +'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>'
        +' تعديل</button>'
        +'<button class="sc-exp-menu-item sc-exp-menu-move"'+upDis+' data-exp-id="'+e.id+'" onclick="if(!this.disabled){window._expMoveUp(this.dataset.expId);window._expMenuClose()}">'
        +'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="18 15 12 9 6 15"/></svg>'
        +' رفع للأعلى</button>'
        +'<button class="sc-exp-menu-item sc-exp-menu-move"'+dnDis+' data-exp-id="'+e.id+'" onclick="if(!this.disabled){window._expMoveDown(this.dataset.expId);window._expMenuClose()}">'
        +'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"/></svg>'
        +' إنزال للأسفل</button>'
        +'<div class="sc-exp-menu-sep"></div>'
        +'<button class="sc-exp-menu-item sc-exp-menu-del" data-exp-id="'+e.id+'" onclick="window._expConfirmDelete(this.dataset.expId);window._expMenuClose()">'
        +'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4h6v2"/></svg>'
        +' حذف</button>'
        +'</div>'
        +'</div>'
      : '';
    return '<div class="sc-exp-card">'
      + '<div class="sc-exp-head">'
      + '<div class="sc-exp-body">'
      + '<div class="sc-exp-title">'+t+'</div>'
      + (c    ? '<div class="sc-exp-company">'+c+'</div>' : '')
      + meta
      + (desc ? '<div class="sc-exp-desc">'+desc+'</div>' : '')
      + '</div>'
      + actions
      + '</div>'
      + '</div>';
  }).join('') + '</div>';
};

// ── Country code → Arabic name (shared with edit modal) ──
window._SC_COUNTRIES = {
  JO:'الأردن', SA:'السعودية', AE:'الإمارات', KW:'الكويت',
  QA:'قطر',    BH:'البحرين', OM:'عُمان',    EG:'مصر',
  IQ:'العراق', SY:'سوريا',   LB:'لبنان',   PS:'فلسطين',
  YE:'اليمن',  MA:'المغرب',  DZ:'الجزائر', TN:'تونس',
  LY:'ليبيا',  SD:'السودان'
};

// Build display location: "البلد - المدينة", or "البلد", or fallback text
window._buildLocText = function(country, city, fallback){
  if(country && window._SC_COUNTRIES[country]){
    var name = window._SC_COUNTRIES[country];
    return city ? (name + ' - ' + city) : name;
  }
  return fallback || '';
};

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

  // expose viewer type for other modules (exp, edu, etc.)
  window._scViewerType = _vt;

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

  // Location — prefer country/city (structured), fall back to p.location (legacy text)
  var locEl=document.getElementById('scLoc');
  if(locEl){
    var _locText = window._buildLocText(p.country, p.city, p.location);
    if(_locText){
      locEl.innerHTML = '<i data-lucide="map-pin" class="ico-sm"></i> ' + esc(_locText);
      locEl.style.display='inline-flex';
      locEl.style.alignItems='center';
      locEl.style.gap='4px';
    } else {
      locEl.innerHTML = '';
      locEl.style.display = '';
    }
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
    var _skOwner = (_vt === 'owner');
    if(window._buildSkillsHTML){
      var _skillsNorm = skills.map(function(s){ return typeof s==='object' ? s : {skill:s}; });
      skEl.innerHTML = window._buildSkillsHTML(_skillsNorm, _skOwner);
    } else {
      skEl.innerHTML = skills.length
        ? skills.map(function(s){
            var label=(s&&typeof s==='object')?(s.skill||''):s;
            return '<span class="sc-skill">'+esc(label)+'</span>';
          }).join('')
        : '<div class="sc-empty">لا توجد مهارات بعد</div>';
    }
  }

  // Tab: Experience
  var expEl=document.getElementById('scExpPane');
  if(expEl){ expEl.innerHTML = _buildExpHTML(exp, _vt === 'owner'); }

  // Tab: Education
  var isOwner = (_vt === 'owner');
  var eduEl=document.getElementById('scEduPane');
  if(eduEl){
    if(window._buildEduHTML){
      eduEl.innerHTML = window._buildEduHTML(edu, isOwner);
    } else {
      eduEl.innerHTML = edu.length
        ? edu.map(function(d){
            var inst=esc(d.institution||''); var deg=esc(d.degree||'');
            var fld=d.field?(' · '+esc(d.field)):'';
            return '<div class="sc-item"><div class="sc-item-t">'+inst+'</div>'+
              ((deg||fld)?'<div class="sc-item-s">'+deg+fld+'</div>':'')+'</div>';
          }).join('')
        : '<div class="sc-empty">لا توجد شهادات بعد</div>';
    }
  }

  // Tab: Courses
  var coursesEl=document.getElementById('scCoursesPane');
  if(coursesEl){
    if(window._buildCoursesHTML) coursesEl.innerHTML = window._buildCoursesHTML(p.courses||[], isOwner);
    else coursesEl.innerHTML = '<div class="sc-empty">لا توجد دورات بعد</div>';
  }

  // Tab: Languages
  var langsEl=document.getElementById('scLangsPane');
  if(langsEl){
    if(window._buildLangsHTML) langsEl.innerHTML = window._buildLangsHTML(p.langs||[], isOwner);
    else langsEl.innerHTML = '<div class="sc-empty">لا توجد لغات بعد</div>';
  }

  // Tab: Links
  var linksEl=document.getElementById('scLinksPane');
  if(linksEl){
    if(window._buildLinksHTML) linksEl.innerHTML = window._buildLinksHTML(p.links||[], isOwner);
    else linksEl.innerHTML = '<div class="sc-empty">لا توجد روابط بعد</div>';
  }

  // Global state for section modules
  window._scProfile    = p;
  window._scViewerType = _vt;
  window._scUserId     = p.id;

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
