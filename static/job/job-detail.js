/* job-detail.js — Job detail page logic
 * Security: all fetch calls use Authorization: Bearer {jwt} only — via getAuthHeaders() (tw_shared.js).
 * XSS safety: all API data set via textContent, never innerHTML.
 * Shared systems (Phase C — PAGE-SHELL / ICON / IMAGE / FEEDBACK):
 *   session  → TwAuthSync.getSessionSnapshot() (public page; guest actions → twLoginHref(this job))
 *   icons    → twIcon.hydrate (static <i data-tw-icon> in the HTML) / twIconEl (dynamic) — DS-ICON
 *   logos    → twAvatarHtml (tw_shared.js)
 *   feedback → showToast (tw_shared.js — F34)
 */
(function () {
  'use strict';

  // ── Auth & state ────────────────────────────────────────────
  // Public page: visitors read the job without login. The session is decided by
  // TwAuthSync.getSessionSnapshot() only (VM-10) — never by tw_user alone.
  // Not authenticated (guest / expired / stale / invalid) → guest view; actions that
  // need an account send the visitor to /login?next=<this job> (_toLogin — NAV-07).
  var _snap   = (window.TwAuthSync && typeof TwAuthSync.getSessionSnapshot === 'function')
    ? TwAuthSync.getSessionSnapshot() : null;
  var _authed = !!(_snap && _snap.isAuthenticated);
  var _user   = _authed ? getTwUser() : null;   // display cache (tw_id / name) — tw_shared.js

  // Authorization header for an authenticated session (getAuthHeaders — tw_shared.js); none for guests.
  function _hdrs(json) {
    if (_authed) return getAuthHeaders(json);
    return json ? { 'Content-Type': 'application/json' } : {};
  }

  // twLoginHref (tw_shared.js) validates the internal path and encodes it as ?next=.
  function _toLogin() { location.href = twLoginHref(location.pathname + location.search); }

  var _jobId   = null;
  var _job     = null;
  var _applied = false;

  // ── Utility ─────────────────────────────────────────────────
  function _el(id) { return document.getElementById(id); }

  var _JOB_TYPES = {
    full_time: 'دوام كامل',
    part_time: 'دوام جزئي',
    contract:  'عقد',
    freelance: 'فريلانس',
    internship:'تدريب',
    remote:    'عن بُعد'
  };

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
    if (diff < 60)      return 'الآن';
    if (diff < 3600)    return Math.floor(diff / 60) + ' دقيقة';
    if (diff < 86400)   return Math.floor(diff / 3600) + ' ساعة';
    if (diff < 2592000) return Math.floor(diff / 86400) + ' يوم';
    if (diff < 31536000)return Math.floor(diff / 2592000) + ' شهر';
    return Math.floor(diff / 31536000) + ' سنة';
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

  // ── Save (placeholder — full feature in future PR with backend) ──
  function toggleSave() {
    if (!_authed) { _toLogin(); return; }
    showToast('ميزة حفظ الوظائف قريباً', 'info');
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
    var box = _el('jdStateBox');
    if (!box) return;
    box.innerHTML = '';
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
      btn.className = 'jd-retry'; _label(btn, 'رجوع', 'back', true);
      btn.onclick = function () { history.back(); };
      box.appendChild(btn);
    }
    box.classList.remove('hidden');
  }

  // ── Load job ────────────────────────────────────────────────
  function loadJob() {
    var raw = new URLSearchParams(location.search).get('id');
    _jobId = raw ? parseInt(raw, 10) || null : null;
    if (!_jobId) {
      showState('error', 'رقم الوظيفة مفقود', 'الرجاء العودة وإعادة المحاولة');
      return;
    }
    showSkeleton();
    fetch('/jobs/' + _jobId, { headers: _hdrs() })
    .then(function (r) {
      if (r.status === 404) {
        var err = new Error('notfound'); err.code = 404; throw err;
      }
      if (!r.ok) { var e2 = new Error('fail'); throw e2; }
      return r.json();
    })
    .then(function (data) {
      _job = data.job;
      if (!_job) { var e3 = new Error('notfound'); e3.code = 404; throw e3; }
      hideSkeleton();
      renderJob(_job);
      _applyOwnerMode(_job);
      showContent();
      _checkJobStatus(_job);
      loadUserSkillsThenMatch();
      loadSimilarJobs();
      _checkAlreadyApplied();
    })
    .catch(function (err) {
      hideSkeleton();
      if (err.code === 404) {
        showState('error', 'الوظيفة غير موجودة', 'ربما تم حذف هذه الوظيفة أو انتهت صلاحيتها');
      } else {
        showState('error', 'حدث خطأ في التحميل', 'تحقق من اتصال الإنترنت ثم حاول مجدداً');
      }
    });
  }

  // Disable apply button when job is paused or closed.
  function _checkJobStatus(job) {
    if (!job || job.status === 'active') return;
    var msg = job.status === 'paused' ? 'التقديم موقوف مؤقتاً' : 'انتهى التقديم';
    document.querySelectorAll('.jd-apply-trigger').forEach(function (b) {
      _label(b, msg);
      b.disabled = true;
      b.classList.add('applied');
    });
    _applied = true;
  }

  // Check if the logged-in employee has already applied, then disable the button.
  function _checkAlreadyApplied() {
    if (!_authed || _snap.userType !== 'emp') return;
    fetch('/my/applications', { headers: _hdrs() })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (data) {
        if (!data || !Array.isArray(data.applications)) return;
        var already = data.applications.some(function (a) {
          return String(a.job_id) === String(_jobId);
        });
        if (!already) return;
        _applied = true;
        document.querySelectorAll('.jd-apply-trigger').forEach(function (b) {
          _label(b, 'تم التقديم', 'check', true); b.classList.add('applied'); b.disabled = true;
        });
      })
      .catch(function () {});
  }

  // ── Render job ──────────────────────────────────────────────
  function renderJob(job) {
    document.title = 'تواصلنا — ' + (job.title || 'وظيفة');

    // Company logo — DS-IMAGE (F38): org = rounded square; URL checked by twSafeImageUrl inside.
    // company_user_type (GET /jobs/{id}) = users.user_type of the publisher (co | edu) → fallback colour;
    // missing on an old cached response → 'co'.
    var _coEntity = { full_name: job.company_name, avatar_url: job.company_logo,
                      user_type: job.company_user_type === 'edu' ? 'edu' : 'co' };
    var logoEl = _el('jdLogo');
    if (logoEl) {
      logoEl.innerHTML = twAvatarHtml(_coEntity, 'xl', { eager: true });
      var logoBadge = _el('jdLogoBadge');
      if (logoBadge) logoBadge.style.display = job.company_verified ? 'flex' : 'none';
    }

    // Title
    var titleEl = _el('jdTitle');
    if (titleEl) titleEl.textContent = job.title || '';

    // Company name + verified badge
    var coEl = _el('jdCoName');
    if (coEl) {
      coEl.textContent = job.company_name || '';
      if (job.company_verified) {
        var badge = document.createElement('span');
        badge.className = 'jd-co-badge'; badge.title = 'شركة موثقة';
        badge.appendChild(twIconEl('check', { size: 'xs' }));
        coEl.appendChild(badge);
      }
      if (job.company_tw_id) {
        coEl.onclick = function () { location.href = '/u/' + job.company_tw_id; };
      }
    }

    // Meta chips
    var metaEl = _el('jdMeta');
    if (metaEl) {
      metaEl.innerHTML = '';
      if (job.location)    metaEl.appendChild(_chip('map-pin', job.location));
      if (job.job_type)    metaEl.appendChild(_chip('clock', _JOB_TYPES[job.job_type] || job.job_type));
      if (job.work_mode)   metaEl.appendChild(_chip('laptop', job.work_mode));
      if (job.experience_years && job.experience_years > 0)
        metaEl.appendChild(_chip('bar-chart-2', job.experience_years + ' سنوات خبرة'));
      if (job.salary_hidden) {
        metaEl.appendChild(_chip('circle-dollar-sign', 'الراتب غير معلن'));
      } else if (job.salary_min) {
        var sal = job.salary_min + (job.salary_max ? '–' + job.salary_max : '+') +
                  (job.currency ? ' ' + job.currency : '');
        metaEl.appendChild(_chip('circle-dollar-sign', sal, 'g'));
      }
      if (job.profession_name_ar) metaEl.appendChild(_chip(job.profession_icon || 'briefcase', job.profession_name_ar, 'b'));
      if (job.created_at) metaEl.appendChild(_chip('calendar', _timeAgo(job.created_at)));
    }

    // Skill tags in header
    var tagsEl = _el('jdTags');
    if (tagsEl) {
      tagsEl.innerHTML = '';
      (job.skills || []).slice(0, 8).forEach(function (s) {
        var sIcon = (window.TW && TW.getSkillIcon) ? (TW.getSkillIcon(s) || 'tag') : 'tag';
        var chip = _chip(sIcon, s, 'g');
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
      skillsEl.innerHTML = '';
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
      if (job.accepts_all_professions) {
        accProfEl.innerHTML = '';
        var allSpan = document.createElement('span');
        allSpan.className = 'jd-skill-chip';
        allSpan.appendChild(twIconEl('users', { size: 'sm' }));
        allSpan.appendChild(document.createTextNode(' مفتوح لجميع التخصصات'));
        accProfEl.appendChild(allSpan);
        if (as) as.classList.remove('hidden');
      } else if (job.accepted_professions && job.accepted_professions.length) {
        accProfEl.innerHTML = '';
        job.accepted_professions.forEach(function (p) {
          var span = document.createElement('span');
          span.className = 'jd-skill-chip';
          span.appendChild(twIconEl(p.icon || 'briefcase', { size: 'sm' }));
          span.appendChild(document.createTextNode(' ' + (p.name_ar || p.name_en || '')));
          accProfEl.appendChild(span);
        });
        if (as) as.classList.remove('hidden');
      }
    }

    // Sidebar — job info rows
    _sideVal('jdSiCo',   job.company_name,
      job.company_tw_id ? function () { location.href = '/u/' + job.company_tw_id; } : null);
    _sideVal('jdSiLoc',  job.location);
    _sideVal('jdSiType', job.job_type ? (_JOB_TYPES[job.job_type] || job.job_type) : null);
    _sideVal('jdSiMode', job.work_mode || null);
    var _expLabel = (function() {
      if (job.experience_years === undefined || job.experience_years === null) return null;
      if (window.TW && TW.EXP_LEVELS) {
        for (var _ei = 0; _ei < TW.EXP_LEVELS.length; _ei++) {
          if (TW.EXP_LEVELS[_ei].value === job.experience_years) return TW.EXP_LEVELS[_ei].label;
        }
      }
      return job.experience_years > 0 ? job.experience_years + ' سنوات' : null;
    }());
    _sideVal('jdSiExp', _expLabel);
    _sideVal('jdSiSal',  job.salary_hidden
      ? 'الراتب غير معلن'
      : (job.salary_min
          ? job.salary_min + (job.salary_max ? '–' + job.salary_max : '+') + (job.currency ? ' ' + job.currency : '')
          : null));
    _sideVal('jdSiViews', job.views ? job.views + ' مشاهدة' : null);
    _sideVal('jdSiDate', job.created_at
      ? new Date(job.created_at).toLocaleDateString('ar-SA', { year: 'numeric', month: 'long', day: 'numeric' })
      : null);

    // Sidebar — company card
    var coAvEl = _el('jdCoCardAv');
    if (coAvEl) coAvEl.innerHTML = twAvatarHtml(_coEntity, 'lg');
    var cnEl = _el('jdCoCardName');
    if (cnEl) {
      cnEl.textContent = job.company_name || '';
      if (job.company_tw_id) {
        cnEl.onclick = function () { location.href = '/u/' + job.company_tw_id; };
      }
    }
    var cvEl = _el('jdCoCardVerif');
    if (cvEl) {
      if (job.company_verified) _label(cvEl, 'شركة موثقة', 'check', true);
      else cvEl.textContent = '';
    }

    // Apply modal title
    var mt = _el('jdModalTitle');
    if (mt) mt.textContent = 'تقديم على: ' + (job.title || 'الوظيفة');
  }

  function _sideVal(id, val, onClick) {
    var el = _el(id);
    if (!el) return;
    if (val) {
      el.textContent = val;
      if (onClick) { el.classList.add('link'); el.onclick = onClick; }
    } else {
      var row = el.closest('.jd-sc-row');
      if (row) row.style.display = 'none';
    }
  }

  // ── Match section ────────────────────────────────────────────
  function loadUserSkillsThenMatch() {
    // Match is only relevant for employees who may apply.
    if (!_authed || _snap.userType !== 'emp') {
      var sec = _el('jdMatchSection');
      if (sec) sec.style.display = 'none';
      return;
    }
    fetch('/profile/' + _snap.userId + '/full', { headers: _hdrs() })
    .then(function (r) { return r.ok ? r.json() : null; })
    .then(function (data) {
      var skillSet = new Set();
      if (data && data.profile && data.profile.skills) {
        data.profile.skills.forEach(function (s) {
          var name = _skillName(s).toLowerCase().trim();
          if (name) skillSet.add(name);
        });
      }
      // tw_user cache fallback (getTwUser — tw_shared.js) — not source of truth
      if (!skillSet.size && _user) {
        (_user.skills || []).forEach(function (s) {
          var name = _skillName(s).toLowerCase().trim();
          if (name) skillSet.add(name);
        });
      }
      _computeAndRenderMatch(_job, skillSet);
    })
    .catch(function () { _computeAndRenderMatch(_job, new Set()); });
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
    if (!sec) return;

    var ring = _el('jdMatchRing');
    var body = _el('jdMatchBody');

    if (pct === null || pct === undefined) {
      // No skills available
      if (ring) {
        ring.style.background = 'rgba(255,255,255,.06)';
        var pctSpan = ring.querySelector('.jd-match-pct');
        if (pctSpan) pctSpan.textContent = '–';
        var lblSpanNull = ring.querySelector('.jd-match-lbl');
        if (lblSpanNull) lblSpanNull.textContent = '';
      }
      if (body) {
        body.innerHTML = '';
        var p = document.createElement('p');
        p.className = 'jd-match-noskills';
        p.textContent = 'أضف مهاراتك في ملفك الشخصي لرؤية نسبة التطابق. ';
        var lnk = document.createElement('a');
        lnk.href = twAccountHref(_user); lnk.textContent = 'أكمل مهاراتك الآن';   // tw_shared.js (Auth Gateway rule 3)
        p.appendChild(lnk);
        body.appendChild(p);
      }
      sec.classList.remove('hidden');
      return;
    }

    // Update ring with conic-gradient
    if (ring) {
      var pStr = pct + '%';
      ring.style.background = 'conic-gradient(var(--ac) 0% ' + pStr +
        ', rgba(255,255,255,.08) ' + pStr + ')';
      var pSpan = ring.querySelector('.jd-match-pct');
      if (pSpan) pSpan.textContent = pStr;
      var lSpan = ring.querySelector('.jd-match-lbl');
      if (lSpan) lSpan.textContent = pct >= 80 ? 'عالي' : pct >= 50 ? 'جيد' : 'جزئي';
    }

    if (body) {
      body.innerHTML = '';
      var title = document.createElement('div');
      title.className = 'jd-match-title';
      title.textContent =
        pct >= 80 ? 'ملفك يتطابق بنسبة ' + pct + '% مع هذه الوظيفة!' :
        pct >= 50 ? 'تطابق جيد — ' + pct + '% من المهارات' :
                   'تطابق جزئي — ' + pct + '% من المهارات';
      body.appendChild(title);

      if (matched.length || missing.length) {
        var chips = document.createElement('div');
        chips.className = 'jd-match-skills';
        matched.slice(0, 5).forEach(function (s) {
          var sp = document.createElement('span');
          sp.className = 'jd-ms yes';
          sp.appendChild(twIconEl('check', { size: 'xs' }));
          sp.appendChild(document.createTextNode(' ' + s));
          chips.appendChild(sp);
        });
        missing.slice(0, 4).forEach(function (s) {
          var sp = document.createElement('span');
          sp.className = 'jd-ms no';
          sp.appendChild(twIconEl('close', { size: 'xs' }));
          sp.appendChild(document.createTextNode(' ' + s));
          chips.appendChild(sp);
        });
        body.appendChild(chips);
      }
    }

    sec.classList.remove('hidden');
  }

  // ── Similar jobs ─────────────────────────────────────────────
  function loadSimilarJobs() {
    fetch('/jobs', { headers: _hdrs() })
    .then(function (r) { return r.json(); })
    .then(function (data) {
      var jobProfId = _job && _job.profession_id ? _job.profession_id : null;
      var jobSkills = (_job && _job.skills ? _job.skills : [])
        .map(function (s) { return String(_skillName(s)).toLowerCase().trim(); })
        .filter(Boolean);

      var all = (data.jobs || []).filter(function (j) { return String(j.id) !== String(_jobId); });

      // Score each candidate: only jobs with a real signal appear
      var scored = all.map(function (j) {
        var score = 0;
        if (jobProfId && j.profession_id && j.profession_id === jobProfId) score += 3;
        if (jobSkills.length) {
          var jSkills = (j.skills || [])
            .map(function (s) { return String(_skillName(s)).toLowerCase().trim(); })
            .filter(Boolean);
          jSkills.forEach(function (s) { if (jobSkills.indexOf(s) !== -1) score += 1; });
        }
        return { job: j, score: score };
      });

      var similar = scored
        .filter(function (item) { return item.score > 0; })
        .sort(function (a, b) { return b.score - a.score; })
        .slice(0, 3)
        .map(function (item) { return item.job; });

      ['jdSimilarList', 'jdSimilarListMobile'].forEach(function (cid) {
        var el = _el(cid); if (!el) return;
        el.innerHTML = '';
        if (!similar.length) {
          var p = document.createElement('p');
          p.className = 'jd-sim-empty';
          p.textContent = 'لا توجد وظائف مشابهة حالياً';
          el.appendChild(p); return;
        }
        similar.forEach(function (j) {
          var item = document.createElement('div');
          item.className = 'jd-sim-item';
          var av = document.createElement('div');
          av.className = 'jd-sim-av';
          av.appendChild(twIconEl('building-2', { size: 'md' }));
          var info = document.createElement('div');
          var t = document.createElement('div'); t.className = 'jd-sim-title'; t.textContent = j.title || '';
          var c = document.createElement('div'); c.className = 'jd-sim-co';
          c.textContent = (j.company_name || '') + (j.location ? ' · ' + j.location : '');
          info.appendChild(t); info.appendChild(c);
          item.appendChild(av); item.appendChild(info);
          (function (jid) {
            item.addEventListener('click', function () { location.href = '/job-detail?id=' + jid; });
          }(j.id));
          el.appendChild(item);
        });
      });
    })
    .catch(function () {});
  }

  // ── Owner mode — hide apply, show ownership badge ────────────
  function _applyOwnerMode(job) {
    if (!_authed || !job) return;
    var isOwner = (_snap.userType === 'co' || _snap.userType === 'edu')
      && parseInt(_snap.userId, 10) === job.company_id;
    if (!isOwner) return;

    // Sidebar card: change title, hide actions
    var title = _el('jdApplyCardTitle');
    _label(title, 'هذه وظيفتك', 'check', false);
    var actions = document.querySelector('.jd-apply-actions');
    if (actions) actions.style.display = 'none';

    // Mobile sticky bar: hide entirely
    var stickyBar = _el('jdStickyBar');
    if (stickyBar) stickyBar.style.display = 'none';

    // Match section is irrelevant for the job owner
    var matchSec = _el('jdMatchSection');
    if (matchSec) matchSec.style.display = 'none';
  }

  // ── Apply ────────────────────────────────────────────────────
  function openApply() {
    if (!_authed) { _toLogin(); return; }
    if (_snap.userType !== 'emp') {
      showToast('التقديم متاح للموظفين فقط', 'error');
      return;
    }
    if (_applied) return;
    var ov = _el('jdApplyOverlay');
    if (ov) ov.classList.add('show');
  }

  function closeApply(ev) {
    if (!ev || ev.target.id === 'jdApplyOverlay') {
      var ov = _el('jdApplyOverlay');
      if (ov) ov.classList.remove('show');
    }
  }

  function confirmApply() {
    if (!_authed) { _toLogin(); return; }
    if (!_jobId) { showToast('خطأ في معرّف الوظيفة', 'error'); return; }
    var cover = _el('jdCoverLetter') ? (_el('jdCoverLetter').value || '') : '';
    var triggers = document.querySelectorAll('.jd-apply-trigger');
    triggers.forEach(function (b) { b.disabled = true; _label(b, 'جاري التقديم...'); });
    fetch('/jobs/' + _jobId + '/apply', {
      method: 'POST',
      headers: _hdrs(true),
      body: JSON.stringify({ cover_letter: cover })
    })
    .then(function (r) {
      return r.json().then(function (data) {
        if (!r.ok) {
          var err = new Error(data.detail || 'apply_failed');
          err.statusCode = r.status;
          throw err;
        }
        return data;
      });
    })
    .then(function (data) {
      _applied = true;
      var label = data.already_applied ? 'قدّمت مسبقاً' : 'تم التقديم';
      triggers.forEach(function (b) {
        b.disabled = true; _label(b, label, 'check', true); b.classList.add('applied');
      });
      closeApply();
      showToast(data.already_applied ? 'لقد قدّمت على هذه الوظيفة مسبقاً' : 'تم إرسال طلبك بنجاح');
    })
    .catch(function (err) {
      triggers.forEach(function (b) { b.disabled = false; _label(b, 'تقديم الآن', 'forward', false); });
      var msg = (err && err.statusCode === 403)
        ? 'التقديم متاح للموظفين فقط'
        : 'حدث خطأ أثناء التقديم، حاول مجدداً';
      showToast(msg, 'error');
    });
  }

  // ── Share ────────────────────────────────────────────────────
  function shareJob() {
    var title = (_job && _job.title) ? _job.title : 'وظيفة على تواصلنا';
    var url   = location.href;
    if (navigator.share) {
      navigator.share({ title: title, url: url }).catch(function () {});
    } else if (navigator.clipboard) {
      navigator.clipboard.writeText(url)
        .then(function () { showToast('تم نسخ رابط الوظيفة'); })
        .catch(function () { showToast('رابط: ' + url, 'info'); });
    }
  }

  // ── Report ───────────────────────────────────────────────────
  function openReport() {
    if (!_authed) { _toLogin(); return; }   // /reports/submit requires a JWT
    var s = _el('jdReportSheet');
    if (s) s.classList.add('open');
    var r = _el('jdReportReason');
    if (r) r.value = '';
  }

  function closeReport() {
    var s = _el('jdReportSheet');
    if (s) s.classList.remove('open');
  }

  function submitReport() {
    var type   = _el('jdReportType')   ? _el('jdReportType').value   : 'other';
    var reason = _el('jdReportReason') ? _el('jdReportReason').value.trim() : '';
    if (!reason) { showToast('اكتب سبب البلاغ', 'error'); return; }
    var btn = _el('jdReportSubmitBtn');
    if (btn) { btn.disabled = true; _label(btn, 'جاري الإرسال...'); }
    fetch('/reports/submit', {
      method: 'POST',
      headers: _hdrs(true),
      body: JSON.stringify({
        reported_id:   _jobId,
        reported_type: 'job',
        report_type:   type,
        reason:        reason,
        target_url:    location.href
      })
    })
    .then(function (r) {
      if (r.ok) { showToast('تم إرسال البلاغ'); closeReport(); }
      else { showToast('خطأ في إرسال البلاغ', 'error'); }
    })
    .catch(function () { showToast('خطأ في إرسال البلاغ', 'error'); })
    .then(function () {
      if (btn) { btn.disabled = false; _label(btn, 'إرسال البلاغ', 'report', true); }
    });
  }

  // ── Init ─────────────────────────────────────────────────────
  function _init() {
    twIcon.hydrate(document.body);   // static <i data-tw-icon> placeholders (DS-ICON)
    if (window.initAppHeader) initAppHeader(_user);

    var backBtn = _el('jdBackBtn');
    if (backBtn) backBtn.addEventListener('click', function () { history.back(); });

    document.querySelectorAll('.jd-apply-trigger').forEach(function (btn) {
      btn.addEventListener('click', openApply);
    });

    document.querySelectorAll('.jd-share-trigger').forEach(function (btn) {
      btn.addEventListener('click', shareJob);
    });

    document.querySelectorAll('.jd-save-trigger').forEach(function (btn) {
      btn.addEventListener('click', toggleSave);
    });

    var overlay = _el('jdApplyOverlay');
    if (overlay) overlay.addEventListener('click', closeApply);

    var cancelBtn = _el('jdApplyCancel');
    if (cancelBtn) cancelBtn.addEventListener('click', function () { closeApply(); });

    var confirmBtn = _el('jdApplyConfirm');
    if (confirmBtn) confirmBtn.addEventListener('click', confirmApply);

    var reportBtn = _el('jdReportBtn');
    if (reportBtn) reportBtn.addEventListener('click', openReport);

    var reportClose = _el('jdReportClose');
    if (reportClose) reportClose.addEventListener('click', closeReport);

    var reportSubmit = _el('jdReportSubmitBtn');
    if (reportSubmit) reportSubmit.addEventListener('click', submitReport);

    loadJob();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', _init);
  } else {
    _init();
  }

}());
