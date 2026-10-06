/**
 * test_ds_image_runtime.js — PR-7b: §54 image-URL fix + DS-IMAGE foundation (F38)
 *
 * Runs the REAL tw_shared.js in a vm with a minimal fake DOM.
 *   A1  twSafeImageUrl: https / root-relative only (javascript:, data:, vbscript:, http:, //, /\ rejected)
 *   A2  twCssUrl: validated + CSS-string escaped (no breakout from url("…"))
 *   A3  the three profile-v2 sites (.sc-avatar · .sc-fl-avatar · employee cover) use the helpers
 *   B1  twAvatarHtml / twAvatarEl: sizes · types · letter · escaping · eager/lazy · invalid URL → fallback
 *   B2  one capture error listener flips [data-tw-ava] to data-fb="1"
 *   B3  consumers = phase-C pages only (allowlist — one approved PR per page)
 *
 * Run: node test_ds_image_runtime.js
 */
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = __dirname;
let failures = 0;
function check(name, ok, detail) {
  console.log((ok ? 'PASS ' : 'FAIL ') + name + (!ok && detail ? ' — ' + detail : ''));
  if (!ok) failures++;
}

// ── Minimal fake DOM ────────────────────────────────────────────────
function makeEl(tag) {
  return {
    tagName: String(tag).toUpperCase(),
    className: '',
    textContent: '',
    attrs: {},
    children: [],
    parentNode: null,
    setAttribute(k, v) { this.attrs[k] = String(v); },
    getAttribute(k) { return Object.prototype.hasOwnProperty.call(this.attrs, k) ? this.attrs[k] : null; },
    hasAttribute(k) { return Object.prototype.hasOwnProperty.call(this.attrs, k); },
    appendChild(c) { c.parentNode = this; this.children.push(c); return c; },
  };
}
const docListeners = [];
const fakeDocument = {
  createElement: makeEl,
  addEventListener(type, fn, capture) { docListeners.push({ type, fn, capture }); },
  querySelectorAll() { return []; },
  getElementById() { return null; },
  body: { appendChild() {}, style: {} },
  documentElement: { style: {} },
};
const fakeWindow = { addEventListener() {}, location: { href: '', pathname: '/' } };
const ctx = {
  window: fakeWindow, document: fakeDocument,
  localStorage: { getItem() { return null; }, setItem() {}, removeItem() {} },
  navigator: { userAgent: 'node' }, location: fakeWindow.location,
  console, setTimeout, clearTimeout, setInterval, clearInterval, fetch: () => Promise.resolve({}),
};
ctx.self = ctx.window;
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(path.join(ROOT, 'tw_shared.js'), 'utf8'), ctx, { filename: 'tw_shared.js' });

const { twSafeImageUrl, twCssUrl, twEscAttr, twAvatarHtml, twAvatarEl } = fakeWindow;
check('exports on window', [twSafeImageUrl, twCssUrl, twAvatarHtml, twAvatarEl].every(f => typeof f === 'function'));

// ── A1 ──────────────────────────────────────────────────────────────
const GOOD = 'https://x.supabase.co/storage/v1/object/public/avatars/1_employee-avatar_abc.jpg';
const OK = [GOOD, 'HTTPS://cdn.example.com/a.png', '/static/img/Cover.png', '/a"b'];
const BAD = ['javascript:alert(1)', 'JaVaScRiPt:alert(1)', 'data:image/png;base64,AAAA',
  'data:text/html,<script>alert(1)</script>', 'vbscript:msgbox(1)', 'http://x.com/a.png',
  '//evil.com/a.png', '/\\evil.com/a.png', ' https://x.com/a.png', '\tjavascript:alert(1)',
  'blob:https://x/1', 'a.png', '', null, undefined, 42, {}];
OK.forEach(u => check('A1 accept ' + JSON.stringify(u), twSafeImageUrl(u) === u));
BAD.forEach(u => check('A1 reject ' + JSON.stringify(u), twSafeImageUrl(u) === ''));

// ── A2 ──────────────────────────────────────────────────────────────
check('A2 valid → url("…")', twCssUrl(GOOD) === 'url("' + GOOD + '")');
check('A2 javascript: → ""', twCssUrl('javascript:alert(1)') === '');
check('A2 data: → ""', twCssUrl('data:image/png;base64,AAAA') === '');
const breakout = twCssUrl('/a.png");background:url("https://evil/x');
check('A2 " escaped (no breakout)', breakout.indexOf('"', 5) === breakout.length - 2 && breakout.includes('\\22 '), breakout);
const bs = twCssUrl('/a\\b\nc');
check('A2 \\ and newline escaped', bs === 'url("/a\\5c b\\a c")', bs);

