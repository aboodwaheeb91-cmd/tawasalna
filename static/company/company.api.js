// company.api.js — feed fetch functions (loadData, loadJobs, loadPosts)
// All auth via JWT Bearer — no X-User-Id.
// Load order: 2nd (after state)
(function () {
  'use strict';

  var _loadController = null;
  var _jobsLoading    = false;
  var _postsLoading   = false;
  var _postsLoaded    = false;

  // Main profile load — AbortController + JWT
  function loadData() {
    if (_loadController) _loadController.abort();
    _loadController = new AbortController();

    var urlParams = new URLSearchParams(window.location.search);
    var coId      = urlParams.get('id');
    var jwt       = window._jwt ? window._jwt() : '';
    var headers   = { 'Content-Type': 'application/json' };
    if (jwt) headers['Authorization'] = 'Bearer ' + jwt;

    if (!coId) {
      console.warn('[Company] No company id in URL');
      return;
    }

    fetch('/company/profile/' + coId, {
      headers: headers,
      signal:  _loadController.signal,
    })
    .then(function (r) { return r.json(); })
    .then(function (data) {
      if (window._mergeCompanyState) window._mergeCompanyState(data);
      if (window._applyViewMode)     window._applyViewMode();
      if (window.renderAll)          window.renderAll();
      if (window.bindEvents)         window.bindEvents();
      if (window.loadJobs)           window.loadJobs();
    })
    .catch(function (err) {
      if (err.name === 'AbortError') return;
      console.error('[Company] loadData error:', err);
    })
    .finally(function () {
      if (window._applyLoadingState) window._applyLoadingState(false);
      _loadController = null;
    });
  }

  // Jobs — public endpoint, fills companyState.jobs then re-renders
  function loadJobs() {
    if (_jobsLoading) return;
    if (!window.companyState || !companyState.profile) return;
    var numericId = companyState.profile.id;
    if (!numericId) return;
    _jobsLoading = true;
    fetch('/jobs?company_id=' + encodeURIComponent(numericId))
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (window.companyState) {
          companyState.jobs = (data && data.jobs) ? data.jobs : [];
          if (window.renderAll) window.renderAll();
        }
      })
      .catch(function () {
        if (window.showToast) showToast('تعذّر تحميل الوظائف', 'error');
      })
      .finally(function () { _jobsLoading = false; });
  }

  // Posts — lazy load; force=true to reload after create/delete
  function loadPosts(force) {
    if (_postsLoading) return;
    if (_postsLoaded && !force) return;
    var companyId = new URLSearchParams(location.search).get('id');
    if (!companyId) return;
    _postsLoading = true;
    fetch('/company/posts/' + companyId)
      .then(function (r) { return r.json(); })
      .then(function (data) {
        _postsLoaded = true;
        if (window.renderPosts) window.renderPosts(data.posts || []);
      })
      .catch(function () {
        if (window.showToast) showToast('تعذّر تحميل المنشورات', 'error');
      })
      .finally(function () { _postsLoading = false; });
  }

  window.loadData  = loadData;
  window.loadJobs  = loadJobs;
  window.loadPosts = loadPosts;
}());
