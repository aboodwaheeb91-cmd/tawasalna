// company.jobs.js — job apply, post job, event binding, rating interactions
// Load order: 5th (after render)
(function () {
  'use strict';

  var isRateLoading = false;

  // Session helpers live on the page namespace (company.state.js)
  function _signedIn() { return TwCompanyPage.signedIn(); }
  function _toLogin()  { TwCompanyPage.toLogin(); }

  // ── Visitor job card actions — share + save ────────────────────
  function _shareFallback(text) {
    var ta = document.createElement('textarea');
    ta.value = text; ta.style.cssText = 'position:fixed;opacity:0;top:0;left:0';
    document.body.appendChild(ta); ta.select();
    try { document.execCommand('copy'); if (window.showToast) showToast('تم نسخ تفاصيل الوظيفة ✓'); }
    catch (e) { if (window.showToast) showToast('تعذّر النسخ تلقائياً'); }
    document.body.removeChild(ta);
  }
  function _shareJob(jid) {
    var url = (location.origin || '') + '/job-detail?id=' + encodeURIComponent(jid);
    // Look up job title + company name from companyState
    var job = null;
    if (window.companyState && companyState.jobs) {
      for (var i = 0; i < companyState.jobs.length; i++) {
        if (String(companyState.jobs[i].id) === String(jid)) { job = companyState.jobs[i]; break; }
      }
    }
    var jobTitle    = (job && job.title) ? job.title : '';
    var companyName = (window.companyState && companyState.profile && companyState.profile.full_name)
      ? companyState.profile.full_name : '';
    // Build rich share payload
    var shareTitle = jobTitle ? 'وظيفة: ' + jobTitle : 'وظيفة على تواصلنا';
    var parts = ['وظيفة على تواصلنا:'];
    if (jobTitle)    parts.push(jobTitle);
    if (companyName) parts.push('لدى: ' + companyName);
    parts.push('رابط التفاصيل:');
    parts.push(url);
    var shareText = parts.join('\n');
    if (navigator.share) {
      navigator.share({ title: shareTitle, text: shareText, url: url }).catch(function () {});
    } else if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(shareText)
        .then(function () { if (window.showToast) showToast('تم نسخ تفاصيل الوظيفة ✓'); })
        .catch(function () { _shareFallback(shareText); });
    } else {
      _shareFallback(shareText);
    }
  }

  // ── Apply ──────────────────────────────────────────────────────
  function _applyJob(btn, jobId) {
    if (!jobId) return;
    if (!_signedIn()) { _toLogin(); return; }
    var origText = btn.textContent;
    btn.disabled = true; btn.textContent = 'جاري...';
    twApi('/jobs/' + encodeURIComponent(jobId) + '/apply', {
      method: 'POST', body: { cover_letter: '' },
    }).then(function (res) {
      if (!res.ok) {
        btn.disabled = false; btn.textContent = origText;
        if (window.showToast) showToast(twApiMessage(res, twT('company.job.apply_failed')), 'error');
        return;
      }
      btn.textContent = (res.raw && res.raw.already_applied) ? '✓ قدّمت مسبقاً' : '✓ تم التقديم';
      btn.classList.add('applied');
    });
  }

  // onclick wrapper — used by hardcoded cards in HTML before dynamic render
  function applyJob(btn) {
    var card  = btn.closest('[data-jid]');
    var jobId = card ? card.dataset.jid : (btn.getAttribute('data-jobid') || '');
    _applyJob(btn, jobId);
  }

  // ── Job manage dropdown (singleton) ───────────────────────────
  var _jMgmtDropEl = null;

  function _closeJobMgmtDrop() {
    if (_jMgmtDropEl && _jMgmtDropEl.parentNode) {
      _jMgmtDropEl.parentNode.removeChild(_jMgmtDropEl);
    }
    _jMgmtDropEl = null;
    window.removeEventListener('scroll', _closeJobMgmtDrop, true);
    window.removeEventListener('resize', _closeJobMgmtDrop);
  }

  function _openJobMgmtDrop(btn, jobId, currentStatus) {
    _closeJobMgmtDrop();
    // expired/closed jobs have no manage button — guard in case called directly
    if (currentStatus === 'expired' || currentStatus === 'closed') return;

    var rect = btn.getBoundingClientRect();
    var pauseLbl = currentStatus === 'active' ? 'إيقاف التقديم' : 'إعادة فتح التقديم';

    var drop = document.createElement('div');
    drop.className = 'co-jmgmt-float';

    var pauseOpt = document.createElement('button');
    pauseOpt.type = 'button';
    pauseOpt.className = 'co-jmgmt-opt';
    pauseOpt.textContent = pauseLbl;
    pauseOpt.addEventListener('click', function (e) {
      e.stopPropagation();
      _closeJobMgmtDrop();
      toggleJobStatus(jobId, currentStatus);
    });

    var closeOpt = document.createElement('button');
    closeOpt.type = 'button';
    closeOpt.className = 'co-jmgmt-opt';
    closeOpt.textContent = 'إنهاء الإعلان';
    closeOpt.addEventListener('click', function (e) {
      e.stopPropagation();
      _closeJobMgmtDrop();
      closeJob(jobId);
    });

    drop.appendChild(pauseOpt);
    drop.appendChild(closeOpt);
    document.body.appendChild(drop);
    _jMgmtDropEl = drop;

    // Viewport-clamped positioning — measure after appending so offsetWidth is available
    var menuW = drop.offsetWidth  || 170;
    var menuH = drop.offsetHeight || 90;
    var vpW   = window.innerWidth;
    var vpH   = window.innerHeight;
    // Horizontal: align right edge of menu to right edge of button, clamp to viewport
    var left = rect.right - menuW;
    if (left < 8)                    left = 8;
    if (left + menuW > vpW - 8)      left = vpW - menuW - 8;
    // Vertical: prefer below button; fall back to above if no room
    var top;
    if (vpH - rect.bottom >= menuH + 8) {
      top = rect.bottom + 4;
    } else {
      top = rect.top - menuH - 4;
      if (top < 8) top = rect.bottom + 4;
    }
    drop.style.left = left + 'px';
    drop.style.top  = top  + 'px';

    // Close on scroll (capture phase catches all scrollable containers) or resize
    window.addEventListener('scroll', _closeJobMgmtDrop, true);
    window.addEventListener('resize', _closeJobMgmtDrop);
    // Close on outside click
    setTimeout(function () {
      document.addEventListener('click', _closeJobMgmtDrop, { once: true });
    }, 0);
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
        var detailBtn = e.target.closest('.visitor-detail-btn');
        if (detailBtn) {
          e.stopPropagation();
          window.location.href = '/job-detail?id=' + card.dataset.jid;
          return;
        }
        var appBtn = e.target.closest('.owner-applicants-btn');
        if (appBtn) {
          e.preventDefault();
          e.stopPropagation();
          if (window.openApplicantsModal) openApplicantsModal(parseInt(card.dataset.jid, 10));
          return;
        }
        var manageBtn = e.target.closest('.job-manage-btn');
        if (manageBtn) {
          e.preventDefault();
          e.stopPropagation();
          _openJobMgmtDrop(manageBtn, parseInt(card.dataset.jid, 10), manageBtn.getAttribute('data-status'));
          return;
        }
        var saveBtn = e.target.closest('.vjc-btn--save');
        if (saveBtn) {
          e.stopPropagation();
          if (window.showToast) showToast('ميزة حفظ الوظائف ستتوفر قريباً');
          return;
        }
        var shareBtn = e.target.closest('.vjc-btn--share');
        if (shareBtn) {
          e.stopPropagation();
          _shareJob(card.dataset.jid);
          return;
        }
        var statusBtn = e.target.closest('.vjc-btn--apply-status');
        if (statusBtn) {
          e.stopPropagation();
          var applied = statusBtn.classList.contains('vjc-btn--applied');
          if (window.showToast) showToast(applied ? 'تم التقديم على هذه الوظيفة' : 'لم تتقدم على هذه الوظيفة بعد');
          return;
        }
        if (e.target.closest('button, a')) { return; }
        if (window.companyState && companyState.viewMode === 'owner') {
          window.location.href = '/job-detail?id=' + card.dataset.jid;
        }
      });
    }
    if (window.bindRateStars) bindRateStars();
  }

  // ── Rating ────────────────────────────────────────────────────
  // #rateBox follows the server's can_rate (emp visitor) — a guest still sees it and is
  // sent to login on click; an owner / company / edu visitor never sees it.
  function _syncRateBox() {
    var rb = document.getElementById('rateBox');
    if (!rb || !window.companyState) return;
    var perms = companyState.permissions || {};
    var show  = !!perms.can_rate || companyState.viewMode === 'guest';
    if (show) rb.style.removeProperty('display');
    else      rb.style.setProperty('display', 'none', 'important');
  }

  function bindRateStars() {
    _syncRateBox();
    var box = document.getElementById('rateStars');
    if (!box || box.dataset.bound) return;
    box.dataset.bound = '1';
    box.addEventListener('click', function (e) {
      var span = e.target.closest('span[data-score]');
      if (!span) return;
      submitRating(parseInt(span.getAttribute('data-score')));
    });
  }

  // @vm-extract-begin: co-rating-submit
  // The ONE rating submit on the page (#rateStars and the ratings modal picker).
  // Returns a Promise<boolean> (true = saved) so the modal can refresh itself.
  function submitRating(score) {
    if (!_signedIn()) { _toLogin(); return Promise.resolve(false); }
    if (!window.companyState || !companyState.permissions || !companyState.permissions.can_rate)
      return Promise.resolve(false);
    if (isRateLoading) return Promise.resolve(false);   // double-click guard

    var companyId = (companyState.profile && companyState.profile.id)
      ? String(companyState.profile.id)
      : new URLSearchParams(location.search).get('id');
    if (!companyId) {
      if (window.showToast) showToast('تعذّر تحديد الشركة', 'error');
      return Promise.resolve(false);
    }

    var prevMine  = companyState.permissions.my_rating;
    var prevAvg   = companyState.stats.rating_avg;
    var prevCount = companyState.stats.rating_count || 0;

    companyState.permissions.my_rating = score;
    if (window._paintRateStars) _paintRateStars(score);

    isRateLoading = true;
    return twApi('/company/rate/' + encodeURIComponent(companyId), {
      method: 'POST', body: { score: score },
    }).then(function (res) {
      isRateLoading = false;
      if (!res.ok) {
        companyState.permissions.my_rating = prevMine;
        companyState.stats.rating_avg      = prevAvg;
        companyState.stats.rating_count    = prevCount;
        if (window.renderRating) renderRating();
        if (window.showToast) showToast(twApiMessage(res, 'تعذّر حفظ التقييم'), 'error');
        return false;
      }
      var data = res.raw || {};
      if (typeof data.rating_avg === 'number' || data.rating_avg === null)
        companyState.stats.rating_avg = data.rating_avg;
      if (typeof data.rating_count === 'number')
        companyState.stats.rating_count = data.rating_count;
      if (typeof data.my_score === 'number')
        companyState.permissions.my_rating = data.my_score;
      if (window.renderRating) renderRating();
      if (window.renderStats)  renderStats();
      if (window.showToast) showToast('تم حفظ تقييمك ✓');
      return true;
    });
  }

  // @vm-extract-end: co-rating-submit

  // ── Post job helpers ───────────────────────────────────────────

  // ── Profession picker ──────────────────────────────────────────
  var _professions  = [];
  var _pendingProfId = null; // profession_id to select after async professions load
  var _postJobHistoryPushed = false; // true after pushState for the postJob modal

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
      html += '<optgroup label="' + twEscHtml(g) + '">';
      groups[g].forEach(function(p) {
        var icon = (p.icon || 'briefcase').replace(/"/g, '');
        html += '<option value="' + twEscHtml(String(p.id)) + '" data-icon="' + twEscHtml(icon) + '">' + twEscHtml(p.name_ar || p.name_en || '') + '</option>';
      });
      html += '</optgroup>';
    });
    sel.innerHTML = html;
    if (_pendingProfId) {
      sel.value = String(_pendingProfId);
      _pendingProfId = null;
    }
    if (window.scSelectInit) scSelectInit();
  }

  function _loadProfessions() {
    var sel = document.getElementById('j-prof');
    if (!sel) return;
    if (_professions.length) { _rebuildProfSelect(); return; }
    twApi('/professions', { auth: false }).then(function (res) {
      if (!res.ok) {
        if (sel) sel.innerHTML = '<option value="">— تعذر التحميل —</option>';
        return;
      }
      var data = res.raw;
      _professions = Array.isArray(data) ? data : ((data && data.professions) || []);
      _rebuildProfSelect();
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
        + twIcon(icon, { className: 'j-chip-ic' })
        + twEscHtml(name)
        + '<button type="button" class="j-skill-chip-del" data-skill="' + twEscHtml(name) + '" aria-label="حذف">×</button>'
        + '</span>';
    });
    box.innerHTML = html;
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
        + twIcon(s.icon || 'circle-check', { className: 'j-drop-ic' })
        + '<span class="j-drop-en">' + twEscHtml(s.en) + '</span>'
        + (s.ar !== s.en ? '<span class="j-drop-ar">' + twEscHtml(s.ar) + '</span>' : '')
        + '</div>';
    });
    drop.innerHTML = html;
    drop.style.display = 'block';
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
        + twIcon(p.icon || 'briefcase', { className: 'j-chip-ic' })
        + twEscHtml(p.name_ar || p.name_en || '')
        + '<button type="button" class="j-skill-chip-del" data-id="' + twEscHtml(String(p.id)) + '" aria-label="حذف">×</button>'
        + '</span>';
    });
    box.innerHTML = html;
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
        + twIcon(p.icon || 'briefcase', { className: 'j-drop-ic' })
        + '<span class="j-drop-ar">' + twEscHtml(p.name_ar || p.name_en || '') + '</span>'
        + '</div>';
    });
    drop.innerHTML = html;
    drop.style.display = 'block';
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
    // Dropdown only shows after typing — not on focus
    inp.addEventListener('input', function() {
      var q = inp.value.trim();
      if (!q) {
        var drop = document.getElementById('j-acc-prof-drop');
        if (drop) { drop.style.display = 'none'; drop.innerHTML = ''; }
        return;
      }
      _jAccShowDrop(q);
    });
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

  function _onAccAllChange() {
    var cb = document.getElementById('j-acc-all');
    var sec = document.getElementById('j-acc-prof-section');
    if (!cb) return;
    if (cb.checked) {
      if (sec) sec.style.display = 'none';
      // Clear individual targets — accepts all supersedes them
      _jAccProfs = [];
      var chips = document.getElementById('j-acc-prof-chips');
      if (chips) chips.innerHTML = '';
      var accInp = document.getElementById('j-acc-prof-inp');
      if (accInp) accInp.value = '';
    } else {
      if (sec) sec.style.display = '';
    }
  }

  function _onJobLocModeChange() {
    var mode       = (document.getElementById('j-loc-mode') || {}).value || 'hq';
    var branchWrap = document.getElementById('j-branch-wrap');
    var customWrap = document.getElementById('j-custom-wrap');
    if (branchWrap) branchWrap.style.display = mode === 'branch' ? '' : 'none';
    if (customWrap) customWrap.style.display  = mode === 'custom' ? '' : 'none';
    if (mode === 'branch') _populateBranchSelector();
    if (mode === 'custom' && window.TW) {
      var countrySel = document.getElementById('j-loc-country');
      if (countrySel) {
        // Only populate if empty — preserves user selection on mode toggle and edit hydration
        if (countrySel.options.length <= 1) {
          TW.fillCountries(countrySel, '— اختر الدولة —', { valueMode: 'name_ar' });
        }
        if (!countrySel.dataset.cityBound) {
          countrySel.dataset.cityBound = '1';
          countrySel.addEventListener('change', function () {
            TW.fillCities(document.getElementById('j-loc-city'), this.value, '');
            if (window.scSelectInit) scSelectInit();
          });
        }
        if (window.scSelectInit) scSelectInit();
      }
    }
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

  function _onSalShowChange() {
    var show   = document.getElementById('j-sal-show');
    var salRow = document.getElementById('j-sal-row');
    // OFF (unchecked) = salary hidden; ON (checked) = show salary fields
    if (salRow) salRow.style.display = (show && show.checked) ? '' : 'none';
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
    var country = (document.getElementById('j-loc-country') || {}).value || '';
    var city    = (document.getElementById('j-loc-city')    || {}).value || '';
    return [country, city].filter(Boolean).join('، ');
  }

  function _resetPostJobModal() {
    ['j-title','j-desc','j-sal1','j-sal2'].forEach(function (id) {
      var el = document.getElementById(id);
      if (el) el.value = '';
    });
    ['j-prof','j-branch-sel','j-loc-country','j-loc-city'].forEach(function (id) {
      var el = document.getElementById(id);
      if (el) el.value = '';
    });
    // Apply defaults
    var typeEl = document.getElementById('j-type');
    if (typeEl) typeEl.value = 'دوام كامل';
    var wmodeEl = document.getElementById('j-wmode');
    if (wmodeEl) wmodeEl.value = 'في الموقع';
    var expEl = document.getElementById('j-exp');
    if (expEl) expEl.value = '0';
    var curEl = document.getElementById('j-cur');
    if (curEl) curEl.value = 'USD';
    var durEl = document.getElementById('j-dur');
    if (durEl) durEl.value = '7';
    // Clear skill chips
    _jSkills = [];
    var chipsEl = document.getElementById('j-skill-chips');
    if (chipsEl) chipsEl.innerHTML = '';
    var inpEl = document.getElementById('j-skill-inp');
    if (inpEl) inpEl.value = '';
    // Clear accepted profession chips
    _jAccProfs = [];
    var accChipsEl = document.getElementById('j-acc-prof-chips');
    if (accChipsEl) accChipsEl.innerHTML = '';
    var accInpEl = document.getElementById('j-acc-prof-inp');
    if (accInpEl) accInpEl.value = '';
    var accDrop = document.getElementById('j-acc-prof-drop');
    if (accDrop) { accDrop.style.display = 'none'; accDrop.innerHTML = ''; }
    // Reset accepts-all toggle (unchecked = use individual targets)
    var accAll = document.getElementById('j-acc-all');
    if (accAll) accAll.checked = false;
    var accSec = document.getElementById('j-acc-prof-section');
    if (accSec) accSec.style.display = '';
    _jHideDrop();
    _pendingProfId = null;
    var pBtn = document.getElementById('publishJobBtn');
    if (pBtn) { pBtn.disabled = false; pBtn.textContent = twT('company.job_form.publish'); }
    var modalTitle = document.querySelector('#postJobOverlay .modal-head-title');
    if (modalTitle) modalTitle.textContent = twT('company.job_form.title');
    // Salary toggle: default OFF = hidden
    var salShow = document.getElementById('j-sal-show');
    if (salShow) salShow.checked = false;
    var locMode = document.getElementById('j-loc-mode');
    if (locMode) locMode.value = 'hq';
    _onSalShowChange();
    _onJobLocModeChange();
    if (window.scSelectInit) scSelectInit();
  }

  // ── Static select population (idempotent — shared by create and edit) ──
  function _fillStaticSelects() {
    if (!window.TW) return;
    var _fill = function (id, arr, ph) {
      var el = document.getElementById(id);
      if (el && el.options.length < 2) TW.fillSelect(el, arr || [], ph);
    };
    _fill('j-type',  TW.JOB_TYPES,      '— نوع الدوام —');
    _fill('j-wmode', TW.JOB_WORK_MODES, '— طبيعة العمل —');
    var curEl = document.getElementById('j-cur');   // currencies = TW.JOB_CURRENCIES (no empty option, USD first)
    if (curEl && !curEl.options.length && TW.JOB_CURRENCIES) {
      TW.JOB_CURRENCIES.forEach(function (c) { curEl.appendChild(new Option(c, c)); });
      curEl.value = 'USD';
    }
    var expEl = document.getElementById('j-exp');
    if (expEl && expEl.options.length < 2 && TW.EXP_LEVELS) {
      expEl.innerHTML = '<option value="">— الخبرة المطلوبة —</option>';
      TW.EXP_LEVELS.forEach(function (lv) {
        var o = document.createElement('option');
        o.value = lv.value;
        o.textContent = lv.label;
        expEl.appendChild(o);
      });
    }
    if (window.scSelectInit) scSelectInit();
  }

  // ── ?post_job=1 deep link (twPostJobHref — PR 4.14) ───────────
  // Read once at load, consumed after the first profile load (permissions known). The param
  // is dropped from the URL first, so closing / reloading does not reopen the form.
  var _postJobFromUrl = new URLSearchParams(location.search).get('post_job') === '1';
  function _openPostJobFromUrl() {
    if (!_postJobFromUrl) return;
    _postJobFromUrl = false;
    if (window.history && history.replaceState) {
      var sp = new URLSearchParams(location.search);
      sp.delete('post_job');
      var qs = sp.toString();
      history.replaceState(history.state, '', location.pathname + (qs ? '?' + qs : '') + location.hash);
    }
    openPostJob();   // no-op unless the owner can post jobs
  }

  // ── Post job modal ─────────────────────────────────────────────
  function openPostJob() {
    if (!window.companyState || !companyState.permissions.can_post_jobs) return;

    _fillStaticSelects();
    // Apply default selections
    var typeEl = document.getElementById('j-type');
    if (typeEl && !typeEl.value) typeEl.value = 'دوام كامل';
    var wmodeEl = document.getElementById('j-wmode');
    if (wmodeEl && !wmodeEl.value) wmodeEl.value = 'في الموقع';

    _loadProfessions();
    _jBindSkillAC();
    _jAccBindAC();
    _onJobLocModeChange();
    var el = document.getElementById('postJobOverlay');
    if (el) el.classList.add('show');
    if (window.history && !_postJobHistoryPushed) {
      history.pushState({ modal: 'postJob' }, '', location.href);
      _postJobHistoryPushed = true;
    }
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
    if (publishBtn) { publishBtn.disabled = true; publishBtn.textContent = twT('company.job_form.publishing'); }

    var salShow   = document.getElementById('j-sal-show');
    var isSalShow = salShow && salShow.checked;  // OFF = hidden (default)
    var accAllCb  = document.getElementById('j-acc-all');
    var acceptsAll = accAllCb && accAllCb.checked;

    var payload = {
      title:                   title,
      description:             val('j-desc'),
      location:                _resolveJobLocation(),
      job_type:                val('j-type') || 'دوام كامل',
      work_mode:               val('j-wmode') || 'في الموقع',
      category:                cat,
      profession_id:           profId,
      salary_min:              isSalShow ? (parseInt(val('j-sal1')) || null) : null,
      salary_max:              isSalShow ? (parseInt(val('j-sal2')) || null) : null,
      currency:                val('j-cur') || 'USD',
      salary_hidden:           !isSalShow,
      experience_years:        parseInt(val('j-exp')) || 0,
      skills:                  _jSkills.slice(),
      accepts_all_professions: acceptsAll,
      accepted_profession_ids: acceptsAll ? [] : _jAccProfs.map(function(p) { return p.id; }),
      duration_days:           parseInt(val('j-dur')) || 7,
    };

    // create only — a published job cannot be edited by the company (owner decision, task 5.3j5)
    var btnOrigText = twT('company.job_form.publish');

    twApi('/company/jobs', { method: 'POST', body: payload }).then(function (res) {
      var data = res.raw || {};
      if (!res.ok || data.status !== 'success') {
        if (publishBtn) { publishBtn.disabled = false; publishBtn.textContent = btnOrigText; }
        if (window.showToast) showToast(twApiMessage(res, 'خطأ في حفظ الوظيفة'), 'error');
        return;
      }

      // ── Confirmed Immediate Update ────────────────────────────
      _closePostJobOverlay();
      if (window.showToast) showToast('تم نشر الوظيفة ✓');

      var newJob = data.job || {};
      if (!newJob.id) newJob = Object.assign(
        { id: 0, status: 'active', created_at: new Date().toISOString() }, payload);
      companyState.jobs = [newJob].concat(companyState.jobs || []);
      if (window.companyState && companyState.stats)
        companyState.stats.jobs_count = (companyState.stats.jobs_count || 0) + 1;
      if (window.renderStats) renderStats();
      if (window.renderJobs) renderJobs();
      _resetPostJobModal();
    });
  }

  // ── Close postJob overlay (Rule #17) ───────────────────
  // fromPopstate=true means popstate already moved back; skip history.back().
  function _closePostJobOverlay(fromPopstate) {
    var el = document.getElementById('postJobOverlay');
    if (el) el.classList.remove('show');
    if (_postJobHistoryPushed && !fromPopstate) {
      _postJobHistoryPushed = false;
      if (window.history) history.back();
    } else {
      _postJobHistoryPushed = false;
    }
  }

  // ── Job management — delete ────────────────────────────────────
  function deleteJob(jobId) {
    twConfirm({
      title:       twT('company.job.delete.title'),
      message:     twT('company.job.delete.msg'),
      confirmText: twT('company.job.delete.ok'),
      danger:      true,
    }).then(function (yes) {
      if (!yes) return;
      twApi('/company/jobs/' + parseInt(jobId, 10), { method: 'DELETE' }).then(function (res) {
        if (!res.ok) {
          var fb = res.status === 403 ? 'ليست وظيفتك أو غير موجودة' : 'تعذّر حذف الوظيفة، حاول مجدداً';
          if (window.showToast) showToast(twApiMessage(res, fb), 'error');
          return;
        }
        companyState.jobs = companyState.jobs.filter(function (j) {
          return String(j.id) !== String(jobId);
        });
        if (companyState.stats)
          companyState.stats.jobs_count = Math.max(0, (companyState.stats.jobs_count || 1) - 1);
        if (window.renderJobs)  renderJobs();
        if (window.renderStats) renderStats();
        if (window.showToast) showToast('تم حذف الوظيفة');
      });
    });
  }

  // ── Job management — pause / resume ───────────────────────────
  function toggleJobStatus(jobId, currentStatus) {
    var newStatus = (currentStatus === 'active') ? 'paused' : 'active';
    twApi('/company/jobs/' + parseInt(jobId, 10) + '/status', {
      method: 'PATCH', body: { status: newStatus },
    }).then(function (res) {
      if (!res.ok) {
        if (window.showToast) showToast(twApiMessage(res, 'تعذّر تغيير حالة الوظيفة'), 'error');
        return;
      }
      var msg = newStatus === 'paused' ? 'تم إيقاف التقديم' : 'تم إعادة فتح التقديم ✓';
      // Optimistic in-place update — only if jobs are already loaded in state
      if (companyState.jobs && companyState.jobs.length > 0) {
        companyState.jobs = companyState.jobs.map(function (j) {
          if (String(j.id) === String(jobId)) return Object.assign({}, j, { status: newStatus });
          return j;
        });
        if (window.renderJobs) renderJobs();
      }
      if (window.showToast) showToast(msg);
      // Background sync from DB to ensure state matches server (also handles edge cases
      // where the optimistic map ran over a stale/empty list)
      if (window.loadJobs) loadJobs();
    });
  }

  // ── Job management — close (إنهاء الإعلان) ────────────────────
  function closeJob(jobId) {
    twConfirm({
      title:       twT('company.job.close.title'),
      message:     twT('company.job.close.msg'),
      confirmText: twT('company.job.close.ok'),
      danger:      true,
    }).then(function (yes) {
      if (!yes) return;
      twApi('/company/jobs/' + parseInt(jobId, 10) + '/status', {
        method: 'PATCH', body: { status: 'closed' },
      }).then(function (res) {
        if (!res.ok) {
          if (window.showToast) showToast(twApiMessage(res, 'تعذّر إنهاء الإعلان'), 'error');
          return;
        }
        companyState.jobs = companyState.jobs.map(function (j) {
          if (String(j.id) === String(jobId)) return Object.assign({}, j, { status: 'closed', effective_status: 'closed' });
          return j;
        });
        if (window.renderJobs) renderJobs();
        if (window.showToast) showToast('تم إنهاء الإعلان الوظيفي');
        if (window.loadJobs) loadJobs(); // background sync
      });
    });
  }

  // ── Event bindings ─────────────────────────────────────────────
  function _bindJobEvents() {
    var q = function (id) { return document.getElementById(id); };

    var postJobOverlay = q('postJobOverlay');
    if (postJobOverlay) postJobOverlay.addEventListener('click', function (e) {
      if (e.target === this) _closePostJobOverlay();
    });

    var publishJobBtn = q('publishJobBtn');
    if (publishJobBtn) publishJobBtn.addEventListener('click', publishJob);

    // Two cancel buttons: header X and footer cancel. Wrapped — passing the handler
    // directly made the click event the truthy fromPopstate arg, so history.back() was
    // skipped and the pushed modal entry stayed behind (Back then re-did nothing).
    ['postJobCancelBtn', 'postJobCancelFootBtn'].forEach(function(id) {
      var btn = q(id);
      if (btn) btn.addEventListener('click', function () { _closePostJobOverlay(); });
    });
  }

  // Read-only accessor for profession catalog — used by renderJobs for sub-title display
  window._getProfName = function (profId) {
    if (!profId || !_professions.length) return '';
    var id = parseInt(profId, 10);
    for (var i = 0; i < _professions.length; i++) {
      if (_professions[i].id === id) return _professions[i].name_ar || _professions[i].name_en || '';
    }
    return '';
  };

  window._applyJob             = _applyJob;
  window.applyJob              = applyJob;
  window.bindEvents            = bindEvents;
  window.bindRateStars         = bindRateStars;
  window.submitRating          = submitRating;
  window.openPostJob           = openPostJob;
  window._openPostJobFromUrl   = _openPostJobFromUrl;
  window.publishJob            = publishJob;
  window._closePostJobOverlay  = _closePostJobOverlay;
  window.toggleJobStatus       = toggleJobStatus;
  window.closeJob              = closeJob;
  window._onJobLocModeChange   = _onJobLocModeChange;
  window._onWmodeChange        = _onWmodeChange;
  window._onSalShowChange      = _onSalShowChange;
  window._onAccAllChange       = _onAccAllChange;

  document.addEventListener('DOMContentLoaded', function () {
    bindEvents();
    _bindJobEvents();
  });

  // _loadProfessions() requires #j-prof element (modal). Fetch catalog eagerly here
  // so _getProfName() is ready when renderJobs() first runs after loadData().
  // /professions is public — no JWT needed; fetch for all viewer types.
  (function _prefetchProfCatalog() {
    twApi('/professions', { auth: false }).then(function (res) {
        if (!res.ok || _professions.length) return; // failed, or already populated (modal opened first)
        var data = res.raw;
        _professions = Array.isArray(data) ? data : ((data && data.professions) || []);
        // Re-render job cards now that profession names are available
        if (window.renderJobs && window.companyState && companyState.jobs && companyState.jobs.length > 0) {
          window.renderJobs();
        }
      });
  }());
}());
