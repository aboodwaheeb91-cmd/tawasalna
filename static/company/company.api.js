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
  // opts.silent = true → state sync only, no renderAll / bindEvents / loadJobs / loadBranches
  function loadData(opts) {
    opts = opts || {};
    var silent = !!opts.silent;

    if (!silent) {
      if (_loadController) _loadController.abort();
      _loadController = new AbortController();
    }

    // Priority: 1) injected by Smart Router (/u/C…), 2) ?id= query param, 3) session owner fallback
    var coId = (window._companyProfileIdFromRoute != null)
      ? String(window._companyProfileIdFromRoute)
      : new URLSearchParams(window.location.search).get('id');
    var jwt       = window._jwt ? window._jwt() : '';
    var headers   = { 'Content-Type': 'application/json' };
    if (jwt) headers['Authorization'] = 'Bearer ' + jwt;

    if (!coId) {
      // Auto-detect from session (company owner visiting /company-profile without ?id=)
      var _u = null;
      try { _u = JSON.parse(localStorage.getItem('tw_user') || 'null'); } catch (e) {}
      if (_u && _u.user_type === 'co' && _u.id) {
        coId = String(_u.id);
      } else {
        // No usable id — redirect rather than show placeholder
        if (!silent && window._applyLoadingState) window._applyLoadingState(false);
        if (!silent) window.location.href = (_u && _u.id) ? '/home' : '/login';
        return;
      }
    }

    var fetchOpts = { headers: headers };
    if (!silent && _loadController) fetchOpts.signal = _loadController.signal;

    fetch('/company/profile/' + coId, fetchOpts)
    .then(function (r) { return r.json(); })
    .then(function (data) {
      if (window._mergeCompanyState) window._mergeCompanyState(data);
      if (!silent) {
        if (window._applyViewMode)          window._applyViewMode();
        if (window.renderAll)               window.renderAll();
        if (window.bindEvents)              window.bindEvents();
        if (window.loadJobs)                window.loadJobs();
        if (window.loadBranches)            window.loadBranches();
        if (window._loadCandidatesBadge)    window._loadCandidatesBadge();
        if (window.loadMyApplications)      window.loadMyApplications();
      }
    })
    .catch(function (err) {
      if (!silent) {
        if (err.name === 'AbortError') return;
        console.error('[Company] loadData error:', err);
      }
    })
    .finally(function () {
      if (!silent) {
        if (window._applyLoadingState) window._applyLoadingState(false);
        _loadController = null;
      }
    });
  }

  // Jobs — owner uses /company/jobs (all statuses); visitor uses public /jobs (active only)
  function loadJobs() {
    if (_jobsLoading) return;
    if (!window.companyState || !companyState.profile) return;
    var numericId = companyState.profile.id;
    if (!numericId) return;
    _jobsLoading = true;

    var isOwner = window.companyState && companyState.viewMode === 'owner';
    var jwt = window._jwt ? window._jwt() : '';
    var url, fetchOpts;
    if (isOwner && jwt) {
      url       = '/company/jobs';
      fetchOpts = { headers: { 'Authorization': 'Bearer ' + jwt } };
    } else {
      url       = '/jobs?company_id=' + encodeURIComponent(numericId);
      fetchOpts = {};
    }

    fetch(url, fetchOpts)
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (window.companyState) {
          companyState.jobs = (data && data.jobs) ? data.jobs : [];
          // Visitor view: closed_count for summary line below job list
          if (!isOwner) {
            companyState.closedJobsCount = (data && data.closed_count) || 0;
          }
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
    if (!companyId && window.companyState && companyState.profile && companyState.profile.id)
      companyId = String(companyState.profile.id);
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

  // Employee applications — visitor/employee only; populates companyState.appliedJobIds (Set)
  function loadMyApplications() {
    if (!window.companyState || companyState.viewMode === 'owner') return;
    var jwt = window._jwt ? window._jwt() : '';
    var _u = null;
    try { _u = JSON.parse(localStorage.getItem('tw_user') || 'null'); } catch (e) {}
    if (!jwt || !_u || _u.user_type !== 'emp') {
      if (window.companyState) companyState.appliedJobIds = new Set();
      return;
    }
    fetch('/my/applications', { headers: { 'Authorization': 'Bearer ' + jwt } })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var apps = Array.isArray(data) ? data : (data.applications || []);
        if (window.companyState) {
          companyState.appliedJobIds = new Set(apps.map(function (a) { return a.job_id; }));
          if (window.renderJobs) renderJobs();
        }
      })
      .catch(function () {
        if (window.companyState) companyState.appliedJobIds = new Set();
      });
  }

  // Branches — public endpoint, fills companyState.branches then renders
  function loadBranches() {
    if (!window.companyState || !companyState.profile) return;
    var companyId = companyState.profile.id;
    if (!companyId) return;

    fetch('/company/branches/' + companyId)
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (window.companyState) {
          companyState.branches = data.branches || [];
          if (window.renderBranches) renderBranches(companyState.branches);
        }
      })
      .catch(function () {});
  }

  function getCompanyFollowersList(companyId, limit, offset, type) {
    var qs = '?limit=' + (limit || 20) + '&offset=' + (offset || 0) + '&type=' + (type || 'all');
    var jwt = window._jwt ? window._jwt() : '';
    var headers = {};
    if (jwt) headers['Authorization'] = 'Bearer ' + jwt;
    return fetch('/company/' + companyId + '/followers' + qs, { headers: headers })
      .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, data: d }; }); });
  }

  function getCompanyRatingsDetail(companyId, limit) {
    var qs = limit ? '?limit=' + limit : '';
    var jwt = window._jwt ? window._jwt() : '';
    var headers = {};
    if (jwt) headers['Authorization'] = 'Bearer ' + jwt;
    return fetch('/company/' + companyId + '/ratings' + qs, { headers: headers })
      .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, data: d }; }); });
  }

  // ── Saved Candidates (Phase 4 — owner-only, JWT required) ────────

  function getSavedCandidatesCount() {
    var jwt = window._jwt ? window._jwt() : '';
    if (!jwt) return Promise.resolve({ ok: false, data: { count: 0 } });
    return fetch('/company/saved-candidates/count', {
      headers: { 'Authorization': 'Bearer ' + jwt }
    }).then(function (r) { return r.json().then(function (d) { return { ok: r.ok, data: d }; }); });
  }

  function getSavedCandidates(limit, offset, filters) {
    var jwt = window._jwt ? window._jwt() : '';
    if (!jwt) return Promise.resolve({ ok: false, data: {} });
    var qs = '?limit=' + (limit || 20) + '&offset=' + (offset || 0);
    if (filters) {
      if (filters.status)   qs += '&status='  + encodeURIComponent(filters.status);
      if (filters.q)        qs += '&q='       + encodeURIComponent(filters.q);
      if (filters.sort)     qs += '&sort='    + encodeURIComponent(filters.sort);
      if (filters.job_id)   qs += '&job_id='  + encodeURIComponent(filters.job_id);
      if (filters.unlinked) qs += '&unlinked=true';
    }
    return fetch('/company/saved-candidates' + qs, {
      headers: { 'Authorization': 'Bearer ' + jwt }
    }).then(function (r) { return r.json().then(function (d) { return { ok: r.ok, data: d }; }); });
  }

  function getSavedCandidatesStats() {
    var jwt = window._jwt ? window._jwt() : '';
    if (!jwt) return Promise.resolve({ ok: false, data: {} });
    return fetch('/company/saved-candidates/stats', {
      headers: { 'Authorization': 'Bearer ' + jwt }
    }).then(function (r) { return r.json().then(function (d) { return { ok: r.ok, data: d }; }); });
  }

  function deleteSavedCandidate(candidateId) {
    var jwt = window._jwt ? window._jwt() : '';
    if (!jwt) return Promise.resolve({ ok: false, data: {} });
    return fetch('/company/saved-candidates/' + candidateId, {
      method: 'DELETE',
      headers: { 'Authorization': 'Bearer ' + jwt }
    }).then(function (r) { return r.json().then(function (d) { return { ok: r.ok, data: d }; }); });
  }

  // ── Candidate Suggestions (Phase 5A endpoint — owner-only) ──────

  function getCandidateSuggestions(limit, offset) {
    var jwt = window._jwt ? window._jwt() : '';
    if (!jwt) return Promise.resolve({ ok: false, data: {} });
    var qs = '?limit=' + (limit || 20) + '&offset=' + (offset || 0);
    return fetch('/company/candidate-suggestions' + qs, {
      headers: { 'Authorization': 'Bearer ' + jwt }
    }).then(function (r) { return r.json().then(function (d) { return { ok: r.ok, status: r.status, data: d }; }); });
  }

  function saveSuggestedCandidate(candidateId) {
    var jwt = window._jwt ? window._jwt() : '';
    if (!jwt) return Promise.resolve({ ok: false, data: {} });
    return fetch('/company/saved-candidates/' + candidateId, {
      method: 'POST',
      headers: { 'Authorization': 'Bearer ' + jwt }
    }).then(function (r) { return r.json().then(function (d) { return { ok: r.ok, status: r.status, data: d }; }); });
  }

  // ── Pipeline management (Phase 6A endpoint — owner-only) ───────

  function updateSavedCandidate(candidateId, payload) {
    var jwt = window._jwt ? window._jwt() : '';
    if (!jwt) return Promise.resolve({ ok: false, data: {} });
    return fetch('/company/saved-candidates/' + candidateId, {
      method: 'PATCH',
      headers: { 'Authorization': 'Bearer ' + jwt, 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }).then(function (r) { return r.json().then(function (d) { return { ok: r.ok, status: r.status, data: d }; }); });
  }

  window.loadData                   = loadData;
  window.loadJobs                   = loadJobs;
  window.loadPosts                  = loadPosts;
  window.loadBranches               = loadBranches;
  window.loadMyApplications         = loadMyApplications;
  window.getCompanyFollowersList    = getCompanyFollowersList;
  window.getCompanyRatingsDetail    = getCompanyRatingsDetail;
  window.getSavedCandidatesCount    = getSavedCandidatesCount;
  window.getSavedCandidates         = getSavedCandidates;
  window.getSavedCandidatesStats    = getSavedCandidatesStats;
  window.deleteSavedCandidate       = deleteSavedCandidate;
  window.getCandidateSuggestions    = getCandidateSuggestions;
  window.saveSuggestedCandidate     = saveSuggestedCandidate;
  window.updateSavedCandidate       = updateSavedCandidate;
}());
