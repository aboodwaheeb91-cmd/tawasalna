// company.render.js — pure render functions + DOM helpers
// All functions read companyState only. No API calls, no state mutation.
// Load order: 4th (after state + permissions)
(function () {
  'use strict';

  // ── DOM helpers ──────────────────────────────────────────────
  function _setText(id, value) {
    var el = document.getElementById(id);
    if (el) el.textContent = value;
  }

  function _esc(str) {
    return String(str || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  function _escapeHtml(s) {
    var d = document.createElement('div');
    d.textContent = s == null ? '' : String(s);
    return d.innerHTML;
  }

  function _relativeTime(iso) {
    if (!iso) return '';
    var then = new Date(iso).getTime();
    if (isNaN(then)) return '';
    var diff = Math.floor((Date.now() - then) / 1000);
    if (diff < 60)      return 'الآن';
    if (diff < 3600)    return 'منذ ' + Math.floor(diff / 60) + ' دقيقة';
    if (diff < 86400)   return 'منذ ' + Math.floor(diff / 3600) + ' ساعة';
    if (diff < 604800)  return 'منذ ' + Math.floor(diff / 86400) + ' يوم';
    if (diff < 2592000) return 'منذ ' + Math.floor(diff / 604800) + ' أسبوع';
    return new Date(iso).toLocaleDateString('ar');
  }

  function _starsString(score, filled, empty) {
    var n = Math.round(score || 0);
    var s = '';
    for (var i = 1; i <= 5; i++) s += (i <= n ? filled : empty);
    return s;
  }

  function _paintRateStars(score) {
    document.querySelectorAll('#rateStars span').forEach(function (s) {
      s.textContent = (parseInt(s.getAttribute('data-score')) <= score) ? '⭐' : '☆';
    });
  }

  // ── Profile ──────────────────────────────────────────────────
  function renderProfile() {
    var p    = companyState.profile;
    var name = p.full_name || '—';

    // Cover: show saved cover_url on top of the CSS fallback background
    var coverUrl = companyState.company && companyState.company.cover_url;
    if (coverUrl && window.setCover) window.setCover(coverUrl);

    _setText('coName',   name);
    _setText('coDesc',   p.bio || 'لا يوجد وصف بعد.');

    document.querySelectorAll('[id^="postCoName"]').forEach(function (el) {
      el.textContent = name;
    });

    // Logo: use DOM createElement to avoid inline styles
    var logoEl = document.getElementById('coLogo');
    if (logoEl && p.avatar_url) {
      var img = document.createElement('img');
      img.src       = p.avatar_url;
      img.alt       = name;
      img.className = 'co-logo-img';
      logoEl.innerHTML = '';
      logoEl.appendChild(img);
    }

    // Verified badge (name row)
    var verifiedBadge = document.getElementById('coVerifiedBadge');
    if (verifiedBadge) {
      verifiedBadge.style.display = p.is_verified ? 'inline-flex' : 'none';
    }

    // Verified badge on logo
    var logoBadge = document.getElementById('coLogoBadge');
    if (logoBadge) {
      logoBadge.style.display = p.is_verified ? 'flex' : 'none';
    }

    // Industry label (replaces generic type badge)
    var badge = document.getElementById('coTypeBadge');
    if (badge) {
      var industry = companyState.company && companyState.company.industry;
      badge.textContent = industry || 'تصنيف غير محدد';
    }

    // Meta row: page URL (always the company's Tawasalna profile link, not p.website)
    var websiteEl      = document.getElementById('coWebsite');
    var websiteLink    = document.getElementById('coWebsiteLink');
    var websiteCopyBtn = document.getElementById('coWebsiteCopyBtn');
    var pageUrl  = window.location.href;
    var locParts = [p.country || '', p.city || '', p.location || ''].filter(Boolean);
    var locStr   = locParts.join(' - ');

    if (websiteEl) websiteEl.style.display = 'inline-flex';
    if (websiteLink) {
      websiteLink.href        = pageUrl;
      websiteLink.textContent = pageUrl.replace(/^https?:\/\//, '');
    }
    if (websiteCopyBtn) {
      websiteCopyBtn.onclick = function () {
        navigator.clipboard.writeText(pageUrl).then(function () {
          if (window.showToast) showToast('تم نسخ الرابط ✓');
        }).catch(function () {});
      };
    }
    var hqRow  = document.getElementById('coHqRow');
    var hqText = document.getElementById('coHqText');
    if (hqRow) hqRow.style.display = locStr ? 'flex' : 'none';
    if (hqText) {
      hqText.innerHTML = '';
      if (window.TW && TW.countryFlagEl && p.country) {
        var flagEl = TW.countryFlagEl(p.country);
        if (flagEl) { flagEl.style.marginLeft = '4px'; hqText.appendChild(flagEl); }
      }
      var hqSpan = document.createElement('span');
      hqSpan.textContent = locStr;
      hqText.appendChild(hqSpan);
    }
  }

  // ── Helpers ───────────────────────────────────────────────────
  function _fmtCount(n) {
    if (n == null || n === '') return '—';
    n = Number(n);
    if (isNaN(n)) return '—';
    if (n >= 1000000) { var m = n / 1000000; return (m % 1 === 0 ? m : m.toFixed(1)) + 'M'; }
    if (n >= 1000)    { var k = n / 1000;    return (k % 1 === 0 ? k : k.toFixed(1)) + 'K'; }
    return String(n);
  }

  function _fmtRating(r) {
    if (r == null || r === '') return '—';
    r = Number(r);
    if (isNaN(r) || r === 0) return '—';
    return r.toFixed(1);
  }

  // ── Stats ─────────────────────────────────────────────────────
  function renderStats() {
    var s = companyState.stats;
    _setText('jobsCount',       _fmtCount(s.jobs_count));
    _setText('postsCount',      _fmtCount(s.posts_count));
    _setText('viewsCount',      _fmtCount(s.views_count));
    _setText('followersCount',  _fmtCount(s.followers_count));
    _setText('followersCount2', _fmtCount(s.followers_count));
    _setText('ratingAvg',       _fmtRating(s.rating_avg));
  }

  // ── Jobs ──────────────────────────────────────────────────────
  function renderJobs() {
    var jobsList = document.getElementById('jobsList');
    if (!jobsList) return;

    if (!companyState.jobs.length) {
      jobsList.innerHTML =
        '<div class="tw-empty"><span class="tw-empty-ico"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" width="40" height="40"><rect width="20" height="14" x="2" y="7" rx="2"/><path d="M16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2"/><line x1="12" x2="12" y1="12" y2="12"/><path d="M12 12h.01"/></svg></span>' +
        '<div class="tw-empty-title">لا توجد وظائف مفتوحة</div>' +
        '<div class="tw-empty-sub">لم تُضف هذه الشركة أي وظائف بعد.</div></div>';
      if (window.bindEvents) bindEvents();
      return;
    }

    jobsList.innerHTML = companyState.jobs.map(function (j) {
      var canApply = companyState.viewMode !== 'owner';

      // ── Logo: company avatar or initial fallback ───────────────
      var avatarUrl = companyState.profile && companyState.profile.avatar_url;
      var logoHtml = avatarUrl
        ? '<img src="' + _esc(avatarUrl) + '" alt="" loading="lazy">'
        : '<span class="job-card-logo-init">'
            + _esc((companyState.profile && companyState.profile.full_name
                ? companyState.profile.full_name.charAt(0) : '؟'))
            + '</span>';

      // ── Profession sub-title ───────────────────────────────────
      var profName = (window._getProfName && j.profession_id)
        ? window._getProfName(j.profession_id) : '';
      var subHtml = profName
        ? '<div class="job-card-sub">' + _esc(profName) + '</div>' : '';

      // ── Relative date ──────────────────────────────────────────
      var relDate = '';
      if (j.created_at) {
        var diffDays = Math.floor((Date.now() - new Date(j.created_at).getTime()) / 86400000);
        if (diffDays === 0)       relDate = 'اليوم';
        else if (diffDays === 1)  relDate = 'أمس';
        else if (diffDays < 7)   relDate = 'منذ ' + diffDays + ' أيام';
        else if (diffDays < 30)  relDate = 'منذ ' + Math.floor(diffDays / 7) + ' أسابيع';
        else                      relDate = 'منذ ' + Math.floor(diffDays / 30) + ' أشهر';
      }

      // ── SVG icons ──────────────────────────────────────────────
      var icoPin  = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/></svg>';
      var icoBag  = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2"/><rect width="20" height="14" x="2" y="7" rx="2"/></svg>';

      // ── Meta chips (all viewers) ───────────────────────────────
      var chips = '';
      if (j.location)  chips += '<span class="job-meta-chip">' + icoPin + ' ' + _esc(j.location) + '</span>';
      if (j.job_type)  chips += '<span class="job-meta-chip">' + icoBag + ' ' + _esc(j.job_type) + '</span>';
      if (j.work_mode) chips += '<span class="job-meta-chip">' + _esc(j.work_mode) + '</span>';
      if (relDate)     chips += '<span class="job-meta-chip">' + _esc(relDate) + '</span>';

      // ── Owner: add status chip in meta ─────────────────────────
      if (!canApply) {
        var st0    = j.status || 'active';
        var stLbl0 = st0 === 'paused' ? 'موقوف' : st0 === 'closed' ? 'مغلق' : 'نشط';
        chips += '<span class="job-status-chip job-status-chip--' + _esc(st0) + '">' + stLbl0 + '</span>';
      }

      // ── Right panel ────────────────────────────────────────────
      var rightHtml;
      if (canApply) {
        rightHtml = '<button class="apply-btn-pill" data-jid="' + _esc(String(j.id)) + '">تقديم الآن</button>';
      } else {
        var jid = parseInt(j.id, 10);
        var st  = j.status || 'active';
        var cnt = parseInt(j.applicant_count, 10) || 0;
        rightHtml = '<div class="job-owner-col">'
          + '<span class="job-applicant-count">عدد المتقدمين: ' + cnt + '</span>'
          + '<button type="button" class="owner-applicants-btn" data-jid="' + jid + '">عرض المتقدمين</button>'
          + '<button type="button" class="job-mgmt-btn job-manage-btn" data-jid="' + jid + '" data-status="' + _esc(st) + '">إدارة</button>'
          + '</div>';
      }

      return '<div class="job-card tw-card-lift" data-jid="' + _esc(String(j.id)) + '">'
        + '<div class="job-card-logo">' + logoHtml + '</div>'
        + '<div class="job-card-body">'
          + '<div class="job-title">' + _esc(j.title) + '</div>'
          + subHtml
          + '<div class="job-card-meta">' + chips + '</div>'
        + '</div>'
        + rightHtml
        + '</div>';
    }).join('');

    if (window.bindEvents) bindEvents();
  }

  // ── Follow button ─────────────────────────────────────────────
  function renderFollowBtn() {
    var btn = document.getElementById('followBtn');
    if (!btn || !window.companyState) return;
    var following = !!companyState.permissions.is_following;
    btn.textContent = following ? '✓ متابَع' : '+ متابعة';
    btn.classList.toggle('following', following);
  }

  // ── Rating display ────────────────────────────────────────────
  function renderRating() {
    if (!window.companyState) return;
    var avg   = companyState.stats.rating_avg;
    var count = companyState.stats.rating_count || 0;
    var mine  = companyState.permissions ? companyState.permissions.my_rating : null;

    var starsStr = avg ? _starsString(avg, '⭐', '☆') : '☆☆☆☆☆';
    _setText('ratingStarsDisplay', starsStr);
    _setText('ratingNum',   avg != null ? avg : '—');

    var subText = count > 0
      ? ('من 5 — بناءً على ' + count + ' تقييم' + (count > 10 ? '' : 'ات'))
      : 'لا تقييمات بعد';
    _setText('ratingSub', subText);

    // Sync ratings tab panel
    _setText('ratingsTabStars', starsStr);
    _setText('ratingsTabAvg',   avg != null ? avg : '—');
    _setText('ratingsTabCount', subText);

    _paintRateStars(mine || 0);

    var prompt = document.getElementById('ratePrompt');
    if (prompt) {
      prompt.textContent = mine
        ? ('تقييمك: ' + mine + ' من 5 (اضغط للتعديل)')
        : 'قيّم هذه الشركة:';
    }
  }

  // ── Posts ─────────────────────────────────────────────────────
  function _postCardHtml(post) {
    var coName = (window.companyState && companyState.profile)
      ? (companyState.profile.full_name || 'الشركة') : 'الشركة';

    var tagsHtml = '';
    if (post.tags && post.tags.length) {
      tagsHtml = '<div class="job-tags">' + post.tags.map(function (t) {
        return '<span class="jtag jtag-green">' + _escapeHtml(t) + '</span>';
      }).join('') + '</div>';
    }

    var canEdit = window.companyState &&
      companyState.permissions && companyState.permissions.can_edit;
    var delBtn = canEdit
      ? '<button class="post-del" data-post-id="' + post.id + '" title="حذف">🗑</button>'
      : '';

    return '<div class="post-card">' +
      '<div class="post-head">' +
        '<div class="post-ava"><svg viewBox="0 0 24 24" fill="none" stroke="rgba(255,255,255,.9)" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M6 22V4a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v18Z"/><path d="M6 12H4a2 2 0 0 0-2 2v6a2 2 0 0 0 2 2h2"/><path d="M18 9h2a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2h-2"/><path d="M10 6h4"/><path d="M10 10h4"/></svg></div>' +
        '<div class="post-head-info">' +
          '<div class="post-nm">' + _escapeHtml(coName) + '</div>' +
          '<div class="post-date">' + _relativeTime(post.created_at) + '</div>' +
        '</div>' +
        delBtn +
      '</div>' +
      '<div class="post-body">' + _escapeHtml(post.body) + '</div>' +
      tagsHtml +
    '</div>';
  }

  function renderPosts(posts) {
    var list  = document.getElementById('postsList');
    var empty = document.getElementById('postsEmpty');
    if (!list) return;
    if (!posts || !posts.length) {
      list.innerHTML = '';
      if (empty) empty.style.display = 'block';
      return;
    }
    if (empty) empty.style.display = 'none';
    list.innerHTML = posts.map(_postCardHtml).join('');
  }

  // ── Branches (public display) ─────────────────────────────────
  // ── Branch label formatter — shared by compact chips and full sheet ──
  // Returns { parts: string[], sameAsHq: boolean }
  // Applies smart dedup: branch_name is omitted if it duplicates city or district.
  function _formatBranchLabel(b, hqCountry) {
    var sameAsHq = !!(hqCountry && window.TW && TW.sameCountry
      && TW.sameCountry(b.country, hqCountry));

    var name = (b.branch_name || '').trim();
    var city = (b.city        || '').trim();
    var dist = (b.district    || '').trim();
    var ctry = (b.country     || '').trim();

    var parts = [];
    if (name && name !== city && name !== dist) parts.push(name);
    if (!sameAsHq && ctry) parts.push(ctry);
    if (city) parts.push(city);
    if (dist && dist !== city) parts.push(dist);

    return { parts: parts, sameAsHq: sameAsHq };
  }

  function renderBranches(branches) {
    var row  = document.getElementById('coBranchesRow');
    var list = document.getElementById('coBranchesText');
    if (!row || !list) return;

    if (!branches || !branches.length) {
      row.style.display = 'none';
      list.innerHTML    = '';
      return;
    }

    var MAX       = 3;
    var shown     = branches.slice(0, MAX);
    var rest      = branches.length - MAX;
    var hqCountry = (window.companyState && companyState.profile)
      ? (companyState.profile.country || '') : '';

    list.innerHTML = '';
    shown.forEach(function (b, i) {
      if (i > 0) {
        var sep = document.createElement('span');
        sep.className   = 'co-branch-sep';
        sep.textContent = '|';
        list.appendChild(sep);
      }

      var chip = document.createElement('span');
      chip.className = 'co-branch-chip';

      // "فرع N:" prefix
      var numEl = document.createElement('span');
      numEl.className   = 'co-branch-num';
      numEl.textContent = 'فرع ' + (i + 1) + ':';
      chip.appendChild(numEl);

      var fmt = _formatBranchLabel(b, hqCountry);

      // Flag only when branch country differs from HQ
      if (!fmt.sameAsHq && b.country && window.TW && TW.countryFlagEl) {
        var fl = TW.countryFlagEl(b.country);
        if (fl) chip.appendChild(fl);
      }

      var chipTxt = document.createElement('span');
      chipTxt.textContent = fmt.parts.join(' - ');
      chip.appendChild(chipTxt);
      list.appendChild(chip);
    });

    if (rest > 0) {
      var sep2 = document.createElement('span');
      sep2.className   = 'co-branch-sep';
      sep2.textContent = '|';
      list.appendChild(sep2);

      var more = document.createElement('span');
      more.className   = 'co-branch-more';
      more.setAttribute('role', 'button');
      more.setAttribute('tabindex', '0');
      more.textContent = '+ ' + rest + ' أخرى';
      more.addEventListener('click', function () {
        if (window.openAllBranchesModal) openAllBranchesModal();
      });
      more.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          if (window.openAllBranchesModal) openAllBranchesModal();
        }
      });
      list.appendChild(more);
    }

    row.style.display = 'flex';
  }

  // ── All-branches bottom sheet ─────────────────────────────────
  function openAllBranchesModal() {
    var branches  = window.companyState ? (companyState.branches || []) : [];
    var listEl    = document.getElementById('allBranchesList');
    var overlayEl = document.getElementById('allBranchesOverlay');
    if (!listEl || !overlayEl) return;

    var hqCountry = (window.companyState && companyState.profile)
      ? (companyState.profile.country || '') : '';

    listEl.innerHTML = '';
    branches.forEach(function (b, i) {
      var item = document.createElement('div');
      item.className = 'co-branch-all-item';

      var numEl = document.createElement('span');
      numEl.className   = 'co-branch-all-num';
      numEl.textContent = 'فرع ' + (i + 1);
      item.appendChild(numEl);

      var infoEl = document.createElement('div');
      infoEl.className = 'co-branch-all-info';

      var fmt = _formatBranchLabel(b, hqCountry);
      if (!fmt.sameAsHq && b.country && window.TW && TW.countryFlagEl) {
        var fl = TW.countryFlagEl(b.country);
        if (fl) infoEl.appendChild(fl);
      }

      var txtEl = document.createElement('span');
      txtEl.textContent = fmt.parts.join(' - ');
      infoEl.appendChild(txtEl);
      item.appendChild(infoEl);
      listEl.appendChild(item);
    });

    overlayEl.classList.add('show');
    if (window.lucide) lucide.createIcons({ nodes: [listEl] });
  }

  function closeAllBranchesModal() {
    var el = document.getElementById('allBranchesOverlay');
    if (el) el.classList.remove('show');
  }

  // ── Orchestrator ──────────────────────────────────────────────
  function renderAll() {
    renderProfile();
    renderStats();
    renderJobs();
    renderBranches(window.companyState ? (companyState.branches || []) : []);
    if (window.renderFollowBtn) renderFollowBtn();
    if (window.renderRating)    renderRating();
    if (window.lucide) lucide.createIcons();
  }

  // ── Expose ────────────────────────────────────────────────────
  window._setText        = _setText;
  window._esc            = _esc;
  window._escapeHtml     = _escapeHtml;
  window._relativeTime   = _relativeTime;
  window._starsString    = _starsString;
  window._paintRateStars = _paintRateStars;
  window.renderProfile   = renderProfile;
  window.renderStats     = renderStats;
  window.renderJobs      = renderJobs;
  window.renderFollowBtn = renderFollowBtn;
  window.renderRating    = renderRating;
  window._postCardHtml   = _postCardHtml;
  window.renderPosts     = renderPosts;
  window.renderBranches        = renderBranches;
  window.openAllBranchesModal  = openAllBranchesModal;
  window.closeAllBranchesModal = closeAllBranchesModal;
  window.renderAll             = renderAll;
}());
