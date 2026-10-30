// static/admin-job/admin-job.js — one job for the admin (admin-job.html · task 5.3j phase 4 ·
// docs/rules/admin-shell.md 21 · SYSTEMS_INDEX §25e)
//   - data: GET /admin/jobs/{id} → {job, applicants, durations} (state from the server — never computed here)
//   - state actions + delete (with its preview): TwAdminJobs — the same buttons as the jobs list
//   - edit: every publish field (the server checks them with the publish rules) + a required reason →
//     run('job.edit') = PUT /admin/jobs/{id}; the company is told the reason, applicants get a notice (server).
//     The duration is not here (extend / reactivate).
//   - applicants: read only
//   - text twT · icons twIcon · colors tokens · dialogs DS-OVL · options from tw-options-data.js
(function () {
  'use strict';
  var root = document.getElementById('ajRoot');
  var raw = new URLSearchParams(location.search).get('id') || '';
  var jobId = /^[0-9]{1,18}$/.test(raw) ? raw : '';
  var D = null, PROFS = [];
  var REMOTE = 'عن بُعد';   // the stored «remote» location (same as the post form)

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }
  function message(key) {
    if (!root) return;
    root.textContent = '';
    root.appendChild(el('p', 'tw-adm-msg', twT(key)));
  }

  // Admin Shell: page outside the panel path — panel root from this tab, menu marks «jobs».
  if (!TwAdminShell.start({ outside: true, current: 'jobs' })) {
    if (!TwAdminSession.panelHref()) message('admin.view.open_panel');
    return;
  }
  document.title = twT('page.title', { page: twT('admin.job.page') });
  TwAdminShell.mount();
  twTApply(document.body);
  if (!jobId) { message('admin.job.no_job'); return; }

  // ── form → PUT body (pure — tests read it). f = {title, description, job_type, work_mode, loc_mode, location,
  //    country, city, show_salary, salary_min, salary_max, currency, experience_years, skills (text),
  //    profession_id, accepts_all, accepted (ids), category, reason} ──
  function num(v) { var n = parseInt(v, 10); return isNaN(n) ? null : n; }
  function formPayload(f) {
    var loc = f.loc_mode === 'remote' ? REMOTE
      : f.loc_mode === 'place' ? [f.country, f.city].filter(Boolean).join('، ') : (f.location || '');
    var show = !!f.show_salary;
    return {
      title: String(f.title || '').trim(), description: String(f.description || '').trim(), location: loc,
      job_type: f.job_type || null, work_mode: f.work_mode || null,
      salary_hidden: !show, salary_min: show ? num(f.salary_min) : null, salary_max: show ? num(f.salary_max) : null,
      currency: f.currency || 'USD', experience_years: num(f.experience_years) || 0,
      skills: String(f.skills || '').split(/[،,]/).map(function (s) { return s.trim(); }).filter(Boolean),
      category: f.category || null, profession_id: num(f.profession_id),
      accepts_all_professions: !!f.accepts_all, accepted_profession_ids: f.accepts_all ? [] : (f.accepted || []).slice(),
      reason: String(f.reason || '').trim(),
    };
  }
  window.TwAdminJobPage = { formPayload: formPayload };

  function field(parent, labelKey, input) {
    var l = el('label', 'aj-field', twT(labelKey));
    l.appendChild(input);
    parent.appendChild(l);
    return input;
  }
  function input(type, value) {
    var i = el(type === 'textarea' ? 'textarea' : 'input', 'tw-input');
    if (type !== 'textarea') i.type = type;
    i.value = value == null ? '' : String(value);
    return i;
  }
  function select(opts, value) {   // opts = [[value, label]]
    var s = el('select', 'tw-input ep-select');
    opts.forEach(function (o) { s.appendChild(new Option(o[1], o[0])); });
    if (value != null) s.value = String(value);
    return s;
  }
  function check(parent, labelKey, on) {
    var l = el('label', 'aj-check'), c = el('input');
    c.type = 'checkbox';
    c.checked = !!on;
    l.appendChild(c);
    l.appendChild(el('span', null, twT(labelKey)));
    parent.appendChild(l);
    return c;
  }
  function pill(text, mod) { return el('span', 'tw-adm-pill' + (mod ? ' is-' + mod : ''), text); }
  var PILL = { active: 'ok', paused: 'warn', closed: 'muted', expired: 'muted', hidden: 'danger', archived: 'muted' };

  function render() {
    var j = D.job;
    root.textContent = '';
    // ── summary + actions ──
    var top = TwAdminShell.card(root, { titleKey: 'admin.job.summary', hintKey: 'admin.job.summary.hint', icon: 'briefcase' });
    top.appendChild(el('div', 'tw-adm-row-title', j.title || '—'));
    var meta = el('div', 'aj-meta');
    var st = PILL[j.admin_status] !== undefined ? j.admin_status : 'closed';
    meta.appendChild(pill(twT('admin.jobs.s.' + st), PILL[st]));
    if (j.company_id) {
      var co = el('a', null, j.company_name || twT('admin.user.unnamed'));
      co.href = '/admin-view?id=' + Number(j.company_id);
      meta.appendChild(co);
    }
    meta.appendChild(el('span', null, twT('admin.jobs.applicants', { n: twFormatNumber(D.applicants.length) })));
    if (j.created_at) meta.appendChild(el('span', null, twT('admin.job.published', { date: twFormatDate(j.created_at) })));
    if (j.expires_at) meta.appendChild(el('span', null, twT('admin.job.expires', { date: twFormatDate(j.expires_at) })));
    top.appendChild(meta);
    if (j.admin_hidden_reason) top.appendChild(el('p', 'aj-note', twT('admin.jobs.hidden_reason', { reason: j.admin_hidden_reason })));
    var acts = el('div', 'aj-btns');
    var row = { id: j.id, title: j.title, status: j.admin_status, admin_status: j.admin_status,
                effective_status: j.effective_status, admin_hidden_at: j.admin_hidden_at };
    var opts = { durations: D.durations, done: function (res) {
      if (res && res.ok && res.data && res.data.removed) { location.replace(TwAdminShell.base() + '#jobs'); return; }
      load();
    } };
    TwAdminJobs.actions(row).forEach(function (a) { acts.appendChild(TwAdminJobs.button(a, row, opts)); });
    top.appendChild(acts);

    renderEdit(j);
    renderApplicants();
  }

  function renderEdit(j) {
    var box = TwAdminShell.card(root, { titleKey: 'admin.job.edit', hintKey: 'admin.job.edit.hint', icon: 'edit' });
    var form = el('div', 'aj-form'), F = {};
    F.title = field(form, 'admin.job.f.title', input('text', j.title));
    F.description = field(form, 'admin.job.f.description', input('textarea', j.description));
    var r1 = el('div', 'aj-row');
    F.job_type = field(r1, 'admin.job.f.job_type', select((TW.JOB_TYPES || []).map(function (v) { return [v, v]; }), j.job_type));
    F.work_mode = field(r1, 'admin.job.f.work_mode', select((TW.JOB_WORK_MODES || []).map(function (v) { return [v, v]; }), j.work_mode));
    F.experience_years = field(r1, 'admin.job.f.experience', select((TW.EXP_LEVELS || []).map(function (l) { return [String(l.value), l.label]; }), j.experience_years || 0));
    form.appendChild(r1);
    // location: keep the stored value · remote · country + city (no free text — same rule as the post form)
    var r2 = el('div', 'aj-row');
    F.loc_mode = field(r2, 'admin.job.f.location', select([
      ['keep', twT('admin.job.loc.keep', { loc: j.location || '—' })], ['remote', REMOTE], ['place', twT('admin.job.loc.place')]], 'keep'));
    F.country = field(r2, 'admin.job.f.country', el('select', 'tw-input ep-select'));
    F.city = field(r2, 'admin.job.f.city', el('select', 'tw-input ep-select'));
    if (TW.fillCountries) TW.fillCountries(F.country, twT('admin.job.f.country'));
    F.country.addEventListener('change', function () { if (TW.fillCities) TW.fillCities(F.city, F.country.value, ''); });
    var showPlace = function () { var on = F.loc_mode.value === 'place'; F.country.parentNode.hidden = !on; F.city.parentNode.hidden = !on; };
    F.loc_mode.addEventListener('change', showPlace);
    showPlace();
    form.appendChild(r2);
    // salary
    F.show_salary = check(form, 'admin.job.f.show_salary', !j.salary_hidden && (j.salary_min || j.salary_max));
    var r3 = el('div', 'aj-row');
    F.salary_min = field(r3, 'admin.job.f.salary_min', input('number', j.salary_min));
    F.salary_max = field(r3, 'admin.job.f.salary_max', input('number', j.salary_max));
    F.currency = field(r3, 'admin.job.f.currency', select((TW.JOB_CURRENCIES || []).map(function (c) { return [c, c]; }), j.currency || 'USD'));
    var showSal = function () { r3.hidden = !F.show_salary.checked; };
    F.show_salary.addEventListener('change', showSal);
    showSal();
    form.appendChild(r3);
    F.skills = field(form, 'admin.job.f.skills', input('text', (j.skills || []).join('، ')));
    // professions (GET /professions — the taxonomy catalog)
    var r4 = el('div', 'aj-row');
    var profOpts = [['', twT('admin.job.f.no_profession')]].concat(PROFS.map(function (p) { return [String(p.id), p.name_ar]; }));
    F.profession_id = field(r4, 'admin.job.f.profession', select(profOpts, j.profession_id || ''));
    form.appendChild(r4);
    F.accepts_all = check(form, 'admin.job.f.accepts_all', j.accepts_all_professions);
    var accepted = (j.accepted_profession_ids || []).slice();
    var accBox = el('div', 'aj-field');
    accBox.appendChild(el('span', null, twT('admin.job.f.accepted')));
    var chips = el('div', 'aj-chips');
    var addSel = select(profOpts.map(function (o, i) { return i ? o : ['', twT('admin.job.f.add_profession')]; }), '');
    var drawChips = function () {
      chips.textContent = '';
      accepted.forEach(function (pid) {
        var p = PROFS.filter(function (x) { return Number(x.id) === pid; })[0];
        var b = el('button', 'tw-act tw-act-secondary');
        b.type = 'button';
        b.setAttribute('aria-label', twT('admin.job.f.remove', { name: p ? p.name_ar : String(pid) }));
        b.appendChild(el('span', null, p ? p.name_ar : String(pid)));
        b.appendChild(twIconEl('close', { size: 'xs' }));
        b.addEventListener('click', function () { accepted = accepted.filter(function (x) { return x !== pid; }); drawChips(); });
        chips.appendChild(b);
      });
    };
    addSel.addEventListener('change', function () {
      var v = parseInt(addSel.value, 10);
      if (v && accepted.indexOf(v) === -1) accepted.push(v);
      addSel.value = '';
      drawChips();
    });
    accBox.appendChild(chips);
    accBox.appendChild(addSel);
    form.appendChild(accBox);
    var showAcc = function () { accBox.hidden = F.accepts_all.checked; };
    F.accepts_all.addEventListener('change', showAcc);
    showAcc();
    drawChips();
    F.reason = field(form, 'admin.job.f.reason', input('textarea', ''));
    var save = el('button', 'tw-act tw-act-primary');
    save.type = 'button';
    save.appendChild(twIconEl('check', { size: 'xs' }));
    save.appendChild(el('span', null, twT('admin.job.edit.save')));
    save.addEventListener('click', function () {
      var body = formPayload({
        title: F.title.value, description: F.description.value, job_type: F.job_type.value, work_mode: F.work_mode.value,
        loc_mode: F.loc_mode.value, location: j.location, country: F.country.value, city: F.city.value,
        show_salary: F.show_salary.checked, salary_min: F.salary_min.value, salary_max: F.salary_max.value,
        currency: F.currency.value, experience_years: F.experience_years.value, skills: F.skills.value,
        category: j.category, profession_id: F.profession_id.value, accepts_all: F.accepts_all.checked,
        accepted: accepted, reason: F.reason.value });
      if (!body.reason) { showToast(twT('admin.jobs.reason.empty'), 'error'); return; }
      if (!body.title) { showToast(twT('admin.job.f.title_empty'), 'error'); return; }
      save.disabled = true;
      TwAdminJobs.run('job.edit', { id: Number(j.id), title: j.title || '', fields: body }).then(function (res) {
        save.disabled = false;
        if (res && res.ok) load();
      });
    });
    var bar = el('div', 'aj-btns');
    bar.appendChild(save);
    form.appendChild(bar);
    box.appendChild(form);
    if (typeof window.scSelectInit === 'function') window.scSelectInit();
  }

  function renderApplicants() {
    var box = TwAdminShell.card(root, { titleKey: 'admin.job.applicants', hintKey: 'admin.job.applicants.hint', icon: 'users' });
    if (!D.applicants.length) { box.appendChild(el('p', 'tw-adm-msg', twT('admin.job.applicants.none'))); return; }
    D.applicants.forEach(function (a) {
      var r = el('div', 'tw-adm-row'), main = el('div', 'tw-adm-row-main');
      var name = el('a', 'tw-adm-row-title', a.full_name || twT('admin.user.unnamed'));
      if (a.user_id) name.href = '/admin-view?id=' + Number(a.user_id);
      main.appendChild(name);
      main.appendChild(el('div', 'tw-adm-row-sub', [a.tw_id, a.applied_at ? twFormatDate(a.applied_at) : ''].filter(Boolean).join(' · ')));
      r.appendChild(main);
      if (a.status) r.appendChild(pill(twT('company.app_status.' + a.status)));
      box.appendChild(r);
    });
  }

  function loadProfs() {
    if (PROFS.length) return Promise.resolve();
    return twApi('/professions', { auth: false }).then(function (res) {
      var d = res.ok ? res.raw : null;
      PROFS = Array.isArray(d) ? d : ((d && d.professions) || []);
    });
  }
  function load() {
    return Promise.all([
      TwAdminSession.fetch('/admin/jobs/' + jobId, { cache: 'no-store' }).then(function (r) {
        if (r.ok) return r.json();
        if (r.status === 401 || r.status === 403) return null;   // TwAdminShell → panel login
        message(r.status === 404 ? 'admin.job.not_found' : 'admin.view.load_error');
        return null;
      }),
      loadProfs(),
    ]).then(function (out) {
      var d = out[0];
      if (!d || !d.ok) return;
      D = d.data;
      render();
    }).catch(function (e) { console.error('[admin-job] load:', e); message('admin.view.load_error'); });
  }

  TwAdminShell.whenAllowed(root, load);   // task 8.4c-1 — no jobs.manage → empty state
}());
