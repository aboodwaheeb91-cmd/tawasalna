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

  // Load unread counts into data-badge spans (guest-safe — loadGlobalBadges checks jwt)
  if(typeof loadGlobalBadges === 'function') loadGlobalBadges();
})();

// ── About tab: navigate to another tab by name ──
window._aboutGoTab = function(tab){
  var btn = document.querySelector('.sc-tab[data-tab="' + tab + '"]');
  if(window.scTab) window.scTab(tab, btn || null);
};

// ── Bio inline editor ──
window._aboutBioEdit = function(){
  var view   = document.getElementById('scAboutBioView');
  var editor = document.getElementById('scAboutBioEditor');
  var ta     = document.getElementById('scAboutBioTa');
  if(!view || !editor || !ta) return;
  view.style.display   = 'none';
  editor.style.display = 'block';
  ta.focus();
  ta.selectionStart = ta.selectionEnd = ta.value.length;
};

window._aboutBioCancel = function(){
  var view   = document.getElementById('scAboutBioView');
  var editor = document.getElementById('scAboutBioEditor');
  var errEl  = document.getElementById('scAboutBioErr');
  if(!view || !editor) return;
  editor.style.display = 'none';
  view.style.display   = '';
  if(errEl){ errEl.textContent = ''; errEl.style.display = 'none'; }
};

window._aboutBioToggle = function(){
  var textEl = document.getElementById('scAboutText');
  var btn    = document.getElementById('scAboutBioMore');
  if(!textEl || !btn) return;
  var expanded = textEl.classList.toggle('sc-bio-expanded');
  btn.textContent = expanded ? 'عرض أقل ▴' : 'عرض المزيد ▾';
};

function _aboutBioCheckMore(){
  var textEl  = document.getElementById('scAboutText');
  var moreBtn = document.getElementById('scAboutBioMore');
  if(!textEl || !moreBtn) return;
  moreBtn.style.display = (textEl.scrollHeight > textEl.clientHeight + 4) ? 'inline-block' : 'none';
}
window._aboutBioCheckMore = _aboutBioCheckMore;

window._aboutBioSave = function(){
  var ta      = document.getElementById('scAboutBioTa');
  var saveBtn = document.getElementById('scAboutBioSaveBtn');
  var errEl   = document.getElementById('scAboutBioErr');
  if(!ta) return;
  var bio = ta.value.trim();

  if(errEl){ errEl.textContent = ''; errEl.style.display = 'none'; }

  var _pcErr = window._scCheckProfessional && window._scCheckProfessional(bio);
  if(_pcErr){
    if(errEl){ errEl.textContent = _pcErr; errEl.style.display = 'block'; }
    return;
  }

  var uid = window._scUserId;
  if(!uid){
    if(errEl){ errEl.textContent = 'خطأ: لم يتم التعرف على المستخدم'; errEl.style.display = 'block'; }
    return;
  }

  if(saveBtn){ saveBtn.disabled = true; saveBtn.textContent = 'جاري الحفظ…'; }

  window.updateProfile(uid, {bio: bio})
  .then(function(res){
    if(saveBtn){ saveBtn.disabled = false; saveBtn.textContent = 'حفظ'; }
    if(!res.ok){
      var status = res.data && res.data.status_code;
      var det    = res.data && res.data.detail;
      var msg = (status === 401 || (det && det.toString().indexOf('401') !== -1))
        ? 'انتهت الجلسة، يرجى تسجيل الدخول مرة أخرى'
        : ((det && typeof det === 'object' && det.message) ? det.message
          : (typeof det === 'string' ? det : 'حدث خطأ، حاول مرة أخرى'));
      if(errEl){ errEl.textContent = msg; errEl.style.display = 'block'; }
      return;
    }
    if(window._scProfile) window._scProfile.bio = bio;
    var textEl = document.getElementById('scAboutText');
    if(textEl){ textEl.textContent = bio; textEl.classList.remove('sc-bio-expanded'); }
    if(ta) ta.value = bio;
    var _card = textEl && textEl.closest && textEl.closest('.sc-ab-card');
    var _hint = _card && _card.querySelector('.sc-ab-empty-hint');
    if(_hint) _hint.style.display = 'none';
    window._aboutBioCancel();
    requestAnimationFrame(function(){ _aboutBioCheckMore(); });
    if(window.toast) toast('تم حفظ النبذة');
  })
  .catch(function(){
    if(saveBtn){ saveBtn.disabled = false; saveBtn.textContent = 'حفظ'; }
    if(errEl){ errEl.textContent = 'تعذّر الحفظ، حاول مرة أخرى'; errEl.style.display = 'block'; }
  });
};

