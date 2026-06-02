// ════════════════════════════════════════════════════════════
// company-profile.js — Action Layer
// Rule #19: All actions read companyState + call API
// Rule #21: event → guard → API → _mergeCompanyState → renderAll
// ════════════════════════════════════════════════════════════

// ── companyState (initialized in HTML core engine script) ──
// ── _jwt() helper (defined in HTML core engine script) ──

// ── Navigation ──
function switchTab(name, el) {
  document.querySelectorAll('.tab').forEach(function(t) { t.classList.remove('active'); });
  el.classList.add('active');
  ['jobs','posts','about','ratings'].forEach(function(t) {
    var el2 = document.getElementById('tab-' + t);
    if (el2) el2.style.display = t === name ? '' : 'none';
  });
  // Phase 3: lazy load posts on first open of posts tab
  if (name === 'posts' && window.loadPosts) loadPosts();
}

function doLogout() {
  localStorage.removeItem('tw_user');
  localStorage.removeItem('tw_jwt');
  window.location.href = '/';
}

// ── Dropdown menu ──
var _menuOpen = false;
function toggleMenu(e) {
  e.stopPropagation();
  _menuOpen = !_menuOpen;
  var m   = document.getElementById('dropMenu');
  var btn = document.getElementById('menuBtn');
  if (!m || !btn) return;
  if (_menuOpen) {
    var r = btn.getBoundingClientRect();
    m.style.left = r.left + 'px';
    m.style.display = 'block';
  } else {
    m.style.display = 'none';
  }
}
document.addEventListener('click', function(e) {
  var btn = document.getElementById('menuBtn');
  var m   = document.getElementById('dropMenu');
  if (_menuOpen && m && btn && !btn.contains(e.target) && !m.contains(e.target)) {
    _menuOpen = false;
    m.style.display = 'none';
  }
});

// ── Follow system (Step 5a: server state, SSOT = companyState) ──
// No local _following. Source of truth: companyState.permissions.is_following
var isFollowLoading = false;

function renderFollowBtn() {
  // Pure: reads companyState.permissions.is_following → updates #followBtn
  var btn = document.getElementById('followBtn');
  if (!btn || !window.companyState) return;
  var following = !!companyState.permissions.is_following;
  btn.textContent = following ? '✓ متابَع' : '+ متابعة';
  btn.classList.toggle('following', following);
}

function toggleFollow() {
  if (!window._jwt || !_jwt()) { window.location.href = '/'; return; }
  if (!window.companyState || !companyState.permissions.can_follow) return;
  if (isFollowLoading) return;  // prevent double-click

  var companyId = new URLSearchParams(location.search).get('id');
  if (!companyId) return;

  // Snapshot previous state for rollback
  var prevFollowing = !!companyState.permissions.is_following;
  var prevCount     = companyState.stats.followers_count || 0;

  // Optimistic update
  var willFollow = !prevFollowing;
  companyState.permissions.is_following = willFollow;
  companyState.stats.followers_count    = prevCount + (willFollow ? 1 : -1);
  if (companyState.stats.followers_count < 0) companyState.stats.followers_count = 0;
  renderFollowBtn();
  if (window.renderStats) renderStats();

  // Lock
  isFollowLoading = true;
  var btn = document.getElementById('followBtn');
  if (btn) btn.disabled = true;

  fetch('/company/follow/' + companyId, {
    method:  willFollow ? 'POST' : 'DELETE',
    headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + _jwt() },
  })
  .then(function(r) {
    if (!r.ok) throw new Error('follow failed: ' + r.status);
    return r.json();
  })
  .then(function(data) {
    // Re-sync from server response (authoritative)
    companyState.permissions.is_following = !!data.following;
    if (typeof data.followers_count === 'number')
      companyState.stats.followers_count = data.followers_count;
    renderFollowBtn();
    if (window.renderStats) renderStats();
  })
  .catch(function() {
    // Rollback to previous state
    companyState.permissions.is_following = prevFollowing;
    companyState.stats.followers_count    = prevCount;
    renderFollowBtn();
    if (window.renderStats) renderStats();
    if (window.showToast) showToast('تعذّر تحديث المتابعة', 'error');
  })
  .finally(function() {
    isFollowLoading = false;
    if (btn) btn.disabled = false;
  });
}

