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
    if (hqRow)  hqRow.style.display  = locStr ? 'flex' : 'none';
    if (hqText) hqText.textContent   = locStr;
  }

  // ── Stats ─────────────────────────────────────────────────────
  function renderStats() {
    var s = companyState.stats;
    _setText('jobsCount',       s.jobs_count       ?? '—');
    _setText('followersCount',  s.followers_count  ?? '—');
    _setText('followersCount2', s.followers_count  ?? '—');
    _setText('ratingAvg',       s.rating_avg       ?? '—');
    _setText('verifiedCount',   s.verified_count   ?? '—');
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
      // Lucide SVG path strings — no external CDN call, rendered synchronously
      var icoBuilding = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M6 22V4a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v18Z"/><path d="M6 12H4a2 2 0 0 0-2 2v6a2 2 0 0 0 2 2h2"/><path d="M18 9h2a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2h-2"/><path d="M10 6h4"/><path d="M10 10h4"/><path d="M10 14h4"/><path d="M10 18h4"/></svg>';
      var icoMapPin  = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/></svg>';
      var icoClock   = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>';

      return '<div class="job-card tw-card-lift" data-jid="' + _esc(String(j.id)) + '">' +
        '<div class="job-card-logo">' + icoBuilding + '</div>' +
        '<div class="job-card-body">' +
          '<div class="job-title">' + _esc(j.title) + '</div>' +
          '<div class="job-card-meta">' +
            '<span class="job-meta-chip">' + icoMapPin + ' ' + _esc(j.location || '—') + '</span>' +
            '<span class="job-meta-chip">' + icoClock  + ' ' + _esc(j.job_type || '—') + '</span>' +
          '</div>' +
        '</div>' +
        (canApply
          ? '<button class="apply-btn-pill" data-jid="' + _esc(String(j.id)) + '">تقديم الآن</button>'
          : '<span class="owner-job-badge">وظيفتك ✓</span>') +
      '</div>';
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
  function renderBranches(branches) {
    var row  = document.getElementById('coBranchesRow');
    var list = document.getElementById('coBranchesText');
    if (!row || !list) return;

    if (!branches || !branches.length) {
      row.style.display = 'none';
      list.innerHTML    = '';
      return;
    }

    var MAX   = 3;
    var shown = branches.slice(0, MAX);
    var rest  = branches.length - MAX;

    list.innerHTML = '';
    shown.forEach(function (b, i) {
      if (i > 0) {
        var sep = document.createElement('span');
        sep.className   = 'co-branch-sep';
        sep.textContent = '|';
        list.appendChild(sep);
      }
      var parts = [b.branch_name, b.country, b.city, b.district].filter(Boolean);
      var chip  = document.createElement('span');
      chip.className   = 'co-branch-chip';
      chip.textContent = parts.join(' - ');
      list.appendChild(chip);
    });

    if (rest > 0) {
      var more = document.createElement('span');
      more.className   = 'co-branch-more';
      more.textContent = '+ ' + rest + ' فروع أخرى';
      list.appendChild(more);
    }

    row.style.display = 'flex';
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
  window.renderBranches  = renderBranches;
  window.renderAll       = renderAll;
}());
