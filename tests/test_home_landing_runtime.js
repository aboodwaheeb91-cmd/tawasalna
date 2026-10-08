/**
 * test_home_landing_runtime.js — PR 4.1: home (home-v2.html) + landing.html on the unified page checklist
 * Runs the REAL Home V2 scripts (static/home/*.js, in the page's load order) in a Node vm with a tiny
 * fake DOM + recorded stubs for the shared helpers (twRequireAuth / twApi / twT / twIconEl / twAvatarEl),
 * and the REAL twAccountHref / twTalentBankHref from tw_shared.js.
 *   A  guard — guest → no request at all · title from twT
 *   B  emp — completion % from GET /profile/{id}/score (not a fixed number) · box hidden when it fails
 *   C  co  — active jobs from GET /company/jobs · no stat when it fails · no placeholder numbers
 *   D  edu — no stats (no API) · links → account page
 *   E  links — no legacy route (/profile · /company-profile · /edu-profile) for any type
 *   F  feed — twApi request · cards via textContent + DS-IMAGE · empty / error states
 *   G  strings — every twT key used (JS + data-tw-t in home-v2.html) exists in tw_strings.json
 *   H  landing — unified guest header placeholder · no GLOSSARY-forbidden word
 *
 * Run: node tests/test_home_landing_runtime.js
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
const flush = async () => { for (let i = 0; i < 8; i++) await new Promise(r => setImmediate(r)); };

const STRINGS = JSON.parse(read('tw_strings.json')).ar;
const HTML = read('home-v2.html');
const SCRIPTS = (HTML.match(/<script src="\/static\/home\/[^"]+"/g) || []).map(s => s.slice(13, -1).replace(/^\//, ''));
const TWS = read('tw_shared.js');
const fnSrc = name => TWS.slice(TWS.indexOf('function ' + name + '('), TWS.indexOf('\n}\n', TWS.indexOf('function ' + name + '(')) + 3);
const SHARED_HREFS = fnSrc('twAccountHref') + fnSrc('twTalentBankHref');

// ── tiny fake DOM ───────────────────────────────────────────────────────────
class El {
  constructor(tag) {
    this.tagName = String(tag).toUpperCase();
    this.children = []; this.parentNode = null; this.attrs = {}; this.style = {};
    this._text = ''; this.listeners = {};
    const self = this;
    this.classList = {
      add: (...c) => { const s = new Set(self._cls()); c.forEach(x => s.add(x)); self.className = [...s].join(' '); },
      remove: (...c) => { self.className = self._cls().filter(x => c.indexOf(x) < 0).join(' '); },
      contains: c => self._cls().indexOf(c) >= 0,
      toggle: c => { const on = !self.classList.contains(c); on ? self.classList.add(c) : self.classList.remove(c); return on; },
    };
  }
  _cls() { return (this.attrs['class'] || '').split(/\s+/).filter(Boolean); }
  get className() { return this.attrs['class'] || ''; }
  set className(v) { this.attrs['class'] = String(v); }
  get id() { return this.attrs.id || ''; }
  get href() { return this.attrs.href; }
  set href(v) { this.attrs.href = String(v); }
  setAttribute(k, v) { this.attrs[k] = String(v); }
  getAttribute(k) { return Object.prototype.hasOwnProperty.call(this.attrs, k) ? this.attrs[k] : null; }
  hasAttribute(k) { return Object.prototype.hasOwnProperty.call(this.attrs, k); }
  appendChild(c) {
    if (c.isFragment) { c.children.slice().forEach(x => this.appendChild(x)); c.children = []; return c; }
    if (c.parentNode) c.remove(); c.parentNode = this; this.children.push(c); return c;
  }
  remove() { if (this.parentNode) { const p = this.parentNode; p.children = p.children.filter(x => x !== this); this.parentNode = null; } }
  get textContent() { return this._text + this.children.map(c => c.textContent).join(''); }
  set textContent(v) { this.children.forEach(c => { c.parentNode = null; }); this.children = []; this._text = String(v); }
  set innerHTML(v) { this.textContent = ''; this.rawHtml = String(v); }
  addEventListener(t, fn) { (this.listeners[t] = this.listeners[t] || []).push(fn); }
  click() { (this.listeners.click || []).forEach(fn => fn({ target: this })); if (this.onclick) this.onclick(); }
  _all() { const out = []; this.children.forEach(c => { out.push(c); out.push(...c._all()); }); return out; }
  matches(sel) { return matchOne(this, sel.trim()); }
  closest() { return null; }
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

// ── page environment (the ids / classes the modules use, as in home-v2.html) ──
async function makePage(opts) {
  opts = opts || {};
  const body = new El('body');
  const mk = (tag, attrs, parent) => { const e = new El(tag); Object.assign(e.attrs, attrs || {}); (parent || body).appendChild(e); return e; };
  ['all', 'opportunities', 'posts', 'news'].forEach(f => mk('button', { class: 'hw-ft' + (f === 'all' ? ' active' : ''), 'data-filter': f }));
  const banner = mk('div', { id: 'hwBanner', class: 'hw-banner hidden' });
  mk('div', { id: 'hwBIco' }, banner); mk('h3', { id: 'hwBTitle' }, banner); mk('p', { id: 'hwBSub' }, banner);
  mk('div', { id: 'hwBStats', class: 'hw-banner-stats hidden' }, banner);
  mk('div', { id: 'hwFeed' });
  const empty = mk('div', { id: 'hwEmpty', class: 'hw-empty hidden' }); mk('h3', {}, empty); mk('p', {}, empty);
  const err = mk('div', { id: 'hwError', class: 'hw-error hidden' }); mk('button', { class: 'hw-retry' }, err);
  const compl = mk('div', { id: 'sbComplBox', class: 'hw-sb-box hidden' });
  mk('div', { id: 'sbFill' }, compl); mk('span', { id: 'sbPct' }, compl); mk('a', { id: 'sbComplLink' }, compl);
  mk('div', { id: 'sbLinks' });

  const document = {
    body, title: '',
    getElementById: id => body.querySelector('#' + id),
    querySelector: s => body.querySelector(s), querySelectorAll: s => body.querySelectorAll(s),
    createElement: t => new El(t),
    createTextNode: t => { const e = new El('#text'); e._text = String(t); return e; },
    createDocumentFragment: () => { const e = new El('#fragment'); e.isFragment = true; return e; },
  };
  const rec = { api: [], missingKeys: new Set(), avatars: [], hydrated: 0 };
  const api = opts.api || {};
  const ctx = {
    document, console: { log() {}, warn() {}, error: console.error }, Promise, Date, Math, Number, String,
    Array, Boolean, Object, JSON, AbortController, encodeURIComponent, parseInt,
    location: { href: '/home', pathname: '/home', search: '' },
    twRequireAuth: () => (opts.guest ? null : { isAuthenticated: true, userId: opts.uid || 7, userType: opts.type || 'emp' }),
    getTwUser: () => (opts.guest ? null : { id: opts.uid || 7, user_type: opts.type || 'emp', tw_id: opts.twId === undefined ? 'U123' : opts.twId }),
    twApi: (path, o) => {
      rec.api.push(path);
      const key = Object.keys(api).find(k => path.indexOf(k) === 0);
      const r = key ? (typeof api[key] === 'function' ? api[key](path, o) : api[key])
                    : { ok: false, status: 404, data: null, error: {} };
      return Promise.resolve(r);
    },
    twT: (k, vars) => {
      if (!Object.prototype.hasOwnProperty.call(STRINGS, k)) { rec.missingKeys.add(k); return k; }
      return STRINGS[k].replace(/\{(\w+)\}/g, (m, n) => (vars && vars[n] !== undefined ? String(vars[n]) : m));
    },
    twIconEl: (name, o) => { const e = new El('svg'); e.attrs['data-ico'] = name; e.attrs['data-size'] = (o && o.size) || ''; return e; },
    twIcon: { hydrate: () => { rec.hydrated++; } },
    twAvatarEl: (entity, size) => { rec.avatars.push({ entity, size }); const e = new El('span'); e.className = 'tw-ava'; return e; },
    twSafeLinkUrl: u => (/^https?:\/\/\w/.test(u) ? u : ''),
  };
  ctx.window = ctx;
  vm.createContext(ctx);
  vm.runInContext(SHARED_HREFS, ctx);
  SCRIPTS.forEach(f => vm.runInContext(read(f), ctx, { filename: f }));
  await flush();
  return { ctx, document, body, rec };
}
const $ = (p, id) => p.document.getElementById(id);
const hidden = el => el.classList.contains('hidden');
const linkHrefs = p => $(p, 'sbLinks').children.map(a => a.href);
const FEED_OK = { ok: true, status: 200, data: { items: [] } };

(async () => {
  console.log('\nA — guard');
  check('A page loads every home module in order (home.main.js last)',
    SCRIPTS.length === 8 && SCRIPTS[SCRIPTS.length - 1] === 'static/home/home.main.js', SCRIPTS);
  let p = await makePage({ guest: true });
  check('A guest → no API request at all (twRequireAuth returned null)', p.rec.api.length === 0, p.rec.api);
  check('A page declares <meta name="tw-page" content="auth"> + no Lucide', /<meta name="tw-page" content="auth">/.test(HTML)
    && !/lucide/i.test(HTML) && !SCRIPTS.some(f => /lucide/i.test(read(f))));
  p = await makePage({ api: { '/home/feed': FEED_OK, '/profile/': { ok: true, status: 200, data: { score: 72, tips: [] } } } });
  check('A title from twT', p.document.title === STRINGS['page.title'].replace('{page}', STRINGS['header.home']), p.document.title);

  console.log('\nB — emp completion (server score)');
  check('B score requested for the session user', p.rec.api.indexOf('/profile/7/score') !== -1, p.rec.api);
  check('B box shown with the API number', !hidden($(p, 'sbComplBox')) && $(p, 'sbPct').textContent === '72%'
    && $(p, 'sbFill').style.width === '72%', [$(p, 'sbPct').textContent, $(p, 'sbFill').style.width]);
  check('B improve link → /u/{tw_id}', $(p, 'sbComplLink').href === '/u/U123', $(p, 'sbComplLink').href);
  const p2 = await makePage({ api: { '/home/feed': FEED_OK, '/profile/': { ok: true, status: 200, data: { score: 35 } } } });
  check('B a different score shows a different number (no fixed value)', $(p2, 'sbPct').textContent === '35%');
  const p3 = await makePage({ api: { '/home/feed': FEED_OK } });
  check('B score API fails → completion box stays hidden (no placeholder)', hidden($(p3, 'sbComplBox'))
    && $(p3, 'sbPct').textContent === '');
  check('B emp: no banner', hidden($(p, 'hwBanner')));

  console.log('\nC — co banner (server count)');
  const jobs = [{ effective_status: 'active' }, { effective_status: 'active' }, { effective_status: 'paused' }];
  p = await makePage({ type: 'co', twId: 'C55', api: { '/home/feed': FEED_OK,
    '/company/jobs': { ok: true, status: 200, data: { jobs, count: 3, view: 'active' } } } });
  const stats = $(p, 'hwBStats');
  check('C GET /company/jobs?view=active requested', p.rec.api.indexOf('/company/jobs?view=active') !== -1, p.rec.api);
  check('C one stat = active jobs from the API (2 of 3)', !hidden(stats) && stats.children.length === 1
    && stats.children[0].children[0].textContent === '2'
    && stats.children[0].children[1].textContent === STRINGS['home.banner.active_jobs'], stats.textContent);
  check('C no completion request / box for a company', !p.rec.api.some(x => /\/score$/.test(x)) && hidden($(p, 'sbComplBox')));
  check('C talent bank link → twTalentBankHref', linkHrefs(p).indexOf('/u/C55?cand=') !== -1, linkHrefs(p));
  const pc = await makePage({ type: 'co', twId: 'C55', api: { '/home/feed': FEED_OK } });
  check('C jobs API fails → no stats, no placeholder', hidden($(pc, 'hwBStats')) && $(pc, 'hwBStats').children.length === 0
    && !$(pc, 'hwBanner').textContent.includes('—'));

  console.log('\nD — edu');
  p = await makePage({ type: 'edu', twId: 'T9', api: { '/home/feed': FEED_OK } });
  check('D banner shown, no stats, only the feed requested', !hidden($(p, 'hwBanner')) && hidden($(p, 'hwBStats'))
    && p.rec.api.length === 1 && p.rec.api[0].indexOf('/home/feed') === 0, p.rec.api);

  console.log('\nE — links: current routes only');
  for (const [type, tw] of [['emp', 'U1'], ['co', 'C1'], ['edu', 'T1']]) {
    const pp = await makePage({ type, twId: tw, api: { '/home/feed': FEED_OK, '/profile/': { ok: true, status: 200, data: { score: 50 } } } });
    const all = linkHrefs(pp).concat([$(pp, 'sbComplLink').href || '']);
    check(`E ${type}: no legacy route`, !all.some(h => /^\/(profile|company-profile|edu-profile|company|edu)(\b|$)/.test(h)), all);
    check(`E ${type}: account links → /u/${tw}`, all.some(h => h === '/u/' + tw), all);
  }

  console.log('\nF — feed');
  const items = [
    { type: 'opportunity', id: 5, title: '<b>x</b>', company_name: 'Acme', company_logo: 'javascript:alert(1)', job_type: 'remote', created_at: new Date().toISOString() },
    { type: 'post', id: 1, body: 'hello', author_name: 'Sara', author_avatar: '', author_tw_id: 'U2' },
    { type: 'news', id: 2, title: 'N', category: 'opportunity', body: 'b', source_url: 'javascript:x' },
  ];
  p = await makePage({ api: { '/home/feed': { ok: true, status: 200, data: { items } }, '/profile/': { ok: false, status: 500 } } });
  check('F GET /home/feed?filter=all&limit=30 via twApi', p.rec.api.indexOf('/home/feed?filter=all&limit=30') !== -1, p.rec.api);
  const feed = $(p, 'hwFeed');
  check('F 3 cards rendered', feed.children.length === 3 && !hidden(feed), feed.children.length);
  check('F API text via textContent (no HTML parsed)', feed.textContent.includes('<b>x</b>') && !feed.rawHtml);
  check('F job type + news category labels via twT', feed.textContent.includes(STRINGS['home.job_type.remote'])
    && feed.textContent.includes(STRINGS['home.news_cat.opportunity']));
  check('F logo + author avatar via twAvatarEl (company = co)', p.rec.avatars.length === 2
    && p.rec.avatars[0].entity.user_type === 'co' && p.rec.avatars[0].entity.avatar_url === 'javascript:alert(1)'
    && p.rec.avatars[1].entity.full_name === 'Sara', p.rec.avatars);
  check('F job link → /job-detail?id=5', feed.querySelectorAll('a').some(a => a.href === '/job-detail?id=5'));
  check('F unsafe news source → no link', !feed.querySelectorAll('a').some(a => /javascript/.test(a.href || '')));
  p = await makePage({ api: { '/home/feed': FEED_OK } });
  check('F empty → empty state from twT', !hidden($(p, 'hwEmpty')) && $(p, 'hwEmpty').children[0].textContent === STRINGS['home.empty.all']);
  let calls = 0;
  p = await makePage({ api: { '/home/feed': () => (++calls === 1 ? { ok: false, status: 0, data: null, error: {} } : FEED_OK) } });
  check('F error → error state', !hidden($(p, 'hwError')) && hidden($(p, 'hwFeed')));
  $(p, 'hwError').children[0].click(); await flush();
  check('F retry reloads the feed', calls === 2 && hidden($(p, 'hwError')) && !hidden($(p, 'hwEmpty')), calls);
  const opp = p.body.querySelectorAll('.hw-ft')[1];
  opp.click(); await flush();
  check('F «opportunities» filter → filter=opportunities request', p.rec.api.slice(-1)[0] === '/home/feed?filter=opportunities&limit=30', p.rec.api);

  console.log('\nG — strings');
  const htmlKeys = (HTML.match(/data-tw-t="([a-z0-9_.]+)"/g) || []).map(s => s.slice(11, -1));
  check('G every data-tw-t key in home-v2.html exists', htmlKeys.length >= 8 && htmlKeys.every(k => k in STRINGS),
    htmlKeys.filter(k => !(k in STRINGS)));
  const allMissing = new Set();
  for (const type of ['emp', 'co', 'edu']) {
    const pp = await makePage({ type, api: { '/home/feed': { ok: true, status: 200, data: { items } },
      '/profile/': { ok: true, status: 200, data: { score: 1 } }, '/company/jobs': { ok: true, status: 200, data: { jobs } } } });
    pp.rec.missingKeys.forEach(k => allMissing.add(k));
  }
  check('G every twT key used at runtime exists in tw_strings.json', allMissing.size === 0, [...allMissing]);
  const homeKeys = Object.keys(STRINGS).filter(k => k.indexOf('home.') === 0);
  check('G home.* strings use no GLOSSARY-forbidden word', !homeKeys.some(k => /فرص|موظف/.test(STRINGS[k])));

  console.log('\nH — landing');
  const L = read('landing.html');
  const visible = L.replace(/<style>[\s\S]*?<\/style>|<script>[\s\S]*?<\/script>|<!--[\s\S]*?-->/g, '');
  check('H one unified header placeholder, no page nav, header CSS loaded',
    (L.match(/data-tw-header/g) || []).length === 1 && !/<nav[\s>]/.test(L) && L.includes('/static/app-header.css'));
  check('H header placeholder has no bottom nav (guest entry page)', !L.includes('data-tw-bottom-nav'));
  const rows = read('docs/GLOSSARY.md').split('\n').filter(r => r.startsWith('| ') && r.split('|').slice(-2)[0].includes('`'));
  const terms = [];
  rows.forEach(r => { const re = /`([^`]+)`/g; let m; while ((m = re.exec(r.split('|').slice(-2)[0]))) terms.push(m[1]); });
  const hits = terms.filter(t => new RegExp(t).test(visible));
  check('H no GLOSSARY-forbidden word on the landing page (incl. «مراجعة» terms)', terms.length >= 8 && hits.length === 0, hits);

  console.log(`\n${passed} passed, ${failed} failed`);
  process.exit(failed ? 1 : 0);
})();
