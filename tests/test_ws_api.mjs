/**
 * Messages API Runtime Tests
 * ===========================
 * Exercises messages.api.js (real file in vm) with a mock twApi + TwAuthSync to verify
 * the cross-account session guard (_isMessagesAuthValid) blocks API calls during
 * account-switch races and in all invalid-session states (PR 4.4 — twApi only).
 *
 * Scenarios:
 *   API01  snapshot.userId=B, _user=A → apiSendMessage blocked (no request)
 *   API02  snapshot.isAuthenticated=false → blocked
 *   API03  Valid session → twApi called once with the right path / method / body
 *   API04  No TwAuthSync → blocked (fail closed)
 *   API05  apiGetConversations / apiGetMessages / apiGetUnreadCount blocked on user mismatch
 *   API06  apiLookupByTwId blocked on user mismatch (resolves null, no request)
 *   API07  apiGetUser removed (PR 3.9b)
 *   API08  twApi ok:false → promise rejects with the HTTP status
 *   API09  twApi ok → resolves with res.data
 *   API10  No _user → blocked
 *   API11  The snapshot is read at call time (switch after page load → blocked)
 *
 * Run:  node tests/test_ws_api.mjs
 */

import vm from 'vm';
import { readFileSync } from 'fs';

let PASS = 0, FAIL = 0;
function check(name, condition, detail = '') {
  if (condition) { PASS++; console.log(`  PASS  ${name}`); }
  else           { FAIL++; console.log(`  FAIL  ${name}${detail ? ' — ' + detail : ''}`); }
}

const src = readFileSync('messages.api.js', 'utf8');

function makeCtx({ userId = 42, snap = { isAuthenticated: true, userId: 42 }, withSync = true,
                   result = { ok: true, status: 200, data: {} } } = {}) {
  const calls = [];
  const ctx = {
    _user: userId != null ? { id: userId } : null,
    TwAuthSync: withSync ? { getSessionSnapshot: () => ctx.__snap } : undefined,
    twApi: (path, opts) => { calls.push({ path, opts: opts || {} }); return Promise.resolve(ctx.__result); },
    JSON, Number, Promise, encodeURIComponent,
    __snap: snap, __result: result, __calls: calls,
  };
  vm.createContext(ctx);
  vm.runInContext(src, ctx);
  return ctx;
}

async function rejects(p) { try { await p; return false; } catch (e) { return true; } }

console.log('\n── Messages API session guard tests (messages.api.js) ──────────────────');

{
  const ctx = makeCtx({ snap: { isAuthenticated: true, userId: 55 } });
  check('API01  snapshot.userId=B, _user=A → apiSendMessage blocked',
        await rejects(ctx.apiSendMessage(99, 'hi')) && ctx.__calls.length === 0);
}
{
  const ctx = makeCtx({ snap: { isAuthenticated: false, userId: null } });
  check('API02  snapshot.isAuthenticated=false → blocked',
        await rejects(ctx.apiSendMessage(99, 'hi')) && ctx.__calls.length === 0);
}
{
  const ctx = makeCtx();
  await ctx.apiSendMessage(99, 'hello');
  const c = ctx.__calls[0] || { opts: {} };
  check('API03  valid session → one twApi POST /messages/send with {receiver_id, content}',
        ctx.__calls.length === 1 && c.path === '/messages/send' && c.opts.method === 'POST'
        && c.opts.body && c.opts.body.receiver_id === 99 && c.opts.body.content === 'hello'
        && !('sender_id' in c.opts.body));
}
{
  const ctx = makeCtx({ withSync: false });
  check('API04  no TwAuthSync → blocked (fail closed)',
        await rejects(ctx.apiGetConversations()) && ctx.__calls.length === 0);
}
{
  const ctx = makeCtx({ snap: { isAuthenticated: true, userId: 55 } });
  const r = [await rejects(ctx.apiGetConversations()), await rejects(ctx.apiGetMessages(7)),
             await rejects(ctx.apiGetUnreadCount())];
  check('API05  conversations / messages / unread blocked on user mismatch',
        r.every(Boolean) && ctx.__calls.length === 0);
}
{
  const ctx = makeCtx({ snap: { isAuthenticated: true, userId: 55 } });
  const v = await ctx.apiLookupByTwId('U123');
  check('API06  apiLookupByTwId blocked on mismatch → null, no request', v === null && ctx.__calls.length === 0);
}
{
  const ctx = makeCtx();
  check('API07  apiGetUser removed (dead code — PR 3.9b)', typeof ctx.apiGetUser === 'undefined');
}
{
  const ctx = makeCtx({ result: { ok: false, status: 503, data: null } });
  let got = null;
  try { await ctx.apiGetMessages(7); } catch (e) { got = e; }
  check('API08  twApi ok:false → rejects with the HTTP status', got === 503);
}
{
  const ctx = makeCtx({ result: { ok: true, status: 200, data: { conversations: [{ other_id: 3 }] } } });
  const d = await ctx.apiGetConversations();
  check('API09  twApi ok → resolves with res.data + path uses _user.id',
        d.conversations.length === 1 && ctx.__calls[0].path === '/messages/conversations/42');
}
{
  const ctx = makeCtx({ userId: null });
  check('API10  _user=null → blocked', await rejects(ctx.apiSendMessage(99, 'x')) && ctx.__calls.length === 0);
}
{
  const ctx = makeCtx();
  await ctx.apiGetUnreadCount();
  ctx.__snap = { isAuthenticated: true, userId: 77 };   // account switched in another tab
  check('API11  snapshot read at call time — after a switch the next call is blocked',
        await rejects(ctx.apiGetUnreadCount()) && ctx.__calls.length === 1);
}

const total = PASS + FAIL;
console.log(`\n${'─'.repeat(60)}`);
console.log(`  ${PASS}/${total} passed  ${FAIL === 0 ? '✓  all green' : `✗  ${FAIL} FAILED`}`);
console.log(`${'─'.repeat(60)}\n`);
process.exit(FAIL === 0 ? 0 : 1);