// ── Rating system (Step 5b: display from state + interactive) ──
var isRateLoading = false;

function _starsString(score, filled, empty) {
  // Build a 5-char star string for given score (rounded)
  var n = Math.round(score || 0);
  var s = '';
  for (var i = 1; i <= 5; i++) s += (i <= n ? filled : empty);
  return s;
}

function renderRating() {
  // Pure: reads companyState.stats + permissions → updates rating UI
  if (!window.companyState) return;
  var avg   = companyState.stats.rating_avg;
  var count = companyState.stats.rating_count || 0;
  var mine  = companyState.permissions ? companyState.permissions.my_rating : null;

  // Display average
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

  // Interactive stars reflect my_rating (if rated before)
  _paintRateStars(mine || 0);
  var prompt = document.getElementById('ratePrompt');
  if (prompt) prompt.textContent = mine ? ('تقييمك: ' + mine + ' من 5 (اضغط للتعديل)') : 'قيّم هذه الشركة:';
}

function _paintRateStars(score) {
  var stars = document.querySelectorAll('#rateStars span');
  stars.forEach(function(s) {
    var v = parseInt(s.getAttribute('data-score'));
    s.textContent = (v <= score) ? '⭐' : '☆';
  });
}

function submitRating(score) {
  if (!window._jwt || !_jwt()) { window.location.href = '/'; return; }
  if (!window.companyState) return;
  if (isRateLoading) return;

  var companyId = new URLSearchParams(location.search).get('id');
  if (!companyId) return;

  // Snapshot for rollback
  var prevMine  = companyState.permissions.my_rating;
  var prevAvg   = companyState.stats.rating_avg;
  var prevCount = companyState.stats.rating_count || 0;

  // Optimistic: paint selected stars
  companyState.permissions.my_rating = score;
  _paintRateStars(score);

  isRateLoading = true;
  fetch('/company/rate/' + companyId, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + _jwt() },
    body:    JSON.stringify({ score: score }),
  })
  .then(function(r) {
    if (!r.ok) throw new Error('rate failed: ' + r.status);
    return r.json();
  })
  .then(function(data) {
    // Re-sync from server (authoritative)
    if (typeof data.rating_avg === 'number' || data.rating_avg === null)
      companyState.stats.rating_avg = data.rating_avg;
    if (typeof data.rating_count === 'number')
      companyState.stats.rating_count = data.rating_count;
    if (typeof data.my_score === 'number')
      companyState.permissions.my_rating = data.my_score;
    renderRating();
    if (window.showToast) showToast('تم حفظ تقييمك ✓');
  })
  .catch(function() {
    // Rollback
    companyState.permissions.my_rating = prevMine;
    companyState.stats.rating_avg      = prevAvg;
    companyState.stats.rating_count    = prevCount;
    renderRating();
    if (window.showToast) showToast('تعذّر حفظ التقييم', 'error');
  })
  .finally(function() {
    isRateLoading = false;
  });
}

function bindRateStars() {
  // Idempotent: bind click on interactive stars once
  var box = document.getElementById('rateStars');
  if (!box || box.dataset.bound) return;
  box.dataset.bound = '1';
  box.addEventListener('click', function(e) {
    var span = e.target.closest('span[data-score]');
    if (!span) return;
    submitRating(parseInt(span.getAttribute('data-score')));
  });
}

// ── Posts system (Phase 3 Step 4: render from API, lazy load) ──
var _postsLoaded = false;
var _postsLoading = false;

function _escapeHtml(s) {
  var d = document.createElement('div');
  d.textContent = s == null ? '' : String(s);
  return d.innerHTML;
}

function _relativeTime(iso) {
  // Convert ISO date to Arabic relative time
  if (!iso) return '';
  var then = new Date(iso).getTime();
  if (isNaN(then)) return '';
  var diff = Math.floor((Date.now() - then) / 1000);
  if (diff < 60)    return 'الآن';
  if (diff < 3600)  return 'منذ ' + Math.floor(diff/60) + ' دقيقة';
  if (diff < 86400) return 'منذ ' + Math.floor(diff/3600) + ' ساعة';
  if (diff < 604800) return 'منذ ' + Math.floor(diff/86400) + ' يوم';
  if (diff < 2592000) return 'منذ ' + Math.floor(diff/604800) + ' أسبوع';
  return new Date(iso).toLocaleDateString('ar');
}

