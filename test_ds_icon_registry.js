/**
 * test_ds_icon_registry.js — DS-ICON (F37 · docs/design-system/ICON-SYSTEM.md)
 * Loads the REAL static/shared/tw-icons.js and checks:
 *   1. every catalog icon name (skill_catalog + profession_categories seeds in auth.py,
 *      TW.SKILL_CATALOG fallback) resolves in the registry
 *   2. LINK_ICONS · _FILTER_ICONS · header menu · skill-icon fallbacks have a registry name
 *   3. unknown name → fallback drawing + one warning; the name never reaches the output
 *   4. output contract (viewBox / fill / stroke / class / aria-hidden / DS-SIZE size)
 *   5. every drawing is a Lucide 0.460 drawing (vendored bundle)
 *   6. tw-icons.js is loaded only by the pages converted in phase C (allowlist)
 *   7. dir:true icons mirror under dir=rtl and not under dir=ltr (real Chromium via
 *      Playwright; reported as SKIP when Playwright is not installed)
 *
 * Run: node test_ds_icon_registry.js
 */
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

let passed = 0, failed = 0;
function check(name, cond, extra) {
  if (cond) { passed++; console.log('  PASS  ' + name); }
  else      { failed++; console.log('  FAIL  ' + name + (extra ? '  → ' + extra : '')); }
}
const read = f => fs.readFileSync(f, 'utf8');
const SRC = read('static/shared/tw-icons.js');

// ── load registry in a vm (no document → style injection skipped) ──
const warns = [];
const ctx = { console: { warn: m => warns.push(m), log() {} } };
ctx.window = ctx;
vm.createContext(ctx);
vm.runInContext(SRC, ctx);
const twIcon = ctx.twIcon;
check('twIcon / twIconEl / twIcon.has exported', typeof twIcon === 'function'
  && typeof ctx.twIconEl === 'function' && typeof twIcon.has === 'function');

function missing(names) { return [...new Set(names)].filter(n => !twIcon.has(n)); }