// ── About Pane builder — summary cards ──
function _buildAboutPane(p, isOwner){
  var sections = [];

  // Card-header icons: inline SVG (not Lucide) — avoids re-render race
  var _icoUser = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>';
  var _icoZap  = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>';
  var _icoBag  = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><rect x="2" y="7" width="20" height="14" rx="2"/><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/></svg>';
  var _icoBook = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>';
  var _icoGrad = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><path d="M22 10v6M2 10l10-5 10 5-10 5z"/><path d="M6 12v5c3 3 9 3 12 0v-5"/></svg>';
  var _icoLang = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><path d="M5 8l6 6"/><path d="M4 14l6-6 2-3"/><path d="M2 5h12"/><path d="M7 2h1"/><path d="M22 22l-5-10-5 10"/><path d="M14 18h6"/></svg>';
  var _icoPen  = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" width="13" height="13"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>';

  function _viewAll(tab){
    return '<button class="sc-ab-viewall" onclick="window._aboutGoTab(\''+tab+'\')">'
      + 'عرض الكل &#x276F;</button>';
  }

  // ── 1. Bio card ──
  var bio = (p.bio || '').trim();
  sections.push(
    '<div class="sc-ab-card">'
    + '<div class="sc-ab-head"><span class="sc-ab-title">'+_icoUser+' نبذة عني</span>'
    + (isOwner ? '<button class="sc-ab-edit owner-only" onclick="window._aboutBioEdit()" title="تعديل النبذة" aria-label="تعديل النبذة">'+_icoPen+'</button>' : '')
    + '</div>'
    // View mode
    + '<div id="scAboutBioView">'
    + '<div class="sc-bio-text" id="scAboutText">' + esc(bio || (isOwner ? '' : 'لا توجد نبذة بعد')) + '</div>'
    + '<button class="sc-ab-biomore" id="scAboutBioMore" onclick="window._aboutBioToggle()" style="display:none">عرض المزيد ▾</button>'
    + '</div>'
    // Inline editor (owner only)
    + (isOwner
      ? '<div id="scAboutBioEditor" style="display:none">'
        + '<textarea class="sc-ab-bio-ta" id="scAboutBioTa" maxlength="1200" placeholder="اكتب نبذة تعريفية عن نفسك…">' + esc(bio) + '</textarea>'
        + '<div class="sc-ab-bio-err" id="scAboutBioErr" style="display:none"></div>'
        + '<div class="sc-ab-bio-actions">'
        + '<button class="sc-ab-bio-save" id="scAboutBioSaveBtn" onclick="window._aboutBioSave()">حفظ</button>'
        + '<button class="sc-ab-bio-cancel" onclick="window._aboutBioCancel()">إلغاء</button>'
        + '</div></div>'
      : '')
    + (isOwner && !bio ? '<div class="sc-ab-empty-hint">أضف نبذة تعريفية من زر التعديل أعلاه</div>' : '')
    + '</div>'
  );

  // ── 2. Skills card ──
  var skills = Array.isArray(p.skills) ? p.skills.map(function(s){ return typeof s==='object'?s:{skill:s}; }) : [];
  if(skills.length || isOwner){
    var _RANK = {'محترف':5,'متقدم':4,'جيد':3,'متوسط':2,'مبتدئ':1};
    var _CLR  = {'مبتدئ':'#9ca3af','متوسط':'#60a5fa','جيد':'#a78bfa','متقدم':'#00c896','محترف':'#fbbf24'};
    var sk5 = skills.slice().sort(function(a,b){ return ((_RANK[b.level]||0)-(_RANK[a.level]||0)); }).slice(0,5);
    var skInner = '';
    if(sk5.length){
      skInner = '<div class="sc-ab-chips" dir="ltr">';
      for(var _si=0;_si<sk5.length;_si++){
        var _s=sk5[_si], _c=_CLR[_s.level]||'#9ca3af';
        var _ico = (window._getSkillIcon && window._getSkillIcon(_s.skill||'')) || 'code';
        skInner += '<span class="sc-ab-chip" style="border-color:'+_c+'44;color:'+_c+'">'
          + '<i data-lucide="'+_ico+'" class="sc-ab-chip-ico"></i>'
          + '<span style="unicode-bidi:isolate">'+esc(_s.skill||'')+'</span>'
          + '</span>';
      }
      skInner += '</div>';
    } else {
      skInner = isOwner ? '<div class="sc-ab-empty-hint">أضف مهاراتك لتظهر هنا</div>' : '';
    }
    if(skInner)
      sections.push(
        '<div class="sc-ab-card"><div class="sc-ab-head"><span class="sc-ab-title">'+_icoZap+' المهارات</span>'
        + (skills.length > 5 ? _viewAll('skills') : (skills.length ? _viewAll('skills') : '')) + '</div>' + skInner + '</div>'
      );
  }

  // ── 3. Experience card ──
  var exp = Array.isArray(p.experience) ? p.experience : [];
  if(exp.length || isOwner){
    var expInner = '';
    if(exp.length){
      expInner = '<div class="sc-ab-rows">';
      for(var _ei=0;_ei<Math.min(exp.length,3);_ei++){
        var _e=exp[_ei];
        var _et  = esc(_e.title||'');
        var _eco = _e.company ? esc(_e.company) : '';
        var _ep  = _e.start_date
          ? esc(_e.start_date)+(_e.is_current?' – الآن':(_e.end_date?' – '+esc(_e.end_date):''))
          : '';
        var _emeta = [_eco,_ep].filter(Boolean).join(' · ');
        expInner += '<div class="sc-ab-row">'
          + '<div class="sc-ab-row-t"><i data-lucide="briefcase" class="sc-ab-row-ico"></i><span dir="auto">'+_et+'</span></div>'
          + (_emeta?'<div class="sc-ab-row-d">'+_emeta+'</div>':'')
          + '</div>';
      }
      expInner += '</div>';
    } else {
      expInner = isOwner ? '<div class="sc-ab-empty-hint">أضف خبراتك لتظهر هنا</div>' : '';
    }
    if(expInner)
      sections.push(
        '<div class="sc-ab-card"><div class="sc-ab-head"><span class="sc-ab-title">'+_icoBag+' الخبرات</span>'
        + (exp.length ? _viewAll('exp') : '') + '</div>' + expInner + '</div>'
      );
  }

  // ── 4. Courses card ──
  var courses = Array.isArray(p.courses) ? p.courses : [];
  if(courses.length || isOwner){
    var crsInner = '';
    if(courses.length){
      crsInner = '<div class="sc-ab-rows">';
      for(var _ci=0;_ci<Math.min(courses.length,3);_ci++){
        var _cr=courses[_ci];
        var _ct = esc(_cr.title||'');
        var _cp = _cr.provider ? esc(_cr.provider) : '';
        var _cd = _cr.completion_date ? esc(String(_cr.completion_date).split('-')[0]) : '';
        var _cmeta = [_cp,_cd].filter(Boolean).join(' · ');
        crsInner += '<div class="sc-ab-row">'
          + '<div class="sc-ab-row-t"><i data-lucide="book-open" class="sc-ab-row-ico"></i><span dir="auto">'+_ct+'</span></div>'
          + (_cmeta?'<div class="sc-ab-row-d">'+_cmeta+'</div>':'')
          + '</div>';
      }
      crsInner += '</div>';
    } else {
      crsInner = isOwner ? '<div class="sc-ab-empty-hint">أضف دوراتك لتظهر هنا</div>' : '';
    }
    if(crsInner)
      sections.push(
        '<div class="sc-ab-card"><div class="sc-ab-head"><span class="sc-ab-title">'+_icoBook+' الدورات</span>'
        + (courses.length ? _viewAll('courses') : '') + '</div>' + crsInner + '</div>'
      );
  }

  // ── 5. Education card ──
  var edu = Array.isArray(p.education) ? p.education : [];
  if(edu.length || isOwner){
    var eduInner = '';
    if(edu.length){
      eduInner = '<div class="sc-ab-rows">';
      for(var _di=0;_di<Math.min(edu.length,3);_di++){
        var _d=edu[_di];
        var _deg    = _d.degree ? esc(_d.degree) : '';
        var _fld    = _d.field  ? esc(_d.field)  : '';
        var _dtitle = _deg ? (_deg+(_fld?' – '+_fld:'')) : (_fld||'شهادة');
        var _inst   = _d.institution ? esc(_d.institution) : '';
        var _dper   = _d.start_year
          ? (String(_d.start_year)+(_d.is_current?' – قيد الدراسة':(_d.end_year?' – '+String(_d.end_year):'')))
          : '';
        var _dmeta = [_inst,_dper].filter(Boolean).join(' · ');
        eduInner += '<div class="sc-ab-row">'
          + '<div class="sc-ab-row-t"><i data-lucide="graduation-cap" class="sc-ab-row-ico"></i><span dir="auto">'+_dtitle+'</span></div>'
          + (_dmeta?'<div class="sc-ab-row-d">'+_dmeta+'</div>':'')
          + '</div>';
      }
      eduInner += '</div>';
    } else {
      eduInner = isOwner ? '<div class="sc-ab-empty-hint">أضف شهاداتك لتظهر هنا</div>' : '';
    }
    if(eduInner)
      sections.push(
        '<div class="sc-ab-card"><div class="sc-ab-head"><span class="sc-ab-title">'+_icoGrad+' التعليم</span>'
        + (edu.length ? _viewAll('edu') : '') + '</div>' + eduInner + '</div>'
      );
  }

  // ── 6. Languages card (max 3) ──
  var langs = Array.isArray(p.langs) ? p.langs : [];
  if(langs.length || isOwner){
    var langs3   = langs.slice(0,3);
    var langInner = '';
    if(langs3.length){
      langInner = '<div class="sc-ab-chips">';
      for(var _li=0;_li<langs3.length;_li++){
        var _l=langs3[_li];
        var _lv = _l.level ? '<span class="sc-ab-chip-sub">'+esc(_l.level)+'</span>' : '';
        langInner += '<span class="sc-ab-chip sc-ab-chip--lang">'
          + '<i data-lucide="globe" class="sc-ab-chip-ico"></i>'
          + '<span dir="auto">'+esc(_l.language||'')+'</span>'
          + _lv + '</span>';
      }
      langInner += '</div>';
    } else {
      langInner = isOwner ? '<div class="sc-ab-empty-hint">أضف لغاتك لتظهر هنا</div>' : '';
    }
    if(langInner)
      sections.push(
        '<div class="sc-ab-card"><div class="sc-ab-head"><span class="sc-ab-title">'+_icoLang+' اللغات</span>'
        + (langs.length ? _viewAll('langs') : '') + '</div>' + langInner + '</div>'
      );
  }

  return sections.join('');
}

