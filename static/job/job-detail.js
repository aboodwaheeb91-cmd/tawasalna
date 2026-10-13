/* job-detail.js — Job detail page logic (PR 4.8 — unified page checklist)
 * Shared systems only:
 *   session  → TwAuthSync.getSessionSnapshot() (public page; guest actions → twLoginHref(this job))
 *   API      → twApi (tw_shared.js — never fetch; JWT added by twApi itself)
 *   actions  → twAction('apply_job' | 'share' | 'report') — Actions Registry decides who sees what
 *   overlays → twModal (DS-OVL) for «تقديم» and «إبلاغ» · selects → DS-SEL (.ep-select + scSelectInit)
 *   text     → twT (tw_strings.json) · dates → twFormatDate (Gregorian, one format site-wide)
 *   icons    → twIcon.hydrate (static) / twIconEl (dynamic) — DS-ICON · logos → twAvatarHtml — DS-IMAGE
 *   feedback → showToast (DS-FEEDBACK — F34)
 * XSS safety: API data via textContent only, never innerHTML.
 */
(function () {
  'use strict';

  // ── Session ─────────────────────────────────────────────────
  // Public page: visitors read the job without login. The session is decided by
  // TwAuthSync.getSessionSnapshot() only (VM-10) — never by tw_user alone.
  var _snap   = (window.TwAuthSync && typeof TwAuthSync.getSessionSnapshot === 'function')
    ? TwAuthSync.getSessionSnapshot() : null;
  var _authed = !!(_snap && _snap.isAuthenticated);
  var _user   = _authed ? getTwUser() : null;   // display cache (tw_id / skills) — tw_shared.js

  // twLoginHref (tw_shared.js) validates the internal path and encodes it as ?next=.
  function _toLogin() { location.href = twLoginHref(location.pathname + location.search); }

  var _jobId       = null;
  var _job         = null;
  var _applyState  = null;   // null = open · 'applied' · 'paused' · 'closed'

  // ── Utility ─────────────────────────────────────────────────
  function _el(id) { return document.getElementById(id); }

  var _JOB_TYPES = ['full_time', 'part_time', 'contract', 'freelance', 'internship', 'remote'];
  function _jobTypeLabel(t) {
    return _JOB_TYPES.indexOf(t) !== -1 ? twT('job.type.' + t) : t;
  }

  function _skillName(s) {
    if (!s) return '';
    if (typeof s === 'string') return s;
    return s.skill || s.name_ar || s.name_en || s.slug || '';
  }

  // DS-ICON (F37): static icons are <i data-tw-icon> in the HTML (twIcon.hydrate at init);
  // icons built at runtime are twIconEl(name, { size }) — size = DS-SIZE token name.
  function _skillIconName(skillName) {
    return (window.TW && TW.getSkillIcon) ? (TW.getSkillIcon(skillName) || 'tag') : 'tag';
  }

  // Replace an element's content with text + icon (icon before the text when iconFirst).
  function _label(el, text, icon, iconFirst) {
    if (!el) return;
    el.textContent = '';
    var ico = icon ? twIconEl(icon, { size: 'sm' }) : null;
    if (ico && iconFirst) el.appendChild(ico);
    el.appendChild(document.createTextNode(text));
    if (ico && !iconFirst) el.appendChild(ico);
  }

  function _timeAgo(iso) {
    if (!iso) return '';
    var diff = (Date.now() - new Date(iso).getTime()) / 1000;
    if (!isFinite(diff)) return '';
    if (diff < 60)       return twT('job.ago.now');
    if (diff < 3600)     return twT('job.ago.minutes', { n: Math.floor(diff / 60) });
    if (diff < 86400)    return twT('job.ago.hours',   { n: Math.floor(diff / 3600) });
    if (diff < 2592000)  return twT('job.ago.days',    { n: Math.floor(diff / 86400) });
    if (diff < 31536000) return twT('job.ago.months',  { n: Math.floor(diff / 2592000) });
    return twT('job.ago.years', { n: Math.floor(diff / 31536000) });
  }

  function _chip(iconName, text, cls) {
    var span = document.createElement('span');
    span.className = 'jd-chip' + (cls ? ' ' + cls : '');
    if (iconName) span.appendChild(twIconEl(iconName, { size: 'xs' }));
    span.appendChild(document.createTextNode(text));
    return span;
  }

  // C# / C++ / F# / .NET need dir="ltr" inside RTL context
  function _isLtrSkill(name) {
    return typeof name === 'string' && /^([CF][#+]|\.NET)/i.test(name);
  }

  // Company link: a real <a href="/u/{tw_id}"> (Smart Router) — no role="link" on a div.
  function _companyHref(job) {
    return job && job.company_tw_id ? '/u/' + encodeURIComponent(job.company_tw_id) : '';
  }
  function _setLink(a, href) {
    if (!a) return;
    if (href) { a.href = href; a.classList.add('is-link'); }
    else { a.removeAttribute('href'); a.classList.remove('is-link'); }
  }

  function _salaryText(job) {
    if (job.salary_hidden) return twT('job.salary_hidden');
    if (!job.salary_min) return null;
    return job.salary_min + (job.salary_max ? '–' + job.salary_max : '+') + (job.currency ? ' ' + job.currency : '');
  }

  // ── Save (placeholder — no backend / registry entry yet) ──────
  function toggleSave() {
    if (!_authed) { _toLogin(); return; }
    showToast(twT('job.save_soon'), 'info');
  }

  // ── Skeleton / state ────────────────────────────────────────
  function showSkeleton() {
    var s = _el('jdSkeleton'); var c = _el('jdContent');
    if (s) s.classList.remove('hidden');
    if (c) c.classList.add('hidden');
    var sb = _el('jdStateBox');
    if (sb) sb.classList.add('hidden');
  }

  function hideSkeleton() {
    var s = _el('jdSkeleton');
    if (s) s.classList.add('hidden');
  }

  function showContent() {
    var c = _el('jdContent');
    if (c) c.classList.remove('hidden');
  }

  function showState(type, title, sub) {
    hideSkeleton();
    var c = _el('jdContent');
    if (c) c.classList.add('hidden');
    var bar = _el('jdStickyBar');
    if (bar) bar.classList.add('hidden');
    var box = _el('jdStateBox');
    if (!box) return;
    box.textContent = '';
    var ico = document.createElement('div');
    ico.className = 'jd-state-ico';
    ico.appendChild(twIconEl(type === 'error' ? 'alert' : 'info'));   // 40px — local (ICON-05 T3)
    var h3 = document.createElement('h3');
    h3.textContent = title;
    var p = document.createElement('p');
    p.textContent = sub || '';
    box.appendChild(ico); box.appendChild(h3); box.appendChild(p);
    if (type === 'error') {
      var btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'jd-retry'; _label(btn, twT('header.back'), 'back', true);
      btn.addEventListener('click', function () { twNavBack(twHomeHref()); });   // NAV-05 resolver
      box.appendChild(btn);
    }
    box.classList.remove('hidden');
  }

  // ── Load job ────────────────────────────────────────────────
  function loadJob() {
    var raw = new URLSearchParams(location.search).get('id');
    _jobId = raw ? parseInt(raw, 10) || null : null;
    if (!_jobId) {
      showState('error', twT('job.err.missing_id'), twT('job.err.missing_id_sub'));
      return;
    }
    showSkeleton();
    twApi('/jobs/' + _jobId).then(function (res) {
      var job = res.ok && res.data ? res.data.job : null;
      if (!job) {
        hideSkeleton();
        if (res.ok || res.status === 404) {
          showState('error', twT('job.err.not_found'), twT('job.err.not_found_sub'));
        } else {
          showState('error', twT('job.err.load'), twApiMessage(res, twT('common.check_connection')));
        }
        return;
      }
      _job = job;
      hideSkeleton();
      renderJob(_job);
      _applyOwnerMode(_job);
      showContent();
      _applyState = _statusApplyState(_job);
      _renderActions();
      loadUserSkillsThenMatch();
      loadSimilarJobs();
      _checkAlreadyApplied();
    });
  }

  // Paused / closed job → apply button disabled with the reason.
  function _statusApplyState(job) {
    if (!job || job.status === 'active' || !job.status) return null;
    return job.status === 'paused' ? 'paused' : 'closed';
  }

  // Has the signed-in personal account already applied? → disabled «تم التقديم».
  function _checkAlreadyApplied() {
    if (!_authed || _snap.userType !== 'emp' || _applyState) return;
    twApi('/my/applications').then(function (res) {
      var apps = res.ok && res.data ? res.data.applications : null;
      if (!Array.isArray(apps)) return;
      var already = apps.some(function (a) { return String(a.job_id) === String(_jobId); });
      if (!already) return;
      _applyState = 'applied';
      _renderApply();
    });
  }

  // ── Action buttons (Actions Registry — twAction) ─────────────
  // apply_job: visibleTo guest + emp → owner / co / edu never see it; guest → login (?next=).
  var _APPLY_LABEL = { applied: 'job.applied', paused: 'job.status.paused', closed: 'job.status.closed' };

  function _renderApply() {
    document.querySelectorAll('[data-jd-apply-slot]').forEach(function (slot) {
      slot.textContent = '';
      var sticky = slot.getAttribute('data-jd-apply-slot') === 'sticky';
      var btn = twAction('apply_job', {
        ownerId: _job ? _job.company_id : null,
        labelKey: _applyState ? _APPLY_LABEL[_applyState] : 'job.apply_now',
        disabled: !!_applyState,
        className: (sticky ? 'jd-sticky-apply' : 'jd-apply-btn') + (_applyState ? ' applied' : ''),
        onClick: openApply,
      });
      if (btn) slot.appendChild(btn);
      slot.hidden = !btn;
    });
  }

  function _renderActions() {
    _renderApply();
    var defs = {
      'share':      ['share',  { className: 'jd-share-btn', labelKey: 'job.share', onClick: shareJob }],
      'share-icon': ['share',  { className: 'jd-sticky-share', iconOnly: true, iconSize: 'lg',
                                 labelKey: 'job.share', onClick: shareJob }],
      'report':     ['report', { className: 'jd-report-link', labelKey: 'job.report', onClick: openReport }],
    };
    document.querySelectorAll('[data-jd-action-slot]').forEach(function (slot) {
      var d = defs[slot.getAttribute('data-jd-action-slot')];
      slot.textContent = '';
      var ctx = d ? Object.assign({ ownerId: _job ? _job.company_id : null }, d[1]) : null;
      var btn = d ? twAction(d[0], ctx) : null;
      if (btn) slot.appendChild(btn);
      slot.hidden = !btn;
    });
  }

  // ── Render job ──────────────────────────────────────────────
  function renderJob(job) {
    document.title = twT('page.title', { page: job.title || twT('job.default_title') });

    // Company logo — DS-IMAGE (F38): org = rounded square; URL checked by twSafeImageUrl inside.
    // company_user_type (GET /jobs/{id}) = users.user_type of the publisher (co | edu) → fallback colour;
    // missing on an old cached response → 'co'.
    var _coEntity = { full_name: job.company_name, avatar_url: job.company_logo,
                      user_type: job.company_user_type === 'edu' ? 'edu' : 'co' };
    var logoEl = _el('jdLogo');
    if (logoEl) logoEl.innerHTML = twAvatarHtml(_coEntity, 'xl', { eager: true });
    var logoBadge = _el('jdLogoBadge');
    if (logoBadge) logoBadge.hidden = !job.company_verified;

    var titleEl = _el('jdTitle');
    if (titleEl) titleEl.textContent = job.title || '';

    var coHref = _companyHref(job);

    // Company name + verified badge
    var coEl = _el('jdCoName');
    if (coEl) {
      coEl.textContent = job.company_name || '';
      if (job.company_verified) {
        var badge = document.createElement('span');
        badge.className = 'jd-co-badge'; badge.title = twT('job.verified_co');
        badge.appendChild(twIconEl('check', { size: 'xs' }));
        coEl.appendChild(badge);
      }
      _setLink(coEl, coHref);
    }

    // Meta chips
    var metaEl = _el('jdMeta');
    if (metaEl) {
      metaEl.textContent = '';
      if (job.location)    metaEl.appendChild(_chip('map-pin', job.location));
      if (job.job_type)    metaEl.appendChild(_chip('clock', _jobTypeLabel(job.job_type)));
      if (job.work_mode)   metaEl.appendChild(_chip('laptop', job.work_mode));
      if (job.experience_years && job.experience_years > 0)
        metaEl.appendChild(_chip('bar-chart-2', twT('job.exp_years', { n: job.experience_years })));
      var sal = _salaryText(job);
      if (sal) metaEl.appendChild(_chip('circle-dollar-sign', sal, job.salary_hidden ? '' : 'g'));
      if (job.profession_name_ar) metaEl.appendChild(_chip(job.profession_icon || 'briefcase', job.profession_name_ar, 'b'));
      if (job.created_at) metaEl.appendChild(_chip('calendar', _timeAgo(job.created_at)));
    }

    // Skill tags in header
    var tagsEl = _el('jdTags');
    if (tagsEl) {
      tagsEl.textContent = '';
      (job.skills || []).slice(0, 8).forEach(function (s) {
        var chip = _chip(_skillIconName(s), s, 'g');
        if (_isLtrSkill(s)) chip.setAttribute('dir', 'ltr');
        tagsEl.appendChild(chip);
      });
    }

    // Description section
    var descEl = _el('jdDesc');
    if (descEl && job.description && job.description.trim()) {
      descEl.textContent = job.description;
      var ds = _el('jdDescSection');
      if (ds) ds.classList.remove('hidden');
    }

    // Skills section (chip list)
    var skillsEl = _el('jdSkillChips');
    if (skillsEl && job.skills && job.skills.length) {
      skillsEl.textContent = '';
      job.skills.forEach(function (s) {
        var span = document.createElement('span');
        span.className = 'jd-skill-chip';
        if (_isLtrSkill(s)) span.setAttribute('dir', 'ltr');
        span.appendChild(twIconEl(_skillIconName(s), { size: 'sm' }));
        span.appendChild(document.createTextNode(s));
        skillsEl.appendChild(span);
      });
      var ss = _el('jdSkillsSection');
      if (ss) ss.classList.remove('hidden');
    }

    // Accepted professions section
    var accProfEl = _el('jdAccProfChips');
    if (accProfEl) {
      var as = _el('jdAccProfSection');
      var profs = job.accepts_all_professions
        ? [{ icon: 'users', name: twT('job.all_prof') }]
        : (job.accepted_professions || []).map(function (p) {
            return { icon: p.icon || 'briefcase', name: p.name_ar || p.name_en || '' };
          });
      if (profs.length) {
        accProfEl.textContent = '';
        profs.forEach(function (p) {
          var span = document.createElement('span');
          span.className = 'jd-skill-chip';
          span.appendChild(twIconEl(p.icon, { size: 'sm' }));
          span.appendChild(document.createTextNode(p.name));
          accProfEl.appendChild(span);
        });
        if (as) as.classList.remove('hidden');
      }
    }

    // Sidebar — job info rows
    _sideVal('jdSiCo', job.company_name, coHref);
    _sideVal('jdSiLoc',  job.location);
    _sideVal('jdSiType', job.job_type ? _jobTypeLabel(job.job_type) : null);
    _sideVal('jdSiMode', job.work_mode || null);
    var _expLabel = (function () {
      if (job.experience_years === undefined || job.experience_years === null) return null;
      if (window.TW && TW.EXP_LEVELS) {
        for (var i = 0; i < TW.EXP_LEVELS.length; i++) {
          if (TW.EXP_LEVELS[i].value === job.experience_years) return TW.EXP_LEVELS[i].label;
        }
      }
      return job.experience_years > 0 ? twT('job.exp_years_short', { n: job.experience_years }) : null;
    }());
    _sideVal('jdSiExp', _expLabel);
    _sideVal('jdSiSal', _salaryText(job));
    _sideVal('jdSiViews', job.views ? twT('job.views_n', { n: job.views }) : null);
    _sideVal('jdSiDate', twFormatDate(job.created_at) || null);   // Gregorian, one format (tw_shared.js)

    // Sidebar — company card
    var coAvEl = _el('jdCoCardAv');
    if (coAvEl) coAvEl.innerHTML = twAvatarHtml(_coEntity, 'lg');
    var cnEl = _el('jdCoCardName');
    if (cnEl) {
      cnEl.textContent = job.company_name || '';
      _setLink(cnEl, coHref);
    }
    var cvEl = _el('jdCoCardVerif');
    if (cvEl) {
      if (job.company_verified) _label(cvEl, twT('job.verified_co'), 'check', true);
      else cvEl.textContent = '';
    }
  }

  // Value cell of a sidebar row; with href the value is a real <a> (no click handler on a div).
  function _sideVal(id, val, href) {
    var el = _el(id);
    if (!el) return;
    if (!val) {
      var row = el.closest('.jd-sc-row');
      if (row) row.hidden = true;
      return;
    }
    el.textContent = '';
    if (href) {
      var a = document.createElement('a');
      a.className = 'jd-sc-link';
      a.href = href;
      a.textContent = val;
      el.appendChild(a);
    } else {
      el.textContent = val;
    }
  }

  // ── Match section ────────────────────────────────────────────
  function loadUserSkillsThenMatch() {
    // Match is only relevant for personal accounts that may apply.
    if (!_authed || _snap.userType !== 'emp') return;
    twApi('/profile/' + _snap.userId + '/full').then(function (res) {
      var skillSet = new Set();
      var prof = res.ok && res.data ? res.data.profile : null;
      (prof && prof.skills || []).forEach(function (s) {
        var name = _skillName(s).toLowerCase().trim();
        if (name) skillSet.add(name);
      });
      // tw_user cache fallback (getTwUser — tw_shared.js) — not source of truth
      if (!skillSet.size && _user) {
        (_user.skills || []).forEach(function (s) {
          var name = _skillName(s).toLowerCase().trim();
          if (name) skillSet.add(name);
        });
      }
      _computeAndRenderMatch(_job, skillSet);
    });
  }

  function _computeAndRenderMatch(job, userSkillSet) {
    var jobSkills = (job.skills || []).map(function (s) { return String(s).toLowerCase().trim(); });
    if (!jobSkills.length || !userSkillSet.size) { renderMatch(null); return; }
    var matched = jobSkills.filter(function (s) { return userSkillSet.has(s); });
    var missing  = jobSkills.filter(function (s) { return !userSkillSet.has(s); });
    var pct = Math.round((matched.length / jobSkills.length) * 100);
    renderMatch(pct, matched, missing);
  }

  function renderMatch(pct, matched, missing) {
    var sec = _el('jdMatchSection');
    if (!sec || (_job && _isOwner(_job))) return;

    var ring = _el('jdMatchRing');
    var body = _el('jdMatchBody');
    var pSpan = ring ? ring.querySelector('.jd-match-pct') : null;
    var lSpan = ring ? ring.querySelector('.jd-match-lbl') : null;

    if (pct === null || pct === undefined) {
      if (ring) ring.style.removeProperty('--jd-match-pct');
      if (pSpan) pSpan.textContent = '–';
      if (lSpan) lSpan.textContent = '';
      if (body) {
        body.textContent = '';
        var p = document.createElement('p');
        p.className = 'jd-match-noskills';
        p.textContent = twT('job.match.noskills') + ' ';
        var lnk = document.createElement('a');
        lnk.href = twAccountHref(_user); lnk.textContent = twT('job.match.complete');   // Auth Gateway rule 3
        p.appendChild(lnk);
        body.appendChild(p);
      }
      sec.classList.remove('hidden');
      return;
    }

    var level = pct >= 80 ? 'high' : pct >= 50 ? 'good' : 'partial';
    // Ring fill = CSS conic-gradient driven by --jd-match-pct (colors stay tokens in job-detail.css)
    if (ring) ring.style.setProperty('--jd-match-pct', pct + '%');
    if (pSpan) pSpan.textContent = pct + '%';
    if (lSpan) lSpan.textContent = twT('job.match.' + level);

    if (body) {
      body.textContent = '';
      var title = document.createElement('div');
      title.className = 'jd-match-title';
      title.textContent = twT('job.match.title_' + level, { pct: pct });
      body.appendChild(title);

      if (matched.length || missing.length) {
        var chips = document.createElement('div');
        chips.className = 'jd-match-skills';
        matched.slice(0, 5).forEach(function (s) {
          var sp = document.createElement('span');
          sp.className = 'jd-ms yes';
          sp.appendChild(twIconEl('check', { size: 'xs' }));
          sp.appendChild(document.createTextNode(s));
          chips.appendChild(sp);
        });
        missing.slice(0, 4).forEach(function (s) {
          var sp = document.createElement('span');
          sp.className = 'jd-ms no';
          sp.appendChild(twIconEl('close', { size: 'xs' }));
          sp.appendChild(document.createTextNode(s));
          chips.appendChild(sp);
        });
        body.appendChild(chips);
      }
    }
    sec.classList.remove('hidden');
  }

  // ── Similar jobs ─────────────────────────────────────────────
  function loadSimilarJobs() {
    twApi('/jobs').then(function (res) {
      var list = _el('jdSimilarList');
      if (!list) return;
      var jobs = res.ok && res.data && Array.isArray(res.data.jobs) ? res.data.jobs : [];
      var jobProfId = _job && _job.profession_id ? _job.profession_id : null;
      var jobSkills = (_job && _job.skills ? _job.skills : [])
        .map(function (s) { return String(_skillName(s)).toLowerCase().trim(); })
        .filter(Boolean);

      // Score each candidate: only jobs with a real signal appear
      var similar = jobs
        .filter(function (j) { return String(j.id) !== String(_jobId); })
        .map(function (j) {
          var score = 0;
          if (jobProfId && j.profession_id && j.profession_id === jobProfId) score += 3;
          (j.skills || []).forEach(function (s) {
            if (jobSkills.indexOf(String(_skillName(s)).toLowerCase().trim()) !== -1) score += 1;
          });
          return { job: j, score: score };
        })
        .filter(function (item) { return item.score > 0; })
        .sort(function (a, b) { return b.score - a.score; })
        .slice(0, 3)
        .map(function (item) { return item.job; });

      list.textContent = '';
      if (!similar.length) {
        var p = document.createElement('p');
        p.className = 'jd-sim-empty';
        p.textContent = twT('job.similar_empty');
        list.appendChild(p);
        return;
      }
      similar.forEach(function (j) {
        var item = document.createElement('a');   // a real link (was a div with a click handler)
        item.className = 'jd-sim-item';
        item.href = '/job-detail?id=' + encodeURIComponent(j.id);
        var av = document.createElement('span');
        av.className = 'jd-sim-av';
        av.appendChild(twIconEl('building-2', { size: 'md' }));
        var info = document.createElement('span');
        info.className = 'jd-sim-info';
        var t = document.createElement('span'); t.className = 'jd-sim-title'; t.textContent = j.title || '';
        var c = document.createElement('span'); c.className = 'jd-sim-co';
        c.textContent = (j.company_name || '') + (j.location ? ' · ' + j.location : '');
        info.appendChild(t); info.appendChild(c);
        item.appendChild(av); item.appendChild(info);
        list.appendChild(item);
      });
    });
  }

  // ── Owner mode — ownership title; no save / sticky bar / match ─
  // (apply / report visibility for the owner comes from the Actions Registry, not from here)
  function _isOwner(job) {
    return !!(_authed && job && (_snap.userType === 'co' || _snap.userType === 'edu')
      && Number(_snap.userId) === Number(job.company_id));
  }

  function _applyOwnerMode(job) {
    if (!_isOwner(job)) return;
    _label(_el('jdApplyCardTitle'), twT('job.yours'), 'check', false);
    document.querySelectorAll('.jd-save-trigger').forEach(function (b) { b.hidden = true; });
    var stickyBar = _el('jdStickyBar');
    if (stickyBar) stickyBar.classList.add('hidden');
  }

  // ── Apply (twModal — DS-OVL) ─────────────────────────────────
  function openApply() {
    if (!_authed) { _toLogin(); return; }
    if (_applyState) return;
    var form = document.createElement('div');
    var hint = document.createElement('p');
    hint.className = 'jd-modal-hint';
    hint.textContent = twT('job.apply.hint');
    var field = document.createElement('div');
    field.className = 'tw-field';
    var lbl = document.createElement('label');
    lbl.htmlFor = 'jdCoverLetter';
    lbl.textContent = twT('job.apply.cover');
    var ta = document.createElement('textarea');
    ta.id = 'jdCoverLetter';
    ta.className = 'tw-textarea';
    ta.rows = 4;
    ta.placeholder = twT('job.apply.cover_ph');
    field.appendChild(lbl); field.appendChild(ta);
    form.appendChild(hint); form.appendChild(field);

    twModal({
      title: twT('job.apply.title', { title: (_job && _job.title) || twT('job.default_title') }),
      content: form,
      actions: [
        { text: twT('common.cancel'), variant: 'secondary' },
        { text: twT('job.apply.send'), variant: 'primary', onClick: function () { return submitApply(ta.value || ''); } },
      ],
    });
  }

  // Resolves true (close the modal) on success, false (keep it open) on failure.
  function submitApply(cover) {
    if (!_jobId) return Promise.resolve(false);
    return twApi('/jobs/' + _jobId + '/apply', { method: 'POST', body: { cover_letter: cover } })
      .then(function (res) {
        if (!res.ok) {
          var msg = res.status === 403 ? twT('job.apply.emp_only')
                  : twApiMessage(res, twT('job.apply.err'));
          showToast(msg, 'error');
          return false;
        }
        var dup = !!(res.data && res.data.already_applied);
        _applyState = 'applied';
        _renderApply();
        showToast(twT(dup ? 'job.apply.duplicate' : 'job.apply.ok'), dup ? 'info' : 'success');
        return true;
      });
  }

  // ── Share ────────────────────────────────────────────────────
  function shareJob() {
    var title = (_job && _job.title) ? _job.title : twT('job.share.default_title');
    var url   = location.href;
    if (navigator.share) {
      navigator.share({ title: title, url: url }).catch(function () {});
    } else if (navigator.clipboard) {
      navigator.clipboard.writeText(url)
        .then(function () { showToast(twT('job.share.copied')); })
        .catch(function () { showToast(twT('job.share.link', { url: url }), 'info'); });
    }
  }

  // ── Report (twModal — DS-OVL · select = DS-SEL) ──────────────
  var _REPORT_TYPES = ['fraud', 'spam', 'misleading', 'harassment', 'other'];

  function openReport() {
    if (!_authed) { _toLogin(); return; }   // /reports/submit requires a JWT
    var form = document.createElement('div');

    var f1 = document.createElement('div'); f1.className = 'tw-field';
    var l1 = document.createElement('label'); l1.htmlFor = 'jdReportType'; l1.textContent = twT('job.report.type');
    var sel = document.createElement('select'); sel.id = 'jdReportType'; sel.className = 'tw-select ep-select';
    _REPORT_TYPES.forEach(function (t) {
      var o = document.createElement('option'); o.value = t; o.textContent = twT('job.report.' + t);
      sel.appendChild(o);
    });
    f1.appendChild(l1); f1.appendChild(sel);

    var f2 = document.createElement('div'); f2.className = 'tw-field';
    var l2 = document.createElement('label'); l2.htmlFor = 'jdReportReason'; l2.textContent = twT('job.report.details');
    var ta = document.createElement('textarea'); ta.id = 'jdReportReason'; ta.className = 'tw-textarea';
    ta.rows = 3; ta.placeholder = twT('job.report.details_ph');
    f2.appendChild(l2); f2.appendChild(ta);

    form.appendChild(f1); form.appendChild(f2);

    twModal({
      title: twT('job.report.title'),
      content: form,
      actions: [
        { text: twT('common.cancel'), variant: 'secondary' },
        { text: twT('job.report.send'), variant: 'danger', onClick: function () {
            return submitReport(sel.value || 'other', ta.value.trim());
          } },
      ],
    });
    if (window.scSelectInit) scSelectInit();   // DS-SEL engine for the report type
  }

  function submitReport(type, reason) {
    if (!reason) { showToast(twT('job.report.need_reason'), 'error'); return false; }
    return twApi('/reports/submit', { method: 'POST', body: {
      reported_id: _jobId, reported_type: 'job', report_type: type,
      reason: reason, target_url: location.href,
    } }).then(function (res) {
      if (!res.ok) { showToast(twApiMessage(res, twT('job.report.err')), 'error'); return false; }
      showToast(twT('job.report.ok'));
      return true;
    });
  }

  // ── Init ─────────────────────────────────────────────────────
  function _init() {
    twIcon.hydrate(document.body);   // static <i data-tw-icon> placeholders (DS-ICON)
    // Header + back button = unified app chrome (tw_shared.js twMountAppChrome — HEADER-NAV.md)
    document.querySelectorAll('.jd-save-trigger').forEach(function (btn) {
      btn.addEventListener('click', toggleSave);
    });
    loadJob();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', _init);
  } else {
    _init();
  }

}());
