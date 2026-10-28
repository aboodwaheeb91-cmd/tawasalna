/* profile-v2.apps.js — "My Applications" tab (owner-only)
 * Re-fetches on every tab activation so company status changes appear immediately.
 * Auth: twApi (JWT from the session — no X-User-Id, no direct tw_jwt read · PR 4.2a).
 * Withdraw (task 8.2b): twAction('withdraw_application') on in_review cards only — the registry
 * carries the DS-OVL twConfirm; POST /jobs/applications/{id}/withdraw; 4xx → the server's text.
 * Load order: after profile-v2.utils.js (scTab must be defined).
 */
(function () {
  'use strict';

  var _loading = false;

  // The server sends the applicant's 3 states only (auth.applicant_visible_status — task 5.0c):
  // in_review / hired / rejected / withdrawn (task 8.2a). Internal company stages never reach this page.
  var _STATUS_KEY = { in_review: 'apps.status.in_review', hired: 'apps.status.hired',
                      rejected: 'apps.status.rejected', withdrawn: 'apps.status.withdrawn' };

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
        // 401 → the session is over; the shared «انتهت الجلسة» notice says it (task 8.3b)
        if (r.status === 401) { pane.innerHTML = ''; return; }
        var msg = twT(r.status === 403 ? 'apps.session_expired' : 'apps.load_error');
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
      _mountWithdraw(pane);
    });
  }

  // «سحب الطلب» — only in_review cards carry a slot (_buildList); the button itself = twAction.
  function _mountWithdraw(pane) {
    if (typeof window.twAction !== 'function') return;
    pane.querySelectorAll('[data-sc-withdraw-slot]').forEach(function (slot) {
      var appId = parseInt(slot.getAttribute('data-app-id'), 10);
      var btn = appId ? twAction('withdraw_application', {
        className: 'sc-app-btn sc-app-btn-danger',
        onClick: function (ctx, el) { _withdraw(appId, el, slot); },
      }) : null;
      if (btn) slot.appendChild(btn);
    });
  }

  function _withdraw(appId, btn, slot) {
    if (btn) btn.disabled = true;
    twApi('/jobs/applications/' + appId + '/withdraw', { method: 'POST' }).then(function (r) {
      if (!r.ok) {
        if (btn) btn.disabled = false;
        if (r.status !== 401) showToast(twApiMessage(r, twT('apps.withdraw.err')), 'error');
        return;
      }
      var card = slot.closest('.sc-app-card');
      var badge = card && card.querySelector('.sc-app-status');
      if (badge) {
        badge.className = 'sc-app-status sc-app-status--withdrawn';
        badge.textContent = twT('apps.status.withdrawn');
      }
      slot.remove();
      showToast(twT('apps.withdraw.ok'), 'success');
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
        +   (statusKey === 'in_review' ? '<span class="sc-app-withdraw-slot" data-sc-withdraw-slot data-app-id="' + parseInt(app.id || 0, 10) + '"></span>' : '')
        + '</div>'
        + '</div>';
    });
    html += '</div>';
    return html;
  }

  // Public: allow forced reload (e.g. after applying from another tab)
  window._scLoadApps = _loadApps;

}());