window._reRenderAbout = function(){
  var pane = document.getElementById('pane-about');
  if(!pane || !window._scProfile) return;
  pane.innerHTML = _buildAboutPane(window._scProfile, window._scViewerType === 'owner');
  if(window.lucide && lucide.createIcons) lucide.createIcons();
  requestAnimationFrame(function(){ _aboutBioCheckMore(); });
};

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

  // Store viewer_action for Interest System (Step 3)
  window._scViewerAction = (res && res.viewer_action) ? res.viewer_action : null;

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
  setText('scBio', p.short_bio || '');

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
    var _qrId  = (p.tw_id || '').trim();
    var _qrUrl = _qrId ? ('https://tawasolna.com/u/' + encodeURIComponent(_qrId) + '?ref=qr') : '';
    var _displayUrl = _qrId ? ('https://tawasolna.com/u/' + encodeURIComponent(_qrId)) : '';

    // Debug log — remove after confirming QR URLs in production
    console.log('[QR] profile.id:', p.id, '| tw_id:', _qrId || '(empty!)', '| qrUrl:', _qrUrl, '| displayUrl:', _displayUrl);

    if(!_qrId){
      // Guard: no tw_id — render placeholder and block modal
      qrEl.innerHTML = '<div class="sc-qr-inner" style="display:flex;align-items:center;justify-content:center;font-size:11px;color:rgba(255,255,255,.4);text-align:center;padding:8px;">تعذّر إنشاء<br>رابط المشاركة</div>';
      qrEl.onclick = function(){ if(window.toast) toast('تعذّر إنشاء رابط المشاركة — يرجى تسجيل الخروج والدخول مجدداً'); };
    } else {
      renderQR(qrEl, _qrUrl);
      qrEl.setAttribute('role', 'button');
      qrEl.setAttribute('tabindex', '0');
      qrEl.setAttribute('aria-label', 'فتح رمز QR لمشاركة البروفايل');
      qrEl.setAttribute('title', 'مشاركة البروفايل');
      qrEl.onclick = function(){ openQRModal(_qrUrl, p.full_name || p.first_name || ''); };
      qrEl.onkeydown = function(e){
        if(e.key === 'Enter' || e.key === ' '){ e.preventDefault(); openQRModal(_qrUrl, p.full_name || p.first_name || ''); }
      };
    }
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

  // Tab: About — summary cards
  var aboutPane = document.getElementById('pane-about');
  if(aboutPane) aboutPane.innerHTML = _buildAboutPane(p, _vt === 'owner');

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

  // ── Follow button ──
  var _isFollowing  = !!res.is_following;
  var _canFollow    = !!(res.permissions && res.permissions.can_follow);
  var _followCount  = (res.followers_count != null) ? res.followers_count : 0;

  // Populate followers counter from API
  setText('scStatFollowers',      formatCompactCount(_followCount));
  setText('scFlPopCountFollowers', formatCompactCount(_followCount));

  // Populate views counter from API
  var _viewsCount = (res.views_count != null) ? Number(res.views_count) : 0;
  setText('scStatViews', formatCompactCount(_viewsCount));
  window._scProfile.views_count = _viewsCount;

  (function(){
    var followBtn = document.getElementById('scFollowBtn');
    if(!followBtn) return;

    // Reset any previous inline display — CSS handles owner hide/preview show
    followBtn.style.display = '';

    function _setBtn(following, newCount){
      if(following){
        followBtn.className = 'sc-btn sc-btn--following';
        followBtn.innerHTML = '<i data-lucide="user-check" class="ico-sm"></i> متابَع';
      } else {
        followBtn.className = 'sc-btn sc-btn-primary';
        followBtn.innerHTML = '<i data-lucide="user-plus" class="ico-sm"></i> متابعة';
      }
      if(newCount != null) setText('scStatFollowers', formatCompactCount(newCount));
      if(window.lucide && lucide.createIcons) lucide.createIcons();
    }

    _setBtn(_isFollowing, null);

    followBtn.onclick = function(){
      // Preview mode: visual only, no API
      var _isPreview = document.body.classList.contains('preview-public-user')
                    || document.body.classList.contains('preview-guest');
      if(_isPreview){
        if(window.toast) toast('هذه معاينة فقط');
        return;
      }

      // Guest or owner (can_follow=false): prompt login
      if(_vt === 'guest' || !_canFollow){
        if(window.toast) toast('سجّل الدخول لمتابعة هذا الحساب');
        return;
      }

      if(followBtn.disabled) return;
      followBtn.disabled = true;

      var _req = _isFollowing
        ? window.unfollowProfile(p.id)
        : window.followProfile(p.id);

      _req.then(function(r){
        if(r.ok){
          _isFollowing = !!r.data.is_following;
          _setBtn(_isFollowing, r.data.followers_count);
        } else {
          if(window.toast) toast('حدث خطأ، حاول مرة أخرى');
        }
      }).catch(function(){
        if(window.toast) toast('خطأ في الاتصال');
      }).finally(function(){
        followBtn.disabled = false;
      });
    };
  })();

  // Contact button — three-mode: owner hidden / guest toast / logged-in navigate
  var contactBtn = document.getElementById('scContactBtn');
  if(contactBtn){
    if(_vt === 'owner'){
      contactBtn.style.display = 'none';
    } else {
      contactBtn.style.display = '';
      contactBtn.onclick = function(){
        if(_vt === 'guest'){
          if(window.toast) toast('سجّل الدخول للتواصل');
          return;
        }
        var tw = window._scProfile && window._scProfile.tw_id;
        if(!tw){ if(window.toast) toast('تعذر فتح المحادثة'); return; }
        window.location.href = '/messages?with=' + encodeURIComponent(tw);
      };
    }
  }
  // ── Profile Interest Button (replaces hardcoded /profile?id nav) ──
  (function(){
    var intBtn = document.getElementById('scFullBtn');
    if(!intBtn) return;

    var va = window._scViewerAction;

    // hidden: owner viewing own profile OR target profile is not emp
    if(!va || va.hidden){
      intBtn.style.display = 'none';
      return;
    }
    intBtn.style.display = '';
    var _vaType = va.type;
    if(_vaType === 'profile_like')   intBtn.classList.add('sc-btn--like');
    if(_vaType === 'candidate_save') intBtn.classList.add('sc-btn--candidate');

    function _icon(isActive){
      if(_vaType === 'candidate_save') return isActive ? 'user-check' : 'user-plus';
      return 'heart';
    }

    function _applyVa(v){
      intBtn.innerHTML = '<i data-lucide="' + _icon(v.is_active) + '" class="ico-sm"></i> ' + esc(v.label);
      if(v.is_active){
        intBtn.classList.add('sc-btn--interested');
        intBtn.classList.remove('sc-btn-ghost');
      } else {
        intBtn.classList.remove('sc-btn--interested');
        intBtn.classList.add('sc-btn-ghost');
      }
      if(window.lucide && lucide.createIcons) lucide.createIcons();
    }

    function _showCandidateHint(){
      var old = document.getElementById('_scCandidateHint');
      if(old) old.remove();
      var hint = document.createElement('div');
      hint.id = '_scCandidateHint';
      hint.className = 'sc-candidate-hint';
      hint.innerHTML =
        '<div class="sc-candidate-hint-msg">'
          + '<i data-lucide="check-circle" class="ico-sm"></i>'
          + '<div><div>تم حفظ المرشح</div>'
          + '<div class="sc-candidate-hint-sub">يمكنك إضافة ملاحظة خاصة</div></div>'
        + '</div>'
        + '<div class="sc-candidate-hint-actions">'
          + '<button class="sc-candidate-hint-btn" id="_scNoteBtn">إضافة ملاحظة</button>'
          + '<button class="sc-candidate-hint-btn sc-candidate-hint-btn--dismiss" id="_scDismissBtn">ليس الآن</button>'
        + '</div>';
      var row = intBtn.closest('.sc-actions') || intBtn.parentNode;
      row.parentNode.insertBefore(hint, row.nextSibling);
      if(window.lucide && lucide.createIcons) lucide.createIcons();
      document.getElementById('_scNoteBtn').onclick = function(){
        if(window.toast) toast('سيتم إضافة ملاحظات المرشحين قريباً');
        hint.remove();
      };
      document.getElementById('_scDismissBtn').onclick = function(){ hint.remove(); };
    }

    _applyVa(va);

    // Guest / login_prompt
    if(_vaType === 'login_prompt' || !va.can_interact){
      intBtn.onclick = function(){
        if(window.toast) toast('سجّل الدخول للتفاعل مع الملفات الشخصية');
      };
      return;
    }

    // Authenticated: POST / DELETE toggle
    var _busy = false;
    intBtn.onclick = function(){
      if(_busy) return;
      _busy = true;
      intBtn.disabled = true;

      var curVa    = window._scViewerAction;
      var targetId = p.id;
      var action   = (curVa && curVa.is_active) ? removeProfileInterest : saveProfileInterest;

      action(targetId)
        .then(function(r){
          if(r.ok && r.data && r.data.viewer_action){
            window._scViewerAction = r.data.viewer_action;
            _applyVa(r.data.viewer_action);
            if(_vaType === 'candidate_save'){
              if(r.data.viewer_action.is_active){
                _showCandidateHint();
              } else {
                var _h = document.getElementById('_scCandidateHint');
                if(_h) _h.remove();
                if(window.toast) toast('تم إلغاء حفظ المرشح');
              }
            } else {
              if(window.toast) toast(r.data.viewer_action.is_active ? 'تم حفظ التفاعل' : 'تم إلغاء التفاعل');
            }
          } else {
            if(window.toast) toast('حدث خطأ، حاول مرة أخرى');
          }
        })
        .catch(function(){ if(window.toast) toast('خطأ في الاتصال'); })
        .finally(function(){ _busy = false; intBtn.disabled = false; });
    };
  })();

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
  requestAnimationFrame(function(){
    fitName(); setTimeout(fitName,50); setTimeout(fitName,300);
    _aboutBioCheckMore();
  });

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

