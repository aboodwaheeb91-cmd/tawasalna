// company.jobs.js — job apply, post job, event binding, rating interactions
// Load order: 5th (after render)
(function () {
  'use strict';

  var isRateLoading = false;

  // ── Apply ──────────────────────────────────────────────────────
  function _applyJob(btn, jobId) {
    if (!jobId) return;
    if (!window._jwt || !_jwt()) { window.location.href = '/'; return; }
    btn.disabled = true; btn.textContent = 'جاري...';
    fetch('/jobs/' + jobId + '/apply', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + _jwt() },
      body:    JSON.stringify({ cover_letter: '' }),
    })
    .then(function (r) { return r.json(); })
    .then(function (data) {
      btn.textContent = data.already_applied ? '✓ قدّمت مسبقاً' : '✓ تم التقديم';
      btn.classList.add('applied');
    })
    .catch(function () {
      btn.disabled = false; btn.textContent = 'تقديم ←';
    });
  }

  // onclick wrapper — used by hardcoded cards in HTML before dynamic render
  function applyJob(btn) {
    var card  = btn.closest('[data-jid]');
    var jobId = card ? card.dataset.jid : (btn.getAttribute('data-jobid') || '');
    _applyJob(btn, jobId);
  }

  // ── Event binding (idempotent) ─────────────────────────────────
  function bindEvents() {
    var jobsList = document.getElementById('jobsList');
    if (jobsList && !jobsList.dataset.bound) {
      jobsList.dataset.bound = '1';
      jobsList.addEventListener('click', function (e) {
        var card = e.target.closest('[data-jid]');
        if (!card) return;
        if (e.target.classList.contains('apply-btn')) {
          e.stopPropagation();
          _applyJob(e.target, card.dataset.jid);
          return;
        }
        window.location.href = 'job-detail.html?id=' + card.dataset.jid;
      });
    }
    if (window.bindRateStars) bindRateStars();
  }

  // ── Rating ────────────────────────────────────────────────────
  function bindRateStars() {
    var box = document.getElementById('rateStars');
    if (!box || box.dataset.bound) return;
    box.dataset.bound = '1';
    box.addEventListener('click', function (e) {
      var span = e.target.closest('span[data-score]');
      if (!span) return;
      submitRating(parseInt(span.getAttribute('data-score')));
    });
  }

  function submitRating(score) {
    if (!window._jwt || !_jwt()) { window.location.href = '/'; return; }
    if (!window.companyState) return;
    if (isRateLoading) return;

    var companyId = new URLSearchParams(location.search).get('id');
    if (!companyId) return;

    var prevMine  = companyState.permissions.my_rating;
    var prevAvg   = companyState.stats.rating_avg;
    var prevCount = companyState.stats.rating_count || 0;

    companyState.permissions.my_rating = score;
    if (window._paintRateStars) _paintRateStars(score);

    isRateLoading = true;
    fetch('/company/rate/' + companyId, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + _jwt() },
      body:    JSON.stringify({ score: score }),
    })
    .then(function (r) {
      if (!r.ok) throw new Error('rate failed: ' + r.status);
      return r.json();
    })
    .then(function (data) {
      if (typeof data.rating_avg === 'number' || data.rating_avg === null)
        companyState.stats.rating_avg = data.rating_avg;
      if (typeof data.rating_count === 'number')
        companyState.stats.rating_count = data.rating_count;
      if (typeof data.my_score === 'number')
        companyState.permissions.my_rating = data.my_score;
      if (window.renderRating) renderRating();
      if (window.showToast) showToast('تم حفظ تقييمك ✓');
    })
    .catch(function () {
      companyState.permissions.my_rating = prevMine;
      companyState.stats.rating_avg      = prevAvg;
      companyState.stats.rating_count    = prevCount;
      if (window.renderRating) renderRating();
      if (window.showToast) showToast('تعذّر حفظ التقييم', 'error');
    })
    .finally(function () { isRateLoading = false; });
  }

  // ── Post job modal ─────────────────────────────────────────────
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
    var val = function (id) { return (document.getElementById(id) || {}).value || ''; };
    var title = val('j-title').trim();
    if (!title) { if (window.showToast) showToast('أدخل المسمى الوظيفي', 'error'); return; }
    var ov = document.getElementById('postJobOverlay');
    fetch('/company/jobs', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + _jwt() },
      body:    JSON.stringify({
        title:      title,
        description: val('j-desc'),
        location:   val('j-loc'),
        job_type:   val('j-type'),
        salary_min: parseInt(val('j-sal1')) || null,
        salary_max: parseInt(val('j-sal2')) || null,
      }),
    })
    .then(function (r) { return r.json(); })
    .then(function (data) {
      if (data.status === 'success') {
        if (ov) ov.classList.remove('show');
        if (window.showToast) showToast('تم نشر الوظيفة ✓');
        if (window.loadData) loadData();
      }
    })
    .catch(function () {
      if (window.showToast) showToast('خطأ في نشر الوظيفة', 'error');
    });
  }

  // ── Event bindings (commit #2) ──────────────────────────────────
  function _bindJobEvents() {
    var q = function (id) { return document.getElementById(id); };

    var postJobOverlay = q('postJobOverlay');
    if (postJobOverlay) postJobOverlay.addEventListener('click', function (e) {
      if (e.target === this) this.classList.remove('show');
    });

    var publishJobBtn = q('publishJobBtn'); if (publishJobBtn) publishJobBtn.addEventListener('click', publishJob);

    var postJobCancelBtn = q('postJobCancelBtn');
    if (postJobCancelBtn) postJobCancelBtn.addEventListener('click', function () {
      var ov = q('postJobOverlay'); if (ov) ov.classList.remove('show');
    });
  }

  window._applyJob     = _applyJob;
  window.applyJob      = applyJob;
  window.bindEvents    = bindEvents;
  window.bindRateStars = bindRateStars;
  window.submitRating  = submitRating;
  window.openPostJob   = openPostJob;
  window.publishJob    = publishJob;

  document.addEventListener('DOMContentLoaded', function () {
    bindEvents();
    _bindJobEvents();
  });
}());