// ── 1. catalog names ───────────────────────────────────────────────
const auth = read('auth.py');
const seedBody = auth.slice(auth.indexOf('_SKILL_SEED = ['), auth.indexOf('# Insert in batches'));
const skillIcons = [...seedBody.matchAll(/\('(?:[^'\\]|\\.)*',\s*'(?:[^'\\]|\\.)*',\s*'(?:[^'\\]|\\.)*',\s*'(?:[^'\\]|\\.)*',\s*'([^']*)',\s*'[^']*',\s*\d+\)/g)].map(m => m[1]);
const profStart = auth.indexOf('INSERT INTO profession_categories (name_ar');
const profBody = auth.slice(profStart, auth.indexOf('ON CONFLICT', profStart));
const profIcons = [...profBody.matchAll(/\('[^']*','[^']*','[^']*','([^']*)','[^']*',\d+\)/g)].map(m => m[1]);
const opt = read('static/shared/tw-options-data.js');
const fbBody = opt.slice(opt.indexOf('TW.SKILL_CATALOG = ['), opt.indexOf('];', opt.indexOf('TW.SKILL_CATALOG = [')));
const fbIcons = [...fbBody.matchAll(/icon:\s*'([a-z0-9-]+)'/g)].map(m => m[1]);
check('skill_catalog seed parsed (≥ 300 rows)', skillIcons.length >= 300, skillIcons.length);
check('profession_categories seed parsed (≥ 50 rows)', profIcons.length >= 50, profIcons.length);
check('TW.SKILL_CATALOG fallback parsed (≥ 80 rows)', fbIcons.length >= 80, fbIcons.length);
check('every skill_catalog.icon is in the registry', missing(skillIcons).length === 0, missing(skillIcons));
check('every profession_categories.icon is in the registry', missing(profIcons).length === 0, missing(profIcons));
check('every TW.SKILL_CATALOG icon is in the registry', missing(fbIcons).length === 0, missing(fbIcons));

// ── 2. maps used by pages today ────────────────────────────────────
const links = read('profile-v2.links.js');
const linkBody = links.slice(links.indexOf('var LINK_ICONS'), links.indexOf('};', links.indexOf('var LINK_ICONS')));
const linkIcons = [...linkBody.matchAll(/\w+\s*:\s*'([a-z0-9-]+)'/g)].map(m => m[1]);
check('LINK_ICONS parsed (8 types)', linkIcons.length === 8, linkIcons);
check('every LINK_ICONS value is in the registry', missing(linkIcons).length === 0, missing(linkIcons));
const linkDefault = (links.match(/LINK_ICONS\[ltype\]\s*\|\|\s*'([a-z0-9-]+)'/) || [])[1];
check('LINK_ICONS default is in the registry', !!linkDefault && twIcon.has(linkDefault), linkDefault);

// _FILTER_ICONS holds inline SVGs today → each key needs a registry meaning (phase C target)
const FILTER_TO_REGISTRY = {
  'null': 'list', saved: 'bookmark', shortlisted: 'star', contacted: 'comment',
  interview: 'calendar', hired: 'success', rejected: 'error', _unlinked: 'user-minus',
};
const cm = read('static/company/company.main.js');
const fBody = cm.slice(cm.indexOf('var _FILTER_ICONS'), cm.indexOf('};', cm.indexOf('var _FILTER_ICONS')));
const filterKeys = [...fBody.matchAll(/^\s*'([^']+)'\s*:/gm)].map(m => m[1]);
check('_FILTER_ICONS keys = mapped keys', JSON.stringify(filterKeys.slice().sort())
  === JSON.stringify(Object.keys(FILTER_TO_REGISTRY).sort()), filterKeys);
check('every _FILTER_ICONS meaning is in the registry',
  missing(Object.values(FILTER_TO_REGISTRY)).length === 0, missing(Object.values(FILTER_TO_REGISTRY)));

const HEADER_TO_REGISTRY = {
  settings: 'settings', candidates: 'search', contact: 'phone', report: 'alert',
  suggest: 'edit', logout: 'log-out', login: 'log-in', register: 'user-plus',
};
const tws = read('tw_shared.js');
const hBody = tws.slice(tws.indexOf('var _TW_HEADER_MENU_POLICY'), tws.indexOf('];', tws.indexOf('var _TW_HEADER_MENU_POLICY')));
const headerKeys = [...hBody.matchAll(/key:\s*'([^']+)'/g)].map(m => m[1]);
check('header menu keys = mapped keys', JSON.stringify(headerKeys.slice().sort())
  === JSON.stringify(Object.keys(HEADER_TO_REGISTRY).sort()), headerKeys);
check('every header menu meaning is in the registry',
  missing(Object.values(HEADER_TO_REGISTRY)).length === 0, missing(Object.values(HEADER_TO_REGISTRY)));

const skFb = (read('static/shared/tw-skills.js').match(/_FALLBACK_ICON\s*=\s*'([a-z0-9-]+)'/) || [])[1];
const pvFb = (read('profile-v2.skills.js').match(/_CUSTOM_FALLBACK_ICON\s*=\s*'([a-z0-9-]+)'/) || [])[1];
check('TW.getSkillIcon fallback is in the registry', !!skFb && twIcon.has(skFb), skFb);
check('profile-v2 custom-skill fallback is in the registry', !!pvFb && twIcon.has(pvFb), pvFb);
check('job-detail skill fallback "tag" is in the registry', twIcon.has('tag'));

// ── 3. unknown name / injection ────────────────────────────────────
const fallbackSvg = twIcon('help');
warns.length = 0;
check('unknown name → fallback drawing', twIcon('no-such-icon') === fallbackSvg);
twIcon('no-such-icon');
check('unknown name warns once', warns.length === 1, warns);
const evil = '"><script>alert(1)</script><x y="';
const evilOut = twIcon(evil);
check('injection name → fallback drawing', evilOut === fallbackSvg);
check('injection name never reaches the output', !/script|alert\(1\)/.test(evilOut));
check('non-string name → fallback', twIcon({ toString() { return 'x'; } }) === fallbackSvg
  && twIcon(null) === fallbackSvg);
check('prototype keys are not icons', !twIcon.has('__proto__') && !twIcon.has('constructor')
  && !twIcon.has('toString') && twIcon('constructor') === fallbackSvg);
check('className tokens filtered', !/onload|"x/.test(twIcon('add', { className: 'ok-1 x" onload="y' }))
  && /class="tw-ico ok-1"/.test(twIcon('add', { className: 'ok-1 x" onload="y' })));
check('manual arrow / chevron names are not registry names',
  ['arrow-left', 'arrow-right', 'chevron-left', 'chevron-right'].every(n => !twIcon.has(n)));

// ── 4. output contract ─────────────────────────────────────────────
const out = twIcon('briefcase');
check('viewBox 0 0 24 24', /viewBox="0 0 24 24"/.test(out));
check('fill none · stroke currentColor · stroke-width 2', /fill="none"/.test(out)
  && /stroke="currentColor"/.test(out) && /stroke-width="2"/.test(out));
check('class tw-ico · aria-hidden', /class="tw-ico"/.test(out) && /aria-hidden="true"/.test(out));
check('no size → width/height 24 (page CSS sizes it)', /width="24" height="24"/.test(out) && !/style=/.test(out));
check('size md → var(--size-icon-md, 16px)',
  twIcon('briefcase', { size: 'md' }).includes('style="width:var(--size-icon-md, 16px);height:var(--size-icon-md, 16px)"'));
check('size 2xl → var(--size-icon-2xl, 22px)', twIcon('briefcase', { size: '2xl' }).includes('var(--size-icon-2xl, 22px)'));
warns.length = 0;
const badSize = twIcon('briefcase', { size: '15px;background:red' });
check('unknown size ignored + warned', /width="24" height="24"/.test(badSize) && !/background/.test(badSize) && warns.length === 1);
check('filled → fill currentColor', /fill="currentColor"/.test(twIcon('heart', { filled: true })));
const DIR = ['back', 'forward', 'prev', 'next', 'send', 'log-in', 'log-out'];
check('meaning names with dir:true carry tw-ico-dir', DIR.every(n => /class="tw-ico tw-ico-dir"/.test(twIcon(n))));
check('non-directional icons have no tw-ico-dir', !/tw-ico-dir/.test(twIcon('home')) && !/tw-ico-dir/.test(twIcon('search')));
check('only colour is currentColor (no hex / rgb in the registry)', !/#[0-9a-fA-F]{3,6}\b|rgb\(/.test(SRC.replace(/^\s*\/\/.*$/gm, '')));

// ── 5. drawings = Lucide 0.460 ─────────────────────────────────────
const entries = [...SRC.matchAll(/^\s*'([a-z0-9-]+)':\s*\[([01]),\s*'([^']*)'\]/gm)].map(m => ({ name: m[1], dir: m[2], inner: m[3] }));
const lucideSrc = read('static/vendor/lucide/lucide.min.js');
check('vendored Lucide is 0.460.0', /@license lucide v0\.460\.0/.test(lucideSrc));
const lctx = { globalThis: null };
lctx.self = lctx; lctx.globalThis = lctx;
vm.createContext(lctx);
vm.runInContext(lucideSrc, lctx);
const ORDER = ['d', 'cx', 'cy', 'r', 'rx', 'ry', 'x', 'y', 'width', 'height', 'x1', 'y1', 'x2', 'y2', 'points', 'fill'];
const lucideInners = new Set(Object.values(lctx.lucide.icons).map(n => n[2].map(c => '<' + c[0]
  + Object.keys(c[1]).sort((a, b) => ORDER.indexOf(a) - ORDER.indexOf(b)).map(a => ' ' + a + '="' + c[1][a] + '"').join('')
  + '/>').join('')));
check('registry parsed (≥ 180 entries)', entries.length >= 180, entries.length);
const notLucide = entries.filter(e => !lucideInners.has(e.inner)).map(e => e.name);
check('every drawing is a Lucide 0.460 drawing', notLucide.length === 0, notLucide);
check('registry names are unique', new Set(entries.map(e => e.name)).size === entries.length);

// ── 6. consumers = phase-C pages only (one PR per page adds itself here) ──
// + unified app header pages (PR 3.2 — HEADER-NAV.md: the header renders its icons with twIcon)
const PHASE_C_PAGES = ['job-detail.html', 'landing.html', 'appointments.html', 'appointment-room.html',
  'home-v2.html', 'notifications.html', 'messages.html', 'edu-profile.html', 'settings.html'];
const SKIP_DIRS = new Set(['.git', 'node_modules', 'docs', 'tests']);
const consumers = [];
(function walk(dir) {
  for (const f of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, f.name);
    if (f.isDirectory()) { if (!SKIP_DIRS.has(f.name)) walk(p); continue; }
    // .py excluded: page_shell.py names the file in its rules — it is not a page loading it
    if (!/\.(html|js|mjs|css|json)$/.test(f.name) || /^test_/.test(f.name)) continue;
    if (p === path.join('static', 'shared', 'tw-icons.js')) continue;
    if (p === 'sw.js') continue;  // §32 precache list for the offline page (landing) — not a consumer
    // DS-OVL shared runtime (PR 3B) — calls twIconEl only when the PAGE loaded tw-icons.js
    // (docs/rules/ds-overlay.md rules 6–7); it is not a page and never loads the file itself.
    if (p === path.join('static', 'shared', 'tw-overlay.js')) continue;
    if (read(p).includes('tw-icons')) consumers.push(p);
  }
}('.'));
check('only phase-C pages load tw-icons.js', JSON.stringify(consumers.slice().sort())
  === JSON.stringify(PHASE_C_PAGES.slice().sort()), consumers);
check('tw-icons.js is not in the Page Shell partials (F37 / F39)',
  !fs.readdirSync('partials').some(f => read(path.join('partials', f)).includes('tw-icons')));

// ── 7. RTL mirroring in a real browser ─────────────────────────────
async function browserPart() {
  let pw = null;
  try { pw = require('playwright'); } catch (_) {
    try {
      const root = require('child_process').execSync('npm root -g').toString().trim();
      pw = require(path.join(root, 'playwright'));
    } catch (_) { pw = null; }
  }
  if (!pw) { console.log('  SKIP  RTL mirroring (Playwright not installed)'); return; }
  const browser = await pw.chromium.launch();
  try {
    const page = await browser.newPage();
    await page.setContent('<!doctype html><html dir="rtl"><head></head><body>'
      + '<div id="r"></div><div id="l" dir="ltr"></div></body></html>');
    await page.addScriptTag({ content: SRC });
    const res = await page.evaluate(() => {
      const tf = el => getComputedStyle(el).transform;
      const back = twIconEl('back'), home = twIconEl('home'), backLtr = twIconEl('back');
      document.getElementById('r').append(back, home);
      document.getElementById('l').append(backLtr);
      const out = {
        ns: back.namespaceURI, styleTags: document.querySelectorAll('#tw-ico-style').length,
        rtlBack: tf(back), rtlHome: tf(home), nestedLtrBack: tf(backLtr),
      };
      twIconEl('next'); twIconEl('prev');
      out.styleTagsAfter = document.querySelectorAll('#tw-ico-style').length;
      document.documentElement.dir = 'ltr';
      out.ltrBack = tf(back);
      return out;
    });
    const MIRROR = 'matrix(-1, 0, 0, 1, 0, 0)';
    check('twIconEl returns an SVG element', res.ns === 'http://www.w3.org/2000/svg', res.ns);
    check('dir:true mirrored under dir=rtl', res.rtlBack === MIRROR, res.rtlBack);
    check('non-dir icon not mirrored under dir=rtl', res.rtlHome === 'none', res.rtlHome);
    check('dir:true not mirrored inside dir=ltr container', res.nestedLtrBack === 'none', res.nestedLtrBack);
    check('dir:true not mirrored under dir=ltr', res.ltrBack === 'none', res.ltrBack);
    check('direction rule injected once', res.styleTags === 1 && res.styleTagsAfter === 1, JSON.stringify(res));
  } finally { await browser.close(); }
}

browserPart().catch(e => { failed++; console.log('  FAIL  browser part threw: ' + e.message); })
  .then(() => {
    console.log('\n' + passed + ' passed, ' + failed + ' failed');
    process.exit(failed ? 1 : 0);
  });
