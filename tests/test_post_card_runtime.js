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
  '_twActDef', '_twActAudience', 'twActionState'];
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
  ctx.companyState = { profile: { full_name: 'شركة', avatar_url: '' }, permissions: { can_edit: true } };
  ctx.renderPosts([BASE, Object.assign({}, BASE, { id: 8 })]);
  check('D2.2 TwPostCard.html called per post (author type co)', calls === 2 && lastOpts.authorType === 'co');
  check('D2.3 owner list has ⋯', (list.innerHTML.match(/pc-dots-btn/g) || []).length === 2);
  ctx.companyState.permissions = { can_edit: false };
  ctx.renderPosts([BASE]);
  check('D2.4 visitor list has no ⋯', !list.innerHTML.includes('pc-dots-btn') && list.innerHTML.includes('pc-btn--appr'));
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
    check('K10 company page loads tw-card.css (versioned) right before company.css', iCard > 0 && iPage > iCard
      && !/<link[^>]*>/.test(html.slice(html.indexOf('>', iCard) + 1, iPage)));
  }

  console.log('\n' + passed + ' passed, ' + failed + ' failed');
  process.exit(failed ? 1 : 0);
}());
