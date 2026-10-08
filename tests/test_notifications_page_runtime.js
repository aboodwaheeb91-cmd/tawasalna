/**
 * test_notifications_page_runtime.js — PR 4.5: notifications.html on the unified page checklist
 * Runs the REAL page script (the inline <script> of notifications.html) in a Node vm with a tiny
 * fake DOM + recorded stubs for the shared helpers (twRequireAuth / twApi / showToast / twT …),
 * and the REAL twSetNotifBadge from tw_shared.js.
 *   A  guard — guest → no request at all
 *   B  load — notifications + applications rendered · API text via textContent · message type
 *      dropped · auto mark-read → header badge 0 · aggregation badge
 *   C  empty state · error state + retry · applications failing alone does not blank the page
 *   D  filter tabs — groups · filtered empty state
 *   E  «mark all read» — optimistic UI + badge, rollback + error toast on failure, success toast
 *   F  twSetNotifBadge (real tw_shared.js) — cap rule · hide at 0 · loadGlobalBadges calls it
 *   G  structure — every twT key used exists in tw_strings.json
 *
 * Run: node tests/test_notifications_page_runtime.js
 */
'use strict';
const fs = require('fs');
const vm = require('vm');

let passed = 0, failed = 0;
function check(name, cond, detail) {
  if (cond) { passed++; console.log('  PASS  ' + name); }
  else      { failed++; console.log('  FAIL  ' + name + (detail !== undefined ? ' — ' + detail : '')); }
}
const read = f => fs.readFileSync(f, 'utf8');
const flush = async () => { for (let i = 0; i < 6; i++) await new Promise(r => setImmediate(r)); };

const STRINGS = JSON.parse(read('tw_strings.json')).ar;
const HTML = read('notifications.html');
const PAGE_JS = (() => {
  const m = HTML.match(/<script>([\s\S]*?)<\/script>/g) || [];
  return m.map(s => s.replace(/^<script>|<\/script>$/g, '')).join('\n');
})();

// ── tiny fake DOM ───────────────────────────────────────────────────────────
function camelToData(k) { return 'data-' + k.replace(/[A-Z]/g, c => '-' + c.toLowerCase()); }