function _postCardHtml(post) {
  var coName = (window.companyState && companyState.profile)
    ? (companyState.profile.full_name || 'الشركة') : 'الشركة';
  var tagsHtml = '';
  if (post.tags && post.tags.length) {
    tagsHtml = '<div class="job-tags">' + post.tags.map(function(t) {
      return '<span class="jtag jtag-green">' + _escapeHtml(t) + '</span>';
    }).join('') + '</div>';
  }
  // Step 5-2: owner-only delete button (can_edit)
  var canEdit = window.companyState && companyState.permissions && companyState.permissions.can_edit;
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
  // Pure: renders posts array into #postsList
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

// ── Jobs loader (separate endpoint, initial load — Option B) ──
var _jobsLoading = false;


function loadJobs() {
  // Fetch company jobs from public endpoint, fill companyState.jobs, render
  // Uses NUMERIC id (companyState.profile.id) — /jobs expects int, not tw_id
  if (_jobsLoading) return;  // prevent duplicate requests
  if (!window.companyState || !companyState.profile) return;
  var numericId = companyState.profile.id;
  if (!numericId) return;
  _jobsLoading = true;
  fetch('/jobs?company_id=' + encodeURIComponent(numericId))
    .then(function(r) { return r.json(); })
    .then(function(data) {
      if (window.companyState) {
        companyState.jobs = (data && data.jobs) ? data.jobs : [];
        // renderJobs is local to the inline IIFE (not on window).
        // renderAll IS exposed and calls renderJobs internally → use it.
        if (window.renderAll) renderAll();
      }
    })
    .catch(function() {
      if (window.showToast) showToast('تعذّر تحميل الوظائف', 'error');
    })
    .finally(function() { _jobsLoading = false; });
}

function loadPosts(force) {
  // Lazy: fetch posts once (or force reload after create/delete)
  if (_postsLoading) return;
  if (_postsLoaded && !force) return;
  var companyId = new URLSearchParams(location.search).get('id');
  if (!companyId) return;
  _postsLoading = true;
  fetch('/company/posts/' + companyId)
    .then(function(r) { return r.json(); })
    .then(function(data) {
      _postsLoaded = true;
      renderPosts(data.posts || []);
    })
    .catch(function() {
      if (window.showToast) showToast('تعذّر تحميل المنشورات', 'error');
    })
    .finally(function() { _postsLoading = false; });
}


// ── Step 5-1: Create post (owner-only) ──
var isPostCreating = false;

function openPostModal() {
  if (!window.companyState || !companyState.permissions.can_edit) return;
  var ov = document.getElementById('postOverlay');
  if (ov) ov.classList.add('show');
  if (window.history) history.pushState({ modal: 'post' }, '', location.href);
}

function createPost() {
  if (!window._jwt || !_jwt()) { window.location.href = '/'; return; }
  if (!window.companyState || !companyState.permissions.can_edit) {
    if (window.showToast) showToast('غير مصرح', 'error'); return;
  }
  if (isPostCreating) return;

  var bodyEl = document.getElementById('p-body');
  var tagsEl = document.getElementById('p-tags');
  var body = (bodyEl ? bodyEl.value : '').trim();
  if (!body) { if (window.showToast) showToast('اكتب محتوى المنشور', 'error'); return; }

  var tags = (tagsEl ? tagsEl.value : '')
    .split(',').map(function(t){ return t.trim(); }).filter(Boolean);

  isPostCreating = true;
  fetch('/company/posts', {
    method:  'POST',
    headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + _jwt() },
    body:    JSON.stringify({ body: body, tags: tags.length ? tags : null }),
  })
  .then(function(r) {
    if (!r.ok) throw new Error('create failed: ' + r.status);
    return r.json();
  })
  .then(function() {
    // Close modal, clear inputs, reload list
    var ov = document.getElementById('postOverlay');
    if (ov) ov.classList.remove('show');
    if (bodyEl) bodyEl.value = '';
    if (tagsEl) tagsEl.value = '';
    loadPosts(true);  // force reload
    if (window.showToast) showToast('تم نشر المنشور ✓');
  })
  .catch(function() {
    if (window.showToast) showToast('تعذّر نشر المنشور', 'error');
  })
  .finally(function() { isPostCreating = false; });
}


