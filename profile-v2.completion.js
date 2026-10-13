// profile-v2.completion.js — Compact Completion + Growth Strip (owner-only, Profile V2)
// Score + checklist come ONLY from the server — GET /profile/{id}/score (PR 4.2a · F29):
// one definition (PROFILE_SCORE_ITEMS in server.py) shared with Home and the stats tile.
// This file maps item ids → label (twT) + UI action; it never recomputes the score.
// Call window._updateCompletion() after any profile save (re-fetches the score).
;(function(){
  'use strict';

  // Session-level state — all reset on page reload, no persistence
  var _dismissed   = false;
  var _growthIdx   = 0;
  var _toastTimer  = null;
  var _server      = null;   // last {score, items:[{id, done, points}]} from /score
  var _scoreGen    = 0;      // drops stale /score responses

  // id (server) → UI action. Labels: twT('profile.compl.item.<id>').
  var _ACTIONS = {
    avatar:'avatar', profession:'edit-modal', bio:'edit-modal', short_bio:'edit-modal',
    location:'edit-modal', avail:'avail-dot', exp:'tab-exp', edu:'tab-edu', skills:'tab-skills',
    courses:'tab-courses', langs:'tab-langs', links:'tab-links', verified:'verify'
  };

  // Returns true only when viewing as authenticated owner outside any preview mode
  function _isOwnerActive(){
    if(window._scViewerType !== 'owner') return false;
    var b = document.body;
    if(b.classList.contains('preview-public-user')) return false;
    if(b.classList.contains('preview-guest'))       return false;
    return true;
  }

  function _items(){
    return (_server && Array.isArray(_server.items)) ? _server.items : [];
  }

  function _score(){
    var n = _server ? Number(_server.score) : NaN;
    return isFinite(n) ? Math.max(0, Math.min(100, Math.round(n))) : null;
  }

  // ── Growth Suggestions (rule-based, no API) ──────────────────────────────
  // Each rule: { id, text, toast, reason, benefit, action }
  // text  — short ethical framing (learn first, then document)
  // toast — 3-4 sentence explanation shown on suggestion-text click
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
        // Triggers for front-end profiles (AR+EN); disappears when React is in skills
        cond:    /javascript|frontend|html|css|واجهات|واجهة|فرونت/.test(_all) && !/react/.test(skillStr),
        text:    'احصل على دورة React.js ثم أضفها لملفك',
        // toast — short actionable tip (1 sentence); shown on suggestion-text click
        toast:   'ابحث عن دورة React.js وبعد ما تنتهي منها أضف المهارة لقسم مهاراتك.',
        // reason + benefit — full explanation shown only in the "تفاصيل" panel
        reason:  'React هي المكتبة الأكثر طلباً في وظائف الفرونت إند حالياً، وخلفيتك في JavaScript تجعلها الخطوة التالية الطبيعية.',
        benefit: 'إضافتها بعد تعلمها يُظهر للشركات أنك متطوّر ويفتح أمامك وظائف الفرونت إند المتقدمة.',
        action:  'tab-skills',
      },
      {
        id:      'git',
        // Triggers for any developer profile (AR+EN); disappears when Git is in skills
        cond:    /developer|frontend|backend|تطوير|مطور|برمجيات|برمجة/.test(_all) && !/git/.test(skillStr),
        text:    'تعلّم Git ثم وثّقه ضمن مهاراتك',
        toast:   'ابدأ باستخدام Git في مشاريعك وبعد ما تتقنه وثّقه ضمن مهاراتك.',
        reason:  'Git هو معيار إدارة الكود في جميع فرق التطوير، وغيابه من ملفك يُثير تساؤلات عند المراجعين.',
        benefit: 'توثيقه بعد الاستخدام الفعلي يُثبت قدرتك على العمل ضمن فريق بشكل احترافي.',
        action:  'tab-skills',
      },
      {
        id:      'nodejs',
        // Triggers for JS/backend profiles; disappears when Node is in skills
        cond:    /javascript|node|backend|خلفية|باك.?اند/.test(_all) && !/node/.test(skillStr),
        text:    'تعلّم Node.js ثم أضفه لمهاراتك',
        toast:   'ابحث عن دورة Node.js وبعد ما تطبّقه في مشروع أضفه لقسم مهاراتك.',
        reason:  'Node.js يُكمل خلفيتك في JavaScript ويُمكّنك من بناء تطبيقات متكاملة من الفرونت للباك إند.',
        benefit: 'إضافته بعد التعلم يرفع قيمتك في سوق العمل ويفتح أمامك وظائف Full Stack.',
        action:  'tab-skills',
      },
      {
        id:      'sql_course',
        // Triggers when profile has SQL/data context OR SQL as a skill but no documented SQL course.
        // SQL in skills WITHOUT a course is a stronger reason to suggest the course, not suppress it.
        cond:    (/data|analyst|backend|erp|بيانات|قواعد.?بيانات|تحليل/.test(_all) || /sql/.test(skillStr))
                 && !/sql|database|قواعد/.test(courseStr),
        text:    'احصل على دورة SQL أو قواعد البيانات ثم أضفها لملفك',
        toast:   'ابحث عن دورة SQL أو قواعد البيانات وبعد الحصول عليها أضفها لقسم الدورات.',
        reason:  'لديك مهارة أو خلفية في البيانات، لكن دورة موثقة تُثبتها رسمياً أمام أصحاب العمل.',
        benefit: 'الدورة تُكمل ما تُظهره مهاراتك وتفتح أمامك وظائف التحليل والـ Backend بشكل أقوى.',
        action:  'tab-courses',
      },
      {
        id:      'github_link',
        // Triggers for developer profiles (AR+EN); disappears when GitHub link is added
        cond:    /developer|frontend|backend|مطور|برمجيات|برمجة/.test(_all) && !/github/.test(linkStr),
        text:    'أنشئ أو حدّث GitHub ثم أضف رابطه لملفك',
        toast:   'أنشئ أو حدّث GitHub وبعدها أضف رابطه لقسم روابط التواصل.',
        reason:  'رابط GitHub يُبرز عملك الفعلي ويُقدّم دليلاً ملموساً على مهاراتك أكثر من أي وصف نصي.',
        benefit: 'الشركات التقنية تبحث عن رابط GitHub قبل أي شيء آخر في ملف المطوّرين.',
        action:  'tab-links',
      },
      {
        id:      'english',
        // Suggests developing and adding English. Disappears once English appears in langs section.
        cond:    !/english|إنجليزي|الإنجليزية/.test(langStr),
        text:    'طوّر لغتك الإنجليزية ثم أضف مستواك للملف',
        toast:   'طوّر لغتك الإنجليزية وبعد ما تحسّن مستواك أضفه لقسم اللغات.',
        reason:  'اللغة الإنجليزية غير موجودة في قسم اللغات، وهي مؤشر مهم للشركات الدولية.',
        benefit: 'إضافتها بعد تطوير مستواك تفتح أمامك وظائف الشركات الدولية والعمل عن بُعد بأجور أعلى.',
        action:  'tab-langs',
      },
      {
        id:      'more_exp',
        cond:    expCount === 1,
        text:    'نفّذ مشروعاً عملياً أو وثّق تجربة حقيقية في ملفك',
        toast:   'نفّذ مشروعاً عملياً أو تطوعياً وبعدها وثّقه في قسم الخبرات.',
        reason:  'الملف الذي يحتوي خبرة واحدة يبدو في بداية المسيرة، حتى لو كانت التجربة قوية.',
        benefit: 'إضافة تجربة أو مشروع ثانٍ — حتى لو شخصي — يُظهر النمو المهني والتنوع.',
        action:  'tab-exp',
      },
      {
        id:      'python',
        // Triggers for data/AI profiles (AR+EN); disappears when Python is in skills
        cond:    /data|machine.?learn|ai|analytics|بيانات|تحليل.?بيانات|ذكاء.?اصطناعي/.test(_all) && !/python/.test(skillStr),
        text:    'تعلّم Python ثم أضفه لمهاراتك',
        toast:   'ابحث عن دورة Python وبعد ما تنتهي منها وتطبّق ما تعلمته أضفها لقسم مهاراتك.',
        reason:  'Python هي اللغة الأساسية في علم البيانات والذكاء الاصطناعي، واهتمامك بهذا المجال يجعلها ضرورية.',
        benefit: 'تعلّمها وتوثيقها يُقوّي ملفك في وظائف تحليل البيانات والـ AI.',
        action:  'tab-skills',
      },
      {
        id:      'php_course',
        // Triggers for PHP/backend profiles; disappears when a Laravel course is added
        cond:    /php|laravel|backend|خلفية|باك.?اند/.test(_all) && !/laravel/.test(courseStr),
        text:    'احصل على دورة Laravel أو PHP المتقدم ثم أضفها لملفك',
        toast:   'ابحث عن دورة Laravel أو PHP المتقدم وبعد الحصول عليها أضفها لقسم الدورات.',
        reason:  'المهارة بدون دورة موثقة تبقى غير رسمية في نظر كثير من أصحاب العمل.',
        benefit: 'الدورة تُثبت مستواك المتقدم وتُميّزك عن مطوري PHP الذين لم يوثّقوا تدريبهم.',
        action:  'tab-courses',
      },
      {
        id:      'first_course',
        cond:    courseCount === 0,
        text:    'أتمّ دورة تدريبية ثم أضفها لملفك',
        toast:   'ابحث عن دورة في مجالك وبعد ما تتمّها أضفها لقسم الدورات.',
        reason:  'قسم الدورات الفارغ يُشير إلى عدم الاستثمار في التعلم الذاتي، حتى لو كنت تتعلم فعلياً.',
        benefit: 'دورة واحدة مكتملة تُظهر التزامك بالتطوير المهني المستمر وتُثري ملفك.',
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

  // Show toast message for 4 s; clicking the suggestion text triggers this
  function _showToast(msg){
    var el = document.getElementById('scGrowthToast');
    if(!el) return;
    if(_toastTimer){ clearTimeout(_toastTimer); _toastTimer = null; }
    el.textContent = msg;
    el.style.display = '';
    _toastTimer = setTimeout(function(){
      el.style.display = 'none';
      _toastTimer = null;
    }, 4000);
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
    if(action === 'verify'){   // identity verification (KYC) lives in settings
      location.href = '/settings';
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
      if(textEl) textEl.textContent = twT('profile.compl.growth_empty');
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

    var pct = _score();
    if(pct === null){ card.style.display = 'none'; return; }   // no server score yet / failed
    card.style.display = '';

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

    if(labelEl) labelEl.textContent = twT('profile.compl.title');
    if(togBtn){
      togBtn.classList.remove('is-done');
      if(!panelEl || panelEl.style.display === 'none'){
        togBtn.textContent = twT('profile.compl.details') + ' ▾';
        togBtn.classList.remove('is-open');
      }
    }

    // Don't rebuild list while panel is hidden
    if(!panelEl || panelEl.style.display === 'none') return;
    if(!listEl) return;

    var missing = [], done = [], all = _items();
    for(var i = 0; i < all.length; i++){
      if(!Object.prototype.hasOwnProperty.call(_ACTIONS, all[i].id)) continue;   // unknown id → skip
      (all[i].done ? done : missing).push(all[i]);
    }

    var html = '';
    for(var m = 0; m < missing.length; m++){
      var it = missing[m];
      html += '<button type="button" class="sc-compl-item missing" data-action="' + twEscAttr(_ACTIONS[it.id]) + '">'
        + '<span class="sc-compl-ico sc-compl-ico-miss"></span>'
        + '<span class="sc-compl-label-text">' + twEscHtml(twT('profile.compl.item.' + it.id)) + '</span>'
        + '<span class="sc-compl-weight">+' + (Number(it.points) || 0) + '%</span>'
        + '</button>';
    }
    for(var d = 0; d < done.length; d++){
      html += '<button type="button" class="sc-compl-item done" disabled>'
        + '<span class="sc-compl-ico sc-compl-ico-done"></span>'
        + '<span class="sc-compl-label-text">' + twEscHtml(twT('profile.compl.item.' + done[d].id)) + '</span>'
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

  // Fetch the canonical score (GET /profile/{id}/score) → stats tile + card. Every caller
  // (renderProfile + each section save) goes through here; stale responses are dropped.
  function _refresh(){
    var uid = window._scUserId;
    if(uid == null || typeof window.getScore !== 'function') return;
    var gen = ++_scoreGen;
    window.getScore(uid).then(function(sc){
      if(gen !== _scoreGen || String(uid) !== String(window._scUserId)) return;
      if(sc && typeof sc.score === 'number'){
        _server = sc;
        var tile = document.getElementById('scStatScore');
        if(tile) tile.textContent = String(sc.score);
        if(window._scProfile) window._scProfile.score = sc.score;
      }
      _render();
    });
  }

  window._renderCompletion = _render;
  window._updateCompletion = _refresh;

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
      togBtn.textContent = twT('profile.compl.details') + ' ▾';
      togBtn.classList.remove('is-open');
    } else {
      panelEl.style.display = '';
      togBtn.textContent = twT('profile.compl.hide') + ' ▴';
      togBtn.classList.add('is-open');
      _render();  // build list now that panel is visible
    }
  });

  // ── Growth: suggestion text click → toast ────────────────────────────────
  document.addEventListener('click', function(e){
    var tgt = e.target.closest('#scGrowthText');
    if(!tgt) return;
    if(!_isOwnerActive()) return;
    var suggs = _buildGrowthSuggestions();
    if(!suggs.length) return;
    var sg = suggs[_growthIdx % suggs.length];
    if(sg && sg.toast) _showToast(sg.toast);
  });

  // ── Growth: التالي ────────────────────────────────────────────────────────
  document.addEventListener('click', function(e){
    if(!e.target.closest('#scGrowthNext')) return;
    if(!_isOwnerActive()) return;
    var suggs = _buildGrowthSuggestions();
    if(!suggs.length) return;
    _growthIdx = (_growthIdx + 1) % suggs.length;
    // Close panel and toast when cycling to next suggestion
    var panelEl   = document.getElementById('scGrowthPanel');
    var detBtn    = document.getElementById('scGrowthDet');
    var toastEl   = document.getElementById('scGrowthToast');
    if(panelEl)  panelEl.style.display = 'none';
    if(detBtn)   { detBtn.textContent = 'تفاصيل'; detBtn.classList.remove('is-open'); }
    if(toastEl)  toastEl.style.display = 'none';
    if(_toastTimer){ clearTimeout(_toastTimer); _toastTimer = null; }
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
