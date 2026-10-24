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

console.log('\n' + passed + ' passed, ' + failed + ' failed');
process.exit(failed ? 1 : 0);
