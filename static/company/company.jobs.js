// company.jobs.js — job apply, post job, event binding, rating interactions
// Load order: 5th (after render)
(function () {
  'use strict';

  var isRateLoading = false;

  // ── Apply ──────────────────────────────────────────────────────
  function _applyJob(btn, jobId) {
    if (!jobId) return;
    if (!window._jwt || !_jwt()) { window.location.href = '/'; return; }
    var origText = btn.textContent;
    btn.disabled = true; btn.textContent = 'جاري...';
    fetch('/jobs/' + jobId + '/apply', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + _jwt() },
      body:    JSON.stringify({ cover_letter: '' }),
    })
    .then(function (r) { return r.json(); })
    .then(function (data) {
      btn.textContent = data.already_applied ? '✓ قدّمت مسبقاً' : '✓ تم التقديم';
      btn.classList.add('applied');
    })
    .catch(function () {
      btn.disabled = false; btn.textContent = origText;
    });
  }

  // onclick wrapper — used by hardcoded cards in HTML before dynamic render
  function applyJob(btn) {
    var card  = btn.closest('[data-jid]');
    var jobId = card ? card.dataset.jid : (btn.getAttribute('data-jobid') || '');
    _applyJob(btn, jobId);
  }

  // ── Event binding (idempotent) ─────────────────────────────────
  function bindEvents() {
    var jobsList = document.getElementById('jobsList');
    if (jobsList && !jobsList.dataset.bound) {
      jobsList.dataset.bound = '1';
      jobsList.addEventListener('click', function (e) {
        var card = e.target.closest('[data-jid]');
        if (!card) return;
        if (e.target.classList.contains('apply-btn') || e.target.classList.contains('apply-btn-pill')) {
          e.stopPropagation();
          _applyJob(e.target, card.dataset.jid);
          return;
        }
        window.location.href = 'job-detail.html?id=' + card.dataset.jid;
      });
    }
    if (window.bindRateStars) bindRateStars();
  }

  // ── Rating ────────────────────────────────────────────────────
  function bindRateStars() {
    var box = document.getElementById('rateStars');
    if (!box || box.dataset.bound) return;
    box.dataset.bound = '1';
    box.addEventListener('click', function (e) {
      var span = e.target.closest('span[data-score]');
      if (!span) return;
      submitRating(parseInt(span.getAttribute('data-score')));
    });
  }

  function submitRating(score) {
    if (!window._jwt || !_jwt()) { window.location.href = '/'; return; }
    if (!window.companyState) return;
    if (isRateLoading) return;

    var companyId = new URLSearchParams(location.search).get('id');
    if (!companyId) return;

    var prevMine  = companyState.permissions.my_rating;
    var prevAvg   = companyState.stats.rating_avg;
    var prevCount = companyState.stats.rating_count || 0;

    companyState.permissions.my_rating = score;
    if (window._paintRateStars) _paintRateStars(score);

    isRateLoading = true;
    fetch('/company/rate/' + companyId, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + _jwt() },
      body:    JSON.stringify({ score: score }),
    })
    .then(function (r) {
      if (!r.ok) throw new Error('rate failed: ' + r.status);
      return r.json();
    })
    .then(function (data) {
      if (typeof data.rating_avg === 'number' || data.rating_avg === null)
        companyState.stats.rating_avg = data.rating_avg;
      if (typeof data.rating_count === 'number')
        companyState.stats.rating_count = data.rating_count;
      if (typeof data.my_score === 'number')
        companyState.permissions.my_rating = data.my_score;
      if (window.renderRating) renderRating();
      if (window.showToast) showToast('تم حفظ تقييمك ✓');
    })
    .catch(function () {
      companyState.permissions.my_rating = prevMine;
      companyState.stats.rating_avg      = prevAvg;
      companyState.stats.rating_count    = prevCount;
      if (window.renderRating) renderRating();
      if (window.showToast) showToast('تعذّر حفظ التقييم', 'error');
    })
    .finally(function () { isRateLoading = false; });
  }

  // ── Post job helpers ───────────────────────────────────────────

  // XSS-safe escape for use in innerHTML
  function _esc(s) {
    return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }

  // ── Profession picker ──────────────────────────────────────────
  var _professions = [];

  function _rebuildProfSelect() {
    var sel = document.getElementById('j-prof');
    if (!sel) return;
    var groups = {}, order = [];
    _professions.forEach(function(p) {
      var g = p.category_group || 'عام';
      if (!groups[g]) { groups[g] = []; order.push(g); }
      groups[g].push(p);
    });
    var html = '<option value="">— اختر التخصص —</option>';
    order.forEach(function(g) {
      html += '<optgroup label="' + _esc(g) + '">';
      groups[g].forEach(function(p) {
        html += '<option value="' + _esc(String(p.id)) + '">' + _esc(p.name_ar || p.name_en || '') + '</option>';
      });
      html += '</optgroup>';
    });
    sel.innerHTML = html;
    if (window.scSelectInit) scSelectInit();
  }

  function _loadProfessions() {
    var sel = document.getElementById('j-prof');
    if (!sel) return;
    if (_professions.length) { _rebuildProfSelect(); return; }
    fetch('/professions', { headers: { 'Authorization': 'Bearer ' + _jwt() } })
      .then(function(r) { return r.json(); })
      .then(function(data) {
        _professions = Array.isArray(data) ? data : (data.professions || []);
        _rebuildProfSelect();
      })
      .catch(function() {
        if (sel) sel.innerHTML = '<option value="">— تعذر التحميل —</option>';
      });
  }

  // ── Skill chips ────────────────────────────────────────────────
  var _jSkills     = [];
  var _jDropRes    = [];
  var _jACBound    = false;

  function _jRenderChips() {
    var box = document.getElementById('j-skill-chips');
    if (!box) return;
    if (!_jSkills.length) { box.innerHTML = ''; return; }
    var html = '';
    _jSkills.forEach(function(name) {
      var icon = (window.TW && TW.getSkillIcon) ? TW.getSkillIcon(name) : 'circle-check';
      html += '<span class="j-skill-chip">'
        + '<i data-lucide="' + _esc(icon) + '" class="j-chip-ic"></i>'
        + _esc(name)
        + '<button type="button" class="j-skill-chip-del" data-skill="' + _esc(name) + '" aria-label="حذف">×</button>'
        + '</span>';
    });
    box.innerHTML = html;
    if (window.lucide && lucide.createIcons) lucide.createIcons({ nodes: [box] });
    var dels = box.querySelectorAll('.j-skill-chip-del');
    for (var k = 0; k < dels.length; k++) {
      (function(btn) {
        btn.addEventListener('click', function(e) {
          e.stopPropagation();
          _jRemoveSkill(btn.getAttribute('data-skill'));
        });
      })(dels[k]);
    }
  }

  function _jAddSkill(raw) {
    var name = (window.TW && TW.normalizeSkill) ? TW.normalizeSkill(raw) : (raw || '').trim();
    if (!name || name.length < 2) return;
    var nl = name.toLowerCase();
    for (var i = 0; i < _jSkills.length; i++) {
      if (_jSkills[i].toLowerCase() === nl) return;
    }
    if (_jSkills.length >= 15) {
      if (window.showToast) showToast('الحد الأقصى 15 مهارة');
      return;
    }
    _jSkills.push(name);
    _jRenderChips();
    var inp = document.getElementById('j-skill-inp');
    if (inp) inp.value = '';
  }

  function _jRemoveSkill(name) {
    var nl = name.toLowerCase();
    _jSkills = _jSkills.filter(function(s) { return s.toLowerCase() !== nl; });
    _jRenderChips();
  }

  function _jShowDrop(results) {
    var drop = document.getElementById('j-skill-drop');
    if (!drop) return;
    _jDropRes = results;
    if (!results.length) { _jHideDrop(); return; }
    var html = '';
    results.forEach(function(s, i) {
      html += '<div class="j-skill-drop-item" data-idx="' + i + '">'
        + '<i data-lucide="' + _esc(s.icon || 'circle-check') + '" class="j-drop-ic"></i>'
        + '<span class="j-drop-en">' + _esc(s.en) + '</span>'
        + (s.ar !== s.en ? '<span class="j-drop-ar">' + _esc(s.ar) + '</span>' : '')
        + '</div>';
    });
    drop.innerHTML = html;
    drop.style.display = 'block';
    if (window.lucide && lucide.createIcons) lucide.createIcons({ nodes: [drop] });
    var items = drop.querySelectorAll('.j-skill-drop-item');
    for (var j = 0; j < items.length; j++) {
      (function(item, res) {
        item.addEventListener('mousedown', function(e) {
          e.preventDefault();
          _jAddSkill(res.en);
          _jHideDrop();
        });
      })(items[j], results[j]);
    }
  }

  function _jHideDrop() {
    var drop = document.getElementById('j-skill-drop');
    if (drop) { drop.style.display = 'none'; drop.innerHTML = ''; }
    _jDropRes = [];
  }

  function _jBindSkillAC() {
    if (_jACBound) return;
    _jACBound = true;
    var inp = document.getElementById('j-skill-inp');
    if (!inp) return;
    inp.addEventListener('input', function() {
      var q = inp.value.trim();
      if (!q) { _jHideDrop(); return; }
      var res = (window.TW && TW.searchSkills) ? TW.searchSkills(q, 7) : [];
      _jShowDrop(res);
    });
    inp.addEventListener('keydown', function(e) {
      if (e.key === 'Enter') {
        e.preventDefault();
        var q = inp.value.trim();
        if (q) { _jAddSkill(q); _jHideDrop(); }
      } else if (e.key === 'Escape') {
        _jHideDrop();
      }
    });
    inp.addEventListener('blur', function() { setTimeout(_jHideDrop, 180); });
  }

  // ── Accepted professions chips ─────────────────────────────────
  var _jAccProfs   = [];   // [{id, name_ar, name_en, icon}]
  var _jAccBound   = false;

  function _jAccRenderChips() {
    var box = document.getElementById('j-acc-prof-chips');
    if (!box) return;
    if (!_jAccProfs.length) { box.innerHTML = ''; return; }
    var html = '';
    _jAccProfs.forEach(function(p) {
      html += '<span class="j-skill-chip">'
        + '<i data-lucide="' + _esc(p.icon || 'briefcase') + '" class="j-chip-ic"></i>'
        + _esc(p.name_ar || p.name_en || '')
        + '<button type="button" class="j-skill-chip-del" data-id="' + _esc(String(p.id)) + '" aria-label="حذف">×</button>'
        + '</span>';
    });
    box.innerHTML = html;
    if (window.lucide && lucide.createIcons) lucide.createIcons({ nodes: [box] });
    var dels = box.querySelectorAll('.j-skill-chip-del');
    for (var k = 0; k < dels.length; k++) {
      (function(btn) {
        btn.addEventListener('click', function(e) {
          e.stopPropagation();
          _jAccRemoveProf(parseInt(btn.getAttribute('data-id'), 10));
        });
      })(dels[k]);
    }
  }

  function _jAccAddProf(prof) {
    if (!prof || !prof.id) return;
    // Can't duplicate
    for (var i = 0; i < _jAccProfs.length; i++) {
      if (_jAccProfs[i].id === prof.id) return;
    }
    // Can't be same as primary profession
    var primSel = document.getElementById('j-prof');
    if (primSel && parseInt(primSel.value, 10) === prof.id) {
      if (window.showToast) showToast('هذا هو التخصص الرئيسي بالفعل');
      return;
    }
    if (_jAccProfs.length >= 5) {
      if (window.showToast) showToast('الحد الأقصى 5 تخصصات إضافية');
      return;
    }
    _jAccProfs.push(prof);
    _jAccRenderChips();
    var inp = document.getElementById('j-acc-prof-inp');
    if (inp) inp.value = '';
  }

  function _jAccRemoveProf(id) {
    _jAccProfs = _jAccProfs.filter(function(p) { return p.id !== id; });
    _jAccRenderChips();
  }

  function _jAccShowDrop(query) {
    var drop = document.getElementById('j-acc-prof-drop');
    if (!drop) return;
    var q = (query || '').trim().toLowerCase();
    var primId = parseInt((document.getElementById('j-prof') || {}).value, 10) || 0;
    var alreadyIds = {};
    _jAccProfs.forEach(function(p) { alreadyIds[p.id] = true; });
    var results = _professions.filter(function(p) {
      if (p.id === primId || alreadyIds[p.id]) return false;
      if (!q) return true;
      return (p.name_ar || '').indexOf(q) !== -1 ||
             (p.name_en || '').toLowerCase().indexOf(q) !== -1;
    }).slice(0, 8);
    if (!results.length) { drop.style.display = 'none'; drop.innerHTML = ''; return; }
    var html = '';
    results.forEach(function(p, i) {
      html += '<div class="j-skill-drop-item" data-idx="' + i + '">'
        + '<i data-lucide="' + _esc(p.icon || 'briefcase') + '" class="j-drop-ic"></i>'
        + '<span class="j-drop-ar">' + _esc(p.name_ar || p.name_en || '') + '</span>'
        + '</div>';
    });
    drop.innerHTML = html;
    drop.style.display = 'block';
    if (window.lucide && lucide.createIcons) lucide.createIcons({ nodes: [drop] });
    var items = drop.querySelectorAll('.j-skill-drop-item');
    for (var j = 0; j < items.length; j++) {
      (function(item, prof) {
        item.addEventListener('mousedown', function(e) {
          e.preventDefault();
          _jAccAddProf(prof);
          drop.style.display = 'none';
          drop.innerHTML = '';
        });
      })(items[j], results[j]);
    }
  }

  function _jAccBindAC() {
    if (_jAccBound) return;
    _jAccBound = true;
    var inp = document.getElementById('j-acc-prof-inp');
    if (!inp) return;
    inp.addEventListener('focus', function() { _jAccShowDrop(inp.value); });
    inp.addEventListener('input', function() { _jAccShowDrop(inp.value); });
    inp.addEventListener('keydown', function(e) {
      if (e.key === 'Escape') {
        var drop = document.getElementById('j-acc-prof-drop');
        if (drop) { drop.style.display = 'none'; drop.innerHTML = ''; }
      }
    });
    inp.addEventListener('blur', function() {
      setTimeout(function() {
        var drop = document.getElementById('j-acc-prof-drop');
        if (drop) { drop.style.display = 'none'; drop.innerHTML = ''; }
      }, 180);
    });
  }

  function _onJobLocModeChange() {
    var mode       = (document.getElementById('j-loc-mode') || {}).value || 'hq';
    var branchWrap = document.getElementById('j-branch-wrap');
    var customWrap = document.getElementById('j-custom-wrap');
    if (branchWrap) branchWrap.style.display = mode === 'branch' ? '' : 'none';
    if (customWrap) customWrap.style.display  = mode === 'custom' ? '' : 'none';
    if (mode === 'branch') _populateBranchSelector();
  }

  function _populateBranchSelector() {
    var sel = document.getElementById('j-branch-sel');
    if (!sel) return;
    sel.innerHTML = '<option value="">— اختر الفرع —</option>';
    var branches = (window.companyState && companyState.branches) || [];
    branches.forEach(function (b) {
      var o    = document.createElement('option');
      var label = [b.branch_name, b.country, b.city].filter(Boolean).join(' — ');
      var locVal = [b.country, b.city, b.district].filter(Boolean).join('، ');
      o.value      = locVal;
      o.textContent = label || locVal;
      sel.appendChild(o);
    });
  }

  function _onWmodeChange() {
    var wmode = (document.getElementById('j-wmode') || {}).value || '';
    if (wmode === 'عن بُعد') {
      var locMode = document.getElementById('j-loc-mode');
      if (locMode) locMode.value = 'remote';
      _onJobLocModeChange();
    }
  }

  function _onSalHideChange() {
    var hide   = document.getElementById('j-sal-hide');
    var salRow = document.getElementById('j-sal-row');
    if (salRow) salRow.style.display = (hide && hide.checked) ? 'none' : '';
  }

  function _resolveJobLocation() {
    var mode = (document.getElementById('j-loc-mode') || {}).value || 'hq';
    if (mode === 'remote') return 'عن بُعد';
    if (mode === 'branch') {
      var br = document.getElementById('j-branch-sel');
      return (br && br.value) || '';
    }
    if (mode === 'hq') {
      var p = window.companyState && companyState.profile;
      if (p) {
        var parts = [p.country, p.city].filter(Boolean);
        return parts.join('، ') || p.location || '';
      }
      return '';
    }
    // custom
    return (document.getElementById('j-loc') || {}).value || '';
  }

  function _resetPostJobModal() {
    ['j-title','j-desc','j-sal1','j-sal2','j-loc'].forEach(function (id) {
      var el = document.getElementById(id);
      if (el) el.value = '';
    });
    ['j-prof','j-type','j-wmode','j-exp','j-cur','j-branch-sel'].forEach(function (id) {
      var el = document.getElementById(id);
      if (el) el.value = '';
    });
    // clear skill chips
    _jSkills = [];
    var chipsEl = document.getElementById('j-skill-chips');
    if (chipsEl) chipsEl.innerHTML = '';
    var inpEl = document.getElementById('j-skill-inp');
    if (inpEl) inpEl.value = '';
    // clear accepted profession chips
    _jAccProfs = [];
    var accChipsEl = document.getElementById('j-acc-prof-chips');
    if (accChipsEl) accChipsEl.innerHTML = '';
    var accInpEl = document.getElementById('j-acc-prof-inp');
    if (accInpEl) accInpEl.value = '';
    var accDrop = document.getElementById('j-acc-prof-drop');
    if (accDrop) { accDrop.style.display = 'none'; accDrop.innerHTML = ''; }
    _jHideDrop();
    var pBtn = document.getElementById('publishJobBtn');
    if (pBtn) { pBtn.disabled = false; pBtn.textContent = 'نشر الوظيفة'; }
    var hide = document.getElementById('j-sal-hide');
    if (hide) hide.checked = false;
    var locMode = document.getElementById('j-loc-mode');
    if (locMode) locMode.value = 'hq';
    _onSalHideChange();
    _onJobLocModeChange();
  }

  // ── Post job modal ─────────────────────────────────────────────
  function openPostJob() {
    if (!window.companyState || !companyState.permissions.can_post_jobs) return;

    // Fill static selects (idempotent — only fills when empty)
    if (window.TW) {
      var _fill = function (id, arr, ph) {
        var el = document.getElementById(id);
        if (el && el.options.length < 2) TW.fillSelect(el, arr || [], ph);
      };
      _fill('j-type',  TW.JOB_TYPES,         '— نوع الدوام —');
      _fill('j-wmode', TW.JOB_WORK_MODES,    '— طبيعة العمل —');
      _fill('j-exp',   TW.EXPERIENCE_LEVELS, '— الخبرة المطلوبة —');
      if (window.scSelectInit) scSelectInit();
    }

    _loadProfessions();
    _jBindSkillAC();
    _jAccBindAC();
    _onJobLocModeChange();
    var el = document.getElementById('postJobOverlay');
    if (el) el.classList.add('show');
    if (window.history) history.pushState({ modal: 'postJob' }, '', location.href);
  }

  function publishJob() {
    if (!window.companyState || !companyState.permissions.can_post_jobs) {
      if (window.showToast) showToast('غير مصرح', 'error'); return;
    }
    var val = function (id) { return (document.getElementById(id) || {}).value || ''; };

    var title = val('j-title').trim();
    if (!title) { if (window.showToast) showToast('أدخل المسمى الوظيفي', 'error'); return; }

    var profId = parseInt(val('j-prof')) || null;
    if (!profId) { if (window.showToast) showToast('اختر التخصص الوظيفي', 'error'); return; }

    // Flush any partially typed skill before building payload
    var inpEl = document.getElementById('j-skill-inp');
    if (inpEl && inpEl.value.trim()) { _jAddSkill(inpEl.value.trim()); }

    // Derive legacy category string from selected profession's optgroup label
    var cat = '';
    var profSel = document.getElementById('j-prof');
    if (profSel && profSel.selectedIndex >= 0) {
      var selOpt = profSel.options[profSel.selectedIndex];
      cat = (selOpt && selOpt.parentElement && selOpt.parentElement.tagName === 'OPTGROUP')
        ? (selOpt.parentElement.label || '') : '';
    }

    var publishBtn = document.getElementById('publishJobBtn');
    if (publishBtn && publishBtn.disabled) return;
    if (publishBtn) { publishBtn.disabled = true; publishBtn.textContent = 'جاري النشر…'; }

    var salHide   = document.getElementById('j-sal-hide');
    var isSalHide = salHide && salHide.checked;

    var payload = {
      title:                   title,
      description:             val('j-desc'),
      location:                _resolveJobLocation(),
      job_type:                val('j-type') || 'دوام كامل',
      work_mode:               val('j-wmode') || 'في الموقع',
      category:                cat,
      profession_id:           profId,
      salary_min:              isSalHide ? null : (parseInt(val('j-sal1')) || null),
      salary_max:              isSalHide ? null : (parseInt(val('j-sal2')) || null),
      currency:                val('j-cur') || 'USD',
      salary_hidden:           isSalHide,
      experience_years:        parseInt(val('j-exp')) || 0,
      skills:                  _jSkills.slice(),
      accepted_profession_ids: _jAccProfs.map(function(p) { return p.id; }),
    };

    fetch('/company/jobs', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + _jwt() },
      body:    JSON.stringify(payload),
    })
    .then(function (r) {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.json();
    })
    .then(function (data) {
      if (data.status !== 'success') throw new Error(data.detail || 'فشل النشر');

      // ── Confirmed Immediate Update ────────────────────────────
      var ov = document.getElementById('postJobOverlay');
      if (ov) ov.classList.remove('show');
      if (window.showToast) showToast('تم نشر الوظيفة ✓');

      var newJob = data.job || {};
      if (!newJob.id) newJob = Object.assign(
        { id: 0, status: 'active', created_at: new Date().toISOString() }, payload);
      companyState.jobs = [newJob].concat(companyState.jobs || []);
      if (window.renderJobs) renderJobs();

      // Increment local jobs counter so stats chip stays in sync
      if (window.companyState && companyState.stats)
        companyState.stats.jobs_count = (companyState.stats.jobs_count || 0) + 1;
      if (window.renderStats) renderStats();
      _resetPostJobModal();
    })
    .catch(function (err) {
      if (publishBtn) { publishBtn.disabled = false; publishBtn.textContent = 'نشر الوظيفة'; }
      if (window.showToast) showToast((err && err.message) || 'خطأ في نشر الوظيفة', 'error');
    });
  }

  // ── Event bindings ─────────────────────────────────────────────
  function _bindJobEvents() {
    var q = function (id) { return document.getElementById(id); };

    var postJobOverlay = q('postJobOverlay');
    if (postJobOverlay) postJobOverlay.addEventListener('click', function (e) {
      if (e.target === this) this.classList.remove('show');
    });

    var publishJobBtn = q('publishJobBtn');
    if (publishJobBtn) publishJobBtn.addEventListener('click', publishJob);

    var postJobCancelBtn = q('postJobCancelBtn');
    if (postJobCancelBtn) postJobCancelBtn.addEventListener('click', function () {
      var ov = q('postJobOverlay'); if (ov) ov.classList.remove('show');
    });
  }

  window._applyJob             = _applyJob;
  window.applyJob              = applyJob;
  window.bindEvents            = bindEvents;
  window.bindRateStars         = bindRateStars;
  window.submitRating          = submitRating;
  window.openPostJob           = openPostJob;
  window.publishJob            = publishJob;
  window._onJobLocModeChange   = _onJobLocModeChange;
  window._onWmodeChange        = _onWmodeChange;
  window._onSalHideChange      = _onSalHideChange;

  document.addEventListener('DOMContentLoaded', function () {
    bindEvents();
    _bindJobEvents();
  });
}());
