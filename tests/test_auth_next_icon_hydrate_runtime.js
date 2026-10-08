/**
 * test_auth_next_icon_hydrate_runtime.js — PR-558: F30 follow-ups of PR #557 (job-detail)
 * Runs the REAL tw_shared.js + auth-sync.js + index.auth.js + tw-icons.js in Node vm contexts.
 *   A  twSafeNext / twLoginHref — internal path only (open-redirect guard, NAV-07)
 *   B  index.auth.js — safe ?next= wins after login / on entry; unsafe ?next= ignored
 *   C  twIcon.hydrate — known / unknown / hostile name · second call is a no-op
 *   D  publisher type — company_user_type 'edu' → tw-ava--org + data-tw-ava="edu" (edu colour)
 *
 * Run: node tests/test_auth_next_icon_hydrate_runtime.js
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
const noop = () => {};

function b64url(obj) {
  return Buffer.from(JSON.stringify(obj)).toString('base64')
    .replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}
const now = Math.floor(Date.now() / 1000);
const USER = { id: 7, tw_id: 'U9620abcdef1234', user_type: 'emp' };
const JWT = b64url({ alg: 'HS256' }) + '.' + b64url({ user_id: 7, user_type: 'emp', exp: now + 3600 }) + '.sig';

// Auth Gateway context: tw_shared.js → auth-sync.js → index.auth.js (same order as index.html)
function gateway(search, loggedIn) {
  const store = loggedIn ? { tw_user: JSON.stringify(USER), tw_jwt: JWT } : {};
  const nav = { replaced: null, href: '' };
  const doc = {
    visibilityState: 'visible', addEventListener: noop,
    getElementById: () => null, querySelector: () => null, querySelectorAll: () => [],
    createElement: () => ({ style: {}, setAttribute: noop, appendChild: noop, classList: { add: noop } }),
    body: { appendChild: noop, classList: { add: noop } }, documentElement: { style: {} },
  };
  const ctx = {
    localStorage: {
      getItem: k => Object.prototype.hasOwnProperty.call(store, k) ? store[k] : null,
      setItem: (k, v) => { store[k] = String(v); }, removeItem: k => { delete store[k]; },
    },
    document: doc, console, URLSearchParams, encodeURIComponent,
    atob: s => Buffer.from(s, 'base64').toString('binary'),
    setTimeout: () => 0, clearTimeout: noop, setInterval: () => 0, clearInterval: noop,
    navigator: { userAgent: 'node' },
  };
  ctx.window = ctx;
  ctx.addEventListener = noop;
  ctx.location = {
    protocol: 'http:', host: 'x', pathname: '/login', search: search || '',
    replace: u => { nav.replaced = u; },
    set href(u) { nav.href = u; }, get href() { return nav.href; },
  };
  vm.createContext(ctx);
  ['tw_shared.js', 'static/shared/auth-sync.js', 'index.auth.js']
    .forEach(f => vm.runInContext(read(f), ctx, { filename: f }));
  return { ctx, nav };
}

const ACCOUNT = '/u/' + USER.tw_id;
const EVIL = ['https://evil.com', '//evil.com', '/\\evil.com', 'javascript:alert(1)',
              '/\t/evil.com', 'http://evil.com/x', '/login', '/login?next=/x', ''];

console.log('\nA — twSafeNext / twLoginHref (tw_shared.js)');
{
  const { ctx } = gateway('', false);
  check('A1 internal path kept', ctx.twSafeNext('/job-detail?id=42') === '/job-detail?id=42');
  check('A2 /u/{tw_id} kept', ctx.twSafeNext('/u/C962abc') === '/u/C962abc');
  EVIL.forEach((n, i) => check('A3.' + i + ' rejected: ' + JSON.stringify(n), ctx.twSafeNext(n) === ''));
  check('A4 non-string rejected', ctx.twSafeNext(null) === '' && ctx.twSafeNext(42) === '');
  check('A5 longer than 512 rejected', ctx.twSafeNext('/' + 'a'.repeat(512)) === '');
  check('A6 twLoginHref encodes the path',
    ctx.twLoginHref('/job-detail?id=42') === '/login?next=%2Fjob-detail%3Fid%3D42');
  check('A7 twLoginHref(unsafe) → plain /login',
    EVIL.every(n => ctx.twLoginHref(n) === '/login'));
}

console.log('\nB — index.auth.js (after login + on-load entry check)');
{
  const ok = gateway('?next=' + encodeURIComponent('/job-detail?id=42'), false);
  ok.ctx.redirect(USER);
  check('B1 login with safe next → back to the job', ok.nav.href === '/job-detail?id=42', ok.nav.href);

  const plain = gateway('', false);
  plain.ctx.redirect(USER);
  check('B2 login without next → twAccountHref', plain.nav.href === ACCOUNT, plain.nav.href);

  ['https://evil.com', '//evil.com', '/\\evil.com', 'javascript:alert(1)'].forEach((n, i) => {
    const g = gateway('?next=' + encodeURIComponent(n), false);
    g.ctx.redirect(USER);
    check('B3.' + i + ' login with ' + JSON.stringify(n) + ' → ignored (account)', g.nav.href === ACCOUNT, g.nav.href);
  });

  const entry = gateway('?next=' + encodeURIComponent('/job-detail?id=42'), true);
  check('B4 already logged in + safe next → entry check goes to next',
    entry.nav.replaced === '/job-detail?id=42', entry.nav.replaced);
  const entryEvil = gateway('?next=' + encodeURIComponent('//evil.com'), true);
  check('B5 already logged in + unsafe next → twEntryDestination()',
    entryEvil.nav.replaced === ACCOUNT, entryEvil.nav.replaced);
  const guest = gateway('?next=' + encodeURIComponent('/job-detail?id=42'), false);
  check('B6 guest + next → no redirect (stays on the login form)',
    guest.nav.replaced === null && guest.nav.href === '');
}

console.log('\nC — twIcon.hydrate (tw-icons.js)');
{
  // Minimal DOM: element tree with querySelectorAll('i[data-tw-icon]') + <template>.
  function node(tag, attrs) {
    return {
      tagName: tag.toUpperCase(), attrs: Object.assign({}, attrs || {}), children: [], parentNode: null,
      getAttribute(k) { return Object.prototype.hasOwnProperty.call(this.attrs, k) ? this.attrs[k] : null; },
      hasAttribute(k) { return Object.prototype.hasOwnProperty.call(this.attrs, k); },
      appendChild(c) { c.parentNode = this; this.children.push(c); return c; },
      replaceChild(n, old) {
        const i = this.children.indexOf(old);
        this.children[i] = n; n.parentNode = this; old.parentNode = null; return old;
      },
      querySelectorAll(sel) {
        const out = [];
        (function walk(el) {
          el.children.forEach(c => {
            if (sel === 'i[data-tw-icon]' && c.tagName === 'I' && c.hasAttribute('data-tw-icon')) out.push(c);
            walk(c);
          });
        }(this));
        return out;
      },
    };
  }
  const ctx = {
    console: { warn: noop, log: noop },
    document: {
      head: null,
      createElement(tag) {
        if (tag !== 'template') return node(tag);
        const t = { content: { firstChild: null } };
        Object.defineProperty(t, 'innerHTML', { set(h) { t.content.firstChild = { tagName: 'SVG', html: h, parentNode: null, children: [] }; } });
        return t;
      },
    },
  };
  ctx.window = ctx;
  vm.createContext(ctx);
  vm.runInContext(read('static/shared/tw-icons.js'), ctx, { filename: 'tw-icons.js' });
  const twIcon = ctx.twIcon;

  const root = node('div');
  const btn = root.appendChild(node('button'));
  btn.appendChild(node('i', { 'data-tw-icon': 'bookmark', 'data-tw-size': 'sm' }));
  root.appendChild(node('i', { 'data-tw-icon': 'no-such-icon' }));
  root.appendChild(node('i', { 'data-tw-icon': '"><img src=x onerror=alert(1)>', 'data-tw-size': 'xl"><b' }));
  root.appendChild(node('i', { 'data-tw-icon': 'star', 'data-tw-size': 'xs', 'data-tw-filled': '' }));
  const outside = node('i', { 'data-tw-icon': 'share' });   // not inside root → untouched

  const n1 = twIcon.hydrate(root);
  const html = [btn.children[0]].concat(root.children.slice(1)).map(c => c.html);
  check('C1 hydrate returns the number of icons', n1 === 4, n1);
  check('C2 known name = the same SVG as twIcon(name, { size })', html[0] === twIcon('bookmark', { size: 'sm' }));
  check('C3 unknown name → FALLBACK drawing', html[1] === twIcon('help'));
  check('C4 hostile name / size never reach the HTML',
    html[2] === twIcon('help') && !/img|onerror|<b/.test(html[2]));
  check('C5 data-tw-filled → filled SVG', html[3] === twIcon('star', { size: 'xs', filled: true }));
  check('C6 placeholders replaced in place (no wrapper <i> left)',
    root.querySelectorAll('i[data-tw-icon]').length === 0 && btn.children.length === 1);
  const n2 = twIcon.hydrate(root);
  check('C7 second hydrate is a no-op (no duplicate icon)',
    n2 === 0 && btn.children.length === 1 && root.children.length === 4);
  check('C8 elements outside root untouched', outside.tagName === 'I' && !outside.html);
  check('C9 bad root → 0, no throw', twIcon.hydrate({}) === 0);
}

console.log('\nD — publisher account type (DS-IMAGE)');
{
  const { ctx } = gateway('', false);
  const edu = ctx.twAvatarHtml({ full_name: 'جامعة', avatar_url: '', user_type: 'edu' }, 'xl');
  const co  = ctx.twAvatarHtml({ full_name: 'شركة', avatar_url: '', user_type: 'co' }, 'xl');
  check('D1 edu → org shape + data-tw-ava="edu"', edu.includes('tw-ava--org') && edu.includes('data-tw-ava="edu"'));
  check('D2 co → org shape + data-tw-ava="co"', co.includes('tw-ava--org') && co.includes('data-tw-ava="co"'));
  check('D3 edu fallback colour rule exists (tw_shared.css)',
    read('tw_shared.css').includes('.tw-ava[data-tw-ava="edu"] > .tw-ava__fb'));
  const js = read('static/job/job-detail.js');
  check('D4 job-detail passes company_user_type (not a fixed \'co\')',
    js.includes("user_type: job.company_user_type === 'edu' ? 'edu' : 'co'") && !js.includes("user_type: 'co' }"));
  check('D5 GET /jobs/{id} returns company_user_type (users.user_type)',
    read('auth.py').includes('"u.user_type AS company_user_type, "'));
}

console.log('\nTests run: ' + (passed + failed) + '  |  Passed: ' + passed + '  |  Failed: ' + failed);
process.exit(failed ? 1 : 0);
