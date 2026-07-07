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

  function _escAttr(str) {
    return String(str || '')
      .replace(/&/g, '&amp;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }

  // Shorten job location to country + city only: "الأردن، عمان، ..." → "الأردن - عمان"
  function _shortLoc(str) {
    if (!str) return '';
    var parts = String(str).split(/[،,]/).map(function (s) { return s.trim(); }).filter(Boolean);
    if (parts.length >= 2) return parts[0] + ' - ' + parts[1];
    return parts[0] || str;
  }

  // ── Job card tab (lifecycle countdown / status label) ─────────
  // Returns English-format time string, or null when the deadline has passed.
  function _fmtCountdown(expiresStr) {
    if (!expiresStr) return null;
    var diffMs = new Date(expiresStr) - new Date();
    if (diffMs <= 0) return null;
    var diffMin = Math.floor(diffMs / 60000);
    if (diffMin < 1) return '< 1m';
    var days  = Math.floor(diffMin / 1440);
    var hours = Math.floor((diffMin % 1440) / 60);
    var mins  = diffMin % 60;
    var parts = [];
    if (days > 0) parts.push(days + 'D');
    if (days > 0 || hours > 0) parts.push(hours + 'h');
    parts.push(mins + 'm');
    while (parts.length > 1) {
      var last = parts[parts.length - 1];
      if (last === '0m' || last === '0h') parts.pop(); else break;
    }
    return parts.join(' ');
  }

  // isOwner = companyState.viewMode === 'owner'
  function _buildTabHtml(eff, expiresAt, closedAt, isOwner) {
    var cls, text, dataAttrs = '';

    if (eff === 'active') {
      cls = 'joc-tab--active';
      var rem = _fmtCountdown(expiresAt);
      if (rem) {
        text = 'ينتهي بعد : ' + rem;
        dataAttrs = ' data-expires="' + _escAttr(String(expiresAt)) + '"'
          + ' data-label="ينتهي بعد"'
          + ' data-expire-text="انتهى التقديم"';
      } else {
        text = 'انتهى التقديم';
      }

    } else if (eff === 'paused') {
      cls  = 'joc-tab--paused';
      text = 'موقوف مؤقتاً';

    } else if (eff === 'closed') {
      cls = 'joc-tab--closed';
      if (isOwner) {
        // 30-day management window from closed_at (or expires_at as fallback)
        var ref = closedAt || expiresAt;
        var deadline = ref
          ? new Date(new Date(ref).getTime() + 30 * 86400000).toISOString()
          : null;
        var rem2 = deadline ? _fmtCountdown(deadline) : null;
        if (rem2) {
          text = 'باقي للاغلاق : ' + rem2;
          dataAttrs = ' data-expires="' + _escAttr(deadline) + '"'
            + ' data-label="باقي للاغلاق"'
            + ' data-expire-text="تم الاغلاق"';
        } else {
          text = 'تم الاغلاق';
        }
      } else {
        text = 'انتهى التقديم';
      }

    } else { // expired
      cls  = 'joc-tab--expired';
      text = isOwner ? 'تم الاغلاق' : 'انتهى التقديم';
    }

    return '<div class="joc-tab ' + cls + '"' + dataAttrs + '>' + _esc(text) + '</div>';
  }

  function _startTabCountdown() {
    clearInterval(window._jocTabTimer);
    window._jocTabTimer = setInterval(function () {
      var tabs = document.querySelectorAll('.joc-tab[data-expires]');
      for (var i = 0; i < tabs.length; i++) {
        var tab   = tabs[i];
        var rem   = _fmtCountdown(tab.getAttribute('data-expires'));
        var label = tab.getAttribute('data-label') || '';
        if (rem) {
          tab.textContent = label ? label + ' : ' + rem : rem;
        } else {
          tab.textContent = tab.getAttribute('data-expire-text') || 'انتهى التقديم';
          tab.removeAttribute('data-expires'); // stop updating this tab
        }
      }
    }, 60000);
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

  function _fmtViews(n) {
    n = Number(n) || 0;
    if (n >= 1000) { var k = n / 1000; return (k % 1 === 0 ? k : k.toFixed(1)) + 'K مشاهدة'; }
    return n + ' مشاهدة';
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

    // Inline SVG icons (Lucide style, no external CDN)
    var icoPin   = '<svg class="jmr-ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/></svg>';
    var icoBriefcase = '<svg class="jmr-ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2"/><rect width="20" height="14" x="2" y="7" rx="2"/></svg>';
    var icoClock  = '<svg class="jmr-ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>';
    // Visitor action row icons
    var icoBookmark = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/></svg>';
    var icoShare    = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8"/><polyline points="16 6 12 2 8 6"/><line x1="12" y1="2" x2="12" y2="15"/></svg>';
    var icoApplied  = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>';
    var icoNotApp   = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>';

    jobsList.innerHTML = companyState.jobs.map(function (j) {
      var canApply = companyState.viewMode !== 'owner';
      // effective_status is computed server-side; fall back to stored status
      var eff = j.effective_status || j.status || 'active';
      var st  = eff; // use effective status for all UI decisions

      // ── Logo: company avatar or initial fallback ───────────────
      var avatarUrl = companyState.profile && companyState.profile.avatar_url;
      var logoInner = avatarUrl
        ? '<img src="' + _escAttr(avatarUrl) + '" alt="" loading="lazy">'
        : '<span class="job-card-logo-init">'
            + _esc((companyState.profile && companyState.profile.full_name
                ? companyState.profile.full_name.charAt(0) : '؟'))
            + '</span>';

      // Status badge below logo (owner only)
      var stLblMap = { active: 'نشطة', paused: 'موقوفة', closed: 'منتهية', expired: 'انتهت صلاحيته' };
      var stLblBadge = stLblMap[eff] || 'نشطة';
      // expired reuses --closed CSS class (same muted color; no new CSS needed)
      var badgeCls = eff === 'expired' ? 'closed' : eff;
      var statusBadge = !canApply
        ? '<span class="job-logo-status job-logo-status--' + _escAttr(badgeCls) + '">' + stLblBadge + '</span>'
        : '';
      var logoHtml = '<div class="job-logo-col"><div class="job-card-logo">' + logoInner + '</div>' + statusBadge + '</div>';

      // ── Profession sub-title (green, no chip) ─────────────────
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

      // ── Info row: each item is a jmr-item (icon + text flex pair) ──
      var sep = '<span class="jmr-sep">│</span>';
      var metaParts = [];
      if (j.location) metaParts.push('<span class="jmr-item">' + icoPin + '<span>' + _esc(_shortLoc(j.location)) + '</span></span>');
      if (j.job_type) metaParts.push('<span class="jmr-item">' + icoBriefcase + '<span>' + _esc(j.job_type) + '</span></span>');
      if (relDate)    metaParts.push('<span class="jmr-item">' + icoClock + '<span>' + _esc(relDate) + '</span></span>');
      var metaRow = metaParts.join(sep);

      // ── Right panel ────────────────────────────────────────────
      var rightHtml;
      if (canApply) {
        // Visitor: detail button + 3 icon actions for active jobs; paused shows nothing
        if (eff === 'active') {
          var jidStr = _escAttr(String(j.id));
          var isApplied = (companyState.appliedJobIds instanceof Set)
            ? companyState.appliedJobIds.has(j.id) : false;
          var applyStatusCls = isApplied ? 'vjc-btn--applied' : 'vjc-btn--not-applied';
          var applyTitle     = isApplied ? 'تم التقديم' : 'لم تتقدم بعد';
          rightHtml = '<div class="job-owner-col">'
            + '<button class="joc-btn joc-btn--primary visitor-detail-btn" data-jid="' + jidStr + '">عرض التفاصيل</button>'
            + '<div class="vjc-actions">'
            + '<button type="button" class="vjc-btn vjc-btn--save" title="حفظ الوظيفة">' + icoBookmark + '</button>'
            + '<button type="button" class="vjc-btn vjc-btn--share" title="مشاركة الوظيفة">' + icoShare + '</button>'
            + '<button type="button" class="vjc-btn vjc-btn--apply-status ' + applyStatusCls + '" title="' + _escAttr(applyTitle) + '">' + (isApplied ? icoApplied : icoNotApp) + '</button>'
            + '</div>'
            + '</div>';
        } else {
          rightHtml = '';
        }
      } else {
        var jid = parseInt(j.id, 10);
        var cnt = parseInt(j.applicant_count, 10) || 0;
        if (eff === 'expired') {
          // Record only: no actions
          rightHtml = '<div class="job-owner-col"></div>';
        } else if (eff === 'closed') {
          // 30-day viewer window: applicants visible, no manage
          rightHtml = '<div class="job-owner-col">'
            + '<span class="job-applicant-count">عدد المتقدمين <span class="job-cnt-badge">' + cnt + '</span></span>'
            + '<button type="button" class="joc-btn joc-btn--primary owner-applicants-btn" data-jid="' + jid + '">مشاهدة المتقدمين</button>'
            + '</div>';
        } else {
          // active or paused: full controls
          rightHtml = '<div class="job-owner-col">'
            + '<span class="job-applicant-count">عدد المتقدمين <span class="job-cnt-badge">' + cnt + '</span></span>'
            + '<button type="button" class="joc-btn joc-btn--primary owner-applicants-btn" data-jid="' + jid + '">مشاهدة المتقدمين</button>'
            + '<button type="button" class="joc-btn joc-btn--muted job-manage-btn" data-jid="' + jid + '" data-status="' + _escAttr(eff) + '">الإدارة</button>'
            + '</div>';
        }
      }

      return '<div class="job-card-wrap">'
        + _buildTabHtml(eff, j.expires_at, j.closed_at, !canApply)
        + '<div class="job-card tw-card-lift" data-jid="' + _escAttr(String(j.id)) + '" data-status="' + _escAttr(eff) + '">'
        + logoHtml
        + '<div class="job-card-body">'
          + '<div class="job-title">' + _esc(j.title) + '</div>'
          + subHtml
          + (metaRow ? '<div class="job-meta-row">' + metaRow + '</div>' : '')
        + '</div>'
        + rightHtml
        + '</div>'
        + '</div>';
    }).join('');
    _startTabCountdown();

    // Visitor summary line: "تم إنهاء X إعلانات وظيفية" shown below job list
    var isVisitor = companyState.viewMode !== 'owner';
    var closedCnt = (window.companyState && companyState.closedJobsCount) || 0;
    if (isVisitor && closedCnt > 0) {
      var summaryEl = document.createElement('div');
      summaryEl.className = 'tw-empty-sub';
      summaryEl.textContent = 'تم إنهاء ' + closedCnt + (closedCnt === 1 ? ' إعلان وظيفي' : ' إعلانات وظيفية');
      jobsList.appendChild(summaryEl);
    }

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
    var coName    = (window.companyState && companyState.profile)
      ? (companyState.profile.full_name || 'الشركة') : 'الشركة';
    var avatarUrl = (window.companyState && companyState.profile)
      ? (companyState.profile.avatar_url || '') : '';

    // Resolve theme color — null/unknown → teal
    var colorKey = (post.theme_color && window.TW && TW.POST_THEME_COLORS && TW.POST_THEME_COLORS[post.theme_color])
      ? post.theme_color : 'teal';
    var clr = (window.TW && TW.POST_THEME_COLORS && TW.POST_THEME_COLORS[colorKey])
      || { accent: '#00c896', soft: 'rgba(0,200,150,.12)', glow: 'rgba(0,200,150,.18)' };
    var cardStyle = '--pa:' + clr.accent + '; --pa-s:' + clr.soft + '; --pa-g:' + clr.glow;

    // Avatar: real logo or initial letter
    var avaContent = avatarUrl
      ? '<img src="' + _escAttr(avatarUrl) + '" alt="">'
      : '<span class="post-ava--init">' + _esc((coName || '?').charAt(0)) + '</span>';

    // Tags — use themed class so they inherit --pa from the card
    var tagsHtml = '';
    if (post.tags && post.tags.length) {
      tagsHtml = '<div class="job-tags">' + post.tags.map(function (t) {
        return '<span class="jtag jtag-themed">' + _esc(t) + '</span>';
      }).join('') + '</div>';
    }

    // 3-dot owner menu
    var canEdit = window.companyState &&
      companyState.permissions && companyState.permissions.can_edit;
    var pid = _escAttr(String(post.id));
    var icoEdit   = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>';
    var icoTrash  = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4h6v2"/></svg>';
    var dotsHtml = canEdit
      ? '<div class="pc-dots">'
          + '<button class="pc-dots-btn" data-post-id="' + pid + '" aria-label="خيارات">&#8943;</button>'
          + '<div class="pc-dots-menu" id="pc-dm-' + pid + '">'
            + '<button class="pc-dots-edit" data-post-id="' + pid + '">' + icoEdit + 'تعديل</button>'
            + '<button class="pc-dots-delete" data-post-id="' + pid + '">' + icoTrash + 'حذف</button>'
          + '</div>'
        + '</div>'
      : '';

    // Inline SVGs
    var icoEye         = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>';
    var icoClock       = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>';
    var icoShare       = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/></svg>';
    var icoHeartOutline = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>';
    var icoHeartFilled  = '<svg viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>';
    var icoComment     = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>';
    var icoBookmark    = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/></svg>';

    return '<div class="post-card" data-post-id="' + pid + '" style="' + cardStyle + '">'
      + '<div class="post-head">'
        + '<div class="post-ava">' + avaContent + '</div>'
        + '<div class="post-head-info">'
          + '<div class="post-nm">' + _esc(coName) + '</div>'
          + '<div class="post-meta-row">'
            + '<span class="post-date">' + icoClock + _relativeTime(post.created_at) + '</span>'
            + '<span class="post-views" data-views-count="' + (Number(post.views_count) || 0) + '">' + icoEye + _fmtViews(post.views_count) + '</span>'
          + '</div>'
        + '</div>'
        + dotsHtml
      + '</div>'
      + '<div class="post-body-wrap">'
        + '<div class="post-body">'
          + '<span class="post-body-text">' + _esc(post.body) + '</span>'
          + '<button type="button" class="post-more-inline" aria-label="عرض المزيد">'
            + '<span class="post-more-ellipsis">…</span>'
            + '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><path d="M12 8v8"/><path d="m8 12 4 4 4-4"/></svg>'
          + '</button>'
        + '</div>'
        + '<button type="button" class="post-less-btn" aria-label="عرض أقل">'
          + '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><path d="m16 12-4-4-4 4"/><path d="M12 16V8"/></svg>'
        + '</button>'
      + '</div>'
      + tagsHtml
      + (function () {
          var appCount = Number(post.appreciations_count) || 0;
          var appActive = post.viewer_appreciated === true || post.viewer_appreciated === 'true' || post.viewer_appreciated === 1;
          var apprCls = 'pc-btn pc-btn--appr' + (appActive ? ' appr-active' : '');
          var apprIco = appActive ? icoHeartFilled : icoHeartOutline;
          var apprLabel = appActive ? ('أقدّر · ' + appCount) : 'أقدّر';
          return '<div class="pc-actions">'
            + '<button class="' + apprCls + '" data-post-id="' + pid + '" data-appr-count="' + appCount + '">' + apprIco + apprLabel + '</button>'
            + (post.comments_enabled !== false ? '<button class="pc-btn pc-btn--cmt" data-post-id="' + pid + '">' + icoComment + 'تعليق</button>' : '')
            + '<button class="pc-btn pc-btn--share" data-post-id="' + pid + '">' + icoShare    + 'مشاركة</button>'
            + '<button class="pc-btn pc-btn--save"  data-post-id="' + pid + '">' + icoBookmark + 'حفظ</button>'
            + '</div>';
        })()
    + '</div>';
  }

  function _initPostClamps(container) {
    container.querySelectorAll('.post-body-wrap').forEach(function (wrap) {
      var body      = wrap.querySelector('.post-body');
      var textSpan  = wrap.querySelector('.post-body-text');
      var moreBtn   = wrap.querySelector('.post-more-inline');
      if (!body || !textSpan || !moreBtn) return;

      var fullText = textSpan.textContent;
      var lh       = parseFloat(getComputedStyle(body).lineHeight) || 22;
      var maxH     = Math.round(lh * 3);

      // scrollHeight works on webkit-line-clamp elements in Chromium (reports true height).
      // Use it to decide whether truncation is needed.
      if (body.scrollHeight <= maxH + 2) {
        // Short post — remove CSS clamp so inline button slot stays hidden & display is normal.
        body.style.cssText = 'display:block;overflow:visible';
        return;
      }

      // Need truncation — switch to unclamped block for binary-search measurements.
      body.style.cssText = 'display:block;overflow:visible';
      moreBtn.style.display = 'inline-flex'; // button width (ellipsis + icon) must be included in measurements

      var lo = 0, hi = fullText.length;
      while (lo < hi - 1) {
        var mid = (lo + hi) >> 1;
        textSpan.textContent = fullText.slice(0, mid);
        if (body.scrollHeight <= maxH + 2) { lo = mid; } else { hi = mid; }
      }

      // Snap to nearest Arabic word boundary (last space)
      var raw       = fullText.slice(0, lo).replace(/\s+$/, '');
      var lastSpace = raw.lastIndexOf(' ');
      // Only snap if the space is reasonably close (keeps at least 60% of lo chars)
      var trimmed   = (lastSpace > lo * 0.6) ? raw.slice(0, lastSpace) : raw;

      textSpan.textContent = trimmed;
      // Store full/short text on the element for the toggle handlers
      wrap._pbFull  = fullText;
      wrap._pbShort = trimmed;
    });
  }

  // Posts cache — used by company.posts.js to populate edit modal without extra fetch
  var _postsCache = {};

  function renderPosts(posts) {
    var list  = document.getElementById('postsList');
    var empty = document.getElementById('postsEmpty');
    if (!list) return;
    _postsCache = {};
    if (!posts || !posts.length) {
      list.innerHTML = '';
      if (empty) empty.style.display = 'block';
      return;
    }
    posts.forEach(function (p) { _postsCache[p.id] = p; });
    if (empty) empty.style.display = 'none';
    list.innerHTML = posts.map(_postCardHtml).join('');
    // Two rAFs: first lets the browser compute layout, second ensures fonts are measured.
    requestAnimationFrame(function () {
      requestAnimationFrame(function () {
        _initPostClamps(list);
        if (window.initPostViewTracking) initPostViewTracking(list);
      });
    });
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
  window._getPostById    = function (id) { return _postsCache[id] || null; };
  window.renderBranches        = renderBranches;
  window.openAllBranchesModal  = openAllBranchesModal;
  window.closeAllBranchesModal = closeAllBranchesModal;
  window.renderAll             = renderAll;
}());
