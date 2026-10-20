/**
 * test_company_profile_page_runtime.js — PR 4.3a company page structure & display.
 * Real code in a Node vm: company.state.js + company.permissions.js + company.api.js +
 * company.render.js + company.posts.js, with the real escaping / URL helpers of tw_shared.js
 * and a small fake DOM. twApi / twAction / twConfirm / twReportDialog are recording stubs.
 *   A  loadData — 404 / 500 → error state (not an empty profile) · retry · success renders
 *   B  About tab — every row from the API, missing data → row hidden · unsafe website = text
 *   C  copy link = /u/{tw_id} (never location.href) · logo through twSafeImageUrl
 *   D  visitor actions through twAction · report → twReportDialog({reportedType:'company'})
 *   E  post delete asks twConfirm (danger) first · cancel → no request · error toast type
 *   F  session from TwAuthSync only — TwCompanyPage.signedIn() follows the snapshot (_jwt() removed — PR 4.3c)
 *   H  PR 4.14 — every twT key in the company JS / tw-schedule.js exists · modal JS has no Arabic literal · no ✕ / ×
 *   G  PR 4.13 — rating stars = DS-ICON star SVGs (real tw-icons.js) · modal markup keys exist in tw_strings.json
 *      · no Arabic text left inside the modals · fake follower avatars (fw-ava) gone
 *
 * Run: node tests/test_company_profile_page_runtime.js
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

// real helpers from tw_shared.js (function text only — no page side effects)
const SHARED = read('tw_shared.js');
function fnSrc(name) {
  const a = SHARED.indexOf('function ' + name + '(');
  const b = SHARED.indexOf('window.' + name + ' = ' + name + ';', a);
  if (a < 0 || b < 0) throw new Error('helper not found: ' + name);
  return SHARED.slice(a, b);
}
const HELPERS = ['twEscAttr', 'twEscHtml', 'twSafeImageUrl', 'twSafeLinkUrl'].map(fnSrc).join('\n');

// ── fake DOM ──────────────────────────────────────────────────────────
function makeDom() {
  const byId = {};
  function classList() {
    const set = new Set();
    return { add: (...c) => c.forEach(x => set.add(x)), remove: (...c) => c.forEach(x => set.delete(x)),
             toggle: (c, on) => { const v = on === undefined ? !set.has(c) : !!on; v ? set.add(c) : set.delete(c); return v; },
             contains: c => set.has(c) };
  }
  function el(tag, id) {
    const attrs = {}, listeners = {};
    const e = {
      tagName: String(tag).toUpperCase(), id: id || '', hidden: false, textContent: '', innerHTML: '',
      className: '', children: [], style: {}, classList: classList(), dataset: {}, disabled: false,
      setAttribute: (k, v) => { attrs[k] = String(v); }, getAttribute: k => (k in attrs ? attrs[k] : null),
      appendChild: c => { e.children.push(c); c.parentNode = e; return c; },
      replaceChild: (n, o) => { const i = e.children.indexOf(o); if (i >= 0) e.children[i] = n; return o; },
      addEventListener: (t, fn) => { (listeners[t] = listeners[t] || []).push(fn); },
      fire: t => (listeners[t] || []).forEach(fn => fn({ preventDefault() {}, target: e })),
      querySelector: () => null, querySelectorAll: () => [],
    };
    Object.defineProperty(e, 'innerHTML', {
      get: () => e._html || '', set: v => { e._html = v; if (v === '') e.children = []; } });
    if (id) byId[id] = e;
    return e;
  }
  const ids = ['coErrTitle', 'coErrSub', 'coRetryBtn', 'coName', 'coDesc', 'coLogo', 'coVerifiedBadge',
    'coLogoBadge', 'coAboutVerifiedRow', 'coTypeBadge', 'coWebsite', 'coWebsiteLink', 'coWebsiteCopyBtn',
    'coHqRow', 'coHqText', 'aboutDesc', 'aboutEmpty', 'visitorActions', 'jobsList', 'coBranchesRow',
    'coBranchesText', 'postsList', 'postsEmpty', 'ratingStarsDisplay', 'ratingSub'];
  ['Type', 'Loc', 'Founded', 'Size', 'Web', 'Email', 'Phone'].forEach(k => { ids.push('about' + k + 'Row', 'about' + k); });
  ids.forEach(i => el('div', i));
  const body = el('body');
  return {
    byId, body,
    document: {
      body, readyState: 'complete',
      getElementById: i => byId[i] || null,
      createElement: t => el(t),
      createTextNode: t => ({ textContent: String(t) }),
      querySelector: () => null, querySelectorAll: () => ({ forEach() {} }),
      addEventListener: () => {},
    },
  };
}

function boot(opts) {
  opts = opts || {};
  const dom = makeDom();
  const calls = { api: [], actions: [], report: [], confirm: [], toast: [], clip: [], rendered: 0, replaced: [] };
  const snap = opts.snap || { isAuthenticated: false, userType: null, userId: null };
  const ctx = {
    console: { log() {}, warn() {}, error() {} }, Object, Number, String, JSON, Array, Set, Math, Date, Promise,
    parseInt, isNaN, encodeURIComponent, URLSearchParams, setTimeout, clearTimeout, setInterval, clearInterval,
    requestAnimationFrame: () => {},
    document: dom.document,
    location: { origin: 'https://tawasolna.com', pathname: '/u/C123', search: '?tab=jobs',
                href: 'https://tawasolna.com/u/C123?tab=jobs&x=1', replace: u => calls.replaced.push(u) },
    navigator: { clipboard: { writeText: t => { calls.clip.push(t); return Promise.resolve(); } } },
    localStorage: { getItem: () => { throw new Error('localStorage read'); }, setItem() {} },
    TwAuthSync: { getSessionSnapshot: () => snap, getToken: () => (snap.isAuthenticated ? 'JWT-from-sync' : '') },
    twT: (k, v) => 'T:' + k + (v ? JSON.stringify(v) : ''),
    twApiMessage: (res, fb) => fb,
    twLoginHref: n => '/login?next=' + encodeURIComponent(n),
    twHomeHref: () => '/home',
    showToast: (m, t) => calls.toast.push([m, t]),
    twApi: (path, o) => { calls.api.push([path, (o && o.method) || 'GET']); return Promise.resolve(opts.api ? opts.api(path, o) : { ok: true, status: 200, data: {} }); },
    twAction: (id, c) => { calls.actions.push([id, c]); if (opts.hideActions && opts.hideActions.includes(id)) return null;
      const b = dom.document.createElement('button'); b._ctx = c; return b; },
    twCanMessage: id => { (calls.canMsg = calls.canMsg || []).push(id);   // server rule (5.0g)
      return Promise.resolve({ can_message: !opts.noMessage, reason: null, ended: false, can_end: false }); },
    twReportDialog: o => calls.report.push(o),
    twConfirm: o => { calls.confirm.push(o); return Promise.resolve(!!opts.confirmAnswer); },
  };
  ctx.window = ctx;
  vm.createContext(ctx);
  vm.runInContext(HELPERS + '\nwindow.twEscAttr=twEscAttr;window.twEscHtml=twEscHtml;window.twSafeImageUrl=twSafeImageUrl;window.twSafeLinkUrl=twSafeLinkUrl;', ctx);
  if (opts.icons) vm.runInContext(read('static/shared/tw-icons.js'), ctx, { filename: 'tw-icons.js' });
  ['state', 'permissions', 'api', 'render', 'posts'].forEach(m =>
    vm.runInContext(read('static/company/company.' + m + '.js'), ctx, { filename: 'company.' + m + '.js' }));
  ctx._companyProfileIdFromRoute = 123;
  return { ctx, dom, calls };
}
const tick = () => new Promise(r => setImmediate(r));

const PROFILE_OK = {
  status: 'success',
  profile: { id: 123, tw_id: 'C123', full_name: 'شركة س', bio: 'نبذة', country: 'الأردن', city: 'عمان',
             website: 'https://acme.example', avatar_url: 'javascript:alert(1)', is_verified: true },
  company: { industry: 'شركة خاصة', founded_year: 2010, company_size: null, contact_email: '', cover_url: null },
  stats: { followers_count: 3 }, permissions: { is_following: false }, viewer_type: 'public-user',
};

(async function main() {
  console.log('\nA — loadData error / success');
  for (const st of [404, 500]) {
    const { ctx, dom, calls } = boot({ api: () => ({ ok: false, status: st, data: null, error: { generalError: { code: 'http' } } }) });
    ctx.loadData(); await tick();
    check(`A1 ${st} → page error state (co-error), not an empty profile`, dom.body.classList.contains('co-error')
      && !dom.body.classList.contains('co-loading') && dom.byId.coName.textContent === '');
    check(`A2 ${st} → title`, dom.byId.coErrTitle.textContent === (st === 404 ? 'T:company.error.not_found' : 'T:company.error.title'),
      dom.byId.coErrTitle.textContent);
    check(`A3 ${st} → retry ${st === 404 ? 'hidden' : 'shown'}`, dom.byId.coRetryBtn.hidden === (st === 404));
    check(`A4 ${st} → request via twApi`, calls.api[0][0] === '/company/profile/123');
  }
  {
    let n = 0;
    const { ctx, dom, calls } = boot({ api: p => (p.indexOf('/company/profile/') === 0 && n++ === 0)
      ? { ok: false, status: 500, data: null, error: { generalError: { code: 'http' } } }
      : { ok: true, status: 200, data: p.indexOf('/company/profile/') === 0 ? PROFILE_OK : {} } });
    ctx.loadData(); await tick();
    dom.byId.coRetryBtn.fire('click'); await tick();
    check('A5 retry button reloads and clears the error', !dom.body.classList.contains('co-error')
      && dom.byId.coName.textContent === 'شركة س' && calls.api.filter(c => c[0] === '/company/profile/123').length === 2);
  }

  console.log('\nB — About tab from API data');
  const { ctx, dom, calls } = boot({ api: p => ({ ok: true, status: 200, data: p.indexOf('/company/profile/') === 0 ? PROFILE_OK : {} }) });
  ctx.loadData(); await tick();
  const row = k => dom.byId['about' + k + 'Row'];
  check('B1 rows with data are shown', !row('Type').hidden && !row('Loc').hidden && !row('Founded').hidden && !row('Web').hidden);
  check('B2 values from API', dom.byId.aboutType.textContent === 'شركة خاصة' && dom.byId.aboutLoc.textContent === 'الأردن، عمان'
    && dom.byId.aboutFounded.textContent === '2010');
  check('B3 missing data → row hidden (no «—»)', row('Size').hidden && row('Email').hidden && row('Phone').hidden);
  const link = dom.byId.aboutWeb.children[0];
  check('B4 safe website → <a> with rel noopener', link && link.tagName === 'A' && link.href === 'https://acme.example'
    && link.rel === 'noopener noreferrer');
  check('B5 verified card shown only when is_verified', dom.byId.coAboutVerifiedRow.hidden === false);
  {
    const b = boot();
    b.ctx.companyState.profile = { id: 1, website: 'javascript:alert(1)' };
    b.ctx.companyState.company = {};
    b.ctx.renderAbout();
    check('B6 unsafe website → plain text, no link', b.dom.byId.aboutWeb.children.length === 0
      && b.dom.byId.aboutWeb.textContent === 'javascript:alert(1)');
    b.ctx.companyState.profile = { id: 1 };
    b.ctx.renderAbout();
    check('B7 no data at all → every row hidden + empty note', ['Type', 'Loc', 'Founded', 'Size', 'Web', 'Email', 'Phone']
      .every(k => b.dom.byId['about' + k + 'Row'].hidden) && b.dom.byId.aboutEmpty.hidden === false);
  }

  console.log('\nC — public link + images');
  dom.byId.coWebsiteCopyBtn.onclick(); await tick();
  check('C1 copy link = /u/{tw_id} (not location.href)', calls.clip[0] === 'https://tawasolna.com/u/C123', calls.clip[0]);
  check('C2 shown link = /u/{tw_id}', dom.byId.coWebsiteLink.href === 'https://tawasolna.com/u/C123');
  check('C3 unsafe logo URL → no <img>', dom.byId.coLogo.children.length === 0);

  console.log('\nD — visitor actions (Actions Registry)');
  const ids = calls.actions.map(a => a[0]);
  check('D1 follow / message / share / report via twAction', ['follow', 'message', 'share', 'report'].every(i => ids.includes(i)), ids.join());
  check('D2 viewer mode from the API view (public-user → registered)', calls.actions.every(a => a[1].mode === 'registered'));
  const rep = calls.actions.find(a => a[0] === 'report')[1];
  rep.onClick();
  check('D3 report → twReportDialog (company)', calls.report.length === 1 && calls.report[0].reportedType === 'company'
    && calls.report[0].reportedId === 123);
  check('D4 follow button keeps id followBtn (company.main.js state updates)',
    dom.byId.visitorActions.children.some(b => b.id === 'followBtn'));
  {
    const m = calls.actions.find(a => a[0] === 'message');
    check('D4b «مراسلة» from the server rule: twCanMessage(company id) → canMessage', (calls.canMsg || []).includes(123)
      && !!m && m[1].canMessage === true);
  }
  {
    const b = boot({ hideActions: ['follow', 'message', 'share', 'report'] });
    b.ctx.companyState.profile = { id: 1 };
    b.ctx.renderVisitorActions();
    check('D5 registry hides all → row hidden', b.dom.byId.visitorActions.hidden === true);
  }

  console.log('\nE — post delete');
  const OWNER = { isAuthenticated: true, userType: 'co', userId: 123 };
  for (const ans of [false, true]) {
    const b = boot({ snap: OWNER, confirmAnswer: ans,
      api: (p, o) => (o && o.method === 'DELETE') ? { ok: false, status: 500, data: null, error: {} } : { ok: true, status: 200, data: {} } });
    b.ctx.companyState.permissions = { can_edit: true };
    b.ctx.deletePost(9); await tick(); await tick();
    const del = b.calls.api.filter(c => c[1] === 'DELETE');
    check(`E1 confirm (${ans ? 'yes' : 'no'}) asked first, danger`, b.calls.confirm.length === 1 && b.calls.confirm[0].danger === true);
    check(`E2 ${ans ? 'confirmed → one DELETE' : 'cancelled → no request'}`, del.length === (ans ? 1 : 0));
    if (ans) check('E3 failed delete → error toast (not success)', b.calls.toast.length && b.calls.toast[0][1] === 'error');
  }

  console.log('\nF — session source');
  {
    const b = boot({ snap: OWNER });
    check('F1 TwCompanyPage.signedIn() = snapshot.isAuthenticated; _jwt() gone (PR 4.3c)',
      b.ctx.TwCompanyPage.signedIn() === true && typeof b.ctx._jwt === 'undefined'
      && boot({ snap: { isAuthenticated: false } }).ctx.TwCompanyPage.signedIn() === false);
    b.ctx._companyProfileIdFromRoute = null;
    b.ctx.location.search = '';
    b.ctx.loadData(); await tick();
    check('F2 no id → session owner id from TwAuthSync', b.calls.api[0] && b.calls.api[0][0] === '/company/profile/123');
  }

  console.log('\nG — PR 4.13: rating stars (DS-ICON) + modal strings');
  {
    const b = boot({ icons: true });
    const star = on => b.ctx.twIcon('star', { size: 'lg', filled: on, className: on ? 'co-star co-star--on' : 'co-star' });
    b.ctx.companyState.stats = { rating_avg: 3.6, rating_count: 4 };
    b.ctx.renderRating();
    const html = b.dom.byId.ratingStarsDisplay.innerHTML;
    check('G1 avg 3.6 → 4 filled + 1 outline star SVGs (twIcon), no glyph',
      html === star(true).repeat(4) + star(false) && !/[★☆⭐]/.test(html), html.slice(0, 80));
    check('G2 summary line through twT (count < 10 → few form)',
      b.dom.byId.ratingSub.textContent === 'T:company.rating.summary_few{"count":4}', b.dom.byId.ratingSub.textContent);
    b.ctx.companyState.stats = { rating_avg: null, rating_count: 0 };
    b.ctx.renderRating();
    check('G3 no rating → 5 outline stars + «none» key', b.dom.byId.ratingStarsDisplay.innerHTML === star(false).repeat(5)
      && b.dom.byId.ratingSub.textContent === 'T:company.rating.none');
    check('G4 the page JS has no star glyph left', ['render', 'main', 'jobs'].every(m =>
      !/[★☆⭐]/.test(read('static/company/company.' + m + '.js'))));

    const page = read('company-profile.html');
    const STR = JSON.parse(read('tw_strings.json')).ar;
    const keys = [...page.matchAll(/data-tw-t(?:-label|-placeholder)?="([^"]+)"/g)].map(m => m[1]);
    const missing = keys.filter(k => !(k in STR));
    check('G5 every data-tw-t key on the page exists in tw_strings.json', keys.length > 50 && !missing.length, missing.join());
    // modal markup = everything after the edit overlay; text nodes only (attributes / comments excluded)
    const modals = page.slice(page.indexOf('id="editOverlay"')).replace(/<!--[\s\S]*?-->/g, '');
    const arText = [...modals.matchAll(/>([^<]*)</g)].map(m => m[1]).filter(t => /[\u0600-\u06FF]/.test(t));
    const arAttr = [...modals.matchAll(/(?:placeholder|aria-label|title)="([^"]*[\u0600-\u06FF][^"]*)"/g)].map(m => m[1]);
    check('G6 no hard-coded Arabic text / placeholder / aria-label inside the modals', !arText.length && !arAttr.length,
      arText.concat(arAttr).join(' | '));
    check('G7 fake follower avatars removed (no fw-ava markup or CSS)',
      !page.includes('fw-ava') && !read('static/company/company.css').includes('fw-ava'));
  }

  console.log('\nH — PR 4.14: modal JS text through twT');
  {
    const STR = JSON.parse(read('tw_strings.json')).ar;
    const main = read('static/company/company.main.js');
    const used = [main, read('static/shared/tw-schedule.js')].flatMap(src =>
      [...src.matchAll(/twT\('([a-z0-9_.]+[a-z0-9_])'/g)].map(m => m[1]));
    const missing = [...new Set(used)].filter(k => !(k in STR));
    check('H1 every twT key in company.main.js + tw-schedule.js exists in tw_strings.json',
      used.length > 150 && !missing.length, missing.join());
    // the JS that builds the edit / applicants / notes / candidates modals: no Arabic string literal
    const fnBody = name => {
      const i = main.indexOf('function ' + name + '(');
      const j = main.indexOf('\n  function ', i + 10);
      return i < 0 ? null : main.slice(i, j < 0 ? undefined : j);
    };
    const FNS = ['_addBranchRow', 'openEditModal', 'saveEdit', '_loadApplicants', '_renderApplicants',
      '_execPromote', '_onSaveToTalentBank', '_renderPanelNotes', '_submitNote', '_initClassifyFloat',
      '_execClassify', '_reRenderCardFoot', '_savedShellHTML', '_doFetchSavedPage', '_savedEmptyHTML',
      '_jobChipSectionsHTML', '_savedCardHTML', '_showJobChipPop', '_handlePanelSave', '_suggItemHTML', '_saveSuggestion'];
    const bad = FNS.filter(n => {
      const body = fnBody(n);
      if (body === null) return true;
      const code = body.split('\n').filter(l => !/^\s*\/\//.test(l)).map(l => l.replace(/\s\/\/ .*$/, '')).join('\n');
      return [...code.matchAll(/'((?:[^'\\\n]|\\.)*)'/g)].some(m => /[\u0600-\u06FF]/.test(m[1]));
    });
    check('H2 modal-building functions have no Arabic string literal (twT keys)', !bad.length, bad.join());
    check('H3 no ✕ / × glyph left in company.main.js (DS-ICON close + aria-label)', !/[✕×]/.test(main));
  }

  console.log('\n' + passed + ' passed, ' + failed + ' failed');
  process.exit(failed ? 1 : 0);
})().catch(e => { console.error(e); process.exit(1); });
