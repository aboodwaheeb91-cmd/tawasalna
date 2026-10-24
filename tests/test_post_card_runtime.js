/**
 * test_post_card_runtime.js — task U.2: TwPostCard (static/shared/tw-post-card.js) renders the
 * company page post card exactly as the pre-U.2 code did (golden = tests/fixtures/
 * legacy_company_post_card.js, a frozen copy). Real code in a Node vm with the real
 * escaping / URL helpers of tw_shared.js.
 *   A  owner · visitor · logo · no logo · unsafe logo · comments off · active states · long text
 *      → TwPostCard.html === legacy _postCardHtml (byte for byte)
 *   B  HTML / script in body · tags · name · id → escaped (no raw tag reaches the markup)
 *   C  button re-render (company.posts.js) = TwPostCard.apprButtonInner / saveButtonInner = legacy
 *   D  company.render.js renderPosts uses TwPostCard (owner sees ⋯, visitor does not)
 *   — task U.2b: behaviour on the real markup (tests/fixtures/post_card_dom.js) —
 *   E  appreciate: toggle · success · rollback on failure / 403 · two fast clicks = one request
 *   F  save: same queue + rollback · guest → toast, no request
 *   G  ⋯ menu: owner only · open / outside-click close · edit / delete callbacks (int id)
 *   H  views: sent once per post after the dwell · guest visitor key · count updated
 *   I  share: navigator.share → clipboard → textarea fallback, same text as before
 *   J  company.posts.js wires the page parts into TwPostCard.create (paths · session · share · callbacks)
 *   K  tw-card.css = the old POST CARDS section (frozen fixture) · nothing left in company.css
 *
 * Run: node tests/test_post_card_runtime.js
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

function fnText(src, name) {
  const i = src.indexOf('function ' + name + '(');
  let depth = 0, j = src.indexOf('{', i);
  for (; j < src.length; j++) {
    if (src[j] === '{') depth++;
    else if (src[j] === '}' && --depth === 0) break;
  }
  return src.slice(i, j + 1);
}
const SHARED = read('tw_shared.js');
const HELPERS = ['twEscAttr', 'twSafeImageUrl'].map(n => fnText(SHARED, n)).join('\n') + '\nvar twEscHtml = twEscAttr;';

const NOW = Date.parse('2026-10-24T12:00:00Z');
function makeCtx() {
  const ctx = { console, Number, String, Math, isNaN, parseFloat };
  ctx.window = ctx;
  vm.createContext(ctx);
  vm.runInContext('Date.now = function () { return ' + NOW + '; };', ctx);
  vm.runInContext(HELPERS + '\nwindow.twEscAttr=twEscAttr;window.twEscHtml=twEscHtml;window.twSafeImageUrl=twSafeImageUrl;', ctx);
  vm.runInContext(read('static/shared/tw-options-data.js'), ctx, { filename: 'tw-options-data.js' });
  vm.runInContext(read('static/shared/tw-post-card.js'), ctx, { filename: 'tw-post-card.js' });
  vm.runInContext(read('tests/fixtures/legacy_company_post_card.js')
    + '\nwindow._legacyCard = _postCardHtml; window._legacyAppr = _renderAppreciationButton; window._legacySave = _renderSaveButton;',
    ctx, { filename: 'legacy_company_post_card.js' });
  // legacy code reads _esc / _escAttr from company.render.js scope
  vm.runInContext('var _esc = twEscHtml, _escAttr = twEscAttr;', ctx);
  return ctx;
}

const ago = s => new Date(NOW - s * 1000).toISOString();
const BASE = { id: 7, body: 'منشور قصير', tags: [], theme_color: 'teal', created_at: ago(120),
  views_count: 3, appreciations_count: 0, viewer_appreciated: false, comments_enabled: true,
  comments_count: 0, viewer_saved: false };
const XSS = '<script>alert(1)</script><img src=x onerror=alert(2)>"\'&';

const CASES = [
  ['owner + logo',          { can_edit: true },  { full_name: 'شركة النور', avatar_url: 'https://cdn.x/logo.png' }, {}],
  ['visitor + logo',        { can_edit: false }, { full_name: 'شركة النور', avatar_url: 'https://cdn.x/logo.png' }, {}],
  ['visitor, no logo',      { can_edit: false }, { full_name: 'شركة النور', avatar_url: '' }, {}],
  ['unsafe logo → initial', { can_edit: false }, { full_name: 'شركة', avatar_url: 'javascript:alert(1)' }, {}],
  ['no profile name',       null,                { full_name: '', avatar_url: null }, {}],
  ['active + counts + tags + color', { can_edit: true }, { full_name: 'ش', avatar_url: '/static/x.png' },
    { viewer_appreciated: 'true', appreciations_count: 12, viewer_saved: 1, comments_count: 4,
      tags: ['توظيف', 'فعالية'], theme_color: 'purple', views_count: 1500, created_at: ago(90000) }],
  ['comments off + unknown color + old date', { can_edit: false }, { full_name: 'ش', avatar_url: '' },
    { comments_enabled: false, theme_color: 'nope', created_at: '2025-01-01T00:00:00Z', views_count: 2000 }],
  ['long text',             { can_edit: false }, { full_name: 'ش', avatar_url: '' }, { body: 'كلمة '.repeat(400) }],
  ['HTML / script everywhere', { can_edit: true }, { full_name: XSS, avatar_url: 'https://x/a.png?"><b>' },
    { id: '9"><b>', body: XSS, tags: [XSS] }],
];

console.log('\nA/B — TwPostCard.html === legacy _postCardHtml');
for (const [name, perms, profile, extra] of CASES) {
  const ctx = makeCtx();
  const post = Object.assign({}, BASE, extra);
  ctx.companyState = { profile: profile, permissions: perms };
  const legacy = ctx._legacyCard(post);
  const now = ctx.TwPostCard.html(post, {
    authorName: profile.full_name || 'الشركة', avatarUrl: profile.avatar_url,
    canEdit: !!(perms && perms.can_edit) });
  check(name + ' — identical', now === legacy, now === legacy ? '' : '\n    new: ' + now.slice(0, 300) + '\n    old: ' + legacy.slice(0, 300));
  check(name + ' — ⋯ only for owner', now.includes('pc-dots-btn') === !!(perms && perms.can_edit));
  if (name.startsWith('HTML')) {
    check('script tag escaped', !now.includes('<script>') && now.includes('&lt;script&gt;'));
    check('img onerror not a tag', !now.includes('<img src=x'));
    check('id escaped in attributes', !now.includes('data-post-id="9"><b>') && now.includes('9&quot;&gt;&lt;b&gt;'));
  }
}

console.log('\nC — button re-render');
{
  const ctx = makeCtx();
  for (const [active, count] of [[true, 0], [true, 5], [false, 0], [false, 3]]) {
    const b = { classList: { add() {}, remove() {} }, dataset: {} };
    ctx._legacyAppr(b, active, count);
    check('appr ' + active + '/' + count, ctx.TwPostCard.apprButtonInner(active, count) === b.innerHTML);
  }
  for (const active of [true, false]) {
    const b = { classList: { add() {}, remove() {} }, dataset: {} };
    ctx._legacySave(b, active);
    check('save ' + active, ctx.TwPostCard.saveButtonInner(active) === b.innerHTML);
  }
}

console.log('\nD — company.render.js renders through TwPostCard');
{
  const ctx = makeCtx();
  const list = { innerHTML: '' }, empty = { style: {} };
  Object.assign(ctx, {
    twT: k => k, twIcon: Object.assign(() => '', { hydrate() {} }), requestAnimationFrame() {},
    document: { getElementById: id => (id === 'postsList' ? list : id === 'postsEmpty' ? empty : null),
                querySelectorAll: () => [], addEventListener() {} },
    setInterval() {}, setTimeout() {},
  });
  let calls = 0;
  const orig = ctx.TwPostCard.html;
  ctx.TwPostCard.html = function () { calls++; return orig.apply(this, arguments); };
  delete ctx._postCardHtml;   // the legacy fixture's global — render.js must not re-expose one
  vm.runInContext(read('static/company/company.render.js'), ctx, { filename: 'company.render.js' });
  check('_postCardHtml not exposed', ctx._postCardHtml === undefined);
  ctx.companyState = { profile: { full_name: 'شركة', avatar_url: '' }, permissions: { can_edit: true } };
  ctx.renderPosts([BASE, Object.assign({}, BASE, { id: 8 })]);
  check('TwPostCard.html called per post', calls === 2, calls);
  check('owner list has ⋯', (list.innerHTML.match(/pc-dots-btn/g) || []).length === 2);
  ctx.companyState.permissions = { can_edit: false };
  ctx.renderPosts([BASE]);
  check('visitor list has no ⋯', !list.innerHTML.includes('pc-dots-btn') && list.innerHTML.includes('pc-btn--appr'));
}

// ── U.2b — behaviour on the real markup ─────────────────────────────────────
const { makeDocument } = require('./fixtures/post_card_dom.js');
const tick = () => new Promise(r => setImmediate(r));
const ok200 = data => ({ ok: true, status: 200, data: data });
const fail = st => ({ ok: false, status: st, data: null, error: {} });

function bootCards(o) {
  o = o || {};
  const ctx = makeCtx();
  const doc = makeDocument();
  const calls = { api: [], toast: [], edit: [], del: [], build: [], load: [], ls: {}, timers: [], observed: [] };
  const pending = [];
  Object.assign(ctx, {
    document: doc, setTimeout: fn => { calls.timers.push(fn); return calls.timers.length; }, clearTimeout() {},
    showToast: (m, t) => calls.toast.push([m, t]),
    twApiMessage: (res, fb) => fb,
    twApi: (path, op) => new Promise(res => { calls.api.push({ path, method: op.method, body: op.body }); pending.push(res); }),
    localStorage: { getItem: k => calls.ls[k] || null, setItem: (k, v) => { calls.ls[k] = v; } },
    navigator: o.navigator || {},
    IntersectionObserver: function (cb) { calls.io = cb; this.observe = el => calls.observed.push(el); this.disconnect = () => {}; },
  });
  const list = doc.createElement('div');
  list.setAttribute('id', 'postsList');
  list.innerHTML = (o.posts || [BASE]).map(p => ctx.TwPostCard.html(p, { authorName: 'شركة', avatarUrl: '', canEdit: !!o.owner })).join('');
  doc.body.appendChild(list);
  const card = ctx.TwPostCard.create({
    signedIn: () => o.signedIn !== false,
    paths: { appreciation: id => '/p/' + id + '/appreciation', save: id => '/p/' + id + '/save', view: id => '/p/' + id + '/view' },
    visitorKeyName: 'vk',
    shareInfo: id => ({ name: 'شركة النور', url: 'https://tw.example/u/C1' }),
    onEdit: id => calls.edit.push(id), onDelete: id => calls.del.push(id),
    comments: { build: id => calls.build.push(id), load: function () { calls.load.push([].slice.call(arguments)); } },
  });
  card.bind(list);
  const q = s => list.querySelector(s);
  const respond = r => pending.shift()(r);
  const norm = h => { const t = doc.createElement('div'); t.innerHTML = h; return t.innerHTML; };   // same serializer
  return { ctx, doc, list, card, calls, q, respond, norm, click: el => doc.click(el) };
}

(async function behaviour() {
  console.log('\nE — appreciate (desired-state queue)');
  {
    const b = bootCards();
    const btn = () => b.q('.pc-btn--appr');
    b.click(btn());
    check('E1 click → active + count 1 immediately', btn().classList.contains('appr-active') && btn().dataset.apprCount === '1'
      && btn().innerHTML === b.norm(b.ctx.TwPostCard.apprButtonInner(true, 1)));
    check('E2 one PUT {appreciated:true} on the page path', b.calls.api.length === 1 && b.calls.api[0].path === '/p/7/appreciation'
      && b.calls.api[0].method === 'PUT' && b.calls.api[0].body.appreciated === true);
    b.respond(ok200({ status: 'success', appreciated: true, appreciations_count: 5 })); await tick();
    check('E3 success → server state shown', btn().classList.contains('appr-active') && btn().dataset.apprCount === '5');
    b.click(btn());
    b.respond(fail(500)); await tick();
    check('E4 failure → rollback to pre-click state + error toast', btn().classList.contains('appr-active')
      && btn().dataset.apprCount === '5' && b.calls.toast.pop()[1] === 'error');
    b.click(btn());
    b.respond(fail(403)); await tick();
    check('E5 403 (own post) → rollback + toast', btn().classList.contains('appr-active') && b.calls.toast.pop()[1] === 'error');
  }
  {
    const b = bootCards();
    const btn = () => b.q('.pc-btn--appr');
    b.click(btn()); b.click(btn()); b.click(btn());
    check('E6 three fast clicks → one request in flight', b.calls.api.length === 1);
    b.respond(ok200({ status: 'success', appreciated: true, appreciations_count: 1 })); await tick();
    check('E7 server = last desired → no second request', b.calls.api.length === 1 && btn().classList.contains('appr-active'));
  }
  {
    const b = bootCards();
    const btn = () => b.q('.pc-btn--appr');
    b.click(btn()); b.click(btn());
    check('E8 two fast clicks → UI back to off, still one request', b.calls.api.length === 1 && !btn().classList.contains('appr-active'));
    b.respond(ok200({ status: 'success', appreciated: true, appreciations_count: 1 })); await tick();
    check('E9 stale response → no flicker, queued request with the last desired', !btn().classList.contains('appr-active')
      && b.calls.api.length === 2 && b.calls.api[1].body.appreciated === false);
    b.respond(fail(500)); await tick();
    check('E10 queued request fails → rollback to the server state', btn().classList.contains('appr-active') && btn().dataset.apprCount === '1');
  }

  console.log('\nF — save');
  {
    const b = bootCards();
    const btn = () => b.q('.pc-btn--save');
    b.click(btn());
    check('F1 click → saved immediately', btn().classList.contains('save-active') && btn().dataset.saved === '1'
      && btn().innerHTML === b.norm(b.ctx.TwPostCard.saveButtonInner(true)));
    check('F2 one PUT {saved:true} on the page path', b.calls.api.length === 1 && b.calls.api[0].path === '/p/7/save'
      && b.calls.api[0].method === 'PUT' && b.calls.api[0].body.saved === true);
    b.click(btn());
    check('F3 second fast click → no second request', b.calls.api.length === 1 && btn().dataset.saved === '0');
    b.respond(ok200({ status: 'success', saved: true })); await tick();
    check('F4 stale response → queued {saved:false}', b.calls.api.length === 2 && b.calls.api[1].body.saved === false
      && !btn().classList.contains('save-active'));
    b.respond(fail(429)); await tick();
    check('F5 429 → rollback to the server state + toast', btn().classList.contains('save-active') && b.calls.toast.pop()[1] === 'error');
    b.click(btn());
    b.respond(fail(500)); await tick();
    check('F6 failure → rollback', btn().classList.contains('save-active') && btn().dataset.saved === '1');
  }
  {
    const b = bootCards({ signedIn: false });
    b.click(b.q('.pc-btn--save')); b.click(b.q('.pc-btn--appr'));
    check('F7 guest → info toasts, no request, no state change', b.calls.api.length === 0
      && b.calls.toast.length === 2 && b.calls.toast.every(t => t[1] === 'info')
      && !b.q('.pc-btn--save').classList.contains('save-active') && !b.q('.pc-btn--appr').classList.contains('appr-active'));
  }

  console.log('\nG — ⋯ menu');
  {
    const v = bootCards({ owner: false });
    check('G1 visitor → no ⋯', v.q('.pc-dots-btn') === null && v.q('.pc-dots-menu') === null);
    const b = bootCards({ owner: true });
    const menu = () => b.doc.getElementById('pc-dm-7');
    b.click(b.q('.pc-dots-btn'));
    check('G2 owner ⋯ → menu opens', menu().classList.contains('open'));
    b.click(b.q('.post-body-text'));
    check('G3 click outside → menu closes', !menu().classList.contains('open'));
    b.click(b.q('.pc-dots-btn')); b.click(b.q('.pc-dots-edit'));
    check('G4 edit → menu closed + onEdit(int id)', !menu().classList.contains('open') && b.calls.edit.length === 1 && b.calls.edit[0] === 7);
    b.click(b.q('.pc-dots-btn')); b.click(b.q('.pc-dots-delete'));
    check('G5 delete → menu closed + onDelete(int id), no request here', !menu().classList.contains('open')
      && b.calls.del[0] === 7 && b.calls.api.length === 0);
  }

  console.log('\nH — view tracking');
  {
    const b = bootCards({ signedIn: false, posts: [BASE, Object.assign({}, BASE, { id: 8 })] });
    b.card.trackViews(b.list);
    check('H1 every card observed', b.calls.observed.length === 2);
    const card7 = b.calls.observed[0];
    b.calls.io([{ target: card7, isIntersecting: true }]);
    check('H2 nothing sent before the dwell', b.calls.api.length === 0 && b.calls.timers.length === 1);
    b.calls.timers.shift()();
    check('H3 POST view on the page path + guest visitor key', b.calls.api.length === 1 && b.calls.api[0].path === '/p/7/view'
      && b.calls.api[0].method === 'POST' && b.calls.api[0].body.visitor_key === b.calls.ls.vk && /^[0-9a-f-]{36}$/.test(b.calls.ls.vk));
    b.respond(ok200({ status: 'success', recorded: true })); await tick();
    const v = b.list.querySelector('.post-card[data-post-id="7"]').querySelector('.post-views');
    check('H4 recorded → count +1', v.dataset.viewsCount === '4' && v.textContent === b.ctx.TwPostCard.formatViews(4)
      && v.querySelector('svg') !== null);
    b.card.trackViews(b.list);
    b.calls.io([{ target: card7, isIntersecting: true }]);
    check('H5 same post again → not sent twice', b.calls.timers.length === 0 && b.calls.api.length === 1);
    const s = bootCards({ signedIn: true });
    s.card.trackViews(s.list); s.calls.io([{ target: s.calls.observed[0], isIntersecting: true }]); s.calls.timers.shift()();
    check('H6 signed in → no visitor key', s.calls.api.length === 1 && !('visitor_key' in s.calls.api[0].body) && !s.calls.ls.vk);
  }

  console.log('\nI — share (same text and fallbacks as before)');
  const TEXT = 'منشور من شركة النور على تواصلنا:\nhttps://tw.example/u/C1';
  {
    let shared = null;
    const b = bootCards({ navigator: { share: d => { shared = d; return Promise.resolve(); } } });
    b.click(b.q('.pc-btn--share'));
    check('I1 navigator.share({title, text, url})', shared && shared.title === 'منشور: شركة النور' && shared.text === TEXT
      && shared.url === 'https://tw.example/u/C1');
  }
  {
    const clip = [];
    const b = bootCards({ navigator: { clipboard: { writeText: t => { clip.push(t); return Promise.resolve(); } } } });
    b.click(b.q('.pc-btn--share')); await tick();
    check('I2 no share → clipboard (same text) + success toast', clip[0] === TEXT && b.calls.toast[0][1] === 'success');
  }
  {
    const b = bootCards({ navigator: {} });
    b.click(b.q('.pc-btn--share'));
    check('I3 no clipboard → textarea fallback + toast, textarea removed', b.calls.toast[0][1] === 'success'
      && b.doc.body.querySelector('textarea') === null);
  }

  console.log('\nJ — company.posts.js passes the page parts to TwPostCard');
  {
    const ctx = makeCtx();
    const doc = makeDocument();
    const list = doc.createElement('div'); list.setAttribute('id', 'postsList'); doc.body.appendChild(list);
    let opts = null, bound = null, tracked = null;
    const orig = ctx.TwPostCard.create;
    ctx.TwPostCard.create = function (o) {
      opts = o; const c = orig(o);
      return { bind: r => { bound = r; c.bind(r); }, trackViews: x => { tracked = x; }, toggleComments: c.toggleComments };
    };
    const dcl = [];
    doc.addEventListener = (t, fn) => { if (t === 'DOMContentLoaded') dcl.push(fn); };
    let snapIn = false;
    Object.assign(ctx, { document: doc, setTimeout() {}, clearTimeout() {},
      TwCompanyPage: { signedIn: () => snapIn },
      location: { origin: 'https://tawasolna.com', pathname: '/u/C9', search: '', href: 'https://tawasolna.com/u/C9?x=1' } });
    vm.runInContext(read('static/company/company.posts.js'), ctx, { filename: 'company.posts.js' });
    check('J1 one TwPostCard.create at load', !!opts);
    check('J2 API paths = the old company endpoints', opts.paths.appreciation('7') === '/company/posts/7/appreciation'
      && opts.paths.save('7') === '/company/posts/7/save' && opts.paths.view('a b') === '/company/posts/a%20b/view');
    check('J3 session check = TwCompanyPage.signedIn', opts.signedIn() === false && (snapIn = true, opts.signedIn() === true));
    check('J4 guest view key name unchanged (cp_vk)', opts.visitorKeyName === 'cp_vk');
    ctx.companyState = { profile: { full_name: 'شركة س', tw_id: 'C9' } };
    const si = opts.shareInfo('7');
    check('J5 share info = company name + /u/{tw_id}', si.name === 'شركة س' && si.url === 'https://tawasolna.com/u/C9');
    ctx.companyState = { profile: {} };
    const si2 = opts.shareInfo('7');
    check('J6 share info fallback = «شركة» + location.href', si2.name === 'شركة' && si2.url === 'https://tawasolna.com/u/C9?x=1');
    check('J7 delete → the page deletePost', opts.onDelete === ctx.deletePost && typeof opts.onEdit === 'function');
    check('J8 comments build / load from the comments system', typeof opts.comments.build === 'function' && typeof opts.comments.load === 'function');
    ctx.initPostViewTracking(list);
    check('J9 initPostViewTracking → TwPostCard trackViews', tracked === list);
    dcl.forEach(fn => fn());
    check('J10 DOMContentLoaded binds the posts list', bound === list);
  }

  console.log('\nK — tw-card.css = old POST CARDS section');
  {
    const rules = css => {
      const m = new Map();
      css.replace(/\/\*[\s\S]*?\*\//g, '').replace(/([^{}]+)\{([^{}]*)\}/g, (_, sel, body) => {
        const decl = body.split(';').map(d => d.trim().replace(/\s+/g, ' ').replace(/\s*:\s*/, ':')).filter(Boolean).join(';');
        sel.split(',').map(x => x.trim().replace(/\s+/g, ' ')).forEach(x => m.set(x, (m.get(x) ? m.get(x) + ';' : '') + decl));
      });
      return m;
    };
    const old = rules(read('tests/fixtures/legacy_post_cards.css'));
    const card = rules(read('static/shared/tw-card.css'));
    const page = rules(read('static/company/company.css'));
    const PAGE_OWNED = ['.posts-owner-bar', '#postsEmpty'];   // the page's list, not the card — stay in company.css
    const moved = [...old.keys()].filter(k => !PAGE_OWNED.includes(k));
    const diff = moved.filter(k => card.get(k) !== old.get(k));
    check('K1 every card selector in tw-card.css with the same values', moved.length > 40 && diff.length === 0, diff.join(' | '));
    check('K2 tw-card.css has nothing extra', [...card.keys()].every(k => old.has(k)) && card.size === moved.length);
    const left = moved.filter(k => page.has(k));
    check('K3 none of them left in company.css', left.length === 0, left.join(' | '));
    check('K4 page list rules stay in company.css', PAGE_OWNED.every(k => page.get(k) === old.get(k) && !card.has(k)));
    const html = read('company-profile.html');
    const iCard = html.indexOf('/static/shared/tw-card.css?v={{v:tw-card.css}}'), iPage = html.indexOf('/static/company/company.css');
    check('K5 company page loads tw-card.css (versioned) right before company.css', iCard > 0 && iPage > iCard
      && !/<link[^>]*>/.test(html.slice(html.indexOf('>', iCard) + 1, iPage)));
  }

  console.log('\n' + passed + ' passed, ' + failed + ' failed');
  process.exit(failed ? 1 : 0);
}());
