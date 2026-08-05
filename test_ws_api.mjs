/**
 * Messages API Runtime Tests
 * ===========================
 * Exercises messages.api.js with a mock fetch to verify the cross-account
 * session guard (_isMessagesAuthValid) blocks API calls during account-switch
 * races and in all invalid-session states.
 *
 * 14 scenarios:
 *   API01  _user=A, tw_user=B in localStorage → apiSendMessage blocked (no fetch)
 *   API02  snapshot.userId=B, _user=A → blocked (no fetch)
 *   API03  Valid session (same user, valid JWT) → fetch called with current localStorage JWT
 *   API04  Empty JWT (tw_jwt='') → blocked (no fetch)
 *   API05  Missing tw_user in localStorage → blocked
 *   API06  snapshot.isAuthenticated=false → blocked
 *   API07  apiGetConversations blocked on user mismatch
 *   API08  apiGetMessages blocked on user mismatch
 *   API09  apiGetUnreadCount blocked on user mismatch
 *   API10  apiLookupByTwId blocked on user mismatch (resolves null)
 *   API11  apiGetUser blocked on user mismatch (resolves null)
 *   API12  apiSendMessage uses latest JWT from localStorage, not stale in-memory _jwt
 *   API13  Valid session with TwAuthSync snapshot present → fetch proceeds
 *   API14  No _user → blocked
 *
 * Run:  node test_ws_api.mjs
 */

import vm from 'vm';
import { readFileSync } from 'fs';
import { strict as assert } from 'assert';

let PASS = 0, FAIL = 0;
function check(name, condition, detail = '') {
  if (condition) { PASS++; console.log(`  PASS  ${name}`); }
  else           { FAIL++; console.log(`  FAIL  ${name}${detail ? ' — ' + detail : ''}`); }
}

const src = readFileSync('messages.api.js', 'utf8');

// ── Context builder ───────────────────────────────────────────────────────

function makeCtx({ userId = 42, storedUserId = 42, jwt = 'valid.jwt.token',
                   twAuthSync = undefined } = {}) {
  let fetchCalled = false;
  let fetchUrl = null;
  let fetchOpts = null;

  const ctx = {
    // In-memory app state (set by page init)
    _user: userId != null ? { id: userId, full_name: 'Test' } : null,
    _jwt:  jwt,

    // localStorage with configurable tw_jwt and tw_user
    localStorage: {
      _data: {
        tw_jwt:  jwt,
        tw_user: storedUserId != null ? JSON.stringify({ id: storedUserId, full_name: 'Stored' }) : null,
      },
      getItem(k)    { return this._data[k] != null ? this._data[k] : null; },
      setItem(k, v) { this._data[k] = v; },
      removeItem(k) { delete this._data[k]; },
    },

    // Mock fetch — records calls
    fetch: function(url, opts) {
      fetchCalled = true;
      fetchUrl  = url;
      fetchOpts = opts || {};
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    },

    // TwAuthSync (optional)
    TwAuthSync: twAuthSync,

    // Needed by the module
    JSON,
    Number,
    Promise,
    encodeURIComponent,

    // Expose spy accessors
    get _fetchCalled() { return fetchCalled; },
    get _fetchUrl()    { return fetchUrl; },
    get _fetchOpts()   { return fetchOpts; },
  };

  vm.createContext(ctx);
  vm.runInContext(src, ctx);
  return ctx;
}

// ── Tests ─────────────────────────────────────────────────────────────────

console.log('\n── Messages API session guard tests (messages.api.js) ──────────────────');