class El {
  constructor(tag) {
    this.tagName = String(tag).toUpperCase();
    this.children = []; this.parentNode = null; this.attrs = {}; this.style = {};
    this._text = ''; this.listeners = {}; this.hidden = false; this.disabled = false;
    const self = this;
    this.classList = {
      add: (...c) => { const s = new Set(self._cls()); c.forEach(x => s.add(x)); self.className = [...s].join(' '); },
      remove: (...c) => { self.className = self._cls().filter(x => c.indexOf(x) < 0).join(' '); },
      contains: c => self._cls().indexOf(c) >= 0,
      toggle: (c, on) => { (on === undefined ? !self.classList.contains(c) : on) ? self.classList.add(c) : self.classList.remove(c); },
    };
    this.dataset = new Proxy({}, {
      get: (_, k) => self.attrs[camelToData(String(k))],
      set: (_, k, v) => { self.attrs[camelToData(String(k))] = String(v); return true; },
    });
  }
  _cls() { return (this.attrs['class'] || '').split(/\s+/).filter(Boolean); }
  get className() { return this.attrs['class'] || ''; }
  set className(v) { this.attrs['class'] = String(v); }
  get id() { return this.attrs.id || ''; }
  setAttribute(k, v) { this.attrs[k] = String(v); }
  getAttribute(k) { return Object.prototype.hasOwnProperty.call(this.attrs, k) ? this.attrs[k] : null; }
  hasAttribute(k) { return Object.prototype.hasOwnProperty.call(this.attrs, k); }
  removeAttribute(k) { delete this.attrs[k]; }
  appendChild(c) { if (c.parentNode) c.remove(); c.parentNode = this; this.children.push(c); return c; }
  prepend(c) { c.parentNode = this; this.children.unshift(c); }
  remove() { if (this.parentNode) { const p = this.parentNode; p.children = p.children.filter(x => x !== this); this.parentNode = null; } }
  get textContent() { return this._text + this.children.map(c => c.textContent).join(''); }
  set textContent(v) { this.children.forEach(c => { c.parentNode = null; }); this.children = []; this._text = String(v); }
  set innerHTML(v) { innerHtmlWrites.push(v); }
  addEventListener(t, fn) { (this.listeners[t] = this.listeners[t] || []).push(fn); }
  click() { (this.listeners.click || []).forEach(fn => fn({ target: this })); if (this.parentNode) this.parentNode._bubble(this); }
  _bubble(target) { (this.listeners.click || []).forEach(fn => fn({ target })); if (this.parentNode) this.parentNode._bubble(target); }
  _all() { const out = []; this.children.forEach(c => { out.push(c); out.push(...c._all()); }); return out; }
  matches(sel) { return sel.split(',').some(s => matchOne(this, s.trim())); }
  closest(sel) { let e = this; while (e && e.matches) { if (e.matches(sel)) return e; e = e.parentNode; } return null; }
  querySelectorAll(sel) { return this._all().filter(e => e.matches(sel)); }
  querySelector(sel) { return this.querySelectorAll(sel)[0] || null; }
}
function matchOne(el, sel) {
  const re = /([.#]?[\w-]+)|\[([\w-]+)(?:="([^"]*)")?\]/g;
  let m, any = false;
  while ((m = re.exec(sel))) {
    any = true;
    if (m[1]) {
      const t = m[1];
      if (t[0] === '.' && !el.classList.contains(t.slice(1))) return false;
      if (t[0] === '#' && el.id !== t.slice(1)) return false;
      if (t[0] !== '.' && t[0] !== '#' && el.tagName !== t.toUpperCase()) return false;
    } else if (m[3] !== undefined ? el.getAttribute(m[2]) !== m[3] : !el.hasAttribute(m[2])) return false;
  }
  return any;
}
let innerHtmlWrites = [];

// ── page environment ────────────────────────────────────────────────────────
function makePage(opts) {
  opts = opts || {};
  innerHtmlWrites = [];
  const body = new El('body');
  const mk = (tag, attrs, parent) => { const e = new El(tag); Object.assign(e.attrs, attrs || {}); (parent || body).appendChild(e); return e; };
  const badge = mk('span', { 'data-badge': 'notif' });
  badge.textContent = '5'; badge.style.display = 'inline-block';
  ['all', 'job', 'comment', 'follow', 'verify'].forEach(f => mk('button', { class: 'notif-tab' + (f === 'all' ? ' active' : ''), 'data-filter': f }));
  mk('button', { id: 'markAllBtn', class: 'notif-markall-btn' });
  mk('div', { id: 'dynamicNotifs' });
  const document = {
    body, title: '',
    getElementById: id => body.querySelector('#' + id),
    querySelector: s => body.querySelector(s), querySelectorAll: s => body.querySelectorAll(s),
    createElement: t => new El(t),
  };
  const rec = { api: [], toasts: [], missingKeys: new Set(), queue: opts.api || {} };
  const ctx = {
    document, console: { log() {}, warn() {}, error: console.error }, Promise, Date, Math, Number, String,
    Array, Boolean, Object, JSON,
    window: null, scrollY: 0, innerHeight: 800, location: { href: '/notifications' },
    addEventListener() {},
    twRequireAuth: () => (opts.guest ? null : { isAuthenticated: true, userId: 7, userType: 'emp' }),
    twT: (k, vars) => {
      if (!Object.prototype.hasOwnProperty.call(STRINGS, k)) { rec.missingKeys.add(k); return k; }
      return STRINGS[k].replace(/\{(\w+)\}/g, (_, n) => (vars && vars[n] != null ? String(vars[n]) : ''));
    },
    twTApply() {}, twIcon: { hydrate() {} },
    twIconEl: name => { const e = new El('svg'); e.attrs['data-icon'] = name; return e; },
    twApi: (path, o) => {
      const method = (o && o.method) || 'GET';
      rec.api.push(method + ' ' + path);
      const h = rec.queue[method + ' ' + path];
      const next = Array.isArray(h) ? (h.length > 1 ? h.shift() : h[0]) : h;
      if (typeof next === 'function') return next();
      return Promise.resolve(next || { ok: false, status: 500, data: null, error: null });
    },
    twApiMessage: (r, fb) => fb,
    showToast: (msg, type) => rec.toasts.push([type, msg]),
  };
  ctx.window = ctx;
  vm.createContext(ctx);
  // the REAL shared badge writer (tw_shared.js) — extracted, same source
  const shared = read('tw_shared.js');
  const fnSrc = s => shared.slice(shared.indexOf('function ' + s), shared.indexOf('window.' + s + ' ='));
  vm.runInContext(fnSrc('twNotifBadgeLabel') + fnSrc('twSetNotifBadge'), ctx);
  vm.runInContext(PAGE_JS, ctx, { filename: 'notifications.html' });
  return { ctx, body, badge, rec, dyn: body.querySelector('#dynamicNotifs'), markBtn: body.querySelector('#markAllBtn') };
}

const ok = data => ({ ok: true, status: 200, data, error: null });
const fail = status => ({ ok: false, status, data: null, error: null });
const N = (id, type, extra) => Object.assign({ id, type, title: 'T' + id, body: 'B' + id, is_read: false,
  created_at: new Date(Date.now() - 5 * 60000).toISOString(), link: '/p/' + id }, extra || {});

(async () => {
  console.log('\nA — guard');
  {
    const p = makePage({ guest: true });
    await flush();
    check('A1 guest (twRequireAuth → null) → no request, nothing rendered', p.rec.api.length === 0 && p.dyn.children.length === 0);
  }

  console.log('\nB — load');
  {
    const p = makePage({ api: {
      'GET /notifications/7': ok({ unread: 2, notifications: [
        N(1, 'comment', { title: '<img src=x onerror=alert(1)>' }),
        N(2, 'job_applied', { aggregation_count: 3, aggregation_kind: 'apply' }),
        N(3, 'message', { link: '/messages/9' }),
        N(4, 'follow', { is_read: true, link: 'javascript:alert(1)' }),
      ] }),
      'GET /my/applications': ok({ applications: [{ status: 'accepted', title: 'Dev', company_name: 'Co', applied_at: '2026-10-01T00:00:00Z' }] }),
      'PUT /notifications/7/read': ok({ status: 'success' }),
    } });
    await flush();
    const cards = p.dyn.querySelectorAll('.notif-card');
    check('B1 requests go through twApi (notifications + applications + auto mark-read)',
      JSON.stringify(p.rec.api) === JSON.stringify(['GET /notifications/7', 'GET /my/applications', 'PUT /notifications/7/read']),
      JSON.stringify(p.rec.api));
    check('B2 message-type notification dropped · 3 notifications + 1 application rendered', cards.length === 4, cards.length);
    check('B3 API title rendered as text (never innerHTML)',
      cards[0].querySelector('.notif-card-title').textContent === '<img src=x onerror=alert(1)>' && innerHtmlWrites.length === 0);
    check('B4 unsafe link not attached · relative link kept',
      cards[2].getAttribute('data-link') === null && cards[0].getAttribute('data-link') === '/p/1');
    check('B5 auto mark-read ok → header badge 0 (hidden)', p.badge.textContent === '0' && p.badge.style.display === 'none');
    const agg = cards[1].querySelector('.notif-agg-badge');
    check('B6 aggregation badge: count + aria-label with the count', agg && agg.textContent === '3'
      && /3/.test(agg.getAttribute('aria-label')) && cards[1].getAttribute('data-aggregated') === 'true');
    check('B7 group label shows unread count', /2/.test(p.dyn.querySelector('.notif-group-lbl').textContent));
    check('B8 page title set via twT', /الإشعارات/.test(p.ctx.document.title));
  }

  console.log('\nC — empty / error states');
  {
    const p = makePage({ api: { 'GET /notifications/7': ok({ unread: 0, notifications: [] }), 'GET /my/applications': ok({ applications: [] }) } });
    await flush();
    const e = p.dyn.querySelector('.notif-empty');
    check('C1 nothing at all → empty state (not a blank page)', e && e.getAttribute('data-state') === 'empty'
      && e.textContent.length > 0 && p.markBtn.disabled === true);
  }
  {
    const p = makePage({ api: {
      'GET /notifications/7': [fail(500), ok({ unread: 0, notifications: [N(1, 'follow', { is_read: true })] })],
      'GET /my/applications': ok({ applications: [] }),
    } });
    await flush();
    const e = p.dyn.querySelector('.notif-empty');
    const retry = e && e.querySelector('.notif-retry-btn');
    check('C2 notifications request fails → error state with retry button', e && e.getAttribute('data-state') === 'error' && !!retry);
    retry.click();
    await flush();
    check('C3 retry → loads again → cards rendered, error gone',
      p.dyn.querySelectorAll('.notif-card').length === 1 && !p.dyn.querySelector('.notif-empty'));
  }
  {
    const p = makePage({ api: { 'GET /notifications/7': ok({ unread: 0, notifications: [N(1, 'comment', { is_read: true })] }), 'GET /my/applications': fail(500) } });
    await flush();
    check('C4 applications fail alone → notifications still rendered', p.dyn.querySelectorAll('.notif-card').length === 1);
  }

  console.log('\nD — filter tabs');
  {
    const p = makePage({ api: {
      'GET /notifications/7': ok({ unread: 0, notifications: [N(1, 'job_applied', { is_read: true }), N(2, 'comment', { is_read: true }), N(3, 'mention', { is_read: true })] }),
      'GET /my/applications': ok({ applications: [] }),
    } });
    await flush();
    const tab = f => p.body.querySelector('.notif-tab[data-filter="' + f + '"]');
    const shown = () => p.dyn.querySelectorAll('.notif-card').filter(c => c.style.display !== 'none').map(c => c.getAttribute('data-type'));
    tab('job').click();
    check('D1 «وظائف» → job_applied only', JSON.stringify(shown()) === '["job_applied"]', JSON.stringify(shown()));
    tab('comment').click();
    check('D2 «تعليقات» → comment + mention', JSON.stringify(shown()) === '["comment","mention"]');
    tab('follow').click();
    check('D3 no match → filtered empty state', shown().length === 0 && !!p.dyn.querySelector('.notif-empty[data-state="filtered"]'));
    tab('all').click();
    check('D4 «الكل» → all cards, filtered state removed', shown().length === 3 && !p.dyn.querySelector('.notif-empty'));
  }

  console.log('\nE — mark all read');
  {
    let release;
    const p = makePage({ api: {
      'GET /notifications/7': ok({ unread: 2, notifications: [N(1, 'comment'), N(2, 'follow')] }),
      'GET /my/applications': ok({ applications: [] }),
      'PUT /notifications/7/read': [fail(500), () => new Promise(r => { release = r; }), ok({ status: 'success' })],
    } });
    await flush();      // auto mark-read failed → still 2 unread, badge untouched
    p.ctx.twSetNotifBadge(2);
    check('E0 auto mark-read failure → badge not zeroed', p.badge.textContent === '2' && p.markBtn.disabled === false);
    p.markBtn.click();
    check('E1 optimistic: cards read + badge 0 before the response',
      p.dyn.querySelectorAll('.notif-card-unread').length === 0 && p.badge.style.display === 'none' && p.markBtn.disabled === true);
    release(fail(500));
    await flush();
    check('E2 failure → rollback: unread cards back, dots visible, badge restored',
      p.dyn.querySelectorAll('.notif-card-unread').length === 2
      && p.dyn.querySelectorAll('.notif-card-dot').every(d => d.hidden === false)
      && p.badge.textContent === '2' && p.badge.style.display === 'inline-block' && p.markBtn.disabled === false,
      p.badge.textContent);
    check('E3 failure → error toast (shared showToast)', p.rec.toasts.length === 1 && p.rec.toasts[0][0] === 'error');
    p.markBtn.click();
    await flush();
    check('E4 success → cards read, dots removed, badge 0, success toast',
      p.dyn.querySelectorAll('.notif-card-unread').length === 0 && p.dyn.querySelectorAll('.notif-card-dot').length === 0
      && p.badge.textContent === '0' && p.rec.toasts[1][0] === 'success');
  }

  console.log('\nF — twSetNotifBadge (tw_shared.js)');
  {
    const p = makePage({ guest: true });
    p.ctx.twSetNotifBadge(120);
    check('F1 > 99 → "99+" shown', p.badge.textContent === '99+' && p.badge.style.display === 'inline-block');
    p.ctx.twSetNotifBadge(0);
    check('F2 0 → hidden', p.badge.style.display === 'none');
    const shared = read('tw_shared.js');
    const lgbAt = shared.indexOf('function loadGlobalBadges');
    const lgb = shared.slice(lgbAt, shared.indexOf('\n}\n', lgbAt));
    check('F3 loadGlobalBadges writes the notif count through twSetNotifBadge (one writer)', /twSetNotifBadge\(/.test(lgb));
  }

  console.log('\nG — structure');
  {
    const p = makePage({ api: { 'GET /notifications/7': fail(500), 'GET /my/applications': fail(500) } });
    await flush();
    const htmlKeys = [...HTML.matchAll(/data-tw-t(?:-label)?="([\w.]+)"/g)].map(m => m[1]);
    const missing = [...p.rec.missingKeys, ...htmlKeys.filter(k => !(k in STRINGS))];
    check('G1 every twT key used by the page exists in tw_strings.json', missing.length === 0, missing.join(', '));
    check('G2 protected page: tw-page auth meta + Page Shell markers',
      /<meta name="tw-page" content="auth">/.test(HTML) && HTML.includes('<!--tw:shell-head-->') && HTML.includes('<!--tw:shell-scripts-->'));
  }

  console.log('\n' + passed + ' passed, ' + failed + ' failed');
  process.exit(failed ? 1 : 0);
})().catch(e => { console.error(e); process.exit(1); });
