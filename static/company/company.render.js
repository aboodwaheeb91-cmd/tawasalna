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

  // Escaping = the shared twEscHtml / twEscAttr (tw_shared.js — §54); no local copy.
  var _esc     = twEscHtml;
  var _escAttr = twEscAttr;

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

  // Rating star (DS-ICON — PR 4.13): on = filled + .co-star--on, off = outline.
  function _coStarIcon(on, size) {
    if (!window.twIcon) return '';
    return twIcon('star', { size: size, filled: !!on, className: on ? 'co-star co-star--on' : 'co-star' });
  }

  // 5 stars for a score (rounded) — the one star renderer on the page.
  function _coStarsHtml(score, size) {
    var n = Math.round(score || 0);
    var s = '';
    for (var i = 1; i <= 5; i++) s += _coStarIcon(i <= n, size);
    return s;
  }

  function _paintRateStars(score) {
    document.querySelectorAll('#rateStars span').forEach(function (s) {
      s.innerHTML = _coStarIcon(parseInt(s.getAttribute('data-score'), 10) <= score, '2xl');
    });
  }

  // ── Profile ──────────────────────────────────────────────────
  // Public link of this company — /u/{tw_id} (Smart Router, F7), never location.href.
  function _companyPublicUrl() {
    var tw = companyState.profile && companyState.profile.tw_id;
    return tw ? location.origin + '/u/' + encodeURIComponent(tw) : '';
  }

  function _copyText(text) {
    if (!text) { if (window.showToast) showToast(twT('company.copy_failed'), 'error'); return; }
    var done = function () { if (window.showToast) showToast(twT('company.link_copied'), 'success'); };
    var fail = function () { if (window.showToast) showToast(twT('company.copy_failed'), 'error'); };
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(text).then(done, fail);
    else fail();
  }

  function renderProfile() {
    var p    = companyState.profile;
    var name = p.full_name || '';

    // Cover: saved cover_url (validated) on top of the CSS fallback background
    var coverUrl = twSafeImageUrl(companyState.company && companyState.company.cover_url);
    if (coverUrl && window.setCover) window.setCover(coverUrl);

    _setText('coName',   name);
    _setText('coDesc',   p.bio || twT('company.desc_empty'));

    document.querySelectorAll('[id^="postCoName"]').forEach(function (el) {
      el.textContent = name;
    });

    // Logo: validated URL only (DS-IMAGE — twSafeImageUrl); DOM createElement, no inline styles
    var logoEl  = document.getElementById('coLogo');
    var logoUrl = twSafeImageUrl(p.avatar_url);
    if (logoEl && logoUrl) {
      var img = document.createElement('img');
      img.src       = logoUrl;
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

    // About → verification card (PR 1.7): shown only when the API says is_verified — no "unverified" text
    var verifiedRow = document.getElementById('coAboutVerifiedRow');
    if (verifiedRow) verifiedRow.hidden = !p.is_verified;

    // Industry label (replaces generic type badge)
    var badge = document.getElementById('coTypeBadge');
    if (badge) {
      var industry = companyState.company && (companyState.company.industry || companyState.company.company_type);
      badge.textContent = industry || twT('company.type_unset');
    }

    // Meta row: the company's public Tawasalna link (/u/{tw_id}) — not p.website, not location.href
    var websiteEl      = document.getElementById('coWebsite');
    var websiteLink    = document.getElementById('coWebsiteLink');
    var websiteCopyBtn = document.getElementById('coWebsiteCopyBtn');
    var pageUrl  = _companyPublicUrl();

    if (websiteEl) websiteEl.style.display = pageUrl ? 'inline-flex' : 'none';
    if (websiteLink && pageUrl) {
      websiteLink.href        = pageUrl;
      websiteLink.textContent = pageUrl.replace(/^https?:\/\//, '');
    }
    if (websiteCopyBtn) websiteCopyBtn.onclick = function () { _copyText(_companyPublicUrl()); };

    var locStr = _locationText(p, ' - ');
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

    renderAbout();
    renderVisitorActions();
  }

  // Location text (Company Profile rule 9): country + city; + district when given;
  // nothing at all → ''.
  function _locationText(p, sep) {
    return [p.country || '', p.city || '', p.location || ''].filter(Boolean).join(sep);
  }

  // ── About tab — every row from the API; no data → the row is not shown ──
  function _aboutRow(rowId, valId, text) {
    var row = document.getElementById(rowId);
    var val = document.getElementById(valId);
    var has = text != null && String(text).trim() !== '';
    if (val && has) val.textContent = String(text);
    if (row) row.hidden = !has;
    return has;
  }

  function renderAbout() {
    var p = companyState.profile || {};
    var c = companyState.company || {};
    var shown = 0;

    var desc = document.getElementById('aboutDesc');
    var descText = p.bio || c.description || '';
    if (desc) { desc.textContent = descText; desc.hidden = !descText; }
    if (descText) shown++;

    if (_aboutRow('aboutTypeRow',    'aboutType',    c.industry || c.company_type)) shown++;
    if (_aboutRow('aboutLocRow',     'aboutLoc',     _locationText(p, '، '))) shown++;
    if (_aboutRow('aboutFoundedRow', 'aboutFounded', c.founded_year)) shown++;
    if (_aboutRow('aboutSizeRow',    'aboutSize',    c.company_size)) shown++;
    if (_aboutRow('aboutEmailRow',   'aboutEmail',   c.contact_email)) shown++;
    if (_aboutRow('aboutPhoneRow',   'aboutPhone',   p.phone)) shown++;   // owner only (server strips it for visitors)

    // Website: a link only when twSafeLinkUrl accepts it; any other value → plain text (§54 4b)
    var webRow = document.getElementById('aboutWebRow');
    var webVal = document.getElementById('aboutWeb');
    var web    = (p.website || '').trim();
    if (webVal) {
      webVal.textContent = '';
      if (web) {
        var safe = twSafeLinkUrl(web);
        if (safe) {
          var a = document.createElement('a');
          a.href = safe; a.target = '_blank'; a.rel = 'noopener noreferrer';
          a.textContent = web;
          webVal.appendChild(a);
        } else {
          webVal.textContent = web;
        }
      }
    }
    if (webRow) webRow.hidden = !web;
    if (web) shown++;

    var empty = document.getElementById('aboutEmpty');
    if (empty) empty.hidden = shown > 0;
  }

  // ── Visitor actions — Actions Registry (twAction · BTN-19). The registry decides who sees
  //    what (owner → share only · guest → login button); the page writes no visibility rule.
  function _actMode() {
    var vm = companyState.viewMode;
    return vm === 'owner' ? 'owner' : (vm === 'public-user' ? 'registered' : 'guest');
  }

  function _shareCompany() {
    var url = _companyPublicUrl();
    if (!url) return;
    var name = (companyState.profile && companyState.profile.full_name) || '';
    if (navigator.share) {
      navigator.share({ title: name, text: twT('company.share_text', { name: name }), url: url })
        .catch(function () {});
    } else {
      _copyText(url);
    }
  }

  var _msgActSeq = 0;
  function _hasVisibleChild(el) {
    for (var i = 0; i < el.children.length; i++) if (!el.children[i].hidden) return true;
    return false;
  }
  function renderVisitorActions() {
    var row = document.getElementById('visitorActions');
    if (!row || typeof twAction !== 'function') return;
    var p    = companyState.profile || {};
    var mode = _actMode();
    row.innerHTML = '';

    var follow = twAction('follow', {
      ownerId: p.id, mode: mode, className: 'nb nb-follow',
      onClick: function () { if (window.toggleFollow) window.toggleFollow(); }
    });
    if (follow) { follow.id = 'followBtn'; row.appendChild(follow); }

    // «مراسلة» only when the server rule allows it (twCanMessage — task 5.0g); slot keeps the order
    var msgSlot = document.createElement('span');
    msgSlot.hidden = true;
    row.appendChild(msgSlot);
    var seq = ++_msgActSeq;
    twCanMessage(p.id).then(function (st) {
      if (seq !== _msgActSeq || !msgSlot.parentNode) return;   // a newer render won
      var msg = twAction('message', {
        ownerId: p.id, mode: mode, className: 'nb nb-outline', canMessage: st.can_message,
        onClick: function () {
          if (!p.tw_id) { if (window.showToast) showToast(twT('profile.message_failed'), 'error'); return; }
          location.href = '/messages?with=' + encodeURIComponent(p.tw_id);
        }
      });
      if (msg) { msg.id = 'contactBtn'; msgSlot.parentNode.replaceChild(msg, msgSlot); }
      row.hidden = !_hasVisibleChild(row);
    });

    var share = twAction('share', {
      ownerId: p.id, mode: mode, className: 'nb nb-outline', onClick: _shareCompany
    });
    if (share) row.appendChild(share);

    var report = twAction('report', {
      ownerId: p.id, mode: mode, className: 'nb nb-outline',
      onClick: function () { twReportDialog({ reportedId: p.id, reportedType: 'company' }); }
    });
    if (report) row.appendChild(report);

    // «حظر» (task 5.4) — signed-in visitors only (registry); confirm from the registry, call = twBlockUser
    var blk = twAction('block', {
      ownerId: p.id, mode: mode, className: 'nb nb-outline', onClick: function () { twBlockUser(p.id); }
    });
    if (blk) row.appendChild(blk);

    row.hidden = !_hasVisibleChild(row);   // the empty «مراسلة» slot does not count
    renderFollowBtn();
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

    // Inline SVG icons (Lucide style, no external CDN)
    var icoPin   = '<svg class="jmr-ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/></svg>';
    var icoBriefcase = '<svg class="jmr-ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2"/><rect width="20" height="14" x="2" y="7" rx="2"/></svg>';
    var icoClock  = '<svg class="jmr-ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>';
    // Visitor action row icons
    var icoShare    = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8"/><polyline points="16 6 12 2 8 6"/><line x1="12" y1="2" x2="12" y2="15"/></svg>';
    var icoApplied  = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>';
    var icoNotApp   = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>';

    jobsList.innerHTML = companyState.jobs.map(function (j) {
      var canApply = companyState.viewMode !== 'owner';
      // effective_status is computed server-side; fall back to stored status
      var eff = j.effective_status || j.status || 'active';
      var st  = eff; // use effective status for all UI decisions

      // ── Logo: company avatar or initial fallback ───────────────
      var avatarUrl = twSafeImageUrl(companyState.profile && companyState.profile.avatar_url);
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
      // Hidden by the admin (task 5.3j) — the owner sees it with the reason (never sent to visitors)
      var hiddenNote = '';
      if (!canApply && j.admin_hidden_at) {
        statusBadge = '<span class="job-logo-status job-logo-status--closed">' + _esc(twT('company.job.admin_hidden')) + '</span>';
        hiddenNote = '<div class="job-card-admin-note">'
          + _esc(twT('company.job.admin_hidden_reason', { reason: j.admin_hidden_reason || '' })) + '</div>';
      }
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
        // Visitor: detail button + 2 icon actions (share · apply status) for active jobs; paused shows nothing
        if (eff === 'active') {
          var jidStr = _escAttr(String(j.id));
          var isApplied = (companyState.appliedJobIds instanceof Set)
            ? companyState.appliedJobIds.has(j.id) : false;
          var applyStatusCls = isApplied ? 'vjc-btn--applied' : 'vjc-btn--not-applied';
          var applyTitle     = isApplied ? 'تم التقديم' : 'لم تتقدم بعد';
          rightHtml = '<div class="job-owner-col">'
            + '<button class="joc-btn joc-btn--primary visitor-detail-btn" data-jid="' + jidStr + '">عرض التفاصيل</button>'
            + '<div class="vjc-actions">'
            + '<button type="button" class="vjc-btn vjc-btn--share" title="مشاركة الوظيفة">' + icoShare + '</button>'
            + '<button type="button" class="vjc-btn vjc-btn--apply-status ' + applyStatusCls + '" title="' + _escAttr(applyTitle) + '">' + (isApplied ? icoApplied : icoNotApp) + '</button>'
            + '</div>'
            + '</div>';
        } else {
          rightHtml = '';
        }
      } else {
        var jid = parseInt(j.id, 10);
        // null = the count could not be read (task 5.0e) → «—», never «0»
        var cnt = (j.applicant_count === null || j.applicant_count === undefined)
          ? twEscHtml(twT('common.count_unknown')) : (parseInt(j.applicant_count, 10) || 0);
        if (eff === 'expired') {
          // Record only: no actions
          rightHtml = '<div class="job-owner-col"></div>';
        } else if (eff === 'closed') {
          // 30-day viewer window: applicants visible, no manage (reopening = admin only — task 5.3j4)
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
          + hiddenNote
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
    var following = !!(companyState.permissions && companyState.permissions.is_following);
    var lbl = btn.querySelector('.tw-act-lbl');
    if (lbl) lbl.textContent = twT(following ? 'action.following' : 'action.follow');
    var ico = btn.querySelector('svg');
    if (ico && window.twIconEl) btn.replaceChild(twIconEl(following ? 'user-check' : 'user-plus', { size: 'sm' }), ico);
    btn.classList.toggle('following', following);
  }

  // ── Rating display ────────────────────────────────────────────
  function renderRating() {
    if (!window.companyState) return;
    var avg   = companyState.stats.rating_avg;
    var count = companyState.stats.rating_count || 0;
    var mine  = companyState.permissions ? companyState.permissions.my_rating : null;

    var starsHtml = _coStarsHtml(avg, 'lg');
    var starsEl = document.getElementById('ratingStarsDisplay');
    if (starsEl) starsEl.innerHTML = starsHtml;
    _setText('ratingNum',   avg != null ? avg : '—');

    var subText = count > 0
      ? twT(count > 10 ? 'company.rating.summary_many' : 'company.rating.summary_few', { count: count })
      : twT('company.rating.none');
    _setText('ratingSub', subText);

    // Sync ratings tab panel
    var tabStarsEl = document.getElementById('ratingsTabStars');
    if (tabStarsEl) tabStarsEl.innerHTML = starsHtml;
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
  // Card markup = TwPostCard (static/shared/tw-post-card.js — task U.2); page supplies author (+ type) + owner flag.
  function _postCardHtml(post) {
    var prof = window.companyState && companyState.profile;
    var snap = window.TwAuthSync && TwAuthSync.getSessionSnapshot();   // session id — never tw_user
    return TwPostCard.html(post, {
      authorName: prof ? (prof.full_name || 'الشركة') : 'الشركة',
      avatarUrl:  prof ? prof.avatar_url : '',
      authorType: 'co',
      canEdit:    !!(window.companyState && companyState.permissions && companyState.permissions.can_edit),
      authorId:   prof ? prof.id : null,   // ⋯ report / block the company (task 8.6c)
      viewerId:   snap && snap.isAuthenticated ? snap.userId : null,
      authorTwId: prof ? prof.tw_id : ''
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
        TwPostCard.initClamps(list);
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
  }

  // Static page icons (DS-ICON — <i data-tw-icon>) → SVG once at init (ICON-03.1).
  if (window.twIcon && typeof twIcon.hydrate === 'function') twIcon.hydrate(document);

  // ── Expose ────────────────────────────────────────────────────
  window._setText        = _setText;
  window._coStarsHtml    = _coStarsHtml;
  window._coStarIcon     = _coStarIcon;
  window._paintRateStars = _paintRateStars;
  window.renderProfile   = renderProfile;
  window.renderAbout     = renderAbout;
  window.renderVisitorActions = renderVisitorActions;
  window.renderStats     = renderStats;
  window.renderJobs      = renderJobs;
  window.renderFollowBtn = renderFollowBtn;
  window.renderRating    = renderRating;
  window.renderPosts     = renderPosts;
  window._getPostById    = function (id) { return _postsCache[id] || null; };
  window.renderBranches        = renderBranches;
  window.openAllBranchesModal  = openAllBranchesModal;
  window.closeAllBranchesModal = closeAllBranchesModal;
  window.renderAll             = renderAll;
}());