// ── Step 5-2: Delete post (owner-only, confirm, no optimistic) ──
var isPostDeleting = false;

function deletePost(postId) {
  if (!window._jwt || !_jwt()) { window.location.href = '/'; return; }
  if (!window.companyState || !companyState.permissions.can_edit) {
    if (window.showToast) showToast('غير مصرح', 'error'); return;
  }
  if (isPostDeleting) return;
  if (!confirm('هل تريد حذف هذا المنشور؟')) return;

  isPostDeleting = true;
  fetch('/company/posts/' + postId, {
    method:  'DELETE',
    headers: { 'Authorization': 'Bearer ' + _jwt() },
  })
  .then(function(r) {
    if (!r.ok) throw new Error('delete failed: ' + r.status);
    return r.json();
  })
  .then(function() {
    loadPosts(true);  // reload from server (no optimistic)
    if (window.showToast) showToast('تم حذف المنشور ✓');
  })
  .catch(function() {
    if (window.showToast) showToast('تعذّر حذف المنشور', 'error');
  })
  .finally(function() { isPostDeleting = false; });
}

// ── Contact modal ──
function openContact() {
  var el = document.getElementById('contactOverlay');
  if (el) el.classList.add('show');
  if (window.history) history.pushState({ modal: 'contact' }, '', location.href);
}
function closeContact(e) {
  var el = document.getElementById('contactOverlay');
  if (!e || e.target === el) el && el.classList.remove('show');
}
function sendMsg() {
  var subject = (document.getElementById('msg-subject') || {}).value || 'رسالة جديدة';
  var body    = ((document.getElementById('msg-body') || {}).value || '').trim();
  if (!body) { if (window.showToast) showToast('أدخل الرسالة', 'error'); return; }
  var coId = new URLSearchParams(location.search).get('id');
  if (coId && window._jwt && _jwt()) {
    fetch('/admin/message', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + _jwt() },
      body:    JSON.stringify({ user_id: parseInt(coId) || 0, subject: subject, message: body }),
    }).catch(function() {});
  }
  if (window.showToast) showToast('تم إرسال رسالتك ✓');
  closeContact();
}

// ── Edit modal (owner only) ──
function openEditModal() {
  if (!window.companyState || !companyState.permissions.can_edit) return;
  var p = companyState.profile || {};
  var c = companyState.company || {};
  var setVal = function(id, val) { var el = document.getElementById(id); if (el) el.value = val || ''; };
  setVal('e-name', p.full_name);
  setVal('e-desc', p.bio);
  setVal('e-loc',  p.location);
  setVal('e-web',  p.website);
  setVal('e-email', c.contact_email);
  var ov = document.getElementById('editOverlay');
  if (ov) ov.classList.add('show');
  if (window.history) history.pushState({ modal: 'edit' }, '', location.href);
}
function closeEdit(e) {
  var el = document.getElementById('editOverlay');
  if (!e || e.target === el) el && el.classList.remove('show');
}
function saveEdit() {
  if (!window.companyState || !companyState.permissions.can_edit) return;
  var val = function(id) { return (document.getElementById(id) || {}).value || ''; };
  var name = val('e-name').trim();
  if (!name) { if (window.showToast) showToast('أدخل اسم الشركة', 'error'); return; }
  var coId = (companyState.profile || {}).id;
  var ov = document.getElementById('editOverlay');
  if (ov) ov.classList.remove('show');
  fetch('/profile/' + coId, {
    method:  'PUT',
    headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + _jwt() },
    body:    JSON.stringify({ full_name: name, bio: val('e-desc'), location: val('e-loc'), website: val('e-web') }),
  })
  .then(function(r) { return r.json(); })
  .then(function() {
    if (window.showToast) showToast('تم الحفظ ✓');
    if (window.loadData) loadData();
  })
  .catch(function() { if (window.showToast) showToast('خطأ في الحفظ', 'error'); });
}