// API01: _user=A (id:42), tw_user=B (id:55) in localStorage → fetch blocked
(async function API01() {
  const ctx = makeCtx({ userId: 42, storedUserId: 55, jwt: 'b.jwt.token' });
  try {
    await ctx.apiSendMessage(99, 'hello');
  } catch(e) {}
  check('API01  _user=A, tw_user=B → apiSendMessage blocked (fetch not called)',
        !ctx._fetchCalled,
        `fetch was called with url=${ctx._fetchUrl}`);
})().then(() => {

// API02: snapshot.userId=B (55), _user=A (42) → fetch blocked
(async function API02() {
  const ctx = makeCtx({
    userId: 42, storedUserId: 42, jwt: 'a.jwt.token',
    twAuthSync: {
      getSessionSnapshot: () => ({ isAuthenticated: true, userId: 55, state: 'authenticated' }),
    },
  });
  try {
    await ctx.apiSendMessage(99, 'hello');
  } catch(e) {}
  check('API02  snapshot.userId=B, _user=A → apiSendMessage blocked',
        !ctx._fetchCalled);
}).call(null).then(() => {

// API03: Same user (42/42), valid JWT, valid snapshot → fetch called using localStorage JWT
(async function API03() {
  const ctx = makeCtx({
    userId: 42, storedUserId: 42, jwt: 'fresh.jwt.from.storage',
    twAuthSync: {
      getSessionSnapshot: () => ({ isAuthenticated: true, userId: 42, state: 'authenticated' }),
    },
  });
  try {
    await ctx.apiSendMessage(99, 'hello');
  } catch(e) {}
  check('API03  Valid session → fetch called',
        ctx._fetchCalled,
        'fetch was not called');
  check('API03b Valid session → fetch uses localStorage JWT',
        ctx._fetchCalled && ctx._fetchOpts &&
        ctx._fetchOpts.headers &&
        ctx._fetchOpts.headers['Authorization'] === 'Bearer fresh.jwt.from.storage',
        `Authorization header: ${ctx._fetchCalled ? JSON.stringify(ctx._fetchOpts.headers) : 'n/a'}`);
}).call(null).then(() => {

// API04: Empty JWT (tw_jwt='') → blocked
(async function API04() {
  const ctx = makeCtx({ userId: 42, storedUserId: 42, jwt: '' });
  try {
    await ctx.apiSendMessage(99, 'hello');
  } catch(e) {}
  check('API04  Empty JWT → apiSendMessage blocked',
        !ctx._fetchCalled);
}).call(null).then(() => {

// API05: Missing tw_user in localStorage → blocked
(async function API05() {
  const ctx = makeCtx({ userId: 42, storedUserId: null, jwt: 'valid.jwt' });
  try {
    await ctx.apiSendMessage(99, 'hello');
  } catch(e) {}
  check('API05  Missing tw_user in localStorage → apiSendMessage blocked',
        !ctx._fetchCalled);
}).call(null).then(() => {

// API06: snapshot.isAuthenticated=false → blocked
(async function API06() {
  const ctx = makeCtx({
    userId: 42, storedUserId: 42, jwt: 'valid.jwt',
    twAuthSync: {
      getSessionSnapshot: () => ({ isAuthenticated: false, userId: 42, state: 'logged_out' }),
    },
  });
  try {
    await ctx.apiSendMessage(99, 'hello');
  } catch(e) {}
  check('API06  snapshot.isAuthenticated=false → apiSendMessage blocked',
        !ctx._fetchCalled);
}).call(null).then(() => {

// API07: apiGetConversations blocked on user mismatch
(async function API07() {
  const ctx = makeCtx({ userId: 42, storedUserId: 55, jwt: 'b.jwt' });
  let rejected = false;
  try {
    await ctx.apiGetConversations();
  } catch(e) { rejected = true; }
  check('API07  _user=A, tw_user=B → apiGetConversations blocked',
        !ctx._fetchCalled && rejected);
}).call(null).then(() => {

// API08: apiGetMessages blocked on user mismatch
(async function API08() {
  const ctx = makeCtx({ userId: 42, storedUserId: 55, jwt: 'b.jwt' });
  let rejected = false;
  try {
    await ctx.apiGetMessages(99);
  } catch(e) { rejected = true; }
  check('API08  _user=A, tw_user=B → apiGetMessages blocked',
        !ctx._fetchCalled && rejected);
}).call(null).then(() => {

// API09: apiGetUnreadCount blocked on user mismatch
(async function API09() {
  const ctx = makeCtx({ userId: 42, storedUserId: 55, jwt: 'b.jwt' });
  let rejected = false;
  try {
    await ctx.apiGetUnreadCount();
  } catch(e) { rejected = true; }
  check('API09  _user=A, tw_user=B → apiGetUnreadCount blocked',
        !ctx._fetchCalled && rejected);
}).call(null).then(() => {

// API10: apiLookupByTwId blocked → resolves null (not rejected)
(async function API10() {
  const ctx = makeCtx({ userId: 42, storedUserId: 55, jwt: 'b.jwt' });
  let result = 'not-null';
  try {
    result = await ctx.apiLookupByTwId('U9620xxx');
  } catch(e) {}
  check('API10  _user=A, tw_user=B → apiLookupByTwId blocked (resolves null)',
        !ctx._fetchCalled && result === null);
}).call(null).then(() => {

// API11: apiGetUser blocked → resolves null (not rejected)
(async function API11() {
  const ctx = makeCtx({ userId: 42, storedUserId: 55, jwt: 'b.jwt' });
  let result = 'not-null';
  try {
    result = await ctx.apiGetUser(10);
  } catch(e) {}
  check('API11  _user=A, tw_user=B → apiGetUser blocked (resolves null)',
        !ctx._fetchCalled && result === null);
}).call(null).then(() => {

// API12: fetch uses latest JWT from localStorage, not stale in-memory _jwt
// Simulate: _jwt in memory is stale, localStorage has a newer token
(async function API12() {
  const ctx = makeCtx({ userId: 42, storedUserId: 42, jwt: 'fresh-localstorage-jwt' });
  // Override in-memory _jwt to a stale value
  ctx._jwt = 'stale-inmemory-jwt';
  try {
    await ctx.apiSendMessage(99, 'hello');
  } catch(e) {}
  check('API12  fetch uses latest JWT from localStorage (not stale _jwt)',
        ctx._fetchCalled &&
        ctx._fetchOpts.headers['Authorization'] === 'Bearer fresh-localstorage-jwt',
        `Authorization: ${ctx._fetchCalled ? ctx._fetchOpts.headers['Authorization'] : 'no fetch'}`);
}).call(null).then(() => {

// API13: Valid session with TwAuthSync, matching snapshot → fetch proceeds
(async function API13() {
  const ctx = makeCtx({
    userId: 42, storedUserId: 42, jwt: 'valid.jwt',
    twAuthSync: {
      getSessionSnapshot: () => ({ isAuthenticated: true, userId: 42, state: 'authenticated' }),
    },
  });
  let result = null;
  try {
    result = await ctx.apiGetConversations();
  } catch(e) {}
  check('API13  Valid TwAuthSync snapshot + matching userId → fetch proceeds',
        ctx._fetchCalled,
        'fetch was not called');
}).call(null).then(() => {

// API14: No _user → blocked
(async function API14() {
  const ctx = makeCtx({ userId: null, storedUserId: 42, jwt: 'valid.jwt' });
  let rejected = false;
  try {
    await ctx.apiSendMessage(99, 'hello');
  } catch(e) { rejected = true; }
  check('API14  _user=null → apiSendMessage blocked',
        !ctx._fetchCalled && rejected);
}).call(null).then(() => {

// ── Summary ───────────────────────────────────────────────────────────────
const total = PASS + FAIL;
console.log(`\n${'─'.repeat(60)}`);
console.log(`  ${PASS}/${total} passed  ${FAIL === 0 ? '✓  all green' : `✗  ${FAIL} FAILED`}`);
console.log(`${'─'.repeat(60)}\n`);
process.exit(FAIL === 0 ? 0 : 1);

}); }); }); }); }); }); }); }); }); }); }); }); }); });
