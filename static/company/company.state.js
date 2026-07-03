// company.state.js — companyState SSOT + viewMode + JWT helper
// Rule #19: companyState is the Single Source of Truth
// Rule #21: API → State → Render → Events (strict pipeline)
// Load order: 1st (no dependencies)
(function () {
  'use strict';

  // Bootstrap guard (Rule #10)
  window.__companyBooted = false;

  // companyState — initial shape (Rule #19)
  window.companyState = {
    profile: {
      id: null, tw_id: null, full_name: null, user_type: null,
      bio: null, location: null, avatar_url: null,
      website: null, phone: null, is_verified: false,
    },
    company: {
      company_type: null, founded_year: null, company_size: null,
      cover_url: null, industry: null, headquarters: null, contact_email: null,
    },
    jobs: [],
    stats: { jobs_count: 0, posts_count: 0, views_count: 0, followers_count: 0, rating_avg: null },
    permissions: {
      is_owner: false, can_edit: false, can_post_jobs: false,
      can_follow: false, can_rate: false,
    },
    viewMode: 'guest',
  };

  // Atomic state replacement — called only from loadData()
  function _mergeCompanyState(apiResponse) {
    if (!apiResponse || apiResponse.status !== 'success') return;
    companyState.profile     = apiResponse.profile     || {};
    companyState.company     = apiResponse.company     || {};
    // Only replace jobs when the API explicitly returns an array — the silent 30-second
    // refresh calls /company/profile which doesn't include jobs, so we must not wipe
    // the already-loaded jobs array in that case.
    if (Array.isArray(apiResponse.jobs)) {
      companyState.jobs = apiResponse.jobs;
    }
    companyState.stats       = apiResponse.stats       || companyState.stats;
    companyState.permissions = apiResponse.permissions || {};
    companyState.viewMode    = apiResponse.viewer_type || 'guest';
  }

  // Pure CSS class setter — called once after _mergeCompanyState
  function _applyViewMode() {
    var vm = companyState.viewMode;
    document.body.classList.remove('view-owner', 'public-view', 'view-guest');
    if      (vm === 'owner')       document.body.classList.add('view-owner');
    else if (vm === 'public-user') document.body.classList.add('public-view');
    else                           document.body.classList.add('view-guest');
  }

  function _jwt() {
    return localStorage.getItem('tw_jwt') || '';
  }

  window._mergeCompanyState = _mergeCompanyState;
  window._applyViewMode     = _applyViewMode;
  window._jwt               = _jwt;
}());