// ── Post Job modal (owner only) ──
function openPostJob() {
  if (!window.companyState || !companyState.permissions.can_post_jobs) return;
  var el = document.getElementById('postJobOverlay');
  if (el) el.classList.add('show');
  if (window.history) history.pushState({ modal: 'postJob' }, '', location.href);
}
function publishJob() {
  if (!window.companyState || !companyState.permissions.can_post_jobs) {
    if (window.showToast) showToast('غير مصرح', 'error'); return;
  }
  var val = function(id) { return (document.getElementById(id) || {}).value || ''; };
  var title = val('j-title').trim();
  if (!title) { if (window.showToast) showToast('أدخل المسمى الوظيفي', 'error'); return; }
  var ov = document.getElementById('postJobOverlay');
  fetch('/company/jobs', {
    method:  'POST',
    headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + _jwt() },
    body:    JSON.stringify({
      title: title, description: val('j-desc'), location: val('j-loc'),
      job_type: val('j-type'),
      salary_min: parseInt(val('j-sal1')) || null,
      salary_max: parseInt(val('j-sal2')) || null,
    }),
  })
  .then(function(r) { return r.json(); })
  .then(function(data) {
    if (data.status === 'success') {
      if (ov) ov.classList.remove('show');
      if (window.showToast) showToast('تم نشر الوظيفة ✓');
      if (window.loadData) loadData();
    }
  })
  .catch(function() { if (window.showToast) showToast('خطأ في نشر الوظيفة', 'error'); });
}

// ── Apply job (onclick wrapper) ──
function applyJob(btn) {
  var card  = btn.closest('[data-jid]');
  var jobId = card ? card.dataset.jid : (btn.getAttribute('data-jobid') || '');
  if (window._applyJob) _applyJob(btn, jobId);
}

// ── Cover photo ──
function setCover(src) {
  var img  = document.getElementById('coverImg');
  var bg   = document.getElementById('heroBg');
  if (!img) return;
  img.src = src; img.style.display = 'block';
  setTimeout(function() { img.style.opacity = '1'; }, 50);
  if (bg) bg.style.opacity = '0';
  document.querySelectorAll('.hero-orb').forEach(function(o) { o.style.display = 'none'; });
}
function uploadCover(input) {
  if (!input.files[0]) return;
  var reader = new FileReader();
  reader.onload = function(e) { setCover(e.target.result); };
  reader.readAsDataURL(input.files[0]);
}

// ── Report system ──
var _reportTargetId = null, _reportTargetType = 'company', _reportTargetUrl = '';
function openReportModal(targetId, targetType, targetUrl) {
  _reportTargetId   = targetId;
  _reportTargetType = targetType  || 'company';
  _reportTargetUrl  = targetUrl   || location.href;
  var el = document.getElementById('reportModal');
  if (el) el.style.display = 'flex';
  var reason = document.getElementById('reportReason');
  if (reason) reason.value = '';
}
function closeReportModal() {
  var el = document.getElementById('reportModal');
  if (el) el.style.display = 'none';
}
function submitReport() {
  var type   = (document.getElementById('reportType')   || {}).value || '';
  var reason = ((document.getElementById('reportReason') || {}).value || '').trim();
  if (!reason) { if (window.showToast) showToast('اكتب سبب البلاغ', 'error'); return; }
  if (!_reportTargetId) { if (window.showToast) showToast('خطأ في البلاغ', 'error'); return; }
  var btn = document.getElementById('reportSubmitBtn');
  if (btn) { btn.disabled = true; btn.textContent = 'جاري الإرسال...'; }
  fetch('/reports/submit', {
    method:  'POST',
    headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + (window._jwt ? _jwt() : '') },
    body:    JSON.stringify({
      reported_id: _reportTargetId, reported_type: _reportTargetType,
      report_type: type, reason: reason, target_url: _reportTargetUrl,
    }),
  })
  .then(function(r) {
    if (r.ok) { if (window.showToast) showToast('تم إرسال البلاغ ✓'); closeReportModal(); }
    else throw new Error();
  })
  .catch(function() { if (window.showToast) showToast('خطأ في إرسال البلاغ', 'error'); })
  .finally(function() {
    if (btn) { btn.disabled = false; btn.textContent = '🚨 إرسال البلاغ'; }
  });
}
