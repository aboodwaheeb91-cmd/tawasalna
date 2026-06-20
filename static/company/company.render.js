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

  // Safe HTML escaping via DOM (used for post content)
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
    var stars = document.querySelectorAll('#rateStars span');
    stars.forEach(function (s) {
      var v = parseInt(s.getAttribute('data-score'));
      s.textContent = (v <= score) ? '⭐' : '☆';
    });
  }

  // ── Profile ──────────────────────────────────────────────────
  function renderProfile() {
    var p    = companyState.profile;
    var name = p.full_name || '—';

    _setText('coName', name);
    _setText('coDesc', p.bio || 'لا يوجد وصف بعد.');
    _setText('coLoc',  p.location ? '📍 ' + p.location : '📍 —');
    document.querySelectorAll('[id^="postCoName"]').forEach(function (el) {
      el.textContent = name;
    });

    var logoEl = document.getElementById('coLogo');
    if (logoEl && p.avatar_url) {
      logoEl.innerHTML = '<img src="' + p.avatar_url +
        '" style="width:100%;height:100%;object-fit:cover;border-radius:inherit">';
    }

    var badge = document.getElementById('coTypeBadge');
    if (badge) badge.textContent = '🏢 ' + (companyState.company.company_type || 'شركة');
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
        '<div class="tw-empty"><span class="tw-empty-ico">💼</span>' +
        '<div class="tw-empty-title">لا توجد وظائف مفتوحة</div></div>';
      return;
    }

    jobsList.innerHTML = companyState.jobs.map(function (j) {
      var canApply = companyState.viewMode !== 'owner';
      return '<div class="job-card tw-card-lift" data-jid="' + j.id + '">' +
        '<div class="job-title">' + _esc(j.title) + '</div>' +
        '<div class="job-meta"><span>📍 ' + _esc(j.location || '—') + '</span>' +
        '<span>⏰ ' + _esc(j.job_type || '—') + '</span></div>' +
        '<div class="job-footer">' +
        (j.salary_min
          ? '<div class="job-salary">' + j.salary_min +
            (j.salary_max ? ' - ' + j.salary_max : '') + '</div>'
          : '<div></div>') +
        (canApply
          ? '<button class="apply-btn" data-jid="' + j.id + '">تقديم ←</button>'
          : '<span style="font-size:.7rem;color:var(--t3)">وظيفتك</span>') +
        '</div></div>';
    }).join('');
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

    var disp = document.getElementById('ratingStarsDisplay');
    if (disp) disp.textContent = avg ? _starsString(avg, '⭐', '☆') : '☆☆☆☆☆';

    var num = document.getElementById('ratingNum');
    if (num) num.textContent = (avg != null) ? avg : '—';

    var sub = document.getElementById('ratingSub');
    if (sub) {
      sub.textContent = count > 0
        ? ('من 5 — بناءً على ' + count + ' تقييم' + (count > 10 ? '' : 'ات'))
        : 'لا تقييمات بعد';
    }

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
      ? '<button class="post-del" onclick="deletePost(' + post.id + ')" title="حذف" ' +
        'style="margin-right:auto;background:none;border:none;color:var(--t3);cursor:pointer;font-size:1rem">🗑</button>'
      : '';

    return '<div class="post-card">' +
      '<div class="post-head">' +
        '<div class="post-ava">🏢</div>' +
        '<div style="flex:1"><div class="post-nm">' + _escapeHtml(coName) + '</div>' +
        '<div class="post-date">' + _relativeTime(post.created_at) + '</div></div>' +
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

  // ── Orchestrator ──────────────────────────────────────────────
  function renderAll() {
    renderProfile();
    renderStats();
    renderJobs();
    if (window.renderFollowBtn) renderFollowBtn();
    if (window.renderRating)    renderRating();
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
  window.renderAll       = renderAll;
}());
