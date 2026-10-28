/**
 * test_post_card_runtime.js — DS-CARD post card (static/shared/tw-post-card.js) in a Node vm with
 * the real shared code: twT + tw_strings.json · twActionState + tw_actions.json · twAvatarHtml ·
 * twRelativeTime / twFormatDate (tw_shared.js) · twIcon (tw-icons.js).
 *   — task U.3: every part from its system —
 *   A  text from twT (an override changes the card) · every <svg> from DS-ICON · avatar = DS-IMAGE
 *   B  buttons from the Actions Registry: ⋯ only for the owner (twActionState) · comments off →
 *      no button / panel · admin off → hidden · every button type=button + data-tw-action
 *   C  HTML / script in body · tags · name · id → escaped
 *   D  twRelativeTime input → output (shared, after 30 days = twFormatDate) · formatViews
 *   D2 company.render.js renders through TwPostCard (owner sees ⋯, visitor does not)
 *   — task U.2b: behaviour on the real markup (tests/fixtures/post_card_dom.js) —
 *   E  appreciate: toggle · success · rollback on failure / 403 · two fast clicks = one request
 *   F  save: same queue + rollback · guest → login (twLoginHref), no request
 *   G  ⋯ menu: owner only · open / outside-click close · edit / delete callbacks (int id)
 *   H  views: sent once per post after the dwell · guest visitor key · count updated
 *   I  share: navigator.share → clipboard → textarea fallback, same text as before
 *   J  company.posts.js wires the page parts into TwPostCard.create (paths · session · share · callbacks)
 *   K  tw-card.css: sizes from tokens · no hex · active save = --color-action-save (not warning,
 *      AA contrast) · card rules not in company.css · load order
 *   — task 8.6b-1: comments = TwPostComments (static/shared/tw-post-comments.js) —
 *   L  create() → build / load · nothing page-specific inside · build / load / send on the real
 *      panel · opts.postOwner joins the mention names · page-wide listeners once for two
 *      controllers · company.posts.js only wires it · CSS = the old section, not in company.css ·
 *      load order
 *   — task 8.6b-2: company posts in the home feed (real static/home/*.js on the fixture DOM) —
 *   M  feed post = .post-card from TwPostCard with the API fields · author link · comments panel opens
 *      inside the feed (no navigation) · post owner in the mention names · re-render: one feed
 *      listener, one panel, built from scratch · no old hw-p card · load order
 *   — task 8.6c: ⋯ report / block + the comment button after send / delete —
 *   N  ⋯ items by the server numbers (owner · non-owner · guest · company on its own post) ·
 *      report → twReportDialog (company · author · /u/{tw_id}) · block → registry confirm →
 *      twBlockUser · guest report → login · twReportDialog targetUrl (default location.href) ·
 *      commentButtonInner(0 / 3) · the comments system redraws the button with it (M6b)
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
const varLine = (src, name) => src.match(new RegExp('^var ' + name + ' = .*$', 'm'))[0];
const SHARED = read('tw_shared.js');
const FNS = ['twEscAttr', 'twSafeImageUrl', 'twT', 'twFormatDate', 'twRelativeTime', '_twAvatarSpec', 'twAvatarHtml',
  '_twActDef', '_twActAudience', 'twActionState', 'twAction'];
const HELPERS = ['_twTWarned', '_TW_AVA_PX', '_twActWarned', '_TW_ACT_VISIBLE_WHEN'].map(n => varLine(SHARED, n)).join('\n')
  + '\n' + FNS.map(n => fnText(SHARED, n)).join('\n') + '\nvar twEscHtml = twEscAttr;\n'
  + FNS.concat('twEscHtml').map(n => 'window.' + n + '=' + n + ';').join('');
const DICT = JSON.parse(read('tw_strings.json')).ar;
const ACTIONS = JSON.parse(read('tw_actions.json')).actions;

const NOW = Date.parse('2026-10-24T12:00:00Z');
function makeCtx(o) {
  o = o || {};
  const ctx = { console: { log: console.log, warn() {}, error: console.error }, Number, String, Math, isNaN, parseFloat, isFinite, Array, Object, JSON };
  ctx.window = ctx;
  vm.createContext(ctx);
  vm.runInContext('Date.now = function () { return ' + NOW + '; };', ctx);
  ctx.TW_STRINGS = { dict: Object.assign({}, DICT, o.dict || {}) };
  ctx.TW_ACTIONS = { actions: Object.assign(JSON.parse(JSON.stringify(ACTIONS)), o.actions || {}) };
  ctx.TwAuthSync = { getSessionSnapshot: () => o.snap || { isAuthenticated: false } };
  vm.runInContext(HELPERS, ctx, { filename: 'tw_shared.js (helpers)' });
  vm.runInContext(read('static/shared/tw-icons.js'), ctx, { filename: 'tw-icons.js' });
  vm.runInContext(read('static/shared/tw-options-data.js'), ctx, { filename: 'tw-options-data.js' });
  vm.runInContext(read('static/shared/tw-post-card.js'), ctx, { filename: 'tw-post-card.js' });
  vm.runInContext(read('static/shared/tw-post-comments.js'), ctx, { filename: 'tw-post-comments.js' });
  return ctx;
}

const ago = s => new Date(NOW - s * 1000).toISOString();
const BASE = { id: 7, body: 'منشور قصير', tags: [], theme_color: 'teal', created_at: ago(120),
  views_count: 3, appreciations_count: 0, viewer_appreciated: false, comments_enabled: true,
  comments_count: 0, viewer_saved: false };
const XSS = '<script>alert(1)</script><img src=x onerror=alert(2)>"\'&';
const REGISTERED = { isAuthenticated: true, userId: 55, userType: 'emp' };
const card = (ctx, post, opts) => ctx.TwPostCard.html(Object.assign({}, BASE, post || {}),
  Object.assign({ authorName: 'شركة النور', avatarUrl: 'https://cdn.x/logo.png', authorType: 'co', canEdit: false }, opts || {}));
const buttons = h => [...h.matchAll(/<button\b[^>]*>/g)].map(m => m[0]);

console.log('\nA — text / icons / avatar from their systems (U.3)');
{
  const ctx = makeCtx();
  const h = card(ctx, { appreciations_count: 12, comments_count: 4, views_count: 1500 }, { canEdit: true });
  const want = ['post.card.appreciate_n', 'post.card.comment_n', 'action.share', 'post.card.save', 'post.card.edit', 'post.card.delete']
    .map(k => ctx.twEscHtml(ctx.twT(k, { count: k === 'post.card.appreciate_n' ? 12 : 4 })));
  check('A1 every label = its twT value', want.every(w => h.includes('<span class="tw-act-lbl">' + w + '</span>')));
  check('A2 aria labels + views + time from twT', h.includes('aria-label="' + DICT['post.card.options'] + '"')
    && h.includes('aria-label="' + DICT['post.card.more'] + '"') && h.includes('aria-label="' + DICT['post.card.less'] + '"')
    && h.includes(DICT['post.card.views'].replace('{count}', '1.5K')) && h.includes(DICT['time.rel.minutes'].replace('{n}', '2')));
  const o = makeCtx({ dict: { 'post.card.save': 'SAVE-X', 'action.share': 'SHARE-X', 'post.card.options': 'OPT-X', 'time.rel.minutes': 'M{n}' } });
  const ho = card(o, {}, { canEdit: true });
  check('A3 admin text override reaches the card (no fixed text)', ho.includes('>SAVE-X<') && ho.includes('>SHARE-X<')
    && ho.includes('aria-label="OPT-X"') && ho.includes('M2'));
  const svgs = (h.match(/<svg\b/g) || []).length, dsIcons = (h.match(/<svg [^>]*class="tw-ico[" ]/g) || []).length;
  check('A4 every <svg> is a DS-ICON twIcon (no hand-written SVG)', svgs >= 10 && svgs === dsIcons, svgs + ' / ' + dsIcons);
  check('A5 no Arabic literal left in tw-post-card.js code', !read('static/shared/tw-post-card.js').split('\n')
    .filter(l => !/^\s*\/\//.test(l)).some(l => /[ء-ي]/.test(l)));
  check('A6 logo = DS-IMAGE twAvatarHtml (co → org shape)', h.includes(ctx.twAvatarHtml({ full_name: 'شركة النور',
    avatar_url: 'https://cdn.x/logo.png', user_type: 'co' }, 'lg')) && h.includes('tw-ava--org'));
  const bad = card(ctx, {}, { avatarUrl: 'javascript:alert(1)' });
  check('A7 unsafe logo → DS-IMAGE fallback letter, no <img>', !/<img\b/.test(bad) && bad.includes('data-fb="1"') && !bad.includes('javascript:'));
  const none = card(ctx, {}, { avatarUrl: '', authorName: '' });
  check('A8 no name / logo → fallback, nothing breaks', none.includes('tw-ava__fb') && !/<img\b/.test(none));
}

console.log('\nB — buttons from the Actions Registry (U.3)');
{
  for (const [who, snap] of [['guest', null], ['registered', REGISTERED]]) {
    const ctx = makeCtx({ snap });
    const h = card(ctx);
    check('B1 ' + who + ' → no ⋯ (twActionState hides post_edit / post_delete)', !h.includes('pc-dots')
      && ctx.twActionState('post_edit', {}) === 'hidden' && ctx.twActionState('post_delete', {}) === 'hidden');
    check('B2 ' + who + ' → appreciate · comment · share · save', ['post_appreciate', 'post_comment', 'share', 'post_save']
      .every(id => h.includes('data-tw-action="' + id + '"')));
  }
  const ctx = makeCtx({ snap: REGISTERED });
  const own = card(ctx, {}, { canEdit: true });
  check('B3 owner → ⋯ with edit + delete', own.includes('pc-dots-btn') && own.includes('data-tw-action="post_edit"')
    && own.includes('data-tw-action="post_delete"'));
  check('B4 guest on appreciate / save = login (auth), share = enabled', makeCtx().twActionState('post_save', {}) === 'login'
    && makeCtx().twActionState('post_appreciate', {}) === 'login' && makeCtx().twActionState('share', {}) === 'enabled');
  const off = card(ctx, { comments_enabled: false });
  check('B5 comments off → no comment button, no panel (registry visibleWhen)', !off.includes('pc-btn--cmt')
    && !off.includes('pc-cmts-panel') && card(ctx).includes('pc-cmts-panel'));
  const adm = makeCtx({ snap: REGISTERED, actions: { post_save: Object.assign({}, ACTIONS.post_save, { off: true }),
    post_edit: Object.assign({}, ACTIONS.post_edit, { off: true }), post_delete: Object.assign({}, ACTIONS.post_delete, { off: true }) } });
  const ha = card(adm, {}, { canEdit: true });
  check('B6 admin off → hidden (save gone · ⋯ gone when both items off)', !ha.includes('pc-btn--save') && !ha.includes('pc-dots'));
  check('B7 every button type="button"', buttons(own).every(b => b.includes('type="button"')), buttons(own).length);
  const st = card(ctx, { viewer_appreciated: 'true', appreciations_count: 2, viewer_saved: 1 });
  check('B8 active states kept (appr-active · save-active · data-saved)', st.includes('pc-btn--appr appr-active')
    && st.includes('pc-btn--save save-active') && st.includes('data-saved="1"') && st.includes('data-appr-count="2"'));
  const filled = ctx.twIcon('bookmark-check', { size: 'sm', filled: true });
  check('B9 saved → filled bookmark-check (DS-ICON)', ctx.TwPostCard.saveButtonInner(true).startsWith(filled)
    && ctx.TwPostCard.saveButtonInner(false).startsWith(ctx.twIcon('bookmark', { size: 'sm' })));
}

console.log('\nC — escaping');
{
  const ctx = makeCtx();
  const h = card(ctx, { id: '9"><b>', body: XSS, tags: [XSS] }, { authorName: XSS, avatarUrl: 'https://x/a.png?"><b>', canEdit: true });
  check('C1 script tag escaped', !h.includes('<script>') && h.includes('&lt;script&gt;'));
  check('C2 img onerror not a tag', !h.includes('<img src=x'));
  check('C3 id escaped in attributes', !h.includes('data-post-id="9"><b>') && h.includes('9&quot;&gt;&lt;b&gt;'));
  check('C4 logo URL escaped', !h.includes('?"><b>'));
}

console.log('\nD — shared relative time (twRelativeTime) + views');
{
  const ctx = makeCtx();
  const rel = v => ctx.twRelativeTime(v);
  check('D1 < 1 min → time.rel.now', rel(ago(30)) === DICT['time.rel.now']);
  check('D2 minutes / hours / days / weeks', rel(ago(120)) === 'منذ 2 دقيقة' && rel(ago(7200)) === 'منذ 2 ساعة'
    && rel(ago(3 * 86400)) === 'منذ 3 يوم' && rel(ago(15 * 86400)) === 'منذ 2 أسبوع');
  check('D3 ≥ 30 days → twFormatDate (Gregorian, Western digits)', rel('2025-01-01T12:00:00Z') === ctx.twFormatDate('2025-01-01T12:00:00Z')
    && rel('2025-01-01T12:00:00Z') === '1 يناير 2025');
  check('D4 empty / invalid → ""', rel('') === '' && rel(null) === '' && rel('nope') === '');
  check('D5 TwPostCard.relativeTime = the shared one', ctx.TwPostCard.relativeTime(ago(7200)) === rel(ago(7200)));
  check('D6 formatViews from twT', ctx.TwPostCard.formatViews(3) === '3 مشاهدة' && ctx.TwPostCard.formatViews(1500) === '1.5K مشاهدة'
    && ctx.TwPostCard.formatViews(2000) === '2K مشاهدة');
}

console.log('\nD2 — company.render.js renders through TwPostCard');
{
  const ctx = makeCtx();
  const list = { innerHTML: '' }, empty = { style: {} };
  Object.assign(ctx, {
    requestAnimationFrame() {},
    document: { getElementById: id => (id === 'postsList' ? list : id === 'postsEmpty' ? empty : null),
                querySelectorAll: () => [], addEventListener() {} },
    setInterval() {}, setTimeout() {},
  });
  ctx.twIcon.hydrate = () => 0;
  let calls = 0, lastOpts = null;
  const orig = ctx.TwPostCard.html;
  ctx.TwPostCard.html = function (p, o) { calls++; lastOpts = o; return orig.apply(this, arguments); };
  vm.runInContext(read('static/company/company.render.js'), ctx, { filename: 'company.render.js' });
  check('D2.1 _postCardHtml not exposed', ctx._postCardHtml === undefined);
  ctx.companyState = { profile: { id: 3, tw_id: 'C3', full_name: 'شركة', avatar_url: '' }, permissions: { can_edit: true } };
  ctx.renderPosts([BASE, Object.assign({}, BASE, { id: 8 })]);
  check('D2.2 TwPostCard.html called per post (author type co)', calls === 2 && lastOpts.authorType === 'co');
  check('D2.3 owner list has ⋯', (list.innerHTML.match(/pc-dots-btn/g) || []).length === 2);
  ctx.companyState.permissions = { can_edit: false };
  ctx.renderPosts([BASE]);
  check('D2.4 guest list: ⋯ = report only (author = the company id 3 → its /u/C3), no edit / delete / block (task 8.6c)',
    list.innerHTML.includes('class="pc-dots-report" data-tw-action="report" data-post-id="7" data-author-id="3" data-author-tw="C3"')
    && !/pc-dots-(edit|delete|block)/.test(list.innerHTML) && list.innerHTML.includes('pc-btn--appr'));
}

// ── U.2b — behaviour on the real markup ─────────────────────────────────────
const { makeDocument } = require('./fixtures/post_card_dom.js');
const tick = () => new Promise(r => setImmediate(r));
const ok200 = data => ({ ok: true, status: 200, data: data });
const fail = st => ({ ok: false, status: st, data: null, error: {} });

function bootCards(o) {
  o = o || {};
  const ctx = makeCtx({ snap: o.signedIn === false ? null : REGISTERED });
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
    location: { pathname: '/u/C1', search: '?tab=posts', href: '' },
    twLoginHref: n => '/login?next=' + encodeURIComponent(n),
    IntersectionObserver: function (cb) { calls.io = cb; this.observe = el => calls.observed.push(el); this.disconnect = () => {}; },
  });
  const list = doc.createElement('div');
  list.setAttribute('id', 'postsList');
  list.innerHTML = (o.posts || [BASE]).map(p => ctx.TwPostCard.html(p, Object.assign({ authorName: 'شركة', avatarUrl: '', canEdit: !!o.owner }, o.cardOpts))).join('');
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
    b.click(b.q('.pc-btn--save'));
    const toSave = b.ctx.location.href; b.ctx.location.href = '';
    b.click(b.q('.pc-btn--appr'));
    check('F7 guest → login with return path (BTN-19), no request, no toast, no state change', b.calls.api.length === 0
      && toSave === '/login?next=%2Fu%2FC1%3Ftab%3Dposts' && b.ctx.location.href === toSave && b.calls.toast.length === 0
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
    let snapIn = false, cmtOpts = null, cmtCtl = null;
    const origCmt = ctx.TwPostComments.create;
    ctx.TwPostComments.create = function (o) { cmtOpts = o; cmtCtl = origCmt(o); return cmtCtl; };
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
    check('J8b … = the TwPostComments controller of the page', !!cmtOpts && opts.comments.build === cmtCtl.build && opts.comments.load === cmtCtl.load);
    check('J8c TwPostComments session check = TwCompanyPage.signedIn', (snapIn = false, cmtOpts.signedIn() === false) && (snapIn = true, cmtOpts.signedIn() === true));
    ctx.companyState = { profile: { full_name: 'شركة س', tw_id: 'C9', avatar_url: null } };
    check('J8d TwPostComments postOwner = companyState.profile', cmtOpts.postOwner('7') === ctx.companyState.profile);
    delete ctx.companyState;
    check('J8e postOwner without companyState → null', cmtOpts.postOwner('7') === null);
    ctx.initPostViewTracking(list);
    check('J9 initPostViewTracking → TwPostCard trackViews', tracked === list);
    dcl.forEach(fn => fn());
    check('J10 DOMContentLoaded binds the posts list', bound === list);
  }

  console.log('\nK — tw-card.css: tokens only · active save = --color-action-save');
  {
    const rules = css => {
      const m = new Map();
      css.replace(/\/\*[\s\S]*?\*\//g, '').replace(/([^{}]+)\{([^{}]*)\}/g, (_, sel, body) => {
        const decl = body.split(';').map(d => d.trim().replace(/\s+/g, ' ').replace(/\s*:\s*/, ':')).filter(Boolean);
        sel.split(',').map(x => x.trim().replace(/\s+/g, ' ')).forEach(x => m.set(x, (m.get(x) || []).concat(decl)));
      });
      return m;
    };
    const cardCss = read('static/shared/tw-card.css');
    const card = rules(cardCss);
    const decls = [...card.values()].flat();
    check('K1 no hex color in the card', !/#[0-9a-f]{3,8}\b/i.test(cardCss.replace(/\/\*[\s\S]*?\*\//g, '')));
    const SIZE_PROPS = /^(padding|margin[\w-]*|gap|font-size|border-radius|width|height|top|left)$/;
    const raw = decls.filter(d => SIZE_PROPS.test(d.split(':')[0]) && /\d(px|rem|em)\b/.test(d));
    check('K2 every size from --space / --radius / --size tokens (CARD-04)', raw.length === 0, raw.join(' | '));
    const save = card.get('.pc-btn--save.save-active') || [];
    check('K3 active save → var(--color-action-save)', save.includes('color:var(--color-action-save)')
      && (card.get('.pc-btn--save:hover') || []).includes('color:var(--color-action-save)'));
    check('K4 no warning color left in the card (save or other)', !/--color-status-warning/.test(cardCss));
    const tok = read('tw_shared.css');
    const def = n => (tok.match(new RegExp('^\\s*' + n + ':\\s*([^;]+);', 'm')) || [])[1];
    const resolve = n => { const v = def(n).trim(); const m = v.match(/^var\((--[\w-]+)\)$/); return m ? resolve(m[1]) : v; };
    const saveHex = resolve('--color-action-save'), warnHex = resolve('--color-status-warning');
    check('K5 token in DS-COLOR Section B (+ -rgb twin), ≠ warning', /^#[0-9a-f]{6}$/i.test(saveHex) && saveHex !== warnHex
      && !!def('--color-action-save-rgb') && tok.indexOf('--color-action-save:') > tok.indexOf('Section B'));
    const lum = h => { const c = [1, 3, 5].map(i => parseInt(h.slice(i, i + 2), 16) / 255)
      .map(v => (v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4))); return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]; };
    const contrast = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
    const cr = contrast(saveHex, resolve('--color-surface-page'));
    check('K6 AA contrast on the page background (≥ 4.5)', cr >= 4.5, cr.toFixed(2));
    const page = rules(read('static/company/company.css'));
    const left = [...card.keys()].filter(k => page.has(k));
    check('K7 no card rule in company.css', left.length === 0, left.join(' | '));
    check('K8 page list rules stay in company.css', ['.posts-owner-bar', '#postsEmpty'].every(k => page.has(k) && !card.has(k)));
    check('K9 avatar = DS-IMAGE (old .post-ava img / --init rules gone)', !card.has('.post-ava img') && !card.has('.post-ava--init'));
    const html = read('company-profile.html');
    const iCard = html.indexOf('/static/shared/tw-card.css?v={{v:tw-card.css}}'), iPage = html.indexOf('/static/company/company.css');
    const between = (html.slice(html.indexOf('>', iCard) + 1, iPage).match(/<link[^>]*>/g) || []);
    check('K10 company page loads tw-card.css (versioned) right before company.css (only the shared comments CSS between — 8.6b-1)',
      iCard > 0 && iPage > iCard && between.every(l => l.indexOf('/static/shared/tw-post-comments.css') !== -1));
  }

  console.log('\nL — comments = TwPostComments (task 8.6b-1)');
  {
    const SRC = read('static/shared/tw-post-comments.js');
    const code = SRC.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '');
    check('L1 tw-post-comments.js: nothing page-specific (companyState · TwCompanyPage · #postsList)',
      !/companyState|TwCompanyPage|postsList/.test(code));
    function bootCmt(o) {
      o = o || {};
      const ctx = makeCtx();
      const doc = makeDocument();
      const calls = { api: [], toast: [], docClick: 0 };
      const pending = [];
      const addDoc = doc.addEventListener;
      doc.addEventListener = (t, fn, op) => { if (t === 'click') calls.docClick++; addDoc(t, fn, op); };
      Object.assign(ctx, {
        document: doc, setTimeout: () => 0, clearTimeout() {}, requestAnimationFrame: fn => fn(),
        showToast: (m, t) => calls.toast.push([m, t]),
        twApiMessage: (res, fb) => fb,
        twApi: (path, op) => new Promise(res => { calls.api.push({ path, method: (op && op.method) || 'GET', body: op && op.body }); pending.push(res); }),
        Event: function (t) { this.type = t; },
      });
      const panel = doc.createElement('div');
      panel.innerHTML = '<div class="pc-cmts-panel" id="pc-cmt-panel-7" data-post-id="7" style="display:none"></div>';
      doc.body.appendChild(panel);
      const ctl = ctx.TwPostComments.create({ signedIn: () => o.signedIn !== false, postOwner: o.postOwner || (() => null) });
      return { ctx, doc, ctl, calls, q: s => doc.body.querySelector(s), respond: r => pending.shift()(r) };
    }
    const b = bootCmt({ postOwner: id => (id === '7' ? { full_name: 'شركة النور', tw_id: 'C1', avatar_url: null } : null) });
    check('L2 create() → { build, load }', typeof b.ctl.build === 'function' && typeof b.ctl.load === 'function');
    b.ctl.build('7');
    const ta = b.q('textarea.pc-cmts-ta'), send = b.q('.pc-cmts-send[data-post-id="7"]');   // (the fixture DOM: simple selectors only)
    check('L3 build: list + reply strip + input row (textarea + send) for a signed-in viewer',
      !!b.q('.pc-cmts-list') && !!b.q('.pc-cmt-reply-strip') && !!ta && !!send && !b.q('.pc-cmts-guest'));
    b.ctl.build('7');
    check('L3b build twice = one input row', b.doc.body.querySelectorAll('.pc-cmts-input-row').length === 1);
    const g = bootCmt({ signedIn: false });
    g.ctl.build('7');
    check('L3c guest → sign-in note, no textarea', !!g.q('.pc-cmts-guest') && !g.q('textarea'));

    b.ctl.load('7');
    check('L4 load → GET the comments of the post', b.calls.api.length === 1 && b.calls.api[0].path === '/company/posts/7/comments' && b.calls.api[0].method === 'GET');
    b.respond(ok200({ comments: [{ id: 3, body: 'أول تعليق', author_name: 'سارة', author_tw_id: 'U5', created_at: ago(60), viewer_can_edit: true, viewer_can_delete: true }], next_cursor: 3 }));
    await tick();
    const item = b.q('.pc-cmt-item[data-cmt-id="3"]');
    check('L4b comment rendered (author link /u/{tw_id} · ⋮ · «more» button for next_cursor)', !!item
      && item.querySelector('a.pc-cmt-author').getAttribute('href') === '/u/U5' && !!item.querySelector('.pc-cmt-menu-btn')
      && !!b.q('.pc-cmts-more'));
    b.ctl.load('7', 3);
    check('L4c load(id, cursor) → ?cursor=', b.calls.api[1].path === '/company/posts/7/comments?cursor=3');
    b.respond(ok200({ comments: [], next_cursor: null }));
    await tick();

    // opts.postOwner joins the mention names: the owner's two-word name is one mention after send
    async function sendWith(bb) {
      bb.ctl.build('7');
      bb.ctl.load('7');
      bb.respond(ok200({ comments: [] }));
      await tick();
      bb.q('textarea.pc-cmts-ta').value = '@شركة النور مرحبا';
      bb.doc.click(bb.q('.pc-cmts-send[data-post-id="7"]'));
      const post = bb.calls.api[bb.calls.api.length - 1];
      bb.respond(ok200({ status: 'success', comment: { id: 9, body: '@شركة النور مرحبا', author_name: 'سارة', author_tw_id: 'U5', created_at: ago(1) } }));
      await tick();
      const it = bb.q('.pc-cmt-item[data-cmt-id="9"]'), m = it && it.querySelector('.pc-cmt-mention');
      return { post, mention: m ? m.textContent : null };
    }
    const withOwner = await sendWith(bootCmt({ postOwner: () => ({ full_name: 'شركة النور', tw_id: 'C1', avatar_url: null }) }));
    const noOwner   = await sendWith(bootCmt());
    check('L5 send → POST body to the post (panel click listener)', withOwner.post.method === 'POST'
      && withOwner.post.path === '/company/posts/7/comments' && withOwner.post.body.body === '@شركة النور مرحبا');
    check('L5b postOwner in the mention names → «@شركة النور» is one mention', withOwner.mention === '@شركة النور');
    check('L5c without postOwner → only «@شركة» (the fallback)', noOwner.mention === '@شركة');

    const two = bootCmt();
    const before = two.calls.docClick;
    two.ctx.TwPostComments.create({ signedIn: () => true, postOwner: () => null });
    check('L6 page-wide click listeners bound once (second controller adds none)', before > 0 && two.calls.docClick === before);

    const posts = read('static/company/company.posts.js');
    check('L7 company.posts.js: no comments code left (no _cmt* / _renderCommentBody)', !/_cmt\w*\s*\(|function _cmt|_renderCommentBody/.test(posts));

    const rules = css => {
      const m = new Map();
      css.replace(/\/\*[\s\S]*?\*\//g, '').replace(/@media[^{]*\{((?:[^{}]*\{[^{}]*\})*)\s*\}/g, (all, inner) =>
        { inner.replace(/([^{}]+)\{([^{}]*)\}/g, (_, sel, body) => m.set('@media ' + all.slice(0, all.indexOf('{')).trim() + ' ' + sel.trim(), body.trim())); return ''; })
        .replace(/@keyframes[^{]*\{(?:[^{}]*\{[^{}]*\})*\s*\}/g, k => { m.set(k.slice(0, k.indexOf('{')).trim(), k.replace(/\s+/g, '')); return ''; })
        .replace(/([^{}]+)\{([^{}]*)\}/g, (_, sel, body) => { m.set(sel.trim().replace(/\s+/g, ' '), body.replace(/\s+/g, ' ').trim()); });
      return m;
    };
    const cmtCss = read('static/shared/tw-post-comments.css');
    const now = rules(cmtCss), old = rules(read('tests/fixtures/legacy_post_comments.css'));
    const diff = [...old.keys()].filter(k => now.get(k) !== old.get(k)).concat([...now.keys()].filter(k => !old.has(k)));
    check('L8 tw-post-comments.css = the old company.css section (same selectors / values)', old.size > 50 && diff.length === 0, diff.join(' | '));
    check('L8b no hex color', !/#[0-9a-f]{3,8}\b/i.test(cmtCss.replace(/\/\*[\s\S]*?\*\//g, '')));
    const page = read('static/company/company.css').replace(/\/\*[\s\S]*?\*\//g, '');
    check('L8c no comment rule left in company.css', !/\.pc-cmts?-/.test(page));
    const html = read('company-profile.html');
    const at = s => html.indexOf(s);
    check('L9 CSS order: tw-card.css → tw-post-comments.css (versioned) → company.css',
      at('/static/shared/tw-card.css') > 0 && at('/static/shared/tw-post-comments.css?v={{v:tw-post-comments.css}}') > at('/static/shared/tw-card.css')
      && at('/static/company/company.css') > at('/static/shared/tw-post-comments.css'));
    check('L9b JS order: tw-post-card.js → tw-post-comments.js (versioned) → company.posts.js',
      at('/static/shared/tw-post-card.js') > 0 && at('/static/shared/tw-post-comments.js?v={{v:tw-post-comments.js}}') > at('/static/shared/tw-post-card.js')
      && at('/static/company/company.posts.js') > at('/static/shared/tw-post-comments.js'));
  }

  console.log('\nM — company posts in the home feed (task 8.6b-2)');
  {
    const HOME = read('home-v2.html');
    const HOME_JS = (HOME.match(/<script src="\/static\/home\/[^"]+"/g) || []).map(x => x.slice(14, -1));
    function bootFeed(items) {
      const ctx = makeCtx({ snap: REGISTERED });
      vm.runInContext(fnText(SHARED, 'twAccountHref'), ctx);
      const doc = makeDocument();
      const calls = { api: [], nav: [], feedClick: 0, observed: 0 };
      const mk = (tag, attrs, parent) => { const e = doc.createElement(tag); Object.assign(e.attrs, attrs); (parent || doc.body).appendChild(e); return e; };
      ['all', 'opportunities', 'posts', 'news'].forEach(f => mk('button', { class: 'hw-ft', 'data-filter': f }));
      const feed = mk('div', { id: 'hwFeed' });
      const addFeed = feed.addEventListener;
      feed.addEventListener = function (t, fn) { if (t === 'click') calls.feedClick++; addFeed.call(this, t, fn); };
      const empty = mk('div', { id: 'hwEmpty', class: 'hidden' }); mk('h3', {}, empty); mk('p', {}, empty);
      const err = mk('div', { id: 'hwError', class: 'hidden' }); mk('button', { class: 'hw-retry' }, err);
      const loc = { pathname: '/home', search: '?f=posts', origin: 'https://x.test' };
      let href = '/home?f=posts';
      Object.defineProperty(loc, 'href', { get: () => href, set: v => { calls.nav.push(v); href = v; } });
      Object.assign(ctx, {
        document: doc, location: loc, URLSearchParams, AbortController, setTimeout: () => 0, clearTimeout() {},
        requestAnimationFrame: fn => fn(), Event: function (t) { this.type = t; },
        getComputedStyle: () => ({ lineHeight: '22px' }),
        localStorage: { getItem: () => null, setItem() {} }, showToast() {}, twApiMessage: (r, fb) => fb,
        IntersectionObserver: function () { this.observe = () => { calls.observed++; }; this.disconnect = () => {}; },
        twRequireAuth: () => REGISTERED, getTwUser: () => ({ tw_id: 'U55' }),
        twApi: (path, op) => {
          const m = (op && op.method) || 'GET';
          calls.api.push({ path, method: m, body: op && op.body });
          if (path.indexOf('/home/feed') === 0) return Promise.resolve(ok200({ items: items() }));
          if (/\/comments$/.test(path) && m === 'GET') return Promise.resolve(ok200({ comments: [] }));
          if (/\/comments$/.test(path)) return Promise.resolve(ok200({ status: 'success', comment: { id: 9, body: op.body.body,
            author_name: 'سارة', author_tw_id: 'U55', created_at: ago(1) } }));
          return Promise.resolve(ok200({ status: 'success', appreciated: op.body.appreciated, appreciations_count: 2 }));
        },
      });
      ctx.twIcon.hydrate = () => 0;
      ctx.Home = { nav: { init() {} } };   // sidebar = test_home_landing_runtime.js
      HOME_JS.filter(f => f !== 'static/home/home.nav.js').forEach(f => vm.runInContext(read(f), ctx, { filename: f }));
      return { ctx, doc, feed, calls, q: x => doc.body.querySelector(x), qa: x => doc.body.querySelectorAll(x) };
    }
    const POST = { type: 'post', id: 41, body: 'منشور بالفيد', tags: ['توظيف'], theme_color: 'purple', comments_enabled: true,
      created_at: ago(300), author_name: 'شركة النور', author_tw_id: 'C9', author_id: 3, author_avatar: '', author_type: 'co',
      views_count: 5, appreciations_count: 3, viewer_appreciated: true, viewer_saved: true, comments_count: 2 };
    const f = bootFeed(() => [POST]);
    await tick(); await tick();
    const c = f.q('.post-card[data-post-id="41"]');
    check('M1 feed requests filter=posts and draws one .post-card from TwPostCard', f.calls.api[0].path === '/home/feed?filter=posts&limit=30'
      && f.qa('.post-card').length === 1 && !!c && c.parentNode === f.feed);
    check('M2 card fields from the API (appreciated 3 · saved · comments 2 · views 5 · purple · tag · ⋯ = report + block of author 3)',
      c.querySelector('.pc-btn--appr').classList.contains('appr-active') && c.querySelector('.pc-btn--appr').getAttribute('data-appr-count') === '3'
      && c.querySelector('.pc-btn--save').getAttribute('data-saved') === '1' && c.querySelector('.pc-btn--cmt').getAttribute('data-cmt-count') === '2'
      && c.querySelector('.post-views').getAttribute('data-views-count') === '5' && c.attrs.style.indexOf('--pa:' + f.ctx.TW.POST_THEME_COLORS.purple.accent + ';') === 0
      && c.querySelector('.jtag').textContent === 'توظيف' && c.querySelector('.pc-dots-report').getAttribute('data-author-id') === '3'
      && c.querySelector('.pc-dots-block').getAttribute('data-author-tw') === 'C9' && !c.querySelector('.pc-dots-edit'), c.attrs.style);
    check('M3 author name + logo link to /u/{tw_id} (org avatar)', c.querySelector('a.post-nm').getAttribute('href') === '/u/C9'
      && c.querySelector('a.post-nm').textContent === 'شركة النور' && c.querySelector('a.post-ava').getAttribute('href') === '/u/C9'
      && !!c.querySelector('.tw-ava--org'));
    check('M4 controller bound once to #hwFeed · views tracked after the render', f.calls.feedClick === 1 && f.calls.observed === 1);

    f.doc.click(c.querySelector('.post-body'));
    f.doc.click(c.querySelector('.pc-btn--cmt'));
    const panel = f.q('#pc-cmt-panel-41');
    check('M5 comment button opens the panel inside the feed card (no navigation)', panel.style.display === ''
      && panel.closest('#hwFeed') === f.feed && !!panel.querySelector('textarea') && f.calls.nav.length === 0, f.calls.nav);
    check('M5b comments loaded from the post', f.calls.api.some(a => a.path === '/company/posts/41/comments' && a.method === 'GET'));
    await tick();
    f.doc.click(c.querySelector('.pc-btn--appr'));
    check('M5c appreciate → PUT on the post path, still no navigation', f.calls.api.some(a => a.path === '/company/posts/41/appreciation'
      && a.method === 'PUT' && a.body.appreciated === false) && f.calls.nav.length === 0);
    panel.querySelector('textarea').value = '@شركة النور مرحبا';
    f.doc.click(panel.querySelector('.pc-cmts-send'));
    await tick(); await tick();
    const sentItem = f.q('.pc-cmt-item[data-cmt-id="9"]'), sent = sentItem && sentItem.querySelector('.pc-cmt-mention');
    check('M6 the post company is in the mention names («@شركة النور» = one mention)', !!sent && sent.textContent === '@شركة النور', sent && sent.textContent);
    const nb = f.doc.createElement('div'); nb.innerHTML = f.ctx.TwPostCard.commentButtonInner(3);
    const cb = c.querySelector('.pc-btn--cmt');
    check('M6b after send: comment button = the card\'s own inner (icon + .tw-act-lbl) with count 3 (task 8.6c)',
      cb.getAttribute('data-cmt-count') === '3' && cb.innerHTML === nb.innerHTML && !!cb.querySelector('.tw-act-lbl')
      && cb.querySelector('.tw-act-lbl').textContent === DICT['post.card.comment_n'].replace('{count}', '3'), cb.innerHTML);

    f.doc.click(f.qa('.hw-ft')[0]); await tick(); await tick();
    f.doc.click(f.qa('.hw-ft')[2]); await tick(); await tick();
    const c2 = f.q('.post-card[data-post-id="41"]');
    check('M7 re-render: same post drawn again, one feed listener, one card / panel id', c2 && c2 !== c
      && f.calls.feedClick === 1 && f.qa('.post-card').length === 1 && f.qa('#pc-cmt-panel-41').length === 1);
    f.doc.click(c2.querySelector('.pc-btn--cmt'));
    const p2 = f.q('#pc-cmt-panel-41');
    check('M7b reopened panel built from scratch (one input row, no old comment, reply strip hidden)', p2.style.display === ''
      && p2.querySelectorAll('.pc-cmts-input-row').length === 1 && !p2.querySelector('.pc-cmt-item[data-cmt-id="9"]')
      && p2.querySelector('.pc-cmt-reply-strip').style.display === 'none' && f.calls.nav.length === 0);

    const cards = read('static/home/home.cards.js'), css = read('static/home-v2.css');
    check('M8 old hw-p post card gone (JS + CSS)', !/hw-p(head|name|sub|body|foot|act)\b/.test(cards + css)
      && !/addEventListener\('click'/.test(cards.slice(cards.indexOf('renderPostCard'), cards.indexOf('renderNewsCard'))));
    const at = x => HOME.indexOf(x);
    check('M9 CSS order: tw-card.css → tw-post-comments.css → home-v2.css (versioned)', at('tw-card.css?v={{v:tw-card.css}}') > 0
      && at('tw-post-comments.css?v={{v:tw-post-comments.css}}') > at('tw-card.css') && at('/static/home-v2.css') > at('tw-post-comments.css'));
    check('M9b JS order: tw-post-card.js → tw-post-comments.js (versioned) → home modules → home.posts.js before render',
      at('tw-post-card.js?v={{v:tw-post-card.js}}') > at('tw-options-data.js') && at('tw-post-comments.js?v={{v:tw-post-comments.js}}') > at('tw-post-card.js')
      && at('/static/home/home.utils.js') > at('tw-post-comments.js') && at('home.posts.js') > at('home.cards.js') && at('home.render.js') > at('home.posts.js'));
  }

  console.log('\nN — ⋯ report / block + comment button (task 8.6c)');
  {
    const CO = { isAuthenticated: true, userId: 5, userType: 'co' };
    const items = h => ['edit', 'delete', 'report', 'block'].filter(k => h.includes('class="pc-dots-' + k + '"'));
    const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
    const own = card(makeCtx({ snap: CO }), {}, { canEdit: true, authorId: 5, viewerId: 5 });
    check('N1 owner (canEdit) → ⋯ edit + delete only', same(items(own), ['edit', 'delete']), items(own));
    const reg = card(makeCtx({ snap: REGISTERED }), {}, { authorId: 5, viewerId: 55, authorTwId: 'C5' });
    check('N2 signed-in non-owner → ⋯ report + block (data-author-id / tw)', same(items(reg), ['report', 'block'])
      && reg.includes('data-author-id="5" data-author-tw="C5"'), items(reg));
    const gst = card(makeCtx(), {}, { authorId: 5, viewerId: null });
    check('N3 guest → ⋯ report only', same(items(gst), ['report']) && gst.includes('pc-dots-btn'), items(gst));
    const self = card(makeCtx({ snap: CO }), {}, { authorId: 5, viewerId: 5, canEdit: false });
    check('N4 company on its own post (viewerId = authorId, no canEdit) → no ⋯ at all', !self.includes('pc-dots'));
    check('N4b ownership from numbers: "5" (string) = 5 · no authorId → no report / block',
      !card(makeCtx({ snap: CO }), {}, { authorId: '5', viewerId: 5 }).includes('pc-dots')
      && !card(makeCtx({ snap: REGISTERED }), {}, { viewerId: 55 }).includes('pc-dots'));
    const xs = card(makeCtx({ snap: REGISTERED }), {}, { authorId: 5, viewerId: 55, authorTwId: '"><b>' });
    check('N4c author tw_id escaped in the attribute', !xs.includes('"><b>') && xs.includes('data-author-tw="&quot;&gt;&lt;b&gt;"'));

    function bootN(o) {
      const b = bootCards({ signedIn: o.signedIn, cardOpts: { authorId: 5, viewerId: o.signedIn === false ? null : 55, authorTwId: 'C5' } });
      const seen = { report: [], block: [], confirm: [] };
      Object.assign(b.ctx, {
        twAccountHref: u => '/u/' + u.tw_id,
        twIconEl: () => b.doc.createElement('span'),   // (the fixture DOM has no <template>)
        twReportDialog: op => seen.report.push(op),
        twBlockUser: id => seen.block.push(id),
        twConfirm: op => { seen.confirm.push(op); return { then: fn => fn(o.confirm !== false) }; },
      });
      return Object.assign(b, { seen });
    }
    const r = bootN({});
    r.click(r.q('.pc-dots-btn')); r.click(r.q('.pc-dots-report'));
    check('N5 report → twReportDialog {reportedId: author, reportedType: company, targetUrl: /u/{tw_id}} · menu closed',
      r.seen.report.length === 1 && r.seen.report[0].reportedId === 5 && r.seen.report[0].reportedType === 'company'
      && r.seen.report[0].targetUrl === '/u/C5' && !r.doc.getElementById('pc-dm-7').classList.contains('open') && r.seen.confirm.length === 0);
    r.click(r.q('.pc-dots-block'));
    const bc = ACTIONS.block.confirm;
    check('N6 block → the registry confirm (twAction path) → twBlockUser(author)', r.seen.confirm.length === 1
      && r.seen.confirm[0].title === DICT[bc.titleKey] && r.seen.confirm[0].danger === true && r.seen.block.length === 1 && r.seen.block[0] === 5);
    const nc = bootN({ confirm: false });
    nc.click(nc.q('.pc-dots-block'));
    check('N6b block cancelled → no twBlockUser', nc.seen.confirm.length === 1 && nc.seen.block.length === 0);
    const g = bootN({ signedIn: false });
    g.click(g.q('.pc-dots-report'));
    check('N7 guest report → login with return path, no dialog, no request', g.seen.report.length === 0
      && g.ctx.location.href === '/login?next=%2Fu%2FC1%3Ftab%3Dposts' && g.calls.api.length === 0 && !g.q('.pc-dots-block'));

    // twReportDialog: targetUrl → target_url · default location.href (real function, stubbed modal / api)
    const rd = vm.createContext({ window: null, String, Number, location: { href: 'https://x.test/u/C5?tab=posts' } });
    rd.window = rd;
    vm.runInContext(fnText(SHARED, 'twReportDialog'), rd);
    const bodies = [];
    Object.assign(rd, {
      twT: k => k, twLimit: () => 0, twReportTypes: () => ['spam'], showToast() {},
      twApi: (p, op) => { bodies.push(op.body); return Promise.resolve({ ok: true }); },
      document: makeDocument(),
      twModal: op => { op.content.querySelector('textarea').value = 'سبب'; op.actions[0].onClick(); return {}; },
    });
    rd.twReportDialog({ reportedId: 5, reportedType: 'company', targetUrl: '/u/C5' });
    rd.twReportDialog({ reportedId: 9, reportedType: 'user' });
    check('N8 twReportDialog: targetUrl sent as target_url · without it = location.href', bodies.length === 2
      && bodies[0].target_url === '/u/C5' && bodies[0].reported_type === 'company' && bodies[0].reported_id === 5
      && bodies[1].target_url === 'https://x.test/u/C5?tab=posts', JSON.stringify(bodies));

    const ctx = makeCtx();
    const inner = n => ctx.TwPostCard.commentButtonInner(n);
    const icon = ctx.twIcon('comment', { size: 'sm' });
    const HOMEH = read('home-v2.html');
    check('N7b /home loads DS-OVL (twConfirm / twModal for block / report) before the card', HOMEH.indexOf('tw-overlay.js?v={{v:tw-overlay.js}}') > 0
      && HOMEH.indexOf('tw-overlay.js') < HOMEH.indexOf('tw-post-card.js'));
    check('N9 commentButtonInner(0) = comment icon + label «post.card.comment»',
      inner(0) === icon + '<span class="tw-act-lbl">' + DICT['post.card.comment'] + '</span>');
    check('N9b commentButtonInner(3) = icon + «post.card.comment_n» with 3 · the card uses it',
      inner(3) === icon + '<span class="tw-act-lbl">' + DICT['post.card.comment_n'].replace('{count}', '3') + '</span>'
      && card(ctx, { comments_count: 3 }).includes('data-cmt-count="3">' + inner(3) + '</button>'));
  }

  console.log('\n' + passed + ' passed, ' + failed + ' failed');
  process.exit(failed ? 1 : 0);
}());
