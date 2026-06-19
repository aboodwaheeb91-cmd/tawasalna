// profile-v2.completion.js — Profile completion card (owner-only, Profile V2)
// Reads exclusively from window._scProfile — no localStorage, no DB field.
// Weights sum to 100. Call window._updateCompletion() after any profile save.
;(function(){
  'use strict';

  var _ITEMS = [
    { id:'avatar',    label:'صورة شخصية',       weight:10, action:'avatar'      },
    { id:'name',      label:'الاسم الكامل',      weight:8,  action:'edit-modal'  },
    { id:'profession',label:'التخصص المهني',     weight:8,  action:'edit-modal'  },
    { id:'avail',     label:'حالة التوظيف',      weight:5,  action:'avail-dot'   },
    { id:'short_bio', label:'نبذة قصيرة',        weight:7,  action:'edit-modal'  },
    { id:'bio',       label:'نبذة عني',          weight:8,  action:'edit-modal'  },
    { id:'location',  label:'المدينة / الدولة',  weight:6,  action:'edit-modal'  },
    { id:'skills',    label:'المهارات',           weight:9,  action:'tab-skills'  },
    { id:'exp',       label:'الخبرات',            weight:10, action:'tab-exp'     },
    { id:'edu',       label:'التعليم',            weight:8,  action:'tab-edu'     },
    { id:'courses',   label:'الدورات',            weight:5,  action:'tab-courses' },
    { id:'langs',     label:'اللغات',             weight:5,  action:'tab-langs'   },
    { id:'links',     label:'روابط التواصل',      weight:5,  action:'tab-links'   },
    { id:'tw_id',     label:'رابط مشاركة عام',    weight:6,  action:'none'        },
  ];
  // Total: 10+8+8+5+7+8+6+9+10+8+5+5+5+6 = 100

  // Returns true only when the current viewer is the authenticated owner
  // and is NOT in any preview mode.
  function _isOwnerActive(){
    if(window._scViewerType !== 'owner') return false;
    var b = document.body;
    if(b.classList.contains('preview-public-user')) return false;
    if(b.classList.contains('preview-guest'))       return false;
    return true;
  }

  function _isDone(id){
    var p = window._scProfile || {};
    switch(id){
      case 'avatar':    return !!(p.avatar_url);
      case 'name':      return !!(p.first_name || (p.full_name && p.full_name.trim()));
      case 'profession':return !!(p.profession_id || (p.title && p.title.trim()));
      case 'avail':     return !!(p.avail);
      case 'short_bio': return !!(p.short_bio && p.short_bio.trim());
      case 'bio':       return !!(p.bio && p.bio.trim());
      case 'location':  return !!(p.city || p.country || p.location);
      case 'skills':    return Array.isArray(p.skills)     && p.skills.length     > 0;
      case 'exp':       return Array.isArray(p.experience) && p.experience.length  > 0;
      case 'edu':       return Array.isArray(p.education)  && p.education.length   > 0;
      case 'courses':   return Array.isArray(p.courses)    && p.courses.length     > 0;
      case 'langs':     return Array.isArray(p.langs)      && p.langs.length       > 0;
      case 'links':     return Array.isArray(p.links)      && p.links.length       > 0;
      case 'tw_id':     return !!(p.tw_id && p.tw_id.trim());
      default: return false;
    }
  }

  function _score(){
    var s = 0;
    for(var i = 0; i < _ITEMS.length; i++){
      if(_isDone(_ITEMS[i].id)) s += _ITEMS[i].weight;
    }
    return Math.min(s, 100);
  }

  function _doAction(action){
    if(!_isOwnerActive()) return;
    if(!action || action === 'none') return;
    if(action === 'avatar'){
      var cam = document.getElementById('avCamBtn');
      if(cam) cam.click();
      return;
    }
    if(action === 'edit-modal'){
      var eBtn = document.getElementById('scEditProfileBtn');
      if(eBtn) eBtn.click();
      return;
    }
    if(action === 'avail-dot'){
      var dot = document.getElementById('scAvailDot');
      if(dot) dot.click();
      return;
    }
    if(action.indexOf('tab-') === 0){
      var tabName = action.slice(4);
      if(window._aboutGoTab) window._aboutGoTab(tabName);
      setTimeout(function(){
        var pane = document.getElementById('pane-' + tabName);
        if(pane) pane.scrollIntoView({ behavior:'smooth', block:'start' });
      }, 120);
    }
  }

  function _render(){
    var card = document.getElementById('scComplCard');
    if(!card) return;

    // Hard guard: hide and bail if not the active owner
    if(!_isOwnerActive()){
      card.style.display = 'none';
      var _safeList = document.getElementById('scComplList');
      if(_safeList) _safeList.innerHTML = '';
      return;
    }

    var pct   = _score();
    var color = pct >= 80 ? '#22c55e' : pct >= 50 ? '#f59e0b' : '#f87171';

    var pctEl  = document.getElementById('scComplPct');
    var fillEl = document.getElementById('scComplFill');
    var listEl = document.getElementById('scComplList');
    var togBtn = document.getElementById('scComplToggle');

    if(pctEl)  { pctEl.textContent = pct + '%'; pctEl.style.color = color; }
    if(fillEl) { fillEl.style.width = pct + '%'; fillEl.style.background = color; }

    if(pct >= 100){
      if(togBtn) togBtn.textContent = '🎉 ملفك مكتمل!';
      if(listEl) listEl.style.display = 'none';
      return;
    }

    var missing = [], done = [];
    for(var i = 0; i < _ITEMS.length; i++){
      (_isDone(_ITEMS[i].id) ? done : missing).push(_ITEMS[i]);
    }

    if(togBtn && listEl && listEl.style.display === 'none'){
      togBtn.textContent = missing.length + ' بنود ناقصة — عرض التفاصيل ▾';
    }

    if(!listEl) return;

    var html = '';
    for(var m = 0; m < missing.length; m++){
      var it = missing[m];
      html += '<button type="button" class="sc-compl-item missing" data-action="' + it.action + '">'
        + '<span class="sc-compl-ico sc-compl-ico-miss"></span>'
        + '<span class="sc-compl-label">' + it.label + '</span>'
        + (it.action !== 'none' ? '<span class="sc-compl-weight">+' + it.weight + '%</span>' : '')
        + '</button>';
    }
    for(var d = 0; d < done.length; d++){
      var it2 = done[d];
      html += '<button type="button" class="sc-compl-item done" disabled>'
        + '<span class="sc-compl-ico sc-compl-ico-done"></span>'
        + '<span class="sc-compl-label">' + it2.label + '</span>'
        + '</button>';
    }
    listEl.innerHTML = html;
  }

  window._renderCompletion = _render;
  window._updateCompletion = _render;

  // Item click → open relevant section (owner-active guard)
  document.addEventListener('click', function(e){
    var item = e.target.closest('.sc-compl-item.missing');
    if(!item) return;
    if(!_isOwnerActive()) return;
    var act = item.getAttribute('data-action');
    if(act) _doAction(act);
  });

  // Toggle list open/close (owner-active guard)
  document.addEventListener('click', function(e){
    if(!e.target.closest('#scComplToggle')) return;
    if(!_isOwnerActive()) return;
    var list = document.getElementById('scComplList');
    var btn  = document.getElementById('scComplToggle');
    if(!list || !btn) return;
    var isOpen = list.style.display !== 'none';
    list.style.display = isOpen ? 'none' : 'block';
    if(isOpen){
      var mc = _ITEMS.filter(function(it){ return !_isDone(it.id); }).length;
      btn.textContent = mc + ' بنود ناقصة — عرض التفاصيل ▾';
    } else {
      btn.textContent = 'إخفاء التفاصيل ▴';
    }
  });
})();
