/**
 * test_news_banner_runtime.js — News Banner (phase 5b · static/shared/tw-news-banner.js · docs/rules/content-admin.md)
 * Runs the REAL tw-news-banner.js in a Node vm with a fake DOM + a stubbed twApi.
 *   A  data null / request failed → nothing shown, nothing logged
 *   B  a news item → title + summary as text (no innerHTML for news text) · safe link with
 *      target=_blank + rel="noopener noreferrer" · an unsafe link → no <a>
 *   C  close → the news id saved, banner hidden · the same id later → not shown · a newer id → shown
 *   D  localStorage that throws → banner still works, close does not throw
 *
 * Run: node tests/test_news_banner_runtime.js
 */
'use strict';
const fs = require('fs');
const vm = require('vm');

let passed = 0, failed = 0;
function check(name, cond, detail) {
  if (cond) { passed++; console.log('  PASS  ' + name); }
  else      { failed++; console.log('  FAIL  ' + name + (detail !== undefined ? ' — ' + detail : '')); }
}
const SRC = fs.readFileSync('static/shared/tw-news-banner.js', 'utf8');

function fakeEl(tag, log) {
  const ls = {};
  const e = {
    tagName: tag, className: '', hidden: false, children: [], attrs: {}, href: '', target: '', rel: '', type: '',
    _text: '',
    get textContent() { return this._text + this.children.map(c => c.textContent).join(''); },
    set textContent(v) { this._text = String(v); this.children = []; },
    set innerHTML(v) { log.push([tag, this.className, String(v)]); this._html = String(v); },
    get innerHTML() { return this._html || ''; },
    setAttribute(k, v) { this.attrs[k] = String(v); }, getAttribute(k) { return this.attrs[k]; },
    appendChild(c) { this.children.push(c); return c; },
    addEventListener(t, fn) { (ls[t] = ls[t] || []).push(fn); }, fire(t) { (ls[t] || []).forEach(fn => fn({})); },
  };
  return e;
}
const all = el => [el].concat((el.children || []).flatMap(all));

// opts: res (twApi result) · store (object) · storageThrows
async function run(opts) {
  const html = [], logs = [];
  const host = fakeEl('div', html);
  host.hidden = true;
  const store = opts.store || {};
  const storage = opts.storageThrows
    ? { getItem() { throw new Error('blocked'); }, setItem() { throw new Error('blocked'); } }
    : { getItem: k => (k in store ? store[k] : null), setItem: (k, v) => { store[k] = String(v); } };
  const quiet = { log: () => {}, warn: (...a) => logs.push(a), error: (...a) => logs.push(a) };
  const ctx = {
    console: quiet, Promise, String,
    document: { readyState: 'complete', addEventListener() {}, createElement: t => fakeEl(t, html),
                querySelectorAll: q => (q === '[data-tw-news-banner]' ? [host] : []) },
    localStorage: storage,
    twT: k => k,
    twIcon: () => '<svg data-i="close"></svg>',
    twSafeLinkUrl: u => (/^https?:\/\/\w/.test(u || '') ? u : ''),
    twApi: (path, o) => { ctx.calls.push([path, o]); return Promise.resolve(opts.res); },
    calls: [],
  };
  ctx.window = ctx;
  vm.createContext(ctx);
  vm.runInContext(SRC, ctx, { filename: 'tw-news-banner.js' });
  for (let i = 0; i < 4; i++) await new Promise(r => setImmediate(r));
  return { host, html, logs, store, ctx };
}
const NEWS = { id: 12, title: '<b>عنوان</b>', summary: 'ملخص <img src=x onerror=1>', source_url: 'https://example.com/a' };

(async function main() {
  console.log('A — nothing to show');
  for (const [name, res] of [['null', { ok: true, status: 200, data: null }],
                             ['failed', { ok: false, status: 0, data: null, error: {} }],
                             ['500', { ok: false, status: 500, data: null, error: {} }]]) {
    const r = await run({ res });
    check('A ' + name + ' → hidden, empty, no console output', r.host.hidden === true && r.host.children.length === 0 && r.logs.length === 0,
      JSON.stringify(r.logs));
    check('A ' + name + ' → public call (auth:false)', r.ctx.calls.length === 1 && r.ctx.calls[0][0] === '/news/banner' && r.ctx.calls[0][1].auth === false);
  }

  console.log('\nB — a news item');
  {
    const r = await run({ res: { ok: true, status: 200, data: NEWS } });
    const els = all(r.host);
    check('B1 shown', r.host.hidden === false && r.host.attrs['data-news-id'] === '12');
    check('B2 title + summary as plain text', els.some(e => e._text === NEWS.title) && els.some(e => e._text === NEWS.summary));
    check('B3 no innerHTML except the registry close icon', r.html.length === 1 && r.html[0][1] === 'tw-news-banner-close', JSON.stringify(r.html));
    const a = els.find(e => e.tagName === 'a');
    check('B4 link: href · target=_blank · rel=noopener noreferrer', !!a && a.href === NEWS.source_url && a.target === '_blank'
      && a.rel === 'noopener noreferrer');
    const u = await run({ res: { ok: true, status: 200, data: Object.assign({}, NEWS, { source_url: 'javascript:alert(1)' }) } });
    check('B5 unsafe link → no <a>, banner still shown', u.host.hidden === false && !all(u.host).some(e => e.tagName === 'a'));
    const n = await run({ res: { ok: true, status: 200, data: Object.assign({}, NEWS, { source_url: null, summary: '' }) } });
    check('B6 no link / no summary → title only', n.host.hidden === false && !all(n.host).some(e => e.tagName === 'a' || e.tagName === 'p'));
  }

  console.log('\nC — close is remembered per news id');
  {
    const store = {};
    const r = await run({ res: { ok: true, status: 200, data: NEWS }, store });
    const close = all(r.host).find(e => e.tagName === 'button');
    close.fire('click');
    check('C1 close → hidden + id saved', r.host.hidden === true && store.tw_news_banner_closed === '12', JSON.stringify(store));
    const again = await run({ res: { ok: true, status: 200, data: NEWS }, store });
    check('C2 same news id later → not shown', again.host.hidden === true && again.host.children.length === 0);
    const newer = await run({ res: { ok: true, status: 200, data: Object.assign({}, NEWS, { id: 13 }) }, store });
    check('C3 a newer news id → shown', newer.host.hidden === false);
  }

  console.log('\nD — storage blocked');
  {
    const r = await run({ res: { ok: true, status: 200, data: NEWS }, storageThrows: true });
    check('D1 shown although storage throws', r.host.hidden === false);
    let threw = false;
    try { all(r.host).find(e => e.tagName === 'button').fire('click'); } catch (e) { threw = true; }
    check('D2 close does not throw, banner hidden, nothing logged', !threw && r.host.hidden === true && r.logs.length === 0);
  }

  console.log(`\n${passed} passed, ${failed} failed`);
  process.exit(failed ? 1 : 0);
})();
