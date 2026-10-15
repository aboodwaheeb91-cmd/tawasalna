// static/shared/admin-jobs.js — admin job actions, shared by the jobs list (admin.js) and the job page
// (admin-job.js) — task 5.3j phase 4 · SYSTEMS_INDEX §25e · docs/rules/admin-shell.md (19–21).
//   - ACTIONS: every job write (TwAdminShell.run — confirm first; «تم» only on {ok: true})
//   - actions(j): which buttons fit a job (server state + effective_status — never computed here)
//   - button(a, j, opts): the button for one action (dialogs: reason = hide / close · duration = reactivate /
//     extend · delete = GET …/delete-preview first, its counts in the typed-word confirm)
//   opts = { durations: [n…] (server list — _ALLOWED_DURATIONS), done(res) → reload / bool }
(function () {
  'use strict';
  var DEL_WORD = 'admin.confirm.word.delete';
  function jobUrl(c, tail) { return '/admin/jobs/' + Number(c.id) + (tail || ''); }
  function apiOk(d) { return !!(d && d.ok); }
  var ACTIONS = {
    'job.delete': {
      confirm: { title: 'admin.delete_job.title', message: 'admin.delete_job.message', confirm: 'admin.delete.confirm',
                 danger: true, typeWord: DEL_WORD },
      request: function (c) { return { url: jobUrl(c), method: 'DELETE' }; },
      done: 'admin.done.deleted' },
    'job.edit': {
      confirm: { title: 'admin.job.edit.title', message: 'admin.job.edit.message', confirm: 'admin.job.edit.save' },
      request: function (c) { return { url: jobUrl(c), method: 'PUT', body: c.fields }; },
      ok: apiOk, done: 'admin.done.job_edited' },
    'job.hide': {
      confirm: { title: 'admin.jobs.hide.title', message: 'admin.jobs.hide.message', confirm: 'admin.jobs.hide', danger: true },
      request: function (c) { return { url: jobUrl(c, '/hide'), method: 'POST', body: { reason: c.reason } }; },
      ok: apiOk, done: 'admin.done.job_hidden' },
    'job.unhide': {
      confirm: { title: 'admin.jobs.unhide.title', message: 'admin.jobs.unhide.message', confirm: 'admin.jobs.unhide' },
      request: function (c) { return { url: jobUrl(c, '/unhide'), method: 'POST' }; },
      ok: apiOk, done: 'admin.done.job_unhidden' },
    'job.reactivate': {
      confirm: { title: 'admin.jobs.reactivate.title', message: 'admin.jobs.reactivate.message', confirm: 'admin.jobs.reactivate' },
      request: function (c) { return { url: jobUrl(c, '/reactivate'), method: 'POST', body: { duration_days: Number(c.days) } }; },
      ok: apiOk, done: 'admin.done.job_reactivated' },
    'job.extend': {
      confirm: { title: 'admin.jobs.extend.title', message: 'admin.jobs.extend.message', confirm: 'admin.jobs.extend' },
      request: function (c) { return { url: jobUrl(c, '/extend'), method: 'POST', body: { duration_days: Number(c.days) } }; },
      ok: apiOk, done: 'admin.done.job_extended' },
    // state changes — the same set_job_status as the company; close needs a reason
    'job.pause': {
      confirm: { title: 'admin.jobs.pause.title', message: 'admin.jobs.pause.message', confirm: 'admin.jobs.pause' },
      request: function (c) { return { url: jobUrl(c, '/status'), method: 'POST', body: { status: 'paused' } }; },
      ok: apiOk, done: 'admin.done.job_paused' },
    'job.resume': {
      confirm: { title: 'admin.jobs.resume.title', message: 'admin.jobs.resume.message', confirm: 'admin.jobs.resume' },
      request: function (c) { return { url: jobUrl(c, '/status'), method: 'POST', body: { status: 'active' } }; },
      ok: apiOk, done: 'admin.done.job_resumed' },
    'job.close': {
      confirm: { title: 'admin.jobs.close.title', message: 'admin.jobs.close.message', confirm: 'admin.jobs.close', danger: true },
      request: function (c) { return { url: jobUrl(c, '/status'), method: 'POST', body: { status: 'closed', reason: c.reason } }; },
      ok: apiOk, done: 'admin.done.job_closed' },
    'job.unarchive': {
      confirm: { title: 'admin.jobs.unarchive.title', message: 'admin.jobs.unarchive.message', confirm: 'admin.jobs.unarchive' },
      request: function (c) { return { url: jobUrl(c, '/unarchive'), method: 'POST' }; },
      ok: apiOk, done: 'admin.done.job_unarchived' },
  };

  // which admin actions fit a job (pure — tests read it). status = the admin state (archived · hidden · effective).
  function actions(j) {
    var out = [], eff = j.effective_status;
    if (j.status === 'archived' || j.admin_status === 'archived') return ['unarchive', 'delete'];
    out.push(j.admin_hidden_at ? 'unhide' : 'hide');
    if (eff === 'active') out.push('pause');
    if (eff === 'paused') out.push('resume');
    if (eff === 'closed' || eff === 'expired') out.push('reactivate');
    if (eff === 'active' || eff === 'paused') out.push('extend', 'close');
    out.push('delete');
    return out;
  }

  function run(name, ctx) { return TwAdminShell.run(ACTIONS[name], ctx); }
  function done(opts) { return function (res) { var ok = !!(res && res.ok); if (ok && opts.done) opts.done(res); return ok; }; }

  function askDays(kind, j, opts) {   // reactivate / extend: pick a duration (server list), then run (its confirm on top)
    var ds = opts.durations || [];
    TwAdminShell.formDialog({
      titleKey: 'admin.jobs.' + kind + '.title', labelKey: 'admin.jobs.days', kind: 'select',
      options: ds.map(function (n) { return [String(n), twT('admin.jobs.days.n', { n: twFormatNumber(n) })]; }),
      value: String(ds[ds.length - 1] || ''), sendKey: 'admin.jobs.' + kind, vars: { title: j.title || '' },
      onSend: function (v) {
        return run('job.' + kind, { id: j.id, title: j.title || '', days: v, n: twFormatNumber(Number(v)) }).then(done(opts));
      },
    });
  }
  function askReason(kind, ctx, opts) {   // hide / close: a reason (sent to the company), then run (its confirm on top)
    TwAdminShell.formDialog({
      titleKey: 'admin.jobs.' + kind + '.title', labelKey: 'admin.jobs.' + kind + '.reason', kind: 'textarea',
      sendKey: 'admin.jobs.' + kind, hintKey: 'admin.jobs.' + kind + '.hint', danger: true, vars: ctx,
      onSend: function (v) {
        v = String(v || '').trim();
        if (!v) { showToast(twT('admin.jobs.reason.empty'), 'error'); return false; }
        return run('job.' + kind, Object.assign({ reason: v }, ctx)).then(done(opts));
      },
    });
  }
  // delete: the server says what goes (preview) — no preview, no delete
  function confirmDelete(j, opts) {
    return TwAdminSession.fetch('/admin/jobs/' + Number(j.id) + '/delete-preview', { cache: 'no-store' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .catch(function (e) { console.error('[TwAdminJobs] delete preview:', e); return null; })
      .then(function (d) {
        var p = d && d.ok && d.data;
        if (!p) { showToast(twT('admin.job.preview.error'), 'error'); return false; }
        return run('job.delete', { id: Number(j.id), title: p.title || j.title || '', n: twFormatNumber(p.applicants || 0),
                                   p: twFormatNumber(p.pipeline_entries || 0), a: twFormatNumber(p.appointments || 0) })
          .then(done(opts));
      });
  }

  var ICON = { hide: 'eye-off', unhide: 'eye', close: 'lock', pause: null, resume: 'refresh-cw', unarchive: 'archive',
               reactivate: 'refresh', extend: 'clock', delete: 'delete' };
  function button(a, j, opts) {
    opts = opts || {};
    var ctx = { id: Number(j.id), title: j.title || '' };
    var b = document.createElement('button');
    b.type = 'button';
    b.className = 'tw-act tw-act-' + (a === 'delete' ? 'danger' : 'secondary');
    if (ICON[a]) b.appendChild(twIconEl(ICON[a], { size: 'xs' }));
    var label = document.createElement('span');
    label.textContent = twT('admin.jobs.' + a);
    b.appendChild(label);
    b.addEventListener('click', function () {
      if (a === 'hide' || a === 'close') return askReason(a, ctx, opts);
      if (a === 'reactivate' || a === 'extend') return askDays(a, j, opts);
      if (a === 'delete') return confirmDelete(j, opts);
      return run('job.' + a, ctx).then(done(opts));
    });
    return b;
  }

  window.TwAdminJobs = { ACTIONS: ACTIONS, actions: actions, button: button, run: run, confirmDelete: confirmDelete };
}());
