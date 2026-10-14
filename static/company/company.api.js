// company.api.js — API calls for the company page (loadData, loadJobs, loadPosts, …)
// Every request goes through twApi (tw_shared.js — API Client Rule); session data from
// TwAuthSync only (never localStorage tw_user / tw_jwt). No X-User-Id.
// Load order: 2nd (after state)
(function () {
  'use strict';

  var _loadController = null;
  var _jobsLoading    = false;
  var _postsLoading   = false;
  var _postsLoaded    = false;

  function _snap() {
    return (window.TwAuthSync && typeof TwAuthSync.getSessionSnapshot === 'function')
      ? TwAuthSync.getSessionSnapshot() : { isAuthenticated: false, userType: null, userId: null };
  }

  // Load failure → the page error state (never an empty profile full of «—»).
  // 404 → «الشركة غير موجودة»; anything else (500 / network / bad body) → generic + retry.
  function _showLoadError(status) {
    var notFound = status === 404;
    var title = document.getElementById('coErrTitle');
    var sub   = document.getElementById('coErrSub');
    var retry = document.getElementById('coRetryBtn');
    if (title) title.textContent = twT(notFound ? 'company.error.not_found' : 'company.error.title');
    if (sub)   sub.textContent   = twT(notFound ? 'company.error.not_found_sub' : 'common.check_connection');
    if (retry) retry.hidden = notFound;
    document.body.classList.add('co-error');
  }

  // Main profile load — twApi (JWT added by twApi when there is a session)
  // opts.silent = true → state sync only, no renderAll / bindEvents / loadJobs / loadBranches
  function loadData(opts) {
    opts = opts || {};
    var silent = !!opts.silent;

    if (!silent) {
      if (_loadController) _loadController.abort();
      _loadController = typeof AbortController !== 'undefined' ? new AbortController() : null;
    }
    var ctrl = silent ? null : _loadController;

    // Priority: 1) injected by Smart Router (/u/C…), 2) ?id= query param, 3) session owner fallback
    var coId = (window._companyProfileIdFromRoute != null)
      ? String(window._companyProfileIdFromRoute)
      : new URLSearchParams(window.location.search).get('id');

    if (!coId) {
      // Auto-detect from the session (TwAuthSync — company account visiting without an id)
      var snap = _snap();
      if (snap.isAuthenticated && snap.userType === 'co' && snap.userId != null) {
        coId = String(snap.userId);
      } else {
        // No usable id — redirect rather than show placeholder
        if (!silent && window._applyLoadingState) window._applyLoadingState(false);
        if (!silent) location.replace(snap.isAuthenticated ? twHomeHref() : twLoginHref(location.pathname + location.search));
        return;
      }
    }

    twApi('/company/profile/' + encodeURIComponent(coId), ctrl ? { signal: ctrl.signal } : {})
    .then(function (res) {
      if (!silent && ctrl !== _loadController) return;   // superseded by a newer load
      var body = res.data;
      var ok = res.ok && body && body.status === 'success';
      if (!ok) {
        if (silent) return;
        if (res.error && res.error.generalError && res.error.generalError.code === 'aborted') return;
        console.error('[Company] loadData failed:', res.status, res.error);
        _showLoadError(res.status);
        if (window._applyLoadingState) window._applyLoadingState(false);
        _loadController = null;
        return;
      }
      if (window._mergeCompanyState) window._mergeCompanyState(body);
      if (!silent) {
        if (window._applyViewMode)          window._applyViewMode();
        if (window.renderAll)               window.renderAll();
        if (window.bindEvents)              window.bindEvents();
        if (window.loadJobs)                window.loadJobs();
        if (window.loadBranches)            window.loadBranches();
        if (window._loadCandidatesBadge)    window._loadCandidatesBadge();
        if (window._openPostJobFromUrl)     window._openPostJobFromUrl();
        if (window.loadMyApplications)      window.loadMyApplications();
        if (window._applyLoadingState)      window._applyLoadingState(false);
        _loadController = null;
      }
    });
  }

  // Retry from the error state (no inline handler in the page)
  (function () {
    var retry = document.getElementById('coRetryBtn');
    if (retry) retry.addEventListener('click', function () {
      if (window._applyLoadingState) window._applyLoadingState(true);
      loadData();
    });
  }());

  // Jobs — owner uses /company/jobs (all statuses); visitor uses public /jobs (active only)
  function loadJobs() {
    if (_jobsLoading) return;
    if (!window.companyState || !companyState.profile) return;
    var numericId = companyState.profile.id;
    if (!numericId) return;
    _jobsLoading = true;

    var isOwner = window.companyState && companyState.viewMode === 'owner' && _snap().isAuthenticated;
    var req = isOwner
      ? twApi('/company/jobs')
      : twApi('/jobs?company_id=' + encodeURIComponent(numericId), { auth: false });

    req.then(function (res) {
      _jobsLoading = false;
      if (!res.ok) {
        if (window.showToast) showToast(twApiMessage(res, 'تعذّر تحميل الوظائف'), 'error');
        return;
      }
      var data = res.data || {};
      if (window.companyState) {
        companyState.jobs = Array.isArray(data.jobs) ? data.jobs : [];
        // Visitor view: closed_count for summary line below job list
        if (!isOwner) {
          companyState.closedJobsCount = data.closed_count || 0;
        }
        if (window.renderAll) window.renderAll();
      }
    });
  }

  // Posts — lazy load; force=true to reload after create/delete
  function loadPosts(force) {
    if (_postsLoading) return;
    if (_postsLoaded && !force) return;
    var companyId = (window.companyState && companyState.profile && companyState.profile.id)
      ? String(companyState.profile.id)
      : new URLSearchParams(location.search).get('id');
    if (!companyId) return;
    _postsLoading = true;
    twApi('/company/posts/' + encodeURIComponent(companyId)).then(function (res) {
      _postsLoading = false;
      if (!res.ok) {
        if (window.showToast) showToast(twApiMessage(res, 'تعذّر تحميل المنشورات'), 'error');
        return;
      }
      _postsLoaded = true;
      if (window.renderPosts) window.renderPosts((res.data && res.data.posts) || []);
    });
  }

  // Employee applications — visitor/employee only; populates companyState.appliedJobIds (Set)
  function loadMyApplications() {
    if (!window.companyState || companyState.viewMode === 'owner') return;
    var snap = _snap();
    if (!snap.isAuthenticated || snap.userType !== 'emp') {
      companyState.appliedJobIds = new Set();
      return;
    }
    twApi('/my/applications').then(function (res) {
      if (!res.ok) {
        console.warn('[Company] /my/applications failed:', res.status);
        companyState.appliedJobIds = new Set();
        return;
      }
      var data = res.data;
      var apps = Array.isArray(data) ? data : ((data && data.applications) || []);
      companyState.appliedJobIds = new Set(apps.map(function (a) { return a.job_id; }));
      if (window.renderJobs) renderJobs();
    });
  }

  // Branches — public endpoint, fills companyState.branches then renders
  function loadBranches() {
    if (!window.companyState || !companyState.profile) return;
    var companyId = companyState.profile.id;
    if (!companyId) return;

    twApi('/company/branches/' + encodeURIComponent(companyId), { auth: false }).then(function (res) {
      if (!res.ok) { console.warn('[Company] branches load failed:', res.status); return; }
      if (window.companyState) {
        companyState.branches = (res.data && res.data.branches) || [];
        if (window.renderBranches) renderBranches(companyState.branches);
      }
    });
  }

  // Legacy result shape for the callers in company.main.js (Talent Bank / ratings): they read
  // the whole response body as res.data (also on errors: res.data.detail / res.data.code).
  // twApi does the request; this only maps {ok, status, raw} → {ok, status, data: body}.
  function _bodyShape(res) {
    return { ok: res.ok, status: res.status, data: res.raw || {}, error: res.error };
  }

  function _ownerOnly() {
    return _snap().isAuthenticated;
  }

  // Follow System (SYSTEMS_INDEX §20 · PR 3.5) — the same endpoints as every profile, via twApi.
  function followAccount(accountId, follow) {
    return twApi('/profile/' + encodeURIComponent(accountId) + '/follow', { method: follow ? 'POST' : 'DELETE' });
  }

  function getCompanyFollowersList(companyId, limit, offset, type) {
    var qs = '?limit=' + (limit || 20) + '&offset=' + (offset || 0) + '&type=' + encodeURIComponent(type || 'all');
    return twApi('/profile/' + encodeURIComponent(companyId) + '/followers' + qs);
  }

  function getCompanyRatingsDetail(companyId, limit) {
    var qs = limit ? '?limit=' + limit : '';
    return twApi('/company/' + encodeURIComponent(companyId) + '/ratings' + qs).then(_bodyShape);
  }

  // ── Saved Candidates (Phase 4 — owner-only, JWT required) ────────

  function getSavedCandidatesCount() {
    if (!_ownerOnly()) return Promise.resolve({ ok: false, data: { count: 0 } });
    return twApi('/company/saved-candidates/count').then(_bodyShape);
  }

  function getSavedCandidates(limit, offset, filters) {
    if (!_ownerOnly()) return Promise.resolve({ ok: false, data: {} });
    var qs = '?limit=' + (limit || 20) + '&offset=' + (offset || 0);
    if (filters) {
      if (filters.status)             qs += '&status='             + encodeURIComponent(filters.status);
      if (filters.q)                  qs += '&q='                  + encodeURIComponent(filters.q);
      if (filters.sort)               qs += '&sort='               + encodeURIComponent(filters.sort);
      if (filters.job_id)             qs += '&job_id='             + encodeURIComponent(filters.job_id);
      if (filters.unlinked)           qs += '&unlinked=true';
      if (filters.priority)           qs += '&priority='           + encodeURIComponent(filters.priority);
      if (filters.min_rating)         qs += '&min_rating='         + encodeURIComponent(filters.min_rating);
      if (filters.tag)                qs += '&tag='                + encodeURIComponent(filters.tag);
      if (filters.save_source_filter) qs += '&save_source_filter=' + encodeURIComponent(filters.save_source_filter);
    }
    return twApi('/company/saved-candidates' + qs).then(_bodyShape);
  }

  function getSavedCandidatesStats() {
    if (!_ownerOnly()) return Promise.resolve({ ok: false, data: {} });
    return twApi('/company/saved-candidates/stats').then(_bodyShape);
  }

  function deleteSavedCandidate(candidateId) {
    if (!_ownerOnly()) return Promise.resolve({ ok: false, data: {} });
    return twApi('/company/saved-candidates/' + encodeURIComponent(candidateId), { method: 'DELETE' }).then(_bodyShape);
  }

  // ── Candidate Suggestions (Phase 5A endpoint — owner-only) ──────

  function getCandidateSuggestions(limit, offset) {
    if (!_ownerOnly()) return Promise.resolve({ ok: false, data: {} });
    var qs = '?limit=' + (limit || 20) + '&offset=' + (offset || 0);
    return twApi('/company/candidate-suggestions' + qs).then(_bodyShape);
  }

  function saveSuggestedCandidate(candidateId) {
    if (!_ownerOnly()) return Promise.resolve({ ok: false, status: 401, data: {} });
    return twApi('/company/saved-candidates/' + encodeURIComponent(candidateId), { method: 'POST' }).then(_bodyShape);
  }

  // ── Pipeline management (Phase 6A endpoint — owner-only) ───────

  function updateSavedCandidate(candidateId, payload) {
    if (!_ownerOnly()) return Promise.resolve({ ok: false, data: {} });
    return twApi('/company/saved-candidates/' + encodeURIComponent(candidateId),
      { method: 'PATCH', body: payload }).then(_bodyShape);
  }

  // Per-job candidate classification — PATCH /company/saved-candidates/{cid}/jobs/{jid}
  // Touches only company_candidate_job_refs.candidate_status.
  // Never modifies job_applications.status or company_saved_candidates.status.
  function updateCandidateJobStatus(candidateId, jobId, candidateStatus) {
    if (!_ownerOnly()) return Promise.resolve({ ok: false, data: {} });
    return twApi('/company/saved-candidates/' + encodeURIComponent(candidateId) + '/jobs/' + encodeURIComponent(jobId),
      { method: 'PATCH', body: { candidate_status: candidateStatus || null } }).then(_bodyShape);
  }

  // Communication Hub — owner-only, calls existing GET /api/appointments endpoint
  function loadCompanyAppointments(cb) {
    if (!_ownerOnly()) { if (cb) cb([]); return; }
    twApi('/api/appointments').then(function (res) {
      var d = res.ok ? res.data : null;
      var appts = Array.isArray(d) ? d : ((d && (d.data || d.appointments)) || []);
      if (!res.ok) console.warn('[Company] appointments load failed:', res.status);
      if (cb) cb(appts);
    });
  }

  window.loadData                   = loadData;
  window.loadJobs                   = loadJobs;
  window.loadPosts                  = loadPosts;
  window.loadBranches               = loadBranches;
  window.loadMyApplications         = loadMyApplications;
  window.getCompanyFollowersList    = getCompanyFollowersList;
  window.followAccount              = followAccount;
  window.getCompanyRatingsDetail    = getCompanyRatingsDetail;
  window.getSavedCandidatesCount    = getSavedCandidatesCount;
  window.getSavedCandidates         = getSavedCandidates;
  window.getSavedCandidatesStats    = getSavedCandidatesStats;
  window.deleteSavedCandidate       = deleteSavedCandidate;
  window.getCandidateSuggestions    = getCandidateSuggestions;
  window.saveSuggestedCandidate     = saveSuggestedCandidate;
  window.updateSavedCandidate       = updateSavedCandidate;
  window.updateCandidateJobStatus   = updateCandidateJobStatus;
  window.loadCompanyAppointments    = loadCompanyAppointments;
}());
