/**
 * test_messages_page_runtime.js — PR 4.4: messages page on the unified page checklist
 * Runs the REAL page scripts (messages.state.js → api.js → ws.js → render.js) in a Node vm with a
 * tiny fake DOM, a controllable twApi (deferred responses) and a mock WebSocket.
 *   A  guard — twRequireAuth null (guest) → no request, no socket
 *   B  thread race — open A then B; A's late response never overwrites B · quiet reload dropped
 *      after a newer open
 *   C  conversation list race — older list response never overwrites a newer one
 *   D  one socket — connectWS twice closes the first · shared badge socket stands down on
 *      <meta name="tw-ws" content="page"> (real tw_shared.js region)
 *   E  retry limits — socket stops after WS_MAX_RETRIES + notice · poll stops after
 *      MSG_MAX_FAILS + notice · manual retry restarts
 *   F  schedule button — twScheduleButton called with the other side, button mounted in the header
 *   G  structure — every msg.* twT key used exists in tw_strings.json
 *
 * Run: node tests/test_messages_page_runtime.js
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
const flush = async () => { for (let i = 0; i < 8; i++) await new Promise(r => setImmediate(r)); };
const STRINGS = JSON.parse(read('tw_strings.json')).ar;
const PAGE_FILES = ['messages.state.js', 'messages.api.js', 'messages.ws.js', 'messages.render.js'];

// ── tiny fake DOM (innerHTML kept as a string) ──────────────────────────────
class El {
  constructor(id) {
    this.id = id || ''; this.innerHTML = ''; this.textContent = ''; this.hidden = false;
    this.attrs = {}; this.style = {}; this.children = []; this.value = ''; this.disabled = false;
    const cls = new Set();
    this.classList = { add: c => cls.add(c), remove: c => cls.delete(c), contains: c => cls.has(c),
                       toggle: c => (cls.has(c) ? cls.delete(c) : cls.add(c)) };
  }
  setAttribute(k, v) { this.attrs[k] = String(v); }
  getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; }
  removeAttribute(k) { delete this.attrs[k]; }
  appendChild(c) { this.children.push(c); return c; }
  insertAdjacentHTML(_, h) { this.innerHTML += h; }
  insertAdjacentElement(_, e) { this.children.unshift(e); }
  querySelector() { return null; }
  querySelectorAll() { return []; }
  addEventListener() {}
  contains() { return false; }
  focus() {}
  remove() {}
}

class MockWS {
  constructor(url) { this.url = url; this.readyState = 0; this.sent = []; this.closed = false; MockWS.all.push(this); }
  send(d) { this.sent.push(d); }
  close(code) { if (this.closed) return; this.closed = true; this.readyState = 3; if (this.onclose) this.onclose({ code: code || 1000 }); }
}
MockWS.all = [];

function makePage(opts) {
  opts = opts || {};
  MockWS.all = [];
  const ids = ['convList', 'convItems', 'convSearch', 'convFilters', 'chatArea', 'chatHead', 'chMenuWrap',
    'chMenuBtn', 'chMenuDropdown', 'chatAva', 'chatName', 'chatTypeBadge', 'chBackArrow', 'chatRole',
    'chatStatus', 'chatSchedSlot', 'msgConnBar', 'msgConnText', 'messages', 'chatInput', 'msgInput'];
  const els = {};
  ids.forEach(i => { els[i] = new El(i); });
  els.msgConnBar.hidden = true;
  const docListeners = {};
  const timers = [];
  let tid = 1;
  const rec = { api: [], keys: new Set(), sched: [], toasts: [], intervals: new Set() };
  const pending = [];   // deferred twApi calls: {path, opts, resolve}
  const ctx = {
    console: { log() {}, warn() {}, error() {} },
    Promise, Date, Math, Number, String, JSON, Array, Object, URLSearchParams,
    WebSocket: MockWS,
    document: {
      hidden: false, title: '', body: new El('body'),
      getElementById: id => els[id] || null,
      querySelector: s => (s === '.conv-items' ? els.convItems : s === '.send-btn' ? null : null),
      querySelectorAll: () => [],
      createElement: () => new El(),
      addEventListener: (t, fn) => { (docListeners[t] = docListeners[t] || []).push(fn); },
    },
    location: { search: opts.search || '', protocol: 'https:', host: 'x', origin: 'https://x', pathname: '/messages' },
    history: { pushState() {}, replaceState() {} },
    navigator: { clipboard: { writeText: () => Promise.resolve() } },
    requestAnimationFrame: fn => fn(),
    setTimeout: (fn, ms) => { const id = tid++; timers.push({ id, fn, ms, done: false }); return id; },
    clearTimeout: id => { const t = timers.find(x => x.id === id); if (t) t.done = true; },
    setInterval: () => { const id = tid++; rec.intervals.add(id); return id; },
    clearInterval: id => { rec.intervals.delete(id); },
    addEventListener() {},
    twRequireAuth: () => (opts.guest ? null : { isAuthenticated: true, userId: opts.uid || 42, userType: opts.type || 'co' }),
    TwAuthSync: {
      onSessionChange() {},
      getSessionSnapshot: () => ({ isAuthenticated: !opts.guest, userId: opts.guest ? null : (opts.uid || 42) }),
      getToken: () => (opts.guest ? '' : 'jwt.a'),
    },
    twApi: (path, o) => { rec.api.push(path); return new Promise(res => pending.push({ path, opts: o || {}, resolve: res })); },
    twT: (k) => { rec.keys.add(k); return k; },
    twEscHtml: s => String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;'),
    twIcon: Object.assign(n => '<svg data-i="' + n + '"></svg>', { hydrate: () => 0 }),
    twAvatarHtml: e => '<span class="tw-ava">' + (e && e.full_name || '') + '</span>',
    twNotifBadgeLabel: n => String(n),
    showToast: (m, t) => rec.toasts.push([m, t]),
    twScheduleButton: o => { rec.sched.push(o); const b = new El('sched'); b.isSched = true; return b; },
  };
  ctx.twEscAttr = ctx.twEscHtml;
  ctx.window = ctx;
  vm.createContext(ctx);
  PAGE_FILES.forEach(f => vm.runInContext(read(f), ctx, { filename: f }));
  const ready = () => (docListeners.DOMContentLoaded || []).forEach(fn => fn());
  const reply = (match, res) => {
    const i = pending.findIndex(p => p.path.indexOf(match) === 0);
    if (i < 0) return false;
    pending.splice(i, 1)[0].resolve(res);
    return true;
  };
  const runTimers = () => { timers.filter(t => !t.done).forEach(t => { t.done = true; t.fn(); }); };
  return { ctx, els, rec, pending, ready, reply, runTimers, timers };
}
const OK = data => ({ ok: true, status: 200, data, error: null });
const FAIL = status => ({ ok: false, status, data: null, error: {} });

(async function main() {
  console.log('\nA — guard');
  {
    const p = makePage({ guest: true });
    p.ready();
    await flush();
    check('A1 guest → _user null', p.ctx._user === null);
    check('A2 guest → no API request, no WebSocket', p.rec.api.length === 0 && MockWS.all.length === 0);
  }

  console.log('\nB — thread race (stale response dropped)');
  {
    const p = makePage();
    p.ready();
    await flush();
    p.ctx.openConversation(5, 'Ahmad', 'emp', '', '', 'U5');
    p.ctx.openConversation(9, 'Sara', 'emp', '', '', 'U9');
    p.reply('/messages/42/9', OK({ messages: [{ id: 2, sender_id: 9, content: 'from-B', created_at: '2026-10-08T10:00:00Z' }] }));
    await flush();
    p.reply('/messages/42/5', OK({ messages: [{ id: 1, sender_id: 5, content: 'from-A', created_at: '2026-10-08T09:00:00Z' }] }));
    await flush();
    const h = p.els.messages.innerHTML;
    check('B1 late response of conversation A never overwrites conversation B', h.indexOf('from-B') >= 0 && h.indexOf('from-A') < 0, h);

    // quiet reload started for B, then B is re-opened → the quiet (older) response is dropped
    p.ctx.reloadMessagesQuiet();
    p.ctx.openConversation(9, 'Sara', 'emp', '', '', 'U9');
    p.reply('/messages/42/9', OK({ messages: [
      { id: 2, sender_id: 9, content: 'old-quiet', created_at: '2026-10-08T10:00:00Z' },
      { id: 3, sender_id: 9, content: 'old-quiet-2', created_at: '2026-10-08T10:01:00Z' }] }));
    await flush();
    check('B2 quiet reload older than the latest open is dropped', p.els.messages.innerHTML.indexOf('old-quiet') < 0);
    p.reply('/messages/42/9', OK({ messages: [{ id: 4, sender_id: 42, content: 'fresh', created_at: '2026-10-08T10:02:00Z' }] }));
    await flush();
    check('B3 newest open renders', p.els.messages.innerHTML.indexOf('fresh') >= 0);
    check('B4 own message rendered as outgoing (sender_id = _user.id)', p.els.messages.innerHTML.indexOf('msg-wrap out') >= 0);
  }

  console.log('\nC — conversation list race');
  {
    const p = makePage();
    p.ready();
    await flush();                                     // initial load pending
    p.ctx.loadConversations();                         // a newer load
    const conv = name => OK({ conversations: [{ other_id: 3, full_name: name, user_type: 'emp', content: 'x' }] });
    // answer the NEWER one first, then the older one
    const newer = p.pending.filter(x => x.path.indexOf('/messages/conversations/') === 0).pop();
    p.pending.splice(p.pending.indexOf(newer), 1); newer.resolve(conv('NEW-LIST'));
    await flush();
    p.reply('/messages/conversations/', conv('OLD-LIST'));
    await flush();
    const h = p.els.convItems.innerHTML;
    check('C1 older list response never overwrites the newer list', h.indexOf('NEW-LIST') >= 0 && h.indexOf('OLD-LIST') < 0, h);
  }

  console.log('\nD — one socket');
  {
    const p = makePage();
    p.ready();
    check('D1 page load opens exactly one socket', MockWS.all.length === 1);
    const first = MockWS.all[0];
    p.ctx.connectWS();
    check('D2 connectWS again closes the first socket — never two open',
      first.closed && MockWS.all.filter(w => !w.closed).length === 1);
    p.runTimers();
    check('D3 the closed socket schedules no reconnect', MockWS.all.length === 2);
    const ws = MockWS.all[1];
    ws.readyState = 1; ws.onopen();
    check('D4 auth frame uses TwAuthSync.getToken()', JSON.parse(ws.sent[0]).token === 'jwt.a');

    // shared badge socket (real tw_shared.js region) stands down on <meta name="tw-ws" content="page">
    const full = read('tw_shared.js');
    const region = full.slice(full.indexOf('// @vm-extract-begin: badge-ws'), full.indexOf('// @vm-extract-end: badge-ws'));
    const run = (hasMeta) => {
      const sockets = [];
      let loadCb = null;
      const timers = [];
      const c = vm.createContext({
        WebSocket: function (u) { sockets.push(u); this.send = () => {}; this.close = () => {}; },
        TwAuthSync: { onSessionChange() {}, getSessionSnapshot: () => ({ isAuthenticated: true, userId: 42 }) },
        localStorage: { getItem: k => (k === 'tw_jwt' ? 'jwt.a' : null) },
        document: { querySelector: s => (hasMeta && s === 'meta[name="tw-ws"][content="page"]' ? {} : null),
                    querySelectorAll: () => ({ forEach() {} }) },
        setTimeout: fn => { timers.push(fn); return timers.length; }, clearTimeout() {},
        JSON, Math, Number,
      });
      c.window = { location: { protocol: 'https:', host: 'x' }, addEventListener: (e, f) => { if (e === 'load') loadCb = f; } };
      vm.runInContext('var _badgeGeneration = 0; function twNotifBadgeLabel(n){return String(n);}\n' + region, c);
      if (loadCb) loadCb();
      timers.forEach(f => f());
      return sockets.length;
    };
    check('D5 shared badge socket opens on a normal page', run(false) === 1);
    check('D6 shared badge socket stands down when the page owns the socket', run(true) === 0);
  }

  console.log('\nE — retry limits');
  {
    const p = makePage();
    p.ready();
    await flush();
    let drops = 0;
    for (let i = 0; i < 20; i++) {
      const live = MockWS.all.filter(w => !w.closed);
      if (!live.length) break;
      live[0].close(1006);                              // network drop
      drops++;
      p.timers.filter(t => !t.done && t.ms >= 2000).forEach(t => { t.done = true; t.fn(); });
    }
    check('E1 socket reconnects at most WS_MAX_RETRIES times, then stops',
      MockWS.all.length === p.ctx.WS_MAX_RETRIES + 1 && MockWS.all.every(w => w.closed), MockWS.all.length);
    check('E2 retry cap reached → connection notice shown (live)',
      p.els.msgConnBar.hidden === false && p.els.msgConnText.textContent === 'msg.live_lost');

    // poll: MSG_MAX_FAILS consecutive list failures → poll stopped + offline notice
    check('E3 poll running before failures', p.rec.intervals.size === 1);
    for (let i = 0; i < p.ctx.MSG_MAX_FAILS; i++) {
      if (i > 0) p.ctx.loadConversations();
      p.reply('/messages/conversations/', FAIL(503));
      await flush();
    }
    check('E4 poll stopped after MSG_MAX_FAILS failures', p.rec.intervals.size === 0);
    check('E5 offline notice shown with a clear message',
      p.els.msgConnBar.hidden === false && p.els.msgConnText.textContent === 'msg.offline');

    // manual retry → reset, reload, poll + socket restarted on success
    const before = MockWS.all.length;
    p.ctx.msgRetryConnection();
    check('E6 retry hides the notice and reconnects the socket', p.els.msgConnBar.hidden === true && MockWS.all.length === before + 1);
    p.reply('/messages/conversations/', OK({ conversations: [] }));
    await flush();
    check('E7 successful retry restarts the poll', p.rec.intervals.size === 1);
  }

  console.log('\nF — schedule button in the conversation header');
  {
    const p = makePage({ type: 'co' });
    p.ready();
    await flush();
    p.ctx.openConversation(5, 'Ahmad', 'emp', '', '', 'U5');
    const o = p.rec.sched[0] || {};
    check('F1 twScheduleButton called with the other side (id / name / type)',
      o.candidateId === 5 && o.candidateName === 'Ahmad' && o.candidateType === 'emp');
    check('F2 button mounted in the chat header slot', p.els.chatSchedSlot.children.some(c => c.isSched));
    p.ctx.backToConvList();
    check('F3 leaving the conversation clears the slot', p.els.chatSchedSlot.innerHTML === '');
  }

  console.log('\nG — strings');
  {
    const used = new Set();
    PAGE_FILES.concat(['messages.html']).forEach(f => {
      (read(f).match(/['"](msg\.[a-z_]+)['"]/g) || []).forEach(m => used.add(m.slice(1, -1)));
    });
    const missing = [...used].filter(k => !Object.prototype.hasOwnProperty.call(STRINGS, k));
    check('G1 every msg.* key used by the page exists in tw_strings.json', used.size > 10 && missing.length === 0, missing.join(', '));
  }

  console.log('\n' + passed + ' passed, ' + failed + ' failed');
  process.exit(failed ? 1 : 0);
})().catch(e => { console.error(e); process.exit(1); });
