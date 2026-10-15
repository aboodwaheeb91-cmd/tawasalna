/* profile-v2.apps.js — "My Applications" tab (owner-only)
 * Re-fetches on every tab activation so company status changes appear immediately.
 * Auth: twApi (JWT from the session — no X-User-Id, no direct tw_jwt read · PR 4.2a).
 * Load order: after profile-v2.utils.js (scTab must be defined).
 */
(function () {
  'use strict';

  var _loading = false;

  // The server sends the applicant's 3 states only (auth.applicant_visible_status — task 5.0c):
  // in_review / hired / rejected. Internal company stages never reach this page.
  var _STATUS_KEY = { in_review: 'apps.status.in_review', hired: 'apps.status.hired', rejected: 'apps.status.rejected' };

  // Re-fetch on every 'apps' tab activation — no _loaded gate — so that
  // status changes made by companies (via PR 322) are always reflected.
  var _origScTab = window.scTab;
  window.scTab = function (name, el) {
    _origScTab(name, el);
    if (name === 'apps' && !_loading) { _loadApps(); }
  };

  function _loadApps() {
    if (_loading) return;
    if (window._scViewerType !== 'owner') return;

    var pane = document.getElementById('scAppsPane');
    if (!pane) return;

    _loading = true;
    pane.innerHTML = '<div class="sc-app-loading">' + twEscHtml(twT('apps.loading')) + '</div>';

    twApi('/my/applications').then(function (r) {
      _loading = false;
      if (!r.ok) {
        var msg = twT((r.status === 401 || r.status === 403) ? 'apps.session_expired' : 'apps.load_error');
        pane.innerHTML = '<div class="sc-app-empty">' + twEscHtml(msg) + '</div>';
        return;
      }
      var data = r.raw;
      var apps = (data && Array.isArray(data.applications)) ? data.applications : [];
      if (!apps.length) {
        pane.innerHTML = '<div class="sc-app-empty">' + twEscHtml(twT('apps.empty')) + '</div>';
        return;
      }
      pane.innerHTML = _buildList(apps);
    });
  }

  function _statusKey(s) { return _STATUS_KEY[s] ? s : 'in_review'; }

  function _buildList(apps) {
    var html = '<div class="sc-app-list">';
    apps.forEach(function (app) {
      var statusKey = _statusKey(app.status);
      html += '<div class="sc-app-card">'
        + '<div class="sc-app-top">'
        +   '<div class="sc-app-info">'
        +     '<div class="sc-app-title">' + twEscHtml(app.title || '—') + '</div>'
        +     '<div class="sc-app-company">' + twEscHtml(app.company_name || '') + '</div>'
        +     (app.location ? '<div class="sc-app-loc">' + twEscHtml(app.location) + '</div>' : '')
        +   '</div>'
        +   '<span class="sc-app-status sc-app-status--' + twEscHtml(statusKey) + '">'
        +     twEscHtml(twT(_STATUS_KEY[statusKey]))
        +   '</span>'
        + '</div>'
        + '<div class="sc-app-meta">' + twEscHtml(twT('apps.applied_at', { date: twFormatDate(app.applied_at) })) + '</div>'
        + '<div class="sc-app-actions">'
        +   '<a class="sc-app-btn" href="/job-detail?id=' + parseInt(app.job_id || 0, 10) + '">' + twEscHtml(twT('apps.view_job')) + '</a>'
        +   (app.company_tw_id ? '<a class="sc-app-btn" href="/u/' + twEscHtml(app.company_tw_id) + '" target="_blank" rel="noopener">' + twEscHtml(twT('apps.company_profile')) + '</a>' : '')
        + '</div>'
        + '</div>';
    });
    html += '</div>';
    return html;
  }

  // Public: allow forced reload (e.g. after applying from another tab)
  window._scLoadApps = _loadApps;

}());
