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
 *   I  task 8.6a — hidden salary → no salary chip · ?f= opens its filter (allowlist, else all) ·
 *      sidebar links → the filter / the post-job deep link
 *   J  task 8.6b-2 — post item → TwPostCard.html (stub here — the real card + comments in the feed:
 *      tests/test_post_card_runtime.js M) · controller bound once · page loads the shared card files
 *   K  task 8.6d-2 — «عرض المزيد»: cursor request · append (no clear) · one card per (type, id) · loading
 *      state + no double click · end → button gone · every filter to the end · filter change mid-flight ·
 *      409 feed_reset / 422 invalid_cursor → top of the same filter + toast · other error → retry, cards stay ·
 *      remember merges · clamp on the new cards only · controller not bound again
 *   L  task 8.6d-2 — the REAL TwPostCard.trackViews called after every append: one live observer,
 *      each post viewed once
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
const SHARED_HREFS = fnSrc('twAccountHref') + fnSrc('twTalentBankHref') + fnSrc('twPostJobHref');

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
      toggle: (c, force) => { const on = force === undefined ? !self.classList.contains(c) : !!force; on ? self.classList.add(c) : self.classList.remove(c); return on; },
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
  // TwPostCard.html string → one element (the stub card below; real markup = test_post_card_runtime.js M)
  get firstElementChild() {
    if (this.children[0]) return this.children[0];
    if (!this.rawHtml) return null;
    const e = new El('div'); e.className = 'post-card'; e.rawHtml = this.rawHtml; return e;
  }
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
  const more = mk('div', { id: 'hwMore', class: 'hw-more hidden' });
  mk('button', { id: 'hwMoreBtn', class: 'hw-retry' }, more); mk('p', { id: 'hwMoreErr', class: 'hw-more-err hidden' }, more);
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
  const rec = { api: [], missingKeys: new Set(), avatars: [], hydrated: 0, postCards: [], binds: [], after: 0,
    clamps: [], toasts: [], commentsOpts: null };
  const api = opts.api || {};
  const ctx = {
    document, console: { log() {}, warn() {}, error: console.error }, Promise, Date, Math, Number, String,
    Array, Boolean, Object, JSON, AbortController, encodeURIComponent, parseInt, URLSearchParams,
    location: { href: '/home', pathname: '/home', search: opts.search || '' },
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
    showToast: (msg, type) => rec.toasts.push({ msg, type }),
    requestAnimationFrame: fn => fn(),
    TwPostCard: {
      html: (post, o) => { rec.postCards.push({ post, o }); return '<div class="post-card" data-post-id="' + post.id + '"></div>'; },
      create: () => ({ bind: el => rec.binds.push(el), trackViews: () => { rec.after++; } }),
      initClamps: el => rec.clamps.push(el),
    },
    TwPostComments: { create: o => { rec.commentsOpts = o; return { build() {}, load() {} }; } },
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
    SCRIPTS.length === 9 && SCRIPTS[SCRIPTS.length - 1] === 'static/home/home.main.js', SCRIPTS);
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
  check('F job logo via twAvatarEl (company = co) · post author via TwPostCard', p.rec.avatars.length === 1
    && p.rec.avatars[0].entity.user_type === 'co' && p.rec.avatars[0].entity.avatar_url === 'javascript:alert(1)'
    && p.rec.postCards.length === 1 && p.rec.postCards[0].o.authorName === 'Sara', p.rec.avatars);
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

  console.log('\nI — task 8.6a');
  const jobItem = extra => Object.assign({ type: 'opportunity', id: 9, title: 'T', company_name: 'Acme', created_at: new Date().toISOString() }, extra);
  p = await makePage({ api: { '/home/feed': { ok: true, status: 200, data: { items: [
    jobItem({ salary_hidden: true, salary_min: 500, salary_max: 900, currency: 'JOD' }),
    jobItem({ id: 10, salary_min: 400, salary_max: 600, currency: 'JOD', accepts_all_professions: true }),
  ] } } } });
  const cards = $(p, 'hwFeed').children;
  check('I hidden salary → no salary chip (even if numbers slipped through)', cards.length === 2
    && !cards[0].querySelectorAll('.hw-chip').some(c => c.classList.contains('g')) && !cards[0].textContent.includes('500'), cards[0] && cards[0].textContent);
  check('I normal salary → chip shown', cards[1].querySelectorAll('.hw-chip').some(c => c.textContent.includes('400–600')));
  check('I accepts_all_professions → «all professions» chip', cards[1].textContent.includes(STRINGS['home.card.all_professions'])
    && !cards[0].textContent.includes(STRINGS['home.card.all_professions']));
  const activeTab = pp => pp.body.querySelectorAll('.hw-ft').filter(b => b.classList.contains('active')).map(b => b.getAttribute('data-filter'));
  p = await makePage({ search: '?f=news', api: { '/home/feed': FEED_OK } });
  check('I ?f=news → news filter requested + its tab active', p.rec.api.indexOf('/home/feed?filter=news&limit=30') !== -1
    && JSON.stringify(activeTab(p)) === '["news"]', [p.rec.api, activeTab(p)]);
  p = await makePage({ search: '?f=companies', api: { '/home/feed': FEED_OK } });
  check('I ?f=<not allowed> → all', p.rec.api.indexOf('/home/feed?filter=all&limit=30') !== -1
    && JSON.stringify(activeTab(p)) === '["all"]', [p.rec.api, activeTab(p)]);
  p = await makePage({ api: { '/home/feed': FEED_OK } });
  check('I emp links → /home?f=opportunities + /home?f=news', linkHrefs(p).indexOf('/home?f=opportunities') !== -1
    && linkHrefs(p).indexOf('/home?f=news') !== -1, linkHrefs(p));
  p = await makePage({ type: 'co', twId: 'C55', api: { '/home/feed': FEED_OK } });
  check('I co «post job» → /u/{tw_id}?post_job=1', linkHrefs(p).indexOf('/u/C55?post_job=1') !== -1, linkHrefs(p));

  console.log('\nJ — task 8.6b-2: posts = TwPostCard');
  p = await makePage({ api: { '/home/feed': { ok: true, status: 200, data: { items } } } });
  const pcard = p.rec.postCards[0];
  check('J post item → TwPostCard.html with the feed author (co · /u/{tw_id} · no edit)', p.rec.postCards.length === 1
    && pcard.post.id === 1 && pcard.o.authorName === 'Sara' && pcard.o.avatarUrl === '' && pcard.o.authorType === 'co'
    && pcard.o.authorHref === '/u/U2' && pcard.o.canEdit === false, pcard && pcard.o);
  const pel = $(p, 'hwFeed').children[1];
  check('J the feed holds the card element (no old hw-card post markup)', pel && pel.classList.contains('post-card')
    && !$(p, 'hwFeed').querySelectorAll('.hw-phead').length);
  check('J controller bound once to #hwFeed · clamp / views after the render', p.rec.binds.length === 1
    && p.rec.binds[0] === $(p, 'hwFeed') && p.rec.after === 1, [p.rec.binds.length, p.rec.after]);
  p.body.querySelectorAll('.hw-ft')[2].click(); await flush();
  p.body.querySelectorAll('.hw-ft')[0].click(); await flush();
  check('J filter switches re-render, the controller is not bound again', p.rec.binds.length === 1 && p.rec.after === 3, [p.rec.binds.length, p.rec.after]);
  const sharedOrder = ['tw-options-data.js', 'tw-post-card.js', 'tw-post-comments.js', 'home/home.utils.js']
    .map(f => HTML.indexOf('/static/' + (f.indexOf('/') < 0 ? 'shared/' : '') + f));
  const cssOrder = ['shared/tw-card.css', 'shared/tw-post-comments.css', 'home-v2.css'].map(f => HTML.indexOf('/static/' + f));
  check('J load order: tw-card.css → tw-post-comments.css → home-v2.css · options → card → comments → home', sharedOrder.every((x, i) => x > 0 && (i === 0 || x > sharedOrder[i - 1]))
    && cssOrder.every((x, i) => x > 0 && (i === 0 || x > cssOrder[i - 1])), [sharedOrder, cssOrder]);

  console.log('\nK — task 8.6d-2: «عرض المزيد»');
  const qp = path => new URLSearchParams(path.split('?')[1] || '');
  const post = id => ({ type: 'post', id, body: 'b' + id, author_name: 'Co' + id, author_tw_id: 'C' + id });
  const job = id => jobItem({ id, title: 'J' + id });
  const news = id => ({ type: 'news', id, title: 'N' + id, category: 'general', body: 'x' });
  const ok = (items, next) => ({ ok: true, status: 200, data: { items, next_cursor: next } });
  const fail = (status, code) => ({ ok: false, status, data: null, error: { fieldErrors: [], generalError: { code, message: 'x' } } });
  // pages[filter][cursor||''] → response (function = deferred / dynamic)
  const pagedApi = pages => ({ '/home/feed': path => { const q = qp(path); const r = pages[q.get('filter')][q.get('cursor') || '']; return typeof r === 'function' ? r() : r; } });
  const feedReqs = pp => pp.rec.api.filter(a => a.indexOf('/home/feed') === 0);
  const moreBtn = pp => $(pp, 'hwMoreBtn');
  const moreShown = pp => !hidden($(pp, 'hwMore'));

  let release;
  const PAGES = { all: {
    '':   ok([job(1), post(1), news(1)], 'c1'),
    'c1': () => new Promise(r => { release = () => r(ok([post(2), job(1), job(2)], 'c2')); }),
    'c2': ok([news(2)], null),
  } };
  p = await makePage({ api: pagedApi(PAGES) });
  const feedK = $(p, 'hwFeed');
  check('K first page: 3 cards + button (next_cursor) with its twT text', feedK.children.length === 3 && moreShown(p)
    && moreBtn(p).textContent === STRINGS['home.more.load'] && !moreBtn(p).disabled && hidden($(p, 'hwMoreErr')));
  moreBtn(p).click(); moreBtn(p).click(); await flush();
  check('K loading: button disabled + loading text · a second click sends nothing',
    moreBtn(p).disabled && moreBtn(p).textContent === STRINGS['common.loading'] && feedReqs(p).length === 2, feedReqs(p));
  check('K request = same filter + limit + cursor=next_cursor (twApi)', feedReqs(p)[1] === '/home/feed?filter=all&limit=30&cursor=c1', feedReqs(p));
  const firstCards = feedK.children.slice();
  release(); await flush();
  check('K page 2 appended under the old cards (not cleared) · the repeated job skipped',
    feedK.children.length === 5 && firstCards.every((c, i) => feedK.children[i] === c), feedK.children.length);
  check('K remember merges: page-1 and page-2 posts both known to comments (mentions / share)',
    !!p.rec.commentsOpts.postOwner(1) && p.rec.commentsOpts.postOwner(2).full_name === 'Co2');
  const postEls = feedK.children.filter(c => c.classList.contains('post-card'));
  check('K clamp ran once per post card, on the new card only (never the whole feed again)', p.rec.clamps.length === 2
    && p.rec.clamps[0] === postEls[0] && p.rec.clamps[1] === postEls[1] && p.rec.clamps.indexOf(feedK) < 0, p.rec.clamps.length);
  check('K one trackViews per render · controller still bound once to #hwFeed (comments / report / block / appreciate / save delegate there)',
    p.rec.after === 2 && p.rec.binds.length === 1 && p.rec.binds[0] === feedK && postEls.every(c => c.parentNode === feedK), [p.rec.after, p.rec.binds.length]);
  check('K button back to idle with a next cursor', moreShown(p) && !moreBtn(p).disabled && moreBtn(p).textContent === STRINGS['home.more.load']);
  moreBtn(p).click(); await flush();
  check('K last page (next_cursor null) → button gone, no new message, feed kept', feedK.children.length === 6 && !moreShown(p)
    && hidden($(p, 'hwEmpty')) && hidden($(p, 'hwError')) && hidden($(p, 'hwMoreErr')) && feedReqs(p)[2] === '/home/feed?filter=all&limit=30&cursor=c2');
  moreBtn(p).click(); await flush();
  check('K no cursor → click sends nothing', feedReqs(p).length === 3);

  // every filter to the end: each item exactly once, then no button
  const mkFor = { all: i => (i % 2 ? post(i) : job(i)), opportunities: job, posts: post, news };
  for (const f of ['all', 'opportunities', 'posts', 'news']) {
    const pg = {}; pg[f] = { '': ok([mkFor[f](1), mkFor[f](2)], f + '1'), [f + '1']: ok([mkFor[f](2), mkFor[f](3), mkFor[f](4)], f + '2'), [f + '2']: ok([mkFor[f](5)], null) };
    const pp = await makePage({ search: '?f=' + f, api: pagedApi(pg) });
    let clicks = 0;
    while (moreShown(pp) && clicks < 5) { moreBtn(pp).click(); await flush(); clicks++; }
    const fc = $(pp, 'hwFeed').children;
    const keys = fc.map(c => c.textContent + '|' + (c.rawHtml || ''));
    check(`K ${f}: clicked to the end → 5 items, each once, button gone`, clicks === 2 && fc.length === 5
      && new Set(keys).size === 5 && !moreShown(pp) && feedReqs(pp).every(r => qp(r).get('filter') === f), [clicks, fc.length]);
  }

  // filter change while a page is loading → no mixing
  let releaseAll;
  p = await makePage({ api: pagedApi({
    all:   { '': ok([job(1)], 'a1'), a1: () => new Promise(r => { releaseAll = () => r(ok([job(50), job(51)], 'a2')); }) },
    posts: { '': ok([post(7)], null) },
  }) });
  moreBtn(p).click(); await flush();
  p.body.querySelectorAll('.hw-ft')[2].click(); await flush();
  releaseAll(); await flush();
  const fx = $(p, 'hwFeed').children;
  check('K filter change mid-load: the old page is dropped, only the new filter\'s items, its own button state',
    fx.length === 1 && fx[0].classList.contains('post-card') && !moreShown(p) && p.ctx.Home.state.nextCursor === null
    && !p.ctx.Home.state.loadingMore, [fx.length, p.ctx.Home.state.nextCursor]);

  // 409 feed_reset / 422 invalid_cursor → the same filter from the top + toast
  for (const [st, code] of [[409, 'feed_reset'], [422, 'invalid_cursor']]) {
    let firsts = 0;
    p = await makePage({ search: '?f=news', api: pagedApi({ news: { '': () => ok([news(++firsts)], 'n1'), n1: fail(st, code) } }) });
    moreBtn(p).click(); await flush();
    const fr = feedReqs(p);
    check(`K ${st} ${code} → toast (twT) + reload of the same filter from the top`, p.rec.toasts.length === 1
      && p.rec.toasts[0].msg === STRINGS['home.more.reset'] && p.rec.toasts[0].type === 'info'
      && fr.length === 3 && fr[2] === '/home/feed?filter=news&limit=30' && firsts === 2
      && $(p, 'hwFeed').children.length === 1 && $(p, 'hwFeed').textContent.includes('N2') && moreShown(p), [p.rec.toasts, fr]);
  }

  // any other error → message by the button + retry, the cards stay
  let tries = 0;
  p = await makePage({ api: pagedApi({ all: { '': ok([job(1), job(2)], 'x1'),
    x1: () => (++tries === 1 ? fail(500, 'server_error') : (tries === 2 ? fail(422, 'validation_error') : ok([job(3)], null))) } }) });
  moreBtn(p).click(); await flush();
  check('K other error → small message + retry button, cards stay, no reload / toast', !hidden($(p, 'hwMoreErr'))
    && moreBtn(p).textContent === STRINGS['home.retry'] && !moreBtn(p).disabled && $(p, 'hwFeed').children.length === 2
    && p.rec.toasts.length === 0 && feedReqs(p).length === 2);
  moreBtn(p).click(); await flush();
  check('K 422 with another code is not a reset (still the retry state)', !hidden($(p, 'hwMoreErr')) && p.rec.toasts.length === 0
    && feedReqs(p).length === 3);
  moreBtn(p).click(); await flush();
  check('K retry with the same cursor → page appended, message gone, end → no button', $(p, 'hwFeed').children.length === 3
    && hidden($(p, 'hwMoreErr')) && !moreShown(p) && feedReqs(p).slice(1).every(r => qp(r).get('cursor') === 'x1'));
  check('K new strings: no GLOSSARY-forbidden word', ['home.more.load', 'home.more.error', 'home.more.reset'].every(k => k in STRINGS && !/فرص/.test(STRINGS[k])));

  console.log('\nL — task 8.6d-2: real TwPostCard.trackViews after appends');
  {
    const observers = [], timers = [], views = [];
    class FakeIO { constructor(cb) { this.cb = cb; this.targets = []; this.live = true; observers.push(this); }
      observe(t) { this.targets.push(t); } disconnect() { this.live = false; this.targets = []; } }
    const lctx = { window: null, IntersectionObserver: FakeIO, console,
      setTimeout: fn => { timers.push(fn); return timers.length; }, clearTimeout: () => {},
      twApi: (path, o) => { views.push(path); return Promise.resolve({ ok: true, data: { status: 'success', recorded: false } }); },
      document: { querySelector: () => null } };
    lctx.window = lctx; vm.createContext(lctx);
    vm.runInContext(read('static/shared/tw-post-card.js'), lctx);
    const ctl = lctx.TwPostCard.create({ signedIn: () => true, paths: { view: id => '/v/' + id } });
    const cards = [1, 2].map(i => ({ dataset: { postId: String(i) } }));
    const box = { querySelectorAll: () => cards.slice() };
    const live = () => observers.filter(o => o.live);
    const see = () => { const o = live()[0]; o.cb(o.targets.map(t => ({ target: t, isIntersecting: true }))); };
    ctl.trackViews(box); see();                         // page 1 visible, dwell timers running
    cards.push({ dataset: { postId: '3' } });
    ctl.trackViews(box); see();                         // append → trackViews again before the timers fire
    timers.splice(0).forEach(fn => fn()); await flush();
    ctl.trackViews(box); see(); timers.splice(0).forEach(fn => fn()); await flush();   // another append round
    check('L one live observer after every append (the previous one disconnected)', live().length === 1 && observers.length === 3);
    check('L each post viewed exactly once across appends', JSON.stringify(views.slice().sort()) === '["/v/1","/v/2","/v/3"]', views);
  }

  console.log(`\n${passed} passed, ${failed} failed`);
  process.exit(failed ? 1 : 0);
})();
