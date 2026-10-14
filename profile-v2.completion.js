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
        text:    twT('profile.growth.react.text'),
        // toast — short actionable tip (1 sentence); shown on suggestion-text click
        toast:   twT('profile.growth.react.toast'),
        // reason + benefit — full explanation shown only in the "تفاصيل" panel
        reason:  twT('profile.growth.react.reason'),
        benefit: twT('profile.growth.react.benefit'),
        action:  'tab-skills',
      },
      {
        id:      'git',
        // Triggers for any developer profile (AR+EN); disappears when Git is in skills
        cond:    /developer|frontend|backend|تطوير|مطور|برمجيات|برمجة/.test(_all) && !/git/.test(skillStr),
        text:    twT('profile.growth.git.text'),
        toast:   twT('profile.growth.git.toast'),
        reason:  twT('profile.growth.git.reason'),
        benefit: twT('profile.growth.git.benefit'),
        action:  'tab-skills',
      },
      {
        id:      'nodejs',
        // Triggers for JS/backend profiles; disappears when Node is in skills
        cond:    /javascript|node|backend|خلفية|باك.?اند/.test(_all) && !/node/.test(skillStr),
        text:    twT('profile.growth.nodejs.text'),
        toast:   twT('profile.growth.nodejs.toast'),
        reason:  twT('profile.growth.nodejs.reason'),
        benefit: twT('profile.growth.nodejs.benefit'),
        action:  'tab-skills',
      },
      {
        id:      'sql_course',
        // Triggers when profile has SQL/data context OR SQL as a skill but no documented SQL course.
        // SQL in skills WITHOUT a course is a stronger reason to suggest the course, not suppress it.
        cond:    (/data|analyst|backend|erp|بيانات|قواعد.?بيانات|تحليل/.test(_all) || /sql/.test(skillStr))
                 && !/sql|database|قواعد/.test(courseStr),
        text:    twT('profile.growth.sql_course.text'),
        toast:   twT('profile.growth.sql_course.toast'),
        reason:  twT('profile.growth.sql_course.reason'),
        benefit: twT('profile.growth.sql_course.benefit'),
        action:  'tab-courses',
      },
      {
        id:      'github_link',
        // Triggers for developer profiles (AR+EN); disappears when GitHub link is added
        cond:    /developer|frontend|backend|مطور|برمجيات|برمجة/.test(_all) && !/github/.test(linkStr),
        text:    twT('profile.growth.github_link.text'),
        toast:   twT('profile.growth.github_link.toast'),
        reason:  twT('profile.growth.github_link.reason'),
        benefit: twT('profile.growth.github_link.benefit'),
        action:  'tab-links',
      },
      {
        id:      'english',
        // Suggests developing and adding English. Disappears once English appears in langs section.
        cond:    !/english|إنجليزي|الإنجليزية/.test(langStr),
        text:    twT('profile.growth.english.text'),
        toast:   twT('profile.growth.english.toast'),
        reason:  twT('profile.growth.english.reason'),
        benefit: twT('profile.growth.english.benefit'),
        action:  'tab-langs',
      },
      {
        id:      'more_exp',
        cond:    expCount === 1,
        text:    twT('profile.growth.more_exp.text'),
        toast:   twT('profile.growth.more_exp.toast'),
        reason:  twT('profile.growth.more_exp.reason'),
        benefit: twT('profile.growth.more_exp.benefit'),
        action:  'tab-exp',
      },
      {
        id:      'python',
        // Triggers for data/AI profiles (AR+EN); disappears when Python is in skills
        cond:    /data|machine.?learn|ai|analytics|بيانات|تحليل.?بيانات|ذكاء.?اصطناعي/.test(_all) && !/python/.test(skillStr),
        text:    twT('profile.growth.python.text'),
        toast:   twT('profile.growth.python.toast'),
        reason:  twT('profile.growth.python.reason'),
        benefit: twT('profile.growth.python.benefit'),
        action:  'tab-skills',
      },
      {
        id:      'php_course',
        // Triggers for PHP/backend profiles; disappears when a Laravel course is added
        cond:    /php|laravel|backend|خلفية|باك.?اند/.test(_all) && !/laravel/.test(courseStr),
        text:    twT('profile.growth.php_course.text'),
        toast:   twT('profile.growth.php_course.toast'),
        reason:  twT('profile.growth.php_course.reason'),
        benefit: twT('profile.growth.php_course.benefit'),
        action:  'tab-courses',
      },
      {
        id:      'first_course',
        cond:    courseCount === 0,
        text:    twT('profile.growth.first_course.text'),
        toast:   twT('profile.growth.first_course.toast'),
        reason:  twT('profile.growth.first_course.reason'),
        benefit: twT('profile.growth.first_course.benefit'),
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
      { re:/javascript|react|vue|angular|frontend|html|css|node|typescript/,  label:twT('profile.growth.topic.frontend') },
      { re:/python|django|fastapi|backend|laravel|php|api|java|spring/,        label:twT('profile.growth.topic.backend') },
      { re:/data|machine.?learn|ai|analytics|power.?bi|tensorflow|pandas/,     label:twT('profile.growth.topic.data_ai') },
      { re:/تسويق|marketing|seo|social.?media|content|google.?ads/,            label:twT('profile.growth.topic.marketing') },
      { re:/design|ui|ux|figma|photoshop|illustrator|تصميم/,                   label:twT('profile.growth.topic.design') },
      { re:/project|management|agile|scrum|pmp|إدارة.?مشاريع/,                 label:twT('profile.growth.topic.pm') },
      { re:/accounting|finance|excel|محاسبة|مالية|erp|sap/,                    label:twT('profile.growth.topic.finance') },
      { re:/sales|مبيعات|crm|negotiation/,                                     label:twT('profile.growth.topic.sales') },
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
          actionEl.textContent   = twT('profile.growth.go_section');
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

    var color    = pct >= 80 ? 'var(--color-status-success-strong)' : pct >= 50 ? 'var(--color-status-warning-strong)' : 'var(--color-status-danger)';
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
        suggestEl.innerHTML = '<div class="sc-compl-suggest-title">' + twEscHtml(twT('profile.growth.suggest_title')) + '</div>'
          + '<div class="sc-compl-suggest-tags">'
          + compSuggs.map(function(s){ return '<span class="sc-compl-suggest-tag">' + twEscHtml(s) + '</span>'; }).join('')
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
    if(detBtn)   { detBtn.textContent = twT('profile.compl.details'); detBtn.classList.remove('is-open'); }
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
      if(detBtn){ detBtn.textContent = twT('profile.compl.details'); detBtn.classList.remove('is-open'); }
    } else {
      var suggs = _buildGrowthSuggestions();
      var sg = suggs.length ? suggs[_growthIdx % suggs.length] : null;
      if(sg){
        if(reasonEl) reasonEl.textContent = sg.reason;
        if(benefEl)  benefEl.textContent  = sg.benefit;
        if(actionEl){
          if(sg.action && sg.action !== 'none'){
            actionEl.textContent    = twT('profile.growth.go_section');
            actionEl.dataset.action = sg.action;
            actionEl.style.display  = '';
          } else {
            actionEl.style.display = 'none';
          }
        }
      }
      panelEl.style.display = '';
      if(detBtn){ detBtn.textContent = twT('profile.compl.hide') + ' ▴'; detBtn.classList.add('is-open'); }
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
