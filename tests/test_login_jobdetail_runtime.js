/**
 * test_login_jobdetail_runtime.js — PR 4.8: index.html (Auth Gateway) + job-detail.html on the
 * unified page checklist. Runs the REAL shared code / page scripts in Node vm contexts.
 *   A  twFormatDate (real tw_shared.js) — Gregorian, one format, Western digits, invalid → ''
 *   B  TwAuthSync.startSession (real auth-sync.js) — the one session writer after login / register
 *   C  index.auth.js (real) — login / register through twApi, clear messages per status, no storage
 *   D  static/job/job-detail.js (real) — twApi only · apply = twAction('apply_job') · Gregorian date
 *      · real links (company / similar jobs) · apply → twModal → POST /jobs/{id}/apply
 *   E  structure — radios / buttons / no role=link / mobile sidebar / every twT key exists
 *
 * Run: node tests/test_login_jobdetail_runtime.js
 */
'use strict';
const fs = require('fs');
const vm = require('vm');

let passed = 0, failed = 0;
function check(name, cond, detail) {
  if (cond) { passed++; console.log('  PASS  ' + name); }
  else      { failed++; console.log('  FAIL  ' + name + (detail !== undefined ? ' — ' + JSON.stringify(detail) : '')); }
}
const read = f => fs.readFileSync(f, 'utf8');
const noop = () => {};
const flush = async () => { for (let i = 0; i < 8; i++) await new Promise(r => setImmediate(r)); };
const STRINGS = JSON.parse(read('tw_strings.json')).ar;

function b64url(o) {
  return Buffer.from(JSON.stringify(o)).toString('base64').replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}
const NOW = Math.floor(Date.now() / 1000);
const jwtFor = (claims) => b64url({ alg: 'HS256' }) + '.' + b64url(claims) + '.sig';
const USER = { id: 42, tw_id: 'U9620abcdef', user_type: 'emp' };
const GOOD_JWT = jwtFor({ user_id: 42, user_type: 'emp', exp: NOW + 3600 });

// ── Auth Gateway context: tw_shared.js → auth-sync.js → index.auth.js (same order as the page) ──
function gateway(opts) {
  opts = opts || {};
  const store = Object.assign({}, opts.store || {});
  const els = {};
  function el(id) {
    if (!els[id]) {
      els[id] = {
        id, attrs: {}, classList: { add: noop, remove: noop }, value: '', textContent: '',
        setAttribute(k, v) { this.attrs[k] = String(v); }, removeAttribute(k) { delete this.attrs[k]; },
        querySelector() { return null; }, focus: noop, scrollIntoView: noop, addEventListener: noop,
      };
      // banners have a text child
      if (/form-error$/.test(id)) {
        const txt = { textContent: '' };
        els[id].text = txt;
        els[id].querySelector = () => txt;
      }
    }
    return els[id];
  }
  const doc = {
    visibilityState: 'visible', addEventListener: noop,
    getElementById: id => (opts.dom ? el(id) : null),
    querySelector: () => null, querySelectorAll: () => [],
    createElement: () => ({ style: {}, setAttribute: noop, appendChild: noop, classList: { add: noop } }),
    body: { appendChild: noop, classList: { add: noop } }, documentElement: { style: {} },
  };
  const toasts = [], timers = [];
  const ctx = {
    localStorage: {
      getItem: k => Object.prototype.hasOwnProperty.call(store, k) ? store[k] : null,
      setItem: (k, v) => { if (opts.quota) throw new Error('QuotaExceededError'); store[k] = String(v); },
      removeItem: k => { delete store[k]; },
    },
    document: doc, console: { log: noop, warn: noop, error: noop }, URLSearchParams, encodeURIComponent,
    atob: s => Buffer.from(s, 'base64').toString('binary'),
    setTimeout: (fn) => { timers.push(fn); return 0; }, clearTimeout: noop, setInterval: () => 0, clearInterval: noop,
    navigator: { userAgent: 'node' }, Date, JSON, Math, Promise,
  };
  ctx.window = ctx;
  ctx.addEventListener = noop;
  const nav = { href: '' };
  ctx.location = { protocol: 'http:', host: 'x', pathname: '/login', search: '',
                   replace: noop, set href(u) { nav.href = u; }, get href() { return nav.href; } };
  vm.createContext(ctx);
  ctx.TW_STRINGS = { dict: STRINGS };
  ['tw_shared.js', 'static/shared/auth-sync.js'].concat(opts.auth ? ['index.auth.js'] : [])
    .forEach(f => vm.runInContext(read(f), ctx, { filename: f }));
  ctx.showToast = (m, t) => toasts.push([m, t]);
  return { ctx, store, els, el, toasts, timers, nav };
}

