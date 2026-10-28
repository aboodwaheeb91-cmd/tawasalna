// static/admin-view/admin-view.js — admin: one user's account (admin-view.html · task 5.3b · docs/rules/admin-shell.md)
//   - route /admin-view?id=N sits outside the panel path: header / menu / session gate =
//     TwAdminShell.start({outside: true}) — panel root = the one this tab saved (TwAdminSession.panelHref)
//   - GET /admin/profile/{id} → account · actions · basic info · experience · education · courses
//     (each a TwAdminShell.card with ⓘ)
//   - every change goes through TwAdminShell.run(ACTIONS[x], ctx): confirm first (typed word for
//     account type change / account delete), the result is checked before «تم» (run → res.ok)
//   - text: twT (admin.view.* / admin.*) · icons: twIcon · colors: --color-* tokens · dialogs: DS-OVL
(function () {
  'use strict';

  // ── actions (the only writes on this page) ──
  function uid(c) { return Number(c.id); }
  var ACTIONS = {
    'user.type': {
      confirm: { title: 'admin.view.type.title', message: 'admin.view.type.message', confirm: 'admin.view.type.confirm',
                 danger: true, typeWord: 'admin.confirm.word.type' },
      request: function (c) { return { url: '/admin/user/' + uid(c) + '/type', method: 'PUT', body: { user_type: c.type } }; },
      done: 'admin.done.type' },
    'user.password': {
      confirm: { title: 'admin.view.password.title', message: 'admin.view.password.message',
                 confirm: 'admin.view.password.confirm', danger: true },
      request: function (c) { return { url: '/admin/user/' + uid(c) + '/password', method: 'PUT', body: { password: c.password } }; },
      done: 'admin.done.password' },
    // task 8.3 — a request only: the link goes to the new address; users.email changes when it is opened
    'user.email': {
      confirm: { title: 'admin.view.email.title', message: 'admin.view.email.message',
                 confirm: 'admin.view.email.confirm', danger: true },
      request: function (c) { return { url: '/admin/user/' + uid(c) + '/email', method: 'PUT', body: { new_email: c.email } }; },
      ok: function (d) { return !!(d && d.ok && d.data && d.data.sent); },   // «تم» only when the link was sent
      done: 'admin.done.email_sent' },
    'user.verify': {
      confirm: { title: 'admin.verify.title', message: 'admin.verify.message', confirm: 'admin.verify.confirm' },
      request: function (c) { return { url: '/admin/user/' + uid(c) + '/verify', method: 'PUT', body: { is_verified: true } }; },
      done: 'admin.done.verified' },
    'user.unverify': {
      confirm: { title: 'admin.view.unverify.title', message: 'admin.view.unverify.message',
                 confirm: 'admin.view.unverify.confirm', danger: true },
      request: function (c) { return { url: '/admin/user/' + uid(c) + '/verify', method: 'PUT', body: { is_verified: false } }; },
      done: 'admin.done.unverified' },
    // task 5.4 — reversible; the reason is admin-only (never shown to the account)
    'user.suspend': {
      confirm: { title: 'admin.suspend.title', message: 'admin.suspend.message', confirm: 'admin.suspend.confirm', danger: true },
      request: function (c) { return { url: '/admin/user/' + uid(c) + '/suspension', method: 'PUT',
                                       body: { suspended: true, reason: c.reason || '' } }; },
      done: 'admin.done.suspended' },
    'user.unsuspend': {
      confirm: { title: 'admin.unsuspend.title', message: 'admin.unsuspend.message', confirm: 'admin.unsuspend.confirm' },
      request: function (c) { return { url: '/admin/user/' + uid(c) + '/suspension', method: 'PUT', body: { suspended: false } }; },
      done: 'admin.done.unsuspended' },
    'user.delete': {
      confirm: { title: 'admin.delete_user.title', message: 'admin.delete_user.message', confirm: 'admin.delete.confirm',
                 danger: true, typeWord: 'admin.confirm.word.delete' },
      request: function (c) { return { url: '/admin/user/' + uid(c), method: 'DELETE' }; },
      done: 'admin.done.deleted' },
    'profile.edit': {
      confirm: { title: 'admin.view.edit.title', message: 'admin.view.edit.message', confirm: 'admin.view.edit.confirm' },
      request: function (c) { var b = {}; b[c.field] = c.value; return { url: '/admin/profile/' + uid(c), method: 'PUT', body: b }; },
      done: 'admin.done.saved' },
    'exp.delete': {
      confirm: { title: 'admin.delete_exp.title', message: 'admin.delete_exp.message', confirm: 'admin.delete.confirm', danger: true },
      request: function (c) { return { url: '/admin/experience/' + Number(c.item), method: 'DELETE' }; },
      done: 'admin.done.deleted' },
    'edu.delete': {
      confirm: { title: 'admin.delete_edu.title', message: 'admin.delete_edu.message', confirm: 'admin.delete.confirm', danger: true },
      request: function (c) { return { url: '/admin/education/' + Number(c.item), method: 'DELETE' }; },
      done: 'admin.done.deleted' },
    'course.delete': {
      confirm: { title: 'admin.delete_course.title', message: 'admin.delete_course.message', confirm: 'admin.delete.confirm', danger: true },
      request: function (c) { return { url: '/admin/course/' + Number(c.item), method: 'DELETE' }; },
      done: 'admin.done.deleted' },
    'message.send': {
      confirm: { title: 'admin.view.msg.confirm.title', message: 'admin.view.msg.confirm.message', confirm: 'admin.msg.send' },
      request: function (c) { return { url: '/admin/message', method: 'POST',
                                       body: { user_id: uid(c), subject: twT('admin.msg.subject'), message: c.text } }; },
      ok: function (d) { return !!(d && d.ok && d.data && d.data.notification_id); },   // «تم» only when the notification exists (5.3b2)
      done: 'admin.done.sent' },
  };
  var TYPES = ['emp', 'co', 'edu'];
  var TYPE_ICON = { emp: 'user', co: 'building', edu: 'graduation-cap' };
  // editable profile fields → [label key, input kind]
  var FIELDS = { full_name: ['admin.view.f.name', 'text'], headline: ['admin.view.f.headline', 'text'],
                 location: ['admin.view.f.location', 'text'], bio: ['admin.view.f.bio', 'textarea'] };
  window.TwAdminUserView = { ACTIONS: ACTIONS };

  var root = document.getElementById('avRoot');
  var raw = new URLSearchParams(location.search).get('id') || '';
  var userId = /^[0-9]{1,18}$/.test(raw) ? raw : '';
  var P = null;

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

  // Admin Shell (task 5.3b): page outside the panel path — panel root from this tab, menu marks «users».
  if (!TwAdminShell.start({ outside: true, current: 'users' })) {
    if (!TwAdminSession.panelHref()) message('admin.view.open_panel');
    return;
  }
  document.title = twT('page.title', { page: twT('admin.view.title') });
  TwAdminShell.mount();
  twTApply(document.body);
  if (!userId) { message('admin.view.no_user'); return; }

  function ctx(extra) {
    var c = { id: userId, name: (P && P.full_name) || twT('admin.user.unnamed') };
    Object.keys(extra || {}).forEach(function (k) { c[k] = extra[k]; });
    return c;
  }
  function run(name, extra) { return TwAdminShell.run(ACTIONS[name], ctx(extra)); }
  function reloadIfOk(res) { if (res && res.ok) load(); return !!(res && res.ok); }

  function btn(variant, icon, labelKey, onClick) {
    var b = el('button', 'tw-act tw-act-' + variant);
    b.type = 'button';
    if (icon) b.appendChild(twIconEl(icon, { size: 'xs' }));
    b.appendChild(el('span', null, twT(labelKey)));
    b.addEventListener('click', onClick);
    return b;
  }
  function pill(text, mod) { return el('span', 'tw-adm-pill' + (mod ? ' is-' + mod : ''), text); }
  function row(title, sub, extra) {
    var r = el('div', 'tw-adm-row'), main = el('div', 'tw-adm-row-main');
    main.appendChild(el('div', 'tw-adm-row-title', title || '—'));
    (sub || []).forEach(function (s) { if (s) main.appendChild(el('div', 'tw-adm-row-sub', s)); });
    r.appendChild(main);
    if (extra) r.appendChild(extra);
    var acts = el('div', 'tw-adm-row-acts');
    r.appendChild(acts);
    return { row: r, main: main, acts: acts };
  }
  function typeLabel(t) { return twT('admin.user.type.' + (TYPES.indexOf(t) === -1 ? 'emp' : t)); }

  // ── dialogs that collect a value — TwAdminShell.formDialog (shared since task 5.3j) ──
  function formDialog(titleKey, labelKey, kind, value, sendKey, onSend) {
    TwAdminShell.formDialog({ titleKey: titleKey, labelKey: labelKey, kind: kind, value: value, sendKey: sendKey, onSend: onSend });
  }
  function editField(field) {
    var f = FIELDS[field];
    formDialog('admin.view.edit.dialog', f[0], f[1], P[field], 'common.save', function (v) {
      v = String(v || '').trim();
      if (!v) { showToast(twT('admin.view.edit.empty'), 'error'); return false; }
      return run('profile.edit', { field: field, value: v, label: twT(f[0]) }).then(reloadIfOk);
    });
  }
  function openPassword() {
    formDialog('admin.view.password.title', 'admin.view.password.label', 'password', '', 'admin.view.password.confirm', function (v) {
      // length rule = the server's _password_policy_error (task 5.0c) — its message is shown by run()
      if (!v) { showToast(twT('admin.view.password.required'), 'error'); return false; }
      return run('user.password', { password: v }).then(function (res) { return !!(res && res.ok); });
    });
  }
  function openEmail() {
    formDialog('admin.view.email.title', 'admin.view.email.label', 'email', '', 'admin.view.email.next', function (v, _x, fieldError) {
      var email = String(v || '').trim();
      if (!email) { fieldError(twT('admin.view.email.required')); return false; }
      return run('user.email', { email: email }).then(function (res) {
        var e = res && !res.ok && res.status === 422 && res.data && res.data.error;
        if (e && e.field === 'new_email') fieldError(e.message || twT('admin.action.error'));
        return !!(res && res.ok);
      });
    });
  }
  function openMessage() {
    formDialog('admin.msg.title', 'admin.msg.body', 'textarea', '', 'admin.msg.send', function (v) {
      v = String(v || '').trim();
      if (!v) { showToast(twT('admin.msg.empty'), 'error'); return false; }
      return run('message.send', { text: v, to: P.email || '' }).then(function (res) { return !!(res && res.ok); });
    });
  }
  function changeType(to) {
    run('user.type', { type: to, from: typeLabel(P.user_type), to: typeLabel(to) }).then(reloadIfOk);
  }
  function openSuspend() {
    formDialog('admin.suspend.title', 'admin.suspend.reason', 'textarea', '', 'admin.suspend.next', function (v) {
      return run('user.suspend', { reason: String(v || '').trim() }).then(reloadIfOk);
    });
  }
  function deleteUser() {
    run('user.delete').then(function (res) {
      if (res && res.ok) location.href = TwAdminShell.base() + '#users';
    });
  }

  // ── render ──
  function render() {
    root.textContent = '';
    var t = TYPES.indexOf(P.user_type) === -1 ? 'emp' : P.user_type;

    var acc = TwAdminShell.card(root, { titleKey: 'admin.view.account', hintKey: 'admin.view.account.hint', icon: TYPE_ICON[t] });
    var pills = el('span', 'av-btns');
    pills.appendChild(pill(typeLabel(t), t === 'emp' ? '' : t));
    pills.appendChild(pill(twT(P.is_verified ? 'admin.view.verified' : 'admin.view.unverified'), P.is_verified ? 'ok' : ''));
    var sus = P.suspension && P.suspension.suspended ? P.suspension : null;
    if (sus) pills.appendChild(pill(twT('admin.view.suspended'), 'danger'));
    acc.appendChild(row(P.full_name, [P.email, P.tw_id], pills).row);
    if (P.created_at) acc.appendChild(el('p', 'tw-adm-row-sub', twT('admin.view.since', { date: twFormatDate(P.created_at) })));
    if (sus) {
      acc.appendChild(el('p', 'tw-adm-row-sub', twT('admin.view.suspended_since', { date: twFormatDateTime(sus.suspended_at) })));
      if (sus.suspended_reason) acc.appendChild(el('p', 'tw-adm-row-sub', twT('admin.view.suspended_reason', { reason: sus.suspended_reason })));
    }

    var act = TwAdminShell.card(root, { titleKey: 'admin.view.actions', hintKey: 'admin.view.actions.hint', icon: 'settings' });
    var b1 = el('div', 'av-btns');
    b1.appendChild(P.is_verified
      ? btn('secondary', 'shield-off', 'admin.view.unverify', function () { run('user.unverify').then(reloadIfOk); })
      : btn('primary', 'verified', 'admin.users.verify', function () { run('user.verify').then(reloadIfOk); }));
    b1.appendChild(btn('secondary', 'lock', 'admin.view.password', openPassword));
    b1.appendChild(btn('secondary', 'at-sign', 'admin.view.email', openEmail));
    b1.appendChild(btn('secondary', 'mail', 'admin.users.message', openMessage));
    b1.appendChild(sus
      ? btn('primary', 'user-check', 'admin.view.unsuspend', function () { run('user.unsuspend').then(reloadIfOk); })
      : btn('danger', 'lock', 'admin.view.suspend', openSuspend));
    b1.appendChild(btn('danger', 'delete', 'admin.view.delete', deleteUser));
    act.appendChild(b1);

    var ty = TwAdminShell.card(root, { titleKey: 'admin.view.type', hintKey: 'admin.view.type.hint', icon: 'users' });
    var b2 = el('div', 'av-btns');
    TYPES.forEach(function (k) {
      var b = btn('secondary', TYPE_ICON[k], 'admin.user.type.' + k, function () { changeType(k); });
      b.setAttribute('data-av-type', k);
      if (k === t) { b.classList.add('is-current'); b.disabled = true; b.setAttribute('aria-current', 'true'); }
      b2.appendChild(b);
    });
    ty.appendChild(b2);

    var info = TwAdminShell.card(root, { titleKey: 'admin.view.info', hintKey: 'admin.view.info.hint', icon: 'id-card' });
    info.parentNode.id = 'edit';   // «تعديل» in the users table links here (/admin-view?id=N#edit — task 5.3a3)
    Object.keys(FIELDS).forEach(function (f) {
      var r = row(P[f] || twT('admin.view.empty_field'), [twT(FIELDS[f][0])]);
      r.main.insertBefore(r.main.lastChild, r.main.firstChild);   // label above the value
      r.acts.appendChild(btn('secondary', 'edit', 'admin.view.edit', function () { editField(f); }));
      info.appendChild(r.row);
    });

    list('admin.view.exp', 'admin.view.exp.hint', 'briefcase', P.experience, 'exp.delete', function (e) {
      return [e.title, [[e.company, e.location].filter(Boolean).join(' · '),
                        [e.start_date, e.end_date].filter(Boolean).join(' ← ')], e.description];
    });
    list('admin.view.edu', 'admin.view.edu.hint', 'graduation-cap', P.education, 'edu.delete', function (e) {
      return [[e.degree, e.field].filter(Boolean).join(' - '), [e.institution, e.end_year ? String(e.end_year) : '']];
    });
    list('admin.view.courses', 'admin.view.courses.hint', 'book-open', P.courses, 'course.delete', function (c) {
      return [c.title, [c.provider, c.completion_date]];
    });
  }

  function list(titleKey, hintKey, icon, items, action, describe) {
    var body = TwAdminShell.card(root, { titleKey: titleKey, hintKey: hintKey, icon: icon });
    items = items || [];
    if (!items.length) { body.appendChild(el('p', 'tw-adm-msg', twT('admin.view.none'))); return; }
    items.forEach(function (it) {
      var d = describe(it), r = row(d[0], d[1]);
      if (d[2]) r.main.appendChild(el('p', 'av-desc', d[2]));
      r.acts.appendChild(btn('danger', 'delete', 'admin.users.delete', function () {
        run(action, { item: it.id }).then(reloadIfOk);
      }));
      body.appendChild(r.row);
    });
  }

  // #edit (from the users table) → scroll to the editable fields once, after the first render
  var jumped = false;
  function jumpOnce() {
    if (jumped) return;
    jumped = true;
    var t = location.hash === '#edit' && document.getElementById('edit');
    if (t && t.scrollIntoView) t.scrollIntoView();
  }

  function load() {
    TwAdminSession.fetch('/admin/profile/' + userId, { cache: 'no-store' })
      .then(function (r) {
        if (r.ok) return r.json().then(function (j) { P = j.profile || j; render(); jumpOnce(); });
        if (r.status === 401 || r.status === 403) return;   // TwAdminShell → panel login
        message(r.status === 404 ? 'admin.view.not_found' : 'admin.view.load_error');
      })
      .catch(function (e) { console.error('[admin-view] load:', e); message('admin.view.load_error'); });
  }

  load();
}());