// ── Profile Metrics soft refresh ──
// Uses GET /profile/{id}/metrics — read-only, no view recording, no full re-render.
// Updates 5 visible counters: views, followers, edu, exp, score.
// Stores remaining counts (courses, skills, langs, links) in state only.
// Triggers: visibilitychange, window.focus, setInterval(30s). Cooldown: 20s.
(function(){
  var _lastCheck = 0;
  var _COOLDOWN  = 20000;

  window.refreshProfileMetrics = function(){
    if(!_scProfileId) return;
    var now = Date.now();
    if(now - _lastCheck < _COOLDOWN) return;
    _lastCheck = now;

    getProfileMetrics(_scProfileId)
      .then(function(res){
        if(!res || !res.metrics) return;
        var m = res.metrics;
        // Visible counters
        if(m.views_count      != null) setText('scStatViews',     formatCompactCount(Number(m.views_count)));
        if(m.followers_count  != null){
          var _fc = formatCompactCount(Number(m.followers_count));
          setText('scStatFollowers',      _fc);
          setText('scFlPopCountFollowers', _fc);
        }
        if(m.following_count  != null) setText('scFlPopCountFollowing', formatCompactCount(Number(m.following_count)));
        if(m.education_count  != null) setText('scStatEdu',   Number(m.education_count));
        if(m.experience_count != null) setText('scStatExp',   Number(m.experience_count));
        if(m.score            != null) setText('scStatScore', Number(m.score));
        // State — all counts preserved as numbers
        if(window._scProfile){
          if(m.views_count      != null) window._scProfile.views_count      = Number(m.views_count);
          if(m.followers_count  != null) window._scProfile.followers_count  = Number(m.followers_count);
          if(m.following_count  != null) window._scProfile.following_count  = Number(m.following_count);
          if(m.education_count  != null) window._scProfile.education_count  = Number(m.education_count);
          if(m.experience_count != null) window._scProfile.experience_count = Number(m.experience_count);
          if(m.courses_count    != null) window._scProfile.courses_count    = Number(m.courses_count);
          if(m.skills_count     != null) window._scProfile.skills_count     = Number(m.skills_count);
          if(m.languages_count  != null) window._scProfile.languages_count  = Number(m.languages_count);
          if(m.links_count      != null) window._scProfile.links_count      = Number(m.links_count);
          if(m.score            != null) window._scProfile.score            = Number(m.score);
        }
        if(res.viewer && res.viewer.is_following != null && window._scProfile)
          window._scProfile.is_following = res.viewer.is_following;
      })
      .catch(function(){ /* silent */ });
  };

  document.addEventListener('visibilitychange', function(){
    if(document.visibilityState === 'visible') window.refreshProfileMetrics();
  });
  window.addEventListener('focus', window.refreshProfileMetrics);
  setInterval(window.refreshProfileMetrics, 30000);
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

// ── Follow List Modal ──
(function(){
  var _overlay  = document.getElementById('scFollowListModal');
  if(!_overlay) return;
  var _list     = document.getElementById('scFlList');
  var _loadWrap = document.getElementById('scFlLoad');
  var _loadBtn  = document.getElementById('scFlLoadMore');
  var _filtersEl= document.getElementById('scFlFilters');

  var _mode    = 'followers';
  var _filter  = 'all';
  var _offset  = 0;
  var _limit   = 20;
  var _loading = false;

  var _TYPE_LABELS = { all: 'الكل', emp: 'موظفون', co: 'شركات', edu: 'مراكز تعليم' };
  var _TYPE_BADGE  = {
    emp: { label: 'موظف',        cls: 'sc-fl-type-badge--emp' },
    co:  { label: 'شركة',        cls: 'sc-fl-type-badge--co'  },
    edu: { label: 'مركز تعليم',  cls: 'sc-fl-type-badge--edu' },
  };

  function _open(mode){
    _mode   = mode || 'followers';
    _filter = 'all';
    _offset = 0;
    _list.innerHTML = '';
    _loadWrap.style.display = 'none';
    if(_filtersEl) _filtersEl.innerHTML = '';
    _overlay.style.display  = 'flex';
    document.body.style.overflow = 'hidden';
    document.getElementById('scFlTabFollowers').classList.toggle('active', _mode === 'followers');
    document.getElementById('scFlTabFollowing').classList.toggle('active', _mode === 'following');
    _fetchPage(true);
  }

  function _close(){
    _overlay.style.display = 'none';
    document.body.style.overflow = '';
  }

  function _setFilter(type){
    if(_filter === type) return;
    _filter = type;
    _offset = 0;
    _fetchPage(true);
  }

  function _fetchPage(replace){
    if(_loading || !_scProfileId) return;
    _loading = true;
    if(replace) _list.innerHTML = '<div class="sc-fl-spin"></div>';
    var fn = _mode === 'followers' ? window.getFollowersList : window.getFollowingList;
    fn(_scProfileId, _limit, _offset, _filter)
      .then(function(res){
        _loading = false;
        if(!res || !res.ok || !res.data) return;
        var d = res.data;
        if(replace) _list.innerHTML = '';
        if(_offset === 0 && d.counts) _renderChips(d.counts);
        _renderItems(d.items || []);
        var pag = d.pagination || {};
        _offset += (d.items || []).length;
        _loadWrap.style.display = pag.has_more ? 'flex' : 'none';
      })
      .catch(function(){ _loading = false; });
  }

  function _renderChips(counts){
    if(!_filtersEl) return;
    _filtersEl.innerHTML = '';
    ['all', 'emp', 'co', 'edu'].forEach(function(t){
      var cnt = counts[t] != null ? Number(counts[t]) : 0;
      var btn = document.createElement('button');
      btn.className = 'sc-fl-chip' + (t === _filter ? ' active' : '');
      btn.dataset.ftype = t;
      if(cnt === 0 && t !== 'all') btn.disabled = true;
      btn.innerHTML = esc(_TYPE_LABELS[t]) + ' <span class="sc-fl-chip-count">' + formatCompactCount(cnt) + '</span>';
      _filtersEl.appendChild(btn);
    });
  }

  _filtersEl && _filtersEl.addEventListener('click', function(e){
    var btn = e.target.closest('.sc-fl-chip');
    if(!btn || btn.disabled) return;
    var t = btn.dataset.ftype;
    if(!t || t === _filter) return;
    _filtersEl.querySelectorAll('.sc-fl-chip').forEach(function(c){
      c.classList.toggle('active', c.dataset.ftype === t);
    });
    _setFilter(t);
  });

  function _typeBadge(user_type){
    var m = _TYPE_BADGE[user_type];
    if(!m) return '';
    return '<span class="sc-fl-type-badge ' + m.cls + '">' + m.label + '</span>';
  }

  function _renderItems(items){
    if(!items.length && _offset === 0){
      _list.innerHTML = '<div class="sc-fl-empty">لا توجد نتائج بعد</div>';
      return;
    }
    items.forEach(function(item){
      var profHtml = item.profession && item.profession.name_ar
        ? '<span class="sc-fl-prof">' + esc(item.profession.name_ar) + '</span>' : '';
      var avatarHtml = item.avatar_url
        ? '<img class="sc-fl-avatar" src="' + esc(item.avatar_url) + '" alt="">'
        : '<div class="sc-fl-avatar sc-fl-avatar-ph"><i data-lucide="user" class="ico-sm"></i></div>';
      var followBtn = item.can_follow
        ? '<button class="sc-fl-follow-btn' + (item.is_following ? ' active' : '') + '" data-uid="' + item.id + '">'
          + (item.is_following ? 'متابَع' : 'تابع') + '</button>' : '';
      var el = document.createElement('div');
      el.className = 'sc-fl-item';
      el.innerHTML =
        '<a class="sc-fl-info" href="/u/' + esc(item.tw_id) + '">'
        + avatarHtml
        + '<div class="sc-fl-meta">'
        + '<span class="sc-fl-name">' + esc(item.display_name || '') + '</span>'
        + '<div class="sc-fl-sub">' + profHtml + _typeBadge(item.user_type) + '</div>'
        + '</div></a>' + followBtn;
      _list.appendChild(el);
    });
    if(window.lucide && lucide.createIcons) lucide.createIcons();
  }

  _list.addEventListener('click', function(e){
    var btn = e.target.closest('.sc-fl-follow-btn');
    if(!btn) return;
    var uid = btn.dataset.uid;
    if(!uid) return;
    var isActive = btn.classList.contains('active');
    btn.disabled = true;
    var fn = isActive ? window.unfollowProfile : window.followProfile;
    fn(uid).then(function(res){
      btn.disabled = false;
      if(res.ok){
        btn.classList.toggle('active', !isActive);
        btn.textContent = !isActive ? 'متابَع' : 'تابع';
      }
    }).catch(function(){ btn.disabled = false; });
  });

  // Tile click wiring handled by Popover IIFE below (_scFlOpen exposed as window._scFlOpen)

  document.getElementById('scFlClose').addEventListener('click', _close);
  _overlay.addEventListener('click', function(e){ if(e.target === _overlay) _close(); });
  document.addEventListener('keydown', function(e){ if(e.key === 'Escape') _close(); });

  if(_loadBtn) _loadBtn.addEventListener('click', function(){ _fetchPage(false); });

  window._scFlSwitch = function(mode, tabEl){
    _mode   = mode;
    _filter = 'all';
    _offset = 0;
    document.querySelectorAll('.sc-fl-tab').forEach(function(t){ t.classList.remove('active'); });
    if(tabEl) tabEl.classList.add('active');
    if(_filtersEl) _filtersEl.innerHTML = '';
    _fetchPage(true);
  };

  window._scFlOpen = _open;
})();

// ── Followers Popover ──
(function(){
  var _popover   = document.getElementById('scFlPopover');
  var _tile      = document.getElementById('scStatFollowersTile');
  if(!_popover || !_tile) return;

  var _visible   = false;
  var _autoHide;

  function _openPop(){
    // Measure width before reveal to center correctly
    _popover.style.visibility = 'hidden';
    _popover.style.display    = 'flex';
    if(window.lucide && lucide.createIcons) lucide.createIcons();

    var rect = _tile.getBoundingClientRect();
    var popW = _popover.offsetWidth;
    var left = rect.left + rect.width / 2 - popW / 2;
    var maxL = window.innerWidth - popW - 8;

    _popover.style.top        = (rect.bottom + window.scrollY + 8) + 'px';
    _popover.style.left       = Math.max(8, Math.min(left, maxL)) + 'px';
    _popover.style.visibility = '';
    _visible = true;

    clearTimeout(_autoHide);
    _autoHide = setTimeout(_closePop, 5000);
  }

  function _closePop(){
    clearTimeout(_autoHide);
    _popover.style.display = 'none';
    _visible = false;
  }

  _tile.addEventListener('click', function(e){
    e.stopPropagation();
    if(_visible){ _closePop(); } else { _openPop(); }
  });

  // Pause auto-hide while hovering the popover
  _popover.addEventListener('mouseenter', function(){ clearTimeout(_autoHide); });
  _popover.addEventListener('mouseleave', function(){
    if(_visible) _autoHide = setTimeout(_closePop, 5000);
  });

  document.addEventListener('click', function(e){
    if(_visible && !_popover.contains(e.target)) _closePop();
  });

  document.addEventListener('keydown', function(e){
    if(e.key === 'Escape' && _visible) _closePop();
  });

  document.getElementById('scFlPopFollowers').addEventListener('click', function(){
    _closePop();
    if(window._scFlOpen) window._scFlOpen('followers');
  });

  document.getElementById('scFlPopFollowing').addEventListener('click', function(){
    _closePop();
    if(window._scFlOpen) window._scFlOpen('following');
  });
})();
