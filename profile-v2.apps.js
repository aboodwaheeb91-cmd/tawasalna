/* profile-v2.apps.js — "My Applications" tab (owner-only)
 * Lazy-loads GET /my/applications on first tab activation.
 * Auth: Authorization: Bearer tw_jwt only — no X-User-Id.
 * Load order: after profile-v2.utils.js (scTab must be defined).
 */
(function () {
  'use strict';

  var _loaded  = false;
  var _loading = false;

  var _STATUS_LABEL = {
    pending:  'بانتظار المراجعة',
    viewed:   'تمت المراجعة',
    accepted: 'مقبول',
    rejected: 'غير مناسب'
  };

  // Wrap scTab to lazy-load on first 'apps' activation
  var _origScTab = window.scTab;
  window.scTab = function (name, el) {
    _origScTab(name, el);
    if (name === 'apps' && !_loaded && !_loading) { _loadApps(); }
  };

  function _loadApps() {
    if (_loading || _loaded) return;
    if (window._scViewerType !== 'owner') return;

    var pane = document.getElementById('scAppsPane');
    if (!pane) return;

    _loading = true;
    pane.innerHTML = '<div class="sc-app-loading">جارٍ التحميل…</div>';

    var jwt = localStorage.getItem('tw_jwt') || '';
    if (!jwt) {
      pane.innerHTML = '<div class="sc-app-empty">يجب تسجيل الدخول أولاً</div>';
      _loading = false;
      return;
    }

    fetch('/my/applications', { headers: { 'Authorization': 'Bearer ' + jwt } })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        _loaded   = true;
        _loading  = false;
        var apps  = (data && Array.isArray(data.applications)) ? data.applications : [];
        if (!apps.length) {
          pane.innerHTML = '<div class="sc-app-empty">لم تقدم على أي وظيفة بعد</div>';
          return;
        }
        pane.innerHTML = _buildList(apps);
      })
      .catch(function () {
        _loading = false;
        pane.innerHTML = '<div class="sc-app-empty">تعذّر تحميل الطلبات، حاول مجدداً</div>';
      });
  }

  function _esc(s) {
    return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
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
      html += '<div class="sc-app-card">'
        + '<div class="sc-app-top">'
        +   '<div class="sc-app-info">'
        +     '<div class="sc-app-title">' + _esc(app.title || '—') + '</div>'
        +     '<div class="sc-app-company">' + _esc(app.company_name || '') + '</div>'
        +   '</div>'
        +   '<span class="sc-app-status sc-app-status--' + _esc(app.status || 'pending') + '">'
        +     _esc(_statusLabel(app.status))
        +   '</span>'
        + '</div>'
        + '<div class="sc-app-meta">تاريخ التقديم: ' + _esc(_fmtDate(app.applied_at)) + '</div>'
        + '<div class="sc-app-actions">'
        +   '<a class="sc-app-btn" href="/job-detail?id=' + parseInt(app.job_id || 0, 10) + '">عرض الوظيفة</a>'
        + '</div>'
        + '</div>';
    });
    html += '</div>';
    return html;
  }

  // Public: allow forced reload (e.g. after applying from another tab)
  window._scLoadApps = _loadApps;

}());
