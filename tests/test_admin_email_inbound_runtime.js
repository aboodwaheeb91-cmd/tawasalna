/**
 * test_admin_email_inbound_runtime.js — «استقبال بريد الدعم» switch on the admin email page
 * (task 7.3a · docs/rules/email.md rule 10 · docs/rules/support.md → البريد الوارد)
 * Runs the REAL static/admin-email/admin-email.js in a Node vm with a fake DOM, a stubbed
 * TwAdminShell / TwAdminSession and a recording twConfirm.
 *   A  the switch is drawn from GET /admin/email inbound_switch, in its own card (not the notify types)
 *   B  off when settings.types[key] is missing or false · on only when true
 *   C  off → on: twConfirm with warn.inbound_on → PUT carries types.support_inbound = true · cancel → no PUT
 *   D  on → off: PUT with false and no confirm · warn.type_off never names this key
 *
 * Run: node tests/test_admin_email_inbound_runtime.js
 */
'use strict';
const fs = require('fs');
const vm = require('vm');

let passed = 0, failed = 0;
function check(name, cond, detail) {
  if (cond) { passed++; console.log('  PASS  ' + name); }
  else      { failed++; console.log('  FAIL  ' + name + (detail !== undefined ? ' — ' + detail : '')); }
}
const SRC = fs.readFileSync('static/admin-email/admin-email.js', 'utf8');
const KEY = 'support_inbound';

function fakeEl(tag) {
  const ls = {};
  return {
    tagName: tag, className: '', children: [], attrs: {}, value: '', type: '', checked: false, disabled: false, _text: '',
    get textContent() { return this._text + this.children.map(c => c.textContent).join(''); },
    set textContent(v) { this._text = String(v); this.children = []; },
    setAttribute(k, v) { this.attrs[k] = String(v); }, getAttribute(k) { return this.attrs[k]; },
    appendChild(c) { c.parent = this; this.children.push(c); return c; },
    addEventListener(t, fn) { (ls[t] = ls[t] || []).push(fn); }, fire(t) { (ls[t] || []).forEach(fn => fn({})); },
    querySelectorAll(sel) {
      const attr = sel.replace(/^\[|\]$/g, '');
      return all(this).filter(e => e !== this && attr in e.attrs);
    },
  };
}
const all = el => [el].concat(el.children.flatMap(all));
const settle = async () => { for (let i = 0; i < 8; i++) await new Promise(r => setImmediate(r)); };

function payload(types) {
  return {
    status: 'configured', stats: null, inbound_switch: KEY,
    notify_types: ['notify_message', 'notify_appointment_invited'],
    notify_limits: { daily_cap: [1, 1000], monthly_cap: [1, 30000], message_delay_minutes: [1, 120], message_throttle_hours: [1, 48] },
    settings: { types: types, notify: { daily_cap: 80, monthly_cap: 2800, message_delay_minutes: 15, message_throttle_hours: 6 } },
  };
}

async function boot(types, confirmAnswer) {
  const root = fakeEl('div');
  const rec = { puts: [], confirms: [], cards: [] };
  const ctx = {
    console, Promise, String, Object, Array, JSON, Number,
    document: { createElement: fakeEl, getElementById: id => (id === 'aeRoot' ? root : null), body: fakeEl('body'), title: '' },
    twT: (k, v) => k + (v && v.type ? ':' + v.type : ''), twTApply() {}, twIcon: { hydrate() {} },
    showToast() {},
    twConfirm: o => { rec.confirms.push(o); return Promise.resolve(confirmAnswer !== false); },
    TwAdminShell: {
      start: () => true, mount() {},
      whenAllowed: (target, fn) => { fn(); return Promise.resolve(true); },   // task 8.4c-1 — allowed (the shell's own test covers the denial)
      card(parent, o) { const s = fakeEl('section'); s.titleKey = o.titleKey; s.hintKey = o.hintKey; rec.cards.push(s); parent.appendChild(s); return s; },
    },
    TwAdminSession: {
      hasLiveToken: () => true,
      fetch(path, o) {
        if (o && o.method === 'PUT') {
          const body = JSON.parse(o.body);
          rec.puts.push(body);
          return Promise.resolve({ ok: true, json: () => Promise.resolve({ data: { settings: Object.assign(payload({}).settings, { types: body.types }) } }) });
        }
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ ok: true, data: payload(types) }) });
      },
    },
  };
  vm.createContext(ctx);
  vm.runInContext(SRC, ctx);
  await settle();
  rec.root = root;
  rec.sw = all(root).find(e => e.attrs['data-inbound'] === KEY);
  rec.save = all(root).find(e => e.tagName === 'button');
  return rec;
}

(async () => {
  console.log('\n[A] the switch is drawn, in its own card');
  let r = await boot({});
  check('A1 switch present (role=switch)', r.sw && r.sw.attrs.role === 'switch' && r.sw.type === 'checkbox');
  const own = r.sw && r.cards.find(c => all(c).includes(r.sw));
  check('A2 own card titled email.type.<key> + hint', own && own.titleKey === 'email.type.' + KEY && own.hintKey === 'email.type.' + KEY + '.hint');
  const typesCard = r.cards.find(c => c.titleKey === 'admin.email.types');
  check('A3 not inside «أنواع الإشعارات»', typesCard && !all(typesCard).includes(r.sw));
  check('A4 not a data-type switch', r.sw && !('data-type' in r.sw.attrs));

  console.log('\n[B] off unless explicitly true');
  check('B1 missing → off', r.sw && r.sw.checked === false);
  r = await boot({ [KEY]: false });
  check('B2 false → off', r.sw && r.sw.checked === false);
  r = await boot({ [KEY]: true });
  check('B3 true → on', r.sw && r.sw.checked === true);

  console.log('\n[C] switching on asks first');
  r = await boot({});
  r.sw.checked = true;
  r.save.fire('click');
  await settle();
  check('C1 one confirm', r.confirms.length === 1);
  check('C2 confirm says warn.inbound_on', r.confirms[0] && r.confirms[0].message.includes('admin.email.warn.inbound_on'));
  check('C3 PUT types.support_inbound = true', r.puts.length === 1 && r.puts[0].types[KEY] === true);
  check('C4 no warn.type_off for this key', r.confirms[0] && !r.confirms[0].message.includes('type_off:email.type.' + KEY));
  r = await boot({ [KEY]: false }, false);
  r.sw.checked = true;
  r.save.fire('click');
  await settle();
  check('C5 cancel → no PUT', r.confirms.length === 1 && r.puts.length === 0);

  console.log('\n[D] switching off saves without a warning');
  r = await boot({ [KEY]: true });
  r.sw.checked = false;
  r.save.fire('click');
  await settle();
  check('D1 no confirm', r.confirms.length === 0);
  check('D2 PUT types.support_inbound = false', r.puts.length === 1 && r.puts[0].types[KEY] === false);
  r = await boot({});   // missing stays off → no type_off, no inbound_on
  r.save.fire('click');
  await settle();
  check('D3 untouched off switch → no confirm · PUT false', r.confirms.length === 0 && r.puts[0] && r.puts[0].types[KEY] === false);

  console.log(`\n${passed} passed, ${failed} failed`);
  process.exit(failed ? 1 : 0);
})();
