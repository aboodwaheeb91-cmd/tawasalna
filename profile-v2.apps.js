/* profile-v2.apps.js — "My Applications" tab (owner-only)
 * Re-fetches on every tab activation so company status changes appear immediately.
 * Auth: twApi (JWT from the session — no X-User-Id, no direct tw_jwt read · PR 4.2a).
 * Load order: after profile-v2.utils.js (scTab must be defined).
 */
(function () {
  'use strict';

  var _loading = false;

  var _STATUS_LABEL = {
    pending:  'بانتظار المراجعة',
    viewed:   'تمت المراجعة',
    accepted: 'مقبول',
    rejected: 'غير مناسب'
  };

  // Re-fetch on every 'apps' tab activation — no _loaded gate — so that
  // status changes made by companies (via PR #322) are always reflected.
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
    pane.innerHTML = '<div class="sc-app-loading">جارٍ تحميل طلباتك…</div>';

    twApi('/my/applications').then(function (r) {
      _loading = false;
      if (!r.ok) {
        var msg = (r.status === 401 || r.status === 403)
          ? 'انتهت الجلسة، يرجى تسجيل الدخول مجدداً'
          : 'تعذّر تحميل طلباتك، حاول مجدداً';
        pane.innerHTML = '<div class="sc-app-empty">' + msg + '</div>';
        return;
      }
      var data = r.raw;
      var apps = (data && Array.isArray(data.applications)) ? data.applications : [];
      if (!apps.length) {
        pane.innerHTML = '<div class="sc-app-empty">لم تقدم على أي وظيفة بعد</div>';
        return;
      }
      pane.innerHTML = _buildList(apps);
    });
  }

  function _fmtDate(iso) {
    if (!iso) return '';
    try {
      return new Date(iso).toLocaleDateString('ar-EG', {
        year: 'numeric', month: 'short', day: 'numeric'
      });
    } catch (e) { return ''; }
  }

  function _statusLabel(s) { return _STATUS_LABEL[s] || s || '—'; }

  function _buildList(apps) {
    var html = '<div class="sc-app-list">';
    apps.forEach(function (app) {
      var statusKey = app.status || 'pending';
      html += '<div class="sc-app-card">'
        + '<div class="sc-app-top">'
        +   '<div class="sc-app-info">'
        +     '<div class="sc-app-title">' + twEscHtml(app.title || '—') + '</div>'
        +     '<div class="sc-app-company">' + twEscHtml(app.company_name || '') + '</div>'
        +     (app.location ? '<div class="sc-app-loc">' + twEscHtml(app.location) + '</div>' : '')
        +   '</div>'
        +   '<span class="sc-app-status sc-app-status--' + twEscHtml(statusKey) + '">'
        +     twEscHtml(_statusLabel(statusKey))
        +   '</span>'
        + '</div>'
        + '<div class="sc-app-meta">تاريخ التقديم: ' + twEscHtml(_fmtDate(app.applied_at)) + '</div>'
        + '<div class="sc-app-actions">'
        +   '<a class="sc-app-btn" href="/job-detail?id=' + parseInt(app.job_id || 0, 10) + '">عرض الوظيفة</a>'
        +   (app.company_tw_id ? '<a class="sc-app-btn" href="/u/' + twEscHtml(app.company_tw_id) + '" target="_blank" rel="noopener">ملف الشركة</a>' : '')
        + '</div>'
        + '</div>';
    });
    html += '</div>';
    return html;
  }

  // Public: allow forced reload (e.g. after applying from another tab)
  window._scLoadApps = _loadApps;

}());
