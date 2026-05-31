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
