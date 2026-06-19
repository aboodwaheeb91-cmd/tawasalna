// profile-v2.completion.js — Compact Completion + Growth Strip (owner-only, Profile V2)
// Reads exclusively from window._scProfile — no localStorage, no DB field.
// Weights sum to 100. Call window._updateCompletion() after any profile save.
;(function(){
  'use strict';

  // Session-level dismiss — reset on page reload, no persistence
  var _dismissed  = false;
  var _growthIdx  = 0;

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

  // ── Growth Suggestions (rule-based, no API) ──────────────────────────────
  // Each rule: { id, text, reason, benefit, action }
  // Filtered out if the profile already satisfies the condition.
  function _buildGrowthSuggestions(){
    var p        = window._scProfile || {};
    var src      = [
      (p.title || ''),
      ((p.profession && (p.profession.name_ar || p.profession.name || '')) || ''),
      (p.bio || ''),
      (p.short_bio || ''),
    ].join(' ').toLowerCase();

    var skillStr = (p.skills || []).map(function(s){
      return (s.skill || s.name || '').toLowerCase();
    }).join(' ');

    var courseStr = (p.courses || []).map(function(c){
      return (c.title || '').toLowerCase();
    }).join(' ');

    var langStr = (p.langs || []).map(function(l){
      return (l.language || l.lang || '').toLowerCase();
    }).join(' ');

    var linkStr = (p.links || []).map(function(l){
      return (l.url || l.link_type || '').toLowerCase();
    }).join(' ');

    var expCount    = Array.isArray(p.experience) ? p.experience.length : 0;
    var courseCount = Array.isArray(p.courses)    ? p.courses.length    : 0;

    var _all = src + ' ' + skillStr;

    var rules = [
      {
        id:      'react',
        cond:    /javascript|frontend|html|css/.test(_all) && !/react/.test(skillStr),
        text:    'أضف مهارة React.js',
        reason:  'ملفك يشير إلى خلفية في تطوير الواجهات الأمامية ولكن React.js غير مضافة.',
        benefit: 'React من أكثر المهارات طلباً في وظائف الفرونت إند حالياً.',
        action:  'tab-skills',
      },
      {
        id:      'git',
        cond:    /developer|frontend|backend|تطوير/.test(_all) && !/git/.test(skillStr),
        text:    'أضف مهارة Git',
        reason:  'Git أساسي لأي مطوّر ولم يُذكر في مهاراتك.',
        benefit: 'يرفع مصداقية ملفك أمام المسؤولين عن التوظيف.',
        action:  'tab-skills',
      },
      {
        id:      'nodejs',
        cond:    /javascript|node|backend/.test(_all) && !/node/.test(skillStr),
        text:    'أضف مهارة Node.js',
        reason:  'خلفيتك في JavaScript تجعل Node.js إضافة طبيعية للملف.',
        benefit: 'يفتح لك فرص وظائف الـ Full Stack.',
        action:  'tab-skills',
      },
      {
        id:      'sql_course',
        cond:    /data|analyst|backend|erp/.test(_all) && !/sql/.test(courseStr) && !/sql/.test(skillStr),
        text:    'أضف دورة SQL أو تحليل البيانات',
        reason:  'تخصصك يستفيد كثيراً من احتراف قواعد البيانات.',
        benefit: 'مهارة SQL تزيد فرصك في وظائف التحليل بنسبة كبيرة.',
        action:  'tab-courses',
      },
      {
        id:      'github_link',
        cond:    /developer|مطور|frontend|backend/.test(_all) && !/github/.test(linkStr),
        text:    'أضف رابط GitHub الخاص بك',
        reason:  'لا يوجد رابط GitHub في روابط تواصلك حتى الآن.',
        benefit: 'يُبرز مشاريعك ويُقنع الشركات بمهاراتك التقنية.',
        action:  'tab-links',
      },
      {
        id:      'english',
        cond:    !/english|إنجليزي/.test(langStr),
        text:    'أضف شهادة لغة إنجليزية',
        reason:  'اللغة الإنجليزية غير مضافة إلى قسم اللغات في ملفك.',
        benefit: 'تفتح لك أبواب وظائف الشركات الدولية والعمل عن بُعد.',
        action:  'tab-langs',
      },
      {
        id:      'more_exp',
        cond:    expCount === 1,
        text:    'أضف تجربة عمل أو مشروع آخر',
        reason:  'ملفك يحتوي على خبرة واحدة فقط.',
        benefit: 'إضافة خبرة أو مشروع ثانٍ يُقوّي ملفك أمام أصحاب العمل.',
        action:  'tab-exp',
      },
      {
        id:      'python',
        cond:    /data|machine.?learn|ai|analytics/.test(_all) && !/python/.test(skillStr),
        text:    'أضف مهارة Python',
        reason:  'اهتمامك بمجال البيانات يجعل Python خطوة أساسية.',
        benefit: 'Python هي اللغة الأولى في علم البيانات والذكاء الاصطناعي.',
        action:  'tab-skills',
      },
      {
        id:      'php_course',
        cond:    /php|laravel|backend/.test(_all) && !/laravel/.test(courseStr),
        text:    'أضف دورة Laravel أو PHP المتقدم',
        reason:  'خلفيتك في PHP تستحق توثيق دورة تدريبية متخصصة.',
        benefit: 'يُثبت للشركات مستواك المتقدم في تطوير الخلفية.',
        action:  'tab-courses',
      },
      {
        id:      'first_course',
        cond:    courseCount === 0,
        text:    'أضف أول دورة تدريبية لك',
        reason:  'قسم الدورات في ملفك فارغ حتى الآن.',
        benefit: 'الدورات تُثري ملفك وتُظهر شغفك بالتطوير المهني.',
        action:  'tab-courses',
      },
    ];

    var results = [];
    for(var i = 0; i < rules.length; i++){
      if(rules[i].cond) results.push(rules[i]);
    }
    return results;
  }

  // ── Completion mode: rule-based topic tags ───────────────────────────────
  function _buildCompletionSuggestions(){
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

  // ── Growth mode rendering ────────────────────────────────────────────────
  function _renderGrowthMode(suggs){
    var rowEl    = document.getElementById('scGrowthRow');
    var textEl   = document.getElementById('scGrowthText');
    var panelEl  = document.getElementById('scGrowthPanel');
    var reasonEl = document.getElementById('scGrowthReason');
    var benefEl  = document.getElementById('scGrowthBenefit');
    var actionEl = document.getElementById('scGrowthAction');
    var detBtn   = document.getElementById('scGrowthDet');
    var complRow = document.getElementById('scComplRow');
    var complPnl = document.getElementById('scComplPanel');

    // Hide completion-mode elements
    if(complRow) complRow.style.display = 'none';
    if(complPnl) complPnl.style.display = 'none';

    if(!rowEl) return;

    if(!suggs || suggs.length === 0){
      // Empty state
      if(textEl) textEl.textContent = 'ملفك قوي! سنقترح لك فرص تطوير لاحقاً';
      var nextBtn = document.getElementById('scGrowthNext');
      var detBtnEl = document.getElementById('scGrowthDet');
      if(nextBtn) nextBtn.style.display = 'none';
      if(detBtnEl) detBtnEl.style.display = 'none';
      if(panelEl) panelEl.style.display = 'none';
      rowEl.style.display = '';
      return;
    }

    // Clamp index
    _growthIdx = _growthIdx % suggs.length;
    var sg = suggs[_growthIdx];

    if(textEl) textEl.textContent = sg.text;

    // Restore buttons
    var nextBtn2 = document.getElementById('scGrowthNext');
    if(nextBtn2) nextBtn2.style.display = suggs.length > 1 ? '' : 'none';
    if(detBtn) {
      detBtn.style.display = '';
    }

    // Update panel if open
    if(panelEl && panelEl.style.display !== 'none'){
      if(reasonEl) reasonEl.textContent = sg.reason;
      if(benefEl)  benefEl.textContent  = sg.benefit;
      if(actionEl){
        if(sg.action && sg.action !== 'none'){
          actionEl.textContent   = 'اذهب إلى القسم';
          actionEl.dataset.action = sg.action;
          actionEl.style.display  = '';
        } else {
          actionEl.style.display = 'none';
        }
      }
    }

    rowEl.style.display = '';
  }

  // ── Main render ──────────────────────────────────────────────────────────
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

    card.style.display = '';

    var pct = _score();

    // ── Growth mode (100%) ──────────────────────────────────────────────
    if(pct >= 100){
      var suggs = _buildGrowthSuggestions();
      _renderGrowthMode(suggs);
      return;
    }

    // ── Completion mode (< 100%) ────────────────────────────────────────
    // Hide growth row/panel
    var growthRow = document.getElementById('scGrowthRow');
    var growthPnl = document.getElementById('scGrowthPanel');
    if(growthRow) growthRow.style.display = 'none';
    if(growthPnl) growthPnl.style.display = 'none';

    // Show completion row
    var complRow = document.getElementById('scComplRow');
    if(complRow) complRow.style.display = '';

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

    if(labelEl) labelEl.textContent = 'اكتمال الملف';
    if(togBtn){
      togBtn.classList.remove('is-done');
      if(!panelEl || panelEl.style.display === 'none'){
        togBtn.textContent = 'تفاصيل ▾';
        togBtn.classList.remove('is-open');
      }
    }

    // Don't rebuild list while panel is hidden
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

    // Inline topic suggestions
    if(suggestEl){
      var compSuggs = _buildCompletionSuggestions();
      if(compSuggs.length){
        suggestEl.innerHTML = '<div class="sc-compl-suggest-title">اقتراحات تناسب تخصصك</div>'
          + '<div class="sc-compl-suggest-tags">'
          + compSuggs.map(function(s){ return '<span class="sc-compl-suggest-tag">' + s + '</span>'; }).join('')
          + '</div>';
        suggestEl.style.display = '';
      } else {
        suggestEl.style.display = 'none';
      }
    }
  }

  window._renderCompletion = _render;
  window._updateCompletion = _render;

  // ── Completion: item click ───────────────────────────────────────────────
  document.addEventListener('click', function(e){
    var item = e.target.closest('.sc-compl-item.missing');
    if(!item) return;
    if(!_isOwnerActive()) return;
    var act = item.getAttribute('data-action');
    if(act) _doAction(act);
  });

  // ── Completion: toggle panel ─────────────────────────────────────────────
  document.addEventListener('click', function(e){
    if(!e.target.closest('#scComplToggle')) return;
    if(!_isOwnerActive()) return;

    var togBtn  = document.getElementById('scComplToggle');
    var panelEl = document.getElementById('scComplPanel');
    if(!togBtn || !panelEl) return;

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

  // ── Growth: التالي ────────────────────────────────────────────────────────
  document.addEventListener('click', function(e){
    if(!e.target.closest('#scGrowthNext')) return;
    if(!_isOwnerActive()) return;
    var suggs = _buildGrowthSuggestions();
    if(!suggs.length) return;
    _growthIdx = (_growthIdx + 1) % suggs.length;
    // Close panel when cycling to next suggestion
    var panelEl = document.getElementById('scGrowthPanel');
    var detBtn  = document.getElementById('scGrowthDet');
    if(panelEl) panelEl.style.display = 'none';
    if(detBtn)  { detBtn.textContent = 'تفاصيل'; detBtn.classList.remove('is-open'); }
    _renderGrowthMode(suggs);
  });

  // ── Growth: تفاصيل toggle ─────────────────────────────────────────────────
  document.addEventListener('click', function(e){
    if(!e.target.closest('#scGrowthDet')) return;
    if(!_isOwnerActive()) return;
    var detBtn  = document.getElementById('scGrowthDet');
    var panelEl = document.getElementById('scGrowthPanel');
    var reasonEl= document.getElementById('scGrowthReason');
    var benefEl = document.getElementById('scGrowthBenefit');
    var actionEl= document.getElementById('scGrowthAction');
    if(!panelEl) return;

    var isOpen = panelEl.style.display !== 'none';
    if(isOpen){
      panelEl.style.display = 'none';
      if(detBtn){ detBtn.textContent = 'تفاصيل'; detBtn.classList.remove('is-open'); }
    } else {
      var suggs = _buildGrowthSuggestions();
      var sg = suggs.length ? suggs[_growthIdx % suggs.length] : null;
      if(sg){
        if(reasonEl) reasonEl.textContent = sg.reason;
        if(benefEl)  benefEl.textContent  = sg.benefit;
        if(actionEl){
          if(sg.action && sg.action !== 'none'){
            actionEl.textContent    = 'اذهب إلى القسم';
            actionEl.dataset.action = sg.action;
            actionEl.style.display  = '';
          } else {
            actionEl.style.display = 'none';
          }
        }
      }
      panelEl.style.display = '';
      if(detBtn){ detBtn.textContent = 'إخفاء ▴'; detBtn.classList.add('is-open'); }
    }
  });

  // ── Growth: action button click ───────────────────────────────────────────
  document.addEventListener('click', function(e){
    var btn = e.target.closest('#scGrowthAction');
    if(!btn) return;
    if(!_isOwnerActive()) return;
    var act = btn.dataset.action;
    if(act) _doAction(act);
  });

  // ── Growth: إخفاء (dismiss for session) ──────────────────────────────────
  document.addEventListener('click', function(e){
    if(!e.target.closest('#scGrowthHide')) return;
    if(!_isOwnerActive()) return;
    _dismissed = true;
    var card = document.getElementById('scComplCard');
    if(card) card.style.display = 'none';
  });
})();