(async function main() {

  console.log('\nA — twFormatDate (tw_shared.js)');
  {
    const { ctx } = gateway();
    const d = new Date(2026, 9, 8, 12, 0, 0);   // local 8 Oct 2026
    check('A1 Date → «8 أكتوبر 2026» (Gregorian month name, Western digits)',
      ctx.twFormatDate(d) === '8 أكتوبر 2026', ctx.twFormatDate(d));
    check('A2 ISO string, same result', ctx.twFormatDate(d.toISOString()) === '8 أكتوبر 2026');
    check('A3 epoch ms, same result', ctx.twFormatDate(d.getTime()) === '8 أكتوبر 2026');
    check('A4 never Hijri (no هـ / Hijri month names)',
      !/هـ|رمضان|ربيع|جمادى|شوال/.test(ctx.twFormatDate('2026-03-10T10:00:00Z')));
    check('A5 every month has a label', [...Array(12).keys()].every(m =>
      !/date\.month/.test(ctx.twFormatDate(new Date(2026, m, 15)))));
    check('A6 empty / null / invalid → \'\'',
      ['', null, undefined, 'not-a-date'].every(v => ctx.twFormatDate(v) === ''));
  }

  console.log('\nB — TwAuthSync.startSession (auth-sync.js)');
  {
    const g = gateway({ store: { tw_cover_x: 'c', tw_prefs: '{"a":1}', tw_user: '{"id":1}', tw_jwt: 'old' } });
    check('B1 valid pair → true', g.ctx.TwAuthSync.startSession(USER, GOOD_JWT) === true);
    check('B2 both keys written', g.store.tw_jwt === GOOD_JWT && JSON.parse(g.store.tw_user).id === 42);
    check('B3 other tw_* keys preserved (allowlist, no startsWith scan)',
      g.store.tw_cover_x === 'c' && g.store.tw_prefs === '{"a":1}');
    check('B4 snapshot authenticated', g.ctx.TwAuthSync.getSessionSnapshot().isAuthenticated === true);

    const bad = [
      ['someone else\'s token', USER, jwtFor({ user_id: 7, user_type: 'emp', exp: NOW + 3600 })],
      ['wrong account type', USER, jwtFor({ user_id: 42, user_type: 'co', exp: NOW + 3600 })],
      ['expired', USER, jwtFor({ user_id: 42, user_type: 'emp', exp: NOW - 10 })],
      ['malformed', USER, 'fresh.jwt.token'],
      ['empty token', USER, ''],
      ['no user', null, GOOD_JWT],
    ];
    bad.forEach(([name, u, t], i) => {
      const b = gateway({ store: { tw_prefs: 'p' } });
      const r = b.ctx.TwAuthSync.startSession(u, t);
      check('B5.' + i + ' ' + name + ' → false, nothing kept',
        r === false && !('tw_jwt' in b.store) && !('tw_user' in b.store) && b.store.tw_prefs === 'p');
    });
    const q = gateway({ quota: true });
    check('B6 storage quota error → false, nothing kept',
      q.ctx.TwAuthSync.startSession(USER, GOOD_JWT) === false && !('tw_jwt' in q.store) && !('tw_user' in q.store));
  }

  console.log('\nC — index.auth.js login / register (twApi)');
  async function login(res, fill) {
    const g = gateway({ auth: true, dom: true });
    g.el('lEmail').value = (fill && fill.email) || 'a@b.co';
    g.el('lPass').value = 'secret1';
    const calls = [];
    g.ctx.twApi = (p, o) => { calls.push([p, o]); return Promise.resolve(res); };
    await g.ctx.doLogin();
    return Object.assign(g, { calls, banner: g.el('l-form-error').text.textContent });
  }
  {
    const ok = await login({ ok: true, status: 200, data: { user: USER, token: GOOD_JWT } });
    check('C1 login → twApi POST /auth/login (auth:false, JSON body)',
      ok.calls.length === 1 && ok.calls[0][0] === '/auth/login' && ok.calls[0][1].method === 'POST'
      && ok.calls[0][1].auth === false && ok.calls[0][1].body.email === 'a@b.co');
    check('C2 success → session written by startSession', ok.store.tw_jwt === GOOD_JWT);
    ok.timers.forEach(fn => fn());
    check('C3 success → redirect to the account (/u/{tw_id})', ok.nav.href === '/u/' + USER.tw_id, ok.nav.href);

    const cases = [
      ['401', { ok: false, status: 401, raw: { error: 'x' } }, STRINGS['login.err.credentials']],
      ['429 locked', { ok: false, status: 429, raw: { detail: { code: 'login_email_locked' } } }, STRINGS['login.err.locked']],
      ['429', { ok: false, status: 429, raw: {} }, STRINGS['login.err.too_many']],
      ['502', { ok: false, status: 502, raw: null }, STRINGS['login.err.server']],
    ];
    for (const [name, res, want] of cases) {
      const g = await login(res);
      check('C4 login ' + name + ' → clear banner text, no session', g.banner === want && !('tw_jwt' in g.store), g.banner);
    }
    const net = await login({ ok: false, status: 0, raw: null,
      error: { fieldErrors: [], generalError: { code: 'network', message: 'لا يوجد اتصال' } } });
    check('C5 network failure → the twApi network message', net.banner === 'لا يوجد اتصال', net.banner);
    const broken = await login({ ok: true, status: 200, data: { user: USER, token: 'bad' } });
    check('C6 2xx with a bad token → banner, no session, no redirect',
      broken.banner === STRINGS['login.err.incomplete'] && !('tw_jwt' in broken.store) && broken.timers.length === 0);
  }
  async function register(res) {
    const g = gateway({ auth: true, dom: true });
    g.el('rFirstName').value = 'سارة'; g.el('rLastName').value = 'علي';
    g.el('rEmail').value = 'new@b.co'; g.el('rPass').value = 'secret12';
    const calls = [];
    g.ctx.twApi = (p, o) => { calls.push([p, o]); return Promise.resolve(res); };
    await g.ctx.doRegister();
    return Object.assign(g, { calls, banner: g.el('r-form-error').text.textContent,
                              emailErr: g.el('r-email-error').textContent });
  }
  {
    const ok = await register({ ok: true, status: 200, data: { user: USER, token: GOOD_JWT } });
    check('C7 register → twApi POST /auth/register with the personal-account name fields',
      ok.calls[0][0] === '/auth/register' && ok.calls[0][1].body.user_type === 'emp'
      && ok.calls[0][1].body.first_name === 'سارة' && ok.calls[0][1].body.last_name === 'علي');
    check('C8 register success → session + success toast', ok.store.tw_jwt === GOOD_JWT
      && ok.toasts.some(t => t[0] === STRINGS['register.success']));
    const taken = await register({ ok: false, status: 409, raw: { error: 'البريد الإلكتروني مسجل مسبقاً' },
      error: { fieldErrors: [], generalError: { code: '', message: 'البريد الإلكتروني مسجل مسبقاً' } } });
    check('C9 409 → server message under the email field (not raw JSON, no toast)',
      taken.emailErr === 'البريد الإلكتروني مسجل مسبقاً' && !taken.toasts.length && !('tw_jwt' in taken.store));
    const weak = await register({ ok: false, status: 400,
      error: { fieldErrors: [], generalError: { code: '', message: 'كلمة المرور يجب أن تكون 6 أحرف على الأقل' } } });
    check('C10 400 → server validation text in the register banner',
      weak.banner === 'كلمة المرور يجب أن تكون 6 أحرف على الأقل', weak.banner);
    const down = await register({ ok: false, status: 500, raw: { error: 'خطأ في الخادم' } });
    check('C11 500 → fixed server-error text', down.banner === STRINGS['register.err.server'], down.banner);
    const html = await register({ ok: false, status: 502, raw: null, error: null });
    check('C12 non-JSON 502 → fixed text (was res.json() throwing → «تعذّر الاتصال»)',
      html.banner === STRINGS['register.err.server']);
  }

  console.log('\nD — job-detail.js (real script, fake DOM)');
  {
    class El {
      constructor(tag) {
        this.tagName = String(tag).toUpperCase(); this.children = []; this.attrs = {}; this.style = {
          setProperty: (k, v) => { this.style[k] = v; }, removeProperty: k => { delete this.style[k]; } };
        this._text = ''; this.listeners = {}; this.hidden = false; this.disabled = false; this._cls = new Set();
        const self = this;
        this.classList = { add: (...c) => c.forEach(x => self._cls.add(x)), remove: (...c) => c.forEach(x => self._cls.delete(x)),
                           contains: c => self._cls.has(c) };
      }
      set className(v) { this._cls = new Set(String(v).split(/\s+/).filter(Boolean)); }
      get className() { return [...this._cls].join(' '); }
      setAttribute(k, v) { this.attrs[k] = String(v); if (k === 'href') this.href = String(v); }
      getAttribute(k) { return Object.prototype.hasOwnProperty.call(this.attrs, k) ? this.attrs[k] : null; }
      removeAttribute(k) { delete this.attrs[k]; if (k === 'href') delete this.href; }
      appendChild(c) { this.children.push(c); c.parentNode = this; return c; }
      addEventListener(t, f) { (this.listeners[t] = this.listeners[t] || []).push(f); }
      querySelector() { return null; }
      closest() { return this._row || null; }
      set textContent(v) { this._text = String(v); this.children = []; }
      get textContent() { return this._text + this.children.map(c => c.textContent || '').join(''); }
      set innerHTML(v) { this._html = v; }
    }
    const ids = {};
    const byId = id => (ids[id] = ids[id] || new El(id === 'jdCoName' || id === 'jdCoCardName' ? 'a' : 'div'));
    ['jdSiCo', 'jdSiLoc', 'jdSiType', 'jdSiMode', 'jdSiExp', 'jdSiSal', 'jdSiViews', 'jdSiDate'].forEach(id => {
      byId(id)._row = new El('div');
    });
    const slots = { apply: [], action: [] };
    ['card', 'sticky'].forEach(k => { const s = new El('div'); s.attrs['data-jd-apply-slot'] = k; slots.apply.push(s); });
    ['share', 'share-icon', 'report'].forEach(k => { const s = new El('div'); s.attrs['data-jd-action-slot'] = k; slots.action.push(s); });
    const doc = {
      readyState: 'complete', body: new El('body'), title: '',
      getElementById: byId, createElement: t => new El(t), createTextNode: t => ({ textContent: String(t) }),
      querySelectorAll: sel => sel === '[data-jd-apply-slot]' ? slots.apply : sel === '[data-jd-action-slot]' ? slots.action : [],
      addEventListener: noop,
    };
    const JOB = { id: 5, title: 'مطوّر', company_id: 77, company_tw_id: 'C962xyz', company_name: 'شركة', status: 'active',
                  created_at: '2026-10-08T09:00:00Z', skills: ['Python'], job_type: 'full_time' };
    const apiCalls = [], actions = [], modals = [], toasts = [];
    const api = {
      '/jobs/5': { ok: true, status: 200, data: { job: JOB } },
      '/my/applications': { ok: true, status: 200, data: { applications: [] } },
      '/profile/9/full': { ok: true, status: 200, data: { profile: { skills: ['python'] } } },
      '/jobs': { ok: true, status: 200, data: { jobs: [{ id: 8, title: 'آخر', skills: ['Python'] }] } },
      '/jobs/5/apply': { ok: true, status: 200, data: { status: 'success' } },
    };
    const ctx = {
      document: doc, console: { log: noop, warn: noop, error: noop }, URLSearchParams, Set, Date, Math, JSON, Promise,
      location: { search: '?id=5', pathname: '/job-detail', href: '/job-detail?id=5' }, navigator: {},
      TwAuthSync: { getSessionSnapshot: () => ({ isAuthenticated: true, userType: 'emp', userId: 9 }) },
      getTwUser: () => ({ id: 9, tw_id: 'U1' }),
      twT: (k, v) => { const s = STRINGS[k]; if (typeof s !== 'string') return k;
        return v ? s.replace(/\{(\w+)\}/g, (m, n) => (n in v ? String(v[n]) : m)) : s; },
      twApi: (p, o) => { apiCalls.push([p, o || {}]); return Promise.resolve(api[p] || { ok: false, status: 404 }); },
      twApiMessage: (r, f) => f,
      twAction: (id, c) => { actions.push([id, c]); const b = new El('button'); b.disabled = !!c.disabled; return b; },
      twModal: o => { modals.push(o); return { close: noop }; },
      twIconEl: () => new El('svg'), twIcon: { hydrate: noop }, twAvatarHtml: () => '',
      twFormatDate: v => 'G:' + v, twLoginHref: p => '/login?next=' + p, twAccountHref: () => '/u/U1',
      twNavBack: noop, twHomeHref: () => '/home', showToast: (m, t) => toasts.push([m, t]),
      fetch: () => { throw new Error('raw fetch called'); },
    };
    ctx.window = ctx;
    vm.createContext(ctx);
    vm.runInContext(read('static/job/job-detail.js'), ctx, { filename: 'job-detail.js' });
    await flush();

    check('D1 every request through twApi (no raw fetch)', apiCalls.length >= 4
      && ['/jobs/5', '/my/applications', '/profile/9/full', '/jobs'].every(p => apiCalls.some(c => c[0] === p)));
    const applies = actions.filter(a => a[0] === 'apply_job');
    check('D2 «تقديم» = twAction(\'apply_job\') in both slots (card + sticky), owner = the company',
      applies.length >= 2 && applies.every(a => a[1].ownerId === 77 && typeof a[1].onClick === 'function')
      && slots.apply.every(s => s.children.length === 1));
    check('D3 share + report via twAction too', ['share', 'report'].every(id => actions.some(a => a[0] === id)));
    check('D4 publish date = twFormatDate (Gregorian helper), not toLocaleDateString',
      byId('jdSiDate').textContent === 'G:' + JOB.created_at, byId('jdSiDate').textContent);
    check('D5 company name = real link to /u/{tw_id}', byId('jdCoName').href === '/u/C962xyz'
      && byId('jdCoCardName').href === '/u/C962xyz');
    const coLink = byId('jdSiCo').children[0];
    check('D6 sidebar company value = <a href>', coLink && coLink.tagName === 'A' && coLink.href === '/u/C962xyz');
    const sim = byId('jdSimilarList').children[0];
    check('D7 similar job = <a href="/job-detail?id=8"> (no click handler on a div)',
      sim && sim.tagName === 'A' && sim.href === '/job-detail?id=8' && !Object.keys(sim.listeners).length);

    applies[0][1].onClick();
    check('D8 apply → twModal (DS-OVL), not a hand-written overlay', modals.length === 1);
    const send = modals[0].actions.find(a => typeof a.onClick === 'function');
    const ok = await send.onClick();
    const post = apiCalls.find(c => c[0] === '/jobs/5/apply');
    check('D9 send → twApi POST /jobs/5/apply {cover_letter}, modal closes',
      post && post[1].method === 'POST' && 'cover_letter' in post[1].body && ok === true);
    const last = actions.filter(a => a[0] === 'apply_job').slice(-2);
    check('D10 after applying → apply_job re-rendered disabled «تم التقديم»',
      last.every(a => a[1].disabled === true && a[1].labelKey === 'job.applied'));
  }

  console.log('\nE — structure');
  {
    const IDX = read('index.html'), JD = read('job-detail.html'), JDCSS = read('static/job/job-detail.css');
    const radios = IDX.match(/<input type="radio" name="accountType" value="(emp|co|edu)"/g) || [];
    check('E1 account type = 3 real radios inside role="radiogroup"',
      radios.length === 3 && /id="typeRow"[^>]*role="radiogroup"/.test(IDX));
    check('E2 no inline onclick in index.html', !/onclick=/i.test(IDX));
    check('E3 «نسيت كلمة السر» = a real <button>', /<button[^>]*id="forgotBtn"/.test(IDX));
    check('E4 personal account label from account.type.emp (no «موظف» card)',
      /data-tw-t="account\.type\.emp"/.test(IDX) && !/>موظف</.test(IDX));
    check('E5 no role="link" in job-detail.html', !/role="link"/.test(JD));
    const mobile = (JDCSS.match(/@media \(max-width: 719px\)\s*\{([\s\S]*?)\n\}/) || [])[1] || '';
    check('E6 mobile: sidebar not hidden (shown under the content)',
      mobile && !/\.jd-sidebar\s*\{[^}]*display:\s*none/.test(mobile));
    const JS = ['index.auth.js', 'index.ui.js', 'static/job/job-detail.js'].map(read).join('\n');
    check('E7 no toLocaleDateString in the two pages', !/toLocaleDateString/.test(JS));
    const keys = new Set();
    (JS.match(/twT\('([a-z0-9_.]+)'/g) || []).forEach(m => keys.add(m.slice(5, -1)));
    (IDX + JD).replace(/data-tw-t(?:-label|-placeholder)?="([a-z0-9_.]+)"/g, (m, k) => keys.add(k));
    ['job.applied', 'job.status.paused', 'job.status.closed', 'job.apply_now', 'job.share', 'job.report']
      .forEach(k => keys.add(k));
    // keys built from a prefix + value (twT('job.type.' + t) …) → the whole family
    [...keys].filter(k => /[._]$/.test(k)).forEach(k => keys.delete(k));
    [1, 2, 3, 4, 5].forEach(n => keys.add('register.strength.' + n));
    ['full_time', 'part_time', 'contract', 'freelance', 'internship', 'remote'].forEach(t => keys.add('job.type.' + t));
    ['high', 'good', 'partial'].forEach(l => { keys.add('job.match.' + l); keys.add('job.match.title_' + l); });
    ['fraud', 'spam', 'misleading', 'harassment', 'other'].forEach(t => keys.add('job.report.' + t));
    const missing = [...keys].filter(k => typeof STRINGS[k] !== 'string');
    check('E8 every twT / data-tw-t key exists in tw_strings.json (' + keys.size + ' keys)', !missing.length, missing);
  }

  console.log('\n' + passed + ' passed, ' + failed + ' failed');
  process.exit(failed ? 1 : 0);
}()).catch(e => { console.error(e); process.exit(1); });
