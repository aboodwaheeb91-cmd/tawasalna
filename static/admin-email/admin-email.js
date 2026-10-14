// static/admin-email/admin-email.js — /tw-ctrl-{ADMIN_URL_TOKEN}/email (task 5.1c)
//   - admin session = TwAdminSession (admin JWT, same tab as the panel login) — never the user JWT
//   - GET /admin/email → provider status · usage (email_send_log: today / month, security vs
//     notification, blocked by the cap) · notification types on/off · caps · message rules
//   - PUT /admin/email {types, notify} — a type switched off, or a cap cut by half or more,
//     asks twConfirm first (DS-OVL) · every card has an ⓘ that shows what it does
//   - text: twT (admin.email.* / email.type.*) · icons: twIcon · colors: --color-* tokens only
(function () {
  'use strict';
  var root = document.getElementById('aeRoot');
  var panel = location.pathname.replace(/\/email\/?$/, '');
  var data = null;

  document.title = twT('page.title', { page: twT('admin.email.title') });
  document.getElementById('aeBack').setAttribute('href', panel);
  twTApply(document.body);
  twIcon.hydrate(document.body);

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }
  function message(key) {
    root.textContent = '';
    root.appendChild(el('p', 'ae-msg', twT(key)));
  }

  // ── card with an ⓘ toggle (hint hidden until asked) ──
  var _cid = 0;
  function card(titleKey, hintKey) {
    var c = el('section', 'ae-card'), hdr = el('div', 'ae-card-hdr'), id = 'ae-hint-' + (++_cid);
    var info = el('button', 'ae-info');
    info.type = 'button';
    info.setAttribute('aria-label', twT('admin.email.info'));
    info.setAttribute('aria-expanded', 'false');
    info.setAttribute('aria-controls', id);
    info.appendChild(twIconEl('info', { size: 'xs' }));
    var hint = el('p', 'ae-hint', twT(hintKey));
    hint.id = id;
    hint.hidden = true;
    info.addEventListener('click', function () {
      hint.hidden = !hint.hidden;
      info.setAttribute('aria-expanded', String(!hint.hidden));
    });
    hdr.appendChild(el('h2', 'ae-card-title', twT(titleKey)));
    hdr.appendChild(info);
    c.appendChild(hdr);
    c.appendChild(hint);
    var body = el('div', 'ae-body');
    c.appendChild(body);
    root.appendChild(c);
    return body;
  }

  function n(obj, status) { return (obj && obj[status]) || 0; }

  function renderUsage(body, stats) {
    if (!stats) { body.appendChild(el('p', 'ae-hint', twT('admin.email.stats_unavailable'))); return; }
    var t = el('table', 'ae-table'), head = el('tr');
    ['', 'admin.email.sent', 'admin.email.failed', 'admin.email.capped'].forEach(function (k) {
      head.appendChild(el('th', null, k ? twT(k) : ''));
    });
    t.appendChild(head);
    ['day', 'month'].forEach(function (p) {
      ['security', 'notification'].forEach(function (cat) {
        var c = stats[p][cat], tr = el('tr');
        tr.appendChild(el('td', null, twT(p === 'day' ? 'admin.email.today' : 'admin.email.month') +
                                      ' · ' + twT('admin.email.cat.' + cat)));
        tr.appendChild(el('td', null, String(n(c, 'sent'))));
        tr.appendChild(el('td', null, String(n(c, 'failed'))));
        tr.appendChild(el('td', null, cat === 'notification' ? String(n(c, 'skipped_cap')) : '—'));
        t.appendChild(tr);
      });
    });
    body.appendChild(t);
  }

  function numField(body, key) {
    var lim = data.notify_limits[key], wrap = el('div', 'ae-field');
    var input = el('input', 'tw-input');
    input.type = 'number';
    input.id = 'ae-' + key;
    input.min = lim[0];
    input.max = lim[1];
    input.step = 1;
    input.inputMode = 'numeric';
    input.value = data.settings.notify[key];
    input.setAttribute('data-notify-field', key);
    var label = el('label', null, twT('admin.email.' + key));
    label.setAttribute('for', input.id);
    wrap.appendChild(label);
    wrap.appendChild(input);
    wrap.appendChild(el('div', 'ae-range', twT('admin.email.range', { min: lim[0], max: lim[1] })));
    body.appendChild(wrap);
  }

  function render() {
    root.textContent = '';
    var st = card('admin.email.status', 'admin.email.status.hint');
    var ok = data.status === 'configured';
    st.appendChild(el('p', ok ? 'ae-ok' : 'ae-bad', twT('admin.email.status.' + (ok ? 'configured' : 'missing'))));

    renderUsage(card('admin.email.usage', 'admin.email.usage.hint'), data.stats);

    var types = card('admin.email.types', 'admin.email.types.hint');
    data.notify_types.forEach(function (k) {
      var row = el('label', 'ae-row');
      var sw = el('input', 'ae-switch');
      sw.type = 'checkbox';
      sw.setAttribute('role', 'switch');
      sw.setAttribute('data-type', k);
      sw.checked = data.settings.types[k] !== false;
      row.appendChild(el('span', 'ae-row-name', twT('email.type.' + k)));
      row.appendChild(sw);
      types.appendChild(row);
    });

    var limits = card('admin.email.limits', 'admin.email.limits.hint');
    numField(limits, 'daily_cap');
    numField(limits, 'monthly_cap');
    var msgs = card('admin.email.messages', 'admin.email.messages.hint');
    numField(msgs, 'message_delay_minutes');
    numField(msgs, 'message_throttle_hours');

    var save = el('button', 'tw-btn ae-save', twT('common.save'));
    save.type = 'button';
    save.addEventListener('click', function () { onSave(save); });
    root.appendChild(save);
  }

  // ── collect + warn (type off · cap cut by half or more) + save ──
  function collect() {
    var body = { types: {}, notify: {} };
    root.querySelectorAll('[data-type]').forEach(function (sw) { body.types[sw.getAttribute('data-type')] = sw.checked; });
    root.querySelectorAll('[data-notify-field]').forEach(function (i) {
      body.notify[i.getAttribute('data-notify-field')] = Number(i.value);
    });
    return body;
  }
  function warnings(body) {
    var out = [];
    Object.keys(body.types).forEach(function (k) {
      if (!body.types[k] && data.settings.types[k] !== false) out.push(twT('admin.email.warn.type_off', { type: twT('email.type.' + k) }));
    });
    ['daily_cap', 'monthly_cap'].forEach(function (k) {
      var old = data.settings.notify[k], nv = body.notify[k];
      if (nv < old && nv <= old / 2) out.push(twT('admin.email.warn.cap_drop', { field: twT('admin.email.' + k), old: old, new: nv }));
    });
    return out;
  }
  function onSave(btn) {
    var body = collect(), warn = warnings(body);
    var go = warn.length ? twConfirm({ title: twT('admin.email.warn.title'), message: warn.join('\n'),
                                       confirmText: twT('admin.email.warn.confirm'), danger: true })
                         : Promise.resolve(true);
    go.then(function (yes) {
      if (!yes) return;
      btn.disabled = true;
      TwAdminSession.fetch('/admin/email', { method: 'PUT', body: JSON.stringify(body) })
        .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
        .then(function (res) {
          btn.disabled = false;
          if (res.ok && res.j && res.j.data) {
            data.settings = res.j.data.settings;
            showToast(twT('admin.email.saved'), 'success');
            return;
          }
          var err = res.j && res.j.error;
          showToast((err && err.message) || twT('admin.email.save_error'), 'error');
        })
        .catch(function () { btn.disabled = false; showToast(twT('admin.email.save_error'), 'error'); });
    });
  }

  function load() {
    TwAdminSession.fetch('/admin/email')
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (j) {
        if (!j || !j.data) { if (TwAdminSession.hasLiveToken()) message('admin.email.load_error'); return; }
        data = j.data;
        render();
      })
      .catch(function () { message('admin.email.load_error'); });
  }

  TwAdminSession.onExpired(function () { message('admin.email.login_needed'); });
  if (!TwAdminSession.hasLiveToken()) message('admin.email.login_needed');
  else load();
}());
