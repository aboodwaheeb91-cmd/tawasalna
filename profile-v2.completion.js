// profile-v2.completion.js — Compact Completion Strip (owner-only, Profile V2)
// Reads exclusively from window._scProfile — no localStorage, no DB field.
// Weights sum to 100. Call window._updateCompletion() after any profile save.
;(function(){
  'use strict';

  // Session-level dismiss — reset on page reload, no persistence
  var _dismissed = false;

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

  // Returns true only when viewing as authenticated owner outside any preview mode
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

  // Rule-based suggestions from profile title/profession/skills — no API call
  function _buildSuggestions(){
    var p   = window._scProfile || {};
    var src = [
      (p.title || ''),
      ((p.profession && (p.profession.name_ar || p.profession.name || '')) || ''),
      (p.bio || ''),
    ].join(' ').toLowerCase();
    var skillStr = (p.skills || []).map(function(s){
      return (s.skill || s.name || '').toLowerCase();
    }).join(' ');
    var all = src + ' ' + skillStr;

    var map = [
      { re:/javascript|react|vue|angular|frontend|html|css|node|typescript/,  label:'تطوير الواجهات الأمامية'          },
      { re:/python|django|fastapi|backend|laravel|php|api|java|spring/,        label:'تطوير الخلفية والـ API'            },
      { re:/data|machine.?learn|ai|analytics|power.?bi|tensorflow|pandas/,     label:'تحليل البيانات والذكاء الاصطناعي' },
      { re:/تسويق|marketing|seo|social.?media|content|google.?ads/,            label:'التسويق الرقمي'                   },
      { re:/design|ui|ux|figma|photoshop|illustrator|تصميم/,                   label:'تصميم UI/UX'                      },
      { re:/project|management|agile|scrum|pmp|إدارة.?مشاريع/,                 label:'إدارة المشاريع'                   },
      { re:/accounting|finance|excel|محاسبة|مالية|erp|sap/,                    label:'المحاسبة والمالية'                 },
      { re:/sales|مبيعات|crm|negotiation/,                                     label:'المبيعات وخدمة العملاء'            },
    ];

    var results = [];
    for(var i = 0; i < map.length && results.length < 3; i++){
      if(map[i].re.test(all)) results.push(map[i].label);
    }
    return results;
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

    // Hard guard — hide immediately if not the active owner
    if(!_isOwnerActive()){
      card.style.display = 'none';
      var safeList = document.getElementById('scComplList');
      if(safeList) safeList.innerHTML = '';
      return;
    }

    // Dismissed this session — stay hidden
    if(_dismissed){ card.style.display = 'none'; return; }

    var pct      = _score();
    var color    = pct >= 80 ? '#22c55e' : pct >= 50 ? '#f59e0b' : '#f87171';
    var labelEl  = document.getElementById('scComplLabel');
    var pctEl    = document.getElementById('scComplPct');
    var fillEl   = document.getElementById('scComplFill');
    var togBtn   = document.getElementById('scComplToggle');
    var panelEl  = document.getElementById('scComplPanel');
    var listEl   = document.getElementById('scComplList');
    var suggestEl= document.getElementById('scComplSuggest');

    if(pctEl)  { pctEl.textContent = pct + '%'; pctEl.style.color = color; }
    if(fillEl) { fillEl.style.width = pct + '%'; fillEl.style.background = color; }

    if(pct >= 100){
      if(labelEl) labelEl.textContent = 'ملفك مكتمل 🎉';
      if(togBtn){
        togBtn.textContent = 'تم';
        togBtn.classList.add('is-done');
        togBtn.classList.remove('is-open');
      }
      if(panelEl) panelEl.style.display = 'none';
      return;
    }

    // Incomplete state — reset header labels
    if(labelEl) labelEl.textContent = 'اكتمال الملف';
    if(togBtn){
      togBtn.classList.remove('is-done');
      // Only reset button text if panel is currently closed
      if(!panelEl || panelEl.style.display === 'none'){
        togBtn.textContent = 'تفاصيل ▾';
        togBtn.classList.remove('is-open');
      }
    }

    // Don't rebuild list while panel is hidden — wait for user to open it
    if(!panelEl || panelEl.style.display === 'none') return;
    if(!listEl) return;

    var missing = [], done = [];
    for(var i = 0; i < _ITEMS.length; i++){
      (_isDone(_ITEMS[i].id) ? done : missing).push(_ITEMS[i]);
    }

    var html = '';
    for(var m = 0; m < missing.length; m++){
      var it = missing[m];
      html += '<button type="button" class="sc-compl-item missing" data-action="' + it.action + '">'
        + '<span class="sc-compl-ico sc-compl-ico-miss"></span>'
        + '<span class="sc-compl-label-text">' + it.label + '</span>'
        + (it.action !== 'none' ? '<span class="sc-compl-weight">+' + it.weight + '%</span>' : '')
        + '</button>';
    }
    for(var d = 0; d < done.length; d++){
      var it2 = done[d];
      html += '<button type="button" class="sc-compl-item done" disabled>'
        + '<span class="sc-compl-ico sc-compl-ico-done"></span>'
        + '<span class="sc-compl-label-text">' + it2.label + '</span>'
        + '</button>';
    }
    listEl.innerHTML = html;

    // Suggestions — rule-based, no API
    if(suggestEl){
      var suggs = _buildSuggestions();
      if(suggs.length){
        suggestEl.innerHTML = '<div class="sc-compl-suggest-title">اقتراحات تناسب تخصصك</div>'
          + '<div class="sc-compl-suggest-tags">'
          + suggs.map(function(s){ return '<span class="sc-compl-suggest-tag">' + s + '</span>'; }).join('')
          + '</div>';
        suggestEl.style.display = '';
      } else {
        suggestEl.style.display = 'none';
      }
    }
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

  // Toggle: open/close panel, or dismiss at 100% (owner-active guard)
  document.addEventListener('click', function(e){
    if(!e.target.closest('#scComplToggle')) return;
    if(!_isOwnerActive()) return;

    var togBtn  = document.getElementById('scComplToggle');
    var panelEl = document.getElementById('scComplPanel');
    var card    = document.getElementById('scComplCard');
    if(!togBtn) return;

    // "تم" at 100% — dismiss for this page session
    if(togBtn.classList.contains('is-done')){
      _dismissed = true;
      if(card) card.style.display = 'none';
      return;
    }

    if(!panelEl) return;
    var isOpen = panelEl.style.display !== 'none';
    if(isOpen){
      panelEl.style.display = 'none';
      togBtn.textContent = 'تفاصيل ▾';
      togBtn.classList.remove('is-open');
    } else {
      panelEl.style.display = '';
      togBtn.textContent = 'إخفاء ▴';
      togBtn.classList.add('is-open');
      _render();  // build list now that panel is visible
    }
  });
})();