// ── A3 — the three sites (source checks + the exact expressions) ────
const render = fs.readFileSync(path.join(ROOT, 'profile-v2.render.js'), 'utf8');
const cover = fs.readFileSync(path.join(ROOT, 'profile-v2.cover.js'), 'utf8');
check('A3 .sc-avatar: img.src = avatarSrc (no esc())', /var avatarSrc=twSafeImageUrl\(p\.avatar_url\)/.test(render)
  && /img\.src=avatarSrc;/.test(render) && !/img\.src=esc\(/.test(render));
check('A3 .sc-fl-avatar: twSafeImageUrl + twEscAttr', /twSafeImageUrl\(item\.avatar_url\)/.test(render)
  && /src="' \+ twEscAttr\(flAvatarSrc\)/.test(render) && !/esc\(item\.avatar_url\)/.test(render));
check('A3 followers href uses twEscAttr', /href="\/u\/' \+ twEscAttr\(item\.tw_id\)/.test(render));
check('A3 cover (render) uses twCssUrl', /twCssUrl\(p\.cover_url\)/.test(render) && !/url\(' \+ esc\(p\.cover_url\)/.test(render));
check('A3 cover (upload) uses twCssUrl', /twCssUrl\(coverUrl\)/.test(cover) && !/'url\(' \+ coverUrl/.test(cover));

// Followers item markup as built by _renderItems (attribute context)
function flAvatar(url) {
  const s = twSafeImageUrl(url);
  return s ? '<img class="sc-fl-avatar" src="' + twEscAttr(s) + '" alt="">' : 'PH';
}
check('A3 fl: javascript: → placeholder', flAvatar('javascript:alert(1)') === 'PH');
check('A3 fl: data: → placeholder', flAvatar('data:image/png;base64,AA') === 'PH');
check('A3 fl: " in URL cannot break attribute',
  flAvatar('/a.png" onerror="alert(1)') === '<img class="sc-fl-avatar" src="/a.png&quot; onerror=&quot;alert(1)" alt="">');
check('A3 fl: valid URL kept', flAvatar(GOOD).includes('src="' + GOOD + '"'));
check('A3 fl: tw_id with " escaped', ('href="/u/' + twEscAttr('U1" onclick="x') + '"') === 'href="/u/U1&quot; onclick=&quot;x"');

// ── B1 — avatar markup ──────────────────────────────────────────────
const PX = { md: 40, lg: 48, xl: 88, '2xl': 106 };
for (const size of Object.keys(PX)) {
  for (const t of ['emp', 'co', 'edu']) {
    const ent = { full_name: 'سارة', avatar_url: GOOD, user_type: t };
    const h = twAvatarHtml(ent, size);
    const shape = t === 'emp' ? 'emp' : 'org';
    check(`B1 html ${size}/${t} classes`, h.startsWith(`<span class="tw-ava tw-ava--${size} tw-ava--${shape}" data-tw-ava="${t}">`), h);
    check(`B1 html ${size}/${t} img w/h=${PX[size]}`, h.includes(`width="${PX[size]}" height="${PX[size]}"`)
      && h.includes('alt="" decoding="async" loading="lazy"'));
    const el = twAvatarEl(ent, size);
    check(`B1 el ${size}/${t}`, el.className === `tw-ava tw-ava--${size} tw-ava--${shape}` && el.getAttribute('data-tw-ava') === t
      && el.children[0].tagName === 'IMG' && el.children[0].getAttribute('width') === String(PX[size])
      && el.children[0].getAttribute('src') === GOOD && !el.hasAttribute('data-fb'));
  }
}
check('B1 unknown size → md', twAvatarHtml({ full_name: 'a' }, 'huge').includes('tw-ava--md'));
check('B1 unknown type → emp', twAvatarHtml({ full_name: 'a', user_type: 'admin' }, 'md').includes('data-tw-ava="emp"'));
check('B1 null entity safe', twAvatarHtml(null, 'md').includes('>؟</span>'));

const letter = h => (h.match(/<span class="tw-ava__fb" aria-hidden="true">([\s\S]*?)<\/span>/) || [])[1];
check('B1 empty name → ؟', letter(twAvatarHtml({ full_name: '   ' }, 'md')) === '؟');
check('B1 missing name → ؟', twAvatarEl({}, 'md').children[0].textContent === '؟');
check('B1 Arabic first letter', letter(twAvatarHtml({ full_name: '  محمد علي' }, 'md')) === 'م');
check('B1 no toUpperCase', letter(twAvatarHtml({ full_name: 'ahmad' }, 'md')) === 'a');
check('B1 emoji/surrogate kept whole', letter(twAvatarHtml({ full_name: '😀 Ali' }, 'md')) === '😀'
  && twAvatarEl({ full_name: '𝒜bc' }, 'md').children[0].textContent === '𝒜');
check('B1 name " escaped', letter(twAvatarHtml({ full_name: '"x' }, 'md')) === '&quot;');
check('B1 name < escaped', letter(twAvatarHtml({ full_name: '<script>alert(1)</script>' }, 'md')) === '&lt;');

for (const bad of ['javascript:alert(1)', 'data:image/png;base64,AA', 'vbscript:x', '//evil.com/a.png']) {
  const h = twAvatarHtml({ full_name: 'x', avatar_url: bad }, 'lg');
  const el = twAvatarEl({ full_name: 'x', avatar_url: bad }, 'lg');
  check('B1 bad URL → fallback ' + bad, !h.includes('<img') && h.includes('data-fb="1"')
    && el.getAttribute('data-fb') === '1' && el.children.length === 1 && el.children[0].className === 'tw-ava__fb');
}
const q = twAvatarHtml({ full_name: 'x', avatar_url: '/a.png" onload="alert(1)' }, 'md');
check('B1 " in URL escaped in src', q.includes('src="/a.png&quot; onload=&quot;alert(1)"'), q);
check('B1 no inline handlers', !/\son\w+=/.test(twAvatarHtml({ full_name: 'x', avatar_url: GOOD }, 'md')));

check('B1 eager (html)', twAvatarHtml({ avatar_url: GOOD }, '2xl', { eager: true }).includes('loading="eager"'));
check('B1 eager (el)', twAvatarEl({ avatar_url: GOOD }, '2xl', { eager: true }).children[0].getAttribute('loading') === 'eager');
check('B1 default lazy (el)', twAvatarEl({ avatar_url: GOOD }, 'xl').children[0].getAttribute('loading') === 'lazy');

// ── B2 — capture error listener ─────────────────────────────────────
const errL = docListeners.filter(l => l.type === 'error');
check('B2 exactly one document error listener, capture', errL.length === 1 && errL[0].capture === true);
const ava = twAvatarEl({ full_name: 'x', avatar_url: GOOD, user_type: 'co' }, 'xl');
errL[0].fn({ target: ava.children[0] });
check('B2 img error → data-fb="1" on [data-tw-ava]', ava.getAttribute('data-fb') === '1');
const other = makeEl('div'); const oimg = other.appendChild(makeEl('img'));
errL[0].fn({ target: oimg });
check('B2 ignores img outside [data-tw-ava]', !other.hasAttribute('data-fb'));
errL[0].fn({ target: makeEl('script') }); errL[0].fn({ target: null });
check('B2 ignores non-img / null targets', true);

// ── B3 — consumers = phase-C pages only ─────────────────────────────
const PHASE_C = [path.join('static', 'job', 'job-detail.js')];
const SKIP = new Set(['.git', 'node_modules', 'vendor', '__pycache__', 'docs']);
const users = [];
(function walk(dir) {
  for (const f of fs.readdirSync(dir, { withFileTypes: true })) {
    if (f.isDirectory()) { if (!SKIP.has(f.name)) walk(path.join(dir, f.name)); continue; }
    if (!/\.(html|js|mjs)$/.test(f.name)) continue;
    const rel = path.relative(ROOT, path.join(dir, f.name));
    if (rel === 'tw_shared.js' || /^test_/.test(f.name) || rel.startsWith('tests' + path.sep)) continue;
    if (/twAvatar(Html|El)|data-tw-ava|tw-ava/.test(fs.readFileSync(path.join(dir, f.name), 'utf8'))) users.push(rel);
  }
})(ROOT);
check('B3 twAvatar* / .tw-ava used only by phase-C pages',
  JSON.stringify(users.slice().sort()) === JSON.stringify(PHASE_C.slice().sort()), users.join(', '));

const css = fs.readFileSync(path.join(ROOT, 'tw_shared.css'), 'utf8');
const avaCss = css.slice(css.indexOf('16. DS-IMAGE'));
check('B3 .tw-ava CSS uses tokens only (no hex / raw px)', avaCss.includes('.tw-ava {')
  && !/#[0-9a-f]{3,8}\b/i.test(avaCss.split('⚠️')[0]) && !/:\s*\d+px/.test(avaCss.split('⚠️')[0]));

console.log(failures ? `\n${failures} FAILED` : '\nALL PASS');
process.exit(failures ? 1 : 0);
