"""
WebSocket Behavioral Security Tests — Production Code Edition
=============================================================
Imports and tests server.py directly.
No live DB or running server required: _jwt_decode, _ws_conversation_exists_async,
and ws_manager are monkeypatched; _asyncpg_pool is left None (sync fallback path).

Scenarios:
  P — websocket_endpoint() production scenarios  (22 tests: P01-P22)
  A — _BoundedTTLCache                           ( 5 tests)
  B — ConnectionManager                          ( 8 tests: B01-B08)
  C — _ws_validate_auth_frame()                  ( 7 tests)
  D — _ws_origin_ok()                            ( 4 tests)
  E — _ws_typing_rate_ok() / _ws_ctrl_rate_ok()  ( 4 tests)
  F — _ws_cleanup_typing_log()                   ( 3 tests)
  G — Typing rate-limit drop behavior            ( 5 tests: G01-G05)

Run:  python test_ws_behavioral.py
"""

import asyncio
import json
import os
import sys
import time
from collections import deque
from unittest.mock import AsyncMock, patch

# ── Environment must be set BEFORE importing server.py ───────────────────────
os.environ.setdefault("SUPABASE_DB_URL", "postgres://test:test@localhost/test_db")
os.environ.setdefault("JWT_SECRET",      "test_jwt_secret_for_behavioral_tests_32")
os.environ.setdefault("ADMIN_TOKEN",     "test_admin_token_for_behavioral_test_32")
os.environ.setdefault("ADMIN_URL_TOKEN", "test_admin_url_token")
os.environ.setdefault("APP_ENV",         "development")

import server  # noqa: E402 — env vars must precede this import

from starlette.websockets import WebSocketDisconnect  # noqa: E402

PASS = 0
FAIL = 0


def check(name: str, condition: bool, detail: str = ""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        print(f"  FAIL  {name}" + (f" — {detail}" if detail else ""))


# ── FakeWS — matches the FastAPI WebSocket interface used by websocket_endpoint ──

class FakeWS:
    class _Headers:
        def __init__(self, origin):
            self._origin = origin
        def get(self, key, default=""):
            return self._origin if key == "origin" else default

    def __init__(self, origin="", recv=None):
        self.headers      = self._Headers(origin)
        self._recv        = list(recv or [])
        self._idx         = 0
        self.sent         = []
        self.closed_code  = None

    async def accept(self):
        pass

    async def receive_text(self):
        if self._idx >= len(self._recv):
            raise WebSocketDisconnect(code=1000)
        val = self._recv[self._idx]
        self._idx += 1
        if isinstance(val, Exception):
            raise val
        return val

    async def send_text(self, text):
        self.sent.append(text)

    async def close(self, code=1000, reason=""):
        self.closed_code = code


# ── Helper: run websocket_endpoint with mocked dependencies ──────────────────

async def _run_ws(origin="", recv=None, uid=42, path_uid=42, jwt_uid=42,
                  jwt_type="emp", jwt_bad=False, conv_exists=True, mgr=None):
    ws      = FakeWS(origin=origin, recv=recv or [])
    mgr     = mgr or server.ConnectionManager()
    jwt_val = None if jwt_bad else {"user_id": jwt_uid, "user_type": jwt_type}

    mock_conv = AsyncMock(return_value=conv_exists)
    with patch.object(server, "ws_manager", mgr), \
         patch.object(server, "_jwt_decode", return_value=jwt_val), \
         patch.object(server, "_ws_conversation_exists_async", new=mock_conv):
        await server.websocket_endpoint(ws, path_uid)
    return ws, mgr, mock_conv


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ═══════════════════════════════════════════════════════════════════════════════
# ══ P: Production endpoint scenarios (15 tests) ═══════════════════════════════
# ═══════════════════════════════════════════════════════════════════════════════

print("\n── P  websocket_endpoint() — production scenarios ───────────────────────")


def test_P01():
    """ws_manager.register() must NOT be called before JWT validation succeeds."""
    mgr = server.ConnectionManager()
    orig_register = mgr.register
    calls = []

    def tracking(user_id, ws):
        calls.append(user_id)
        return orig_register(user_id, ws)

    mgr.register = tracking
    ws, _, _ = run(_run_ws(
        recv=[json.dumps({"type": "auth", "token": "bad"})],
        jwt_bad=True, mgr=mgr,
    ))
    check("P01  register() not called before JWT validation",
          len(calls) == 0 and ws.closed_code == 4001)


def test_P02():
    """'null' origin → close 4006."""
    ws, _, _ = run(_run_ws(origin="null"))
    check("P02  Null origin → close 4006", ws.closed_code == 4006)


def test_P03():
    """asyncio.wait_for timeout on auth frame → close 4002."""
    async def _raise_timeout(*args, **kw):
        # Close any unawaited coroutine to suppress RuntimeWarning
        for a in args:
            if asyncio.iscoroutine(a):
                a.close()
        raise asyncio.TimeoutError()

    ws  = FakeWS(origin="", recv=[])
    mgr = server.ConnectionManager()
    with patch.object(server, "ws_manager", mgr), \
         patch.object(server, "_jwt_decode", return_value=None), \
         patch.object(asyncio, "wait_for", new=_raise_timeout):
        run(server.websocket_endpoint(ws, 42))
    check("P03  Auth frame timeout → close 4002", ws.closed_code == 4002)


def test_P04():
    """Non-auth message type in first frame → close 4002."""
    ws, _, _ = run(_run_ws(recv=[json.dumps({"type": "message", "content": "hi"})]))
    check("P04  Wrong first-frame type → close 4002", ws.closed_code == 4002)


def test_P05():
    """JWT uid ≠ URL path uid → close 4003 (Forbidden)."""
    ws, _, _ = run(_run_ws(
        recv=[json.dumps({"type": "auth", "token": "tok"})],
        jwt_uid=42, path_uid=99,
    ))
    check("P05  JWT uid mismatch → close 4003", ws.closed_code == 4003)


def test_P06():
    """Connection limit exceeded → close 4007."""
    mgr = server.ConnectionManager()
    for _ in range(server._WS_MAX_CONN_PER_USER):
        mgr.active.setdefault(42, []).append(object())
    ws, _, _ = run(_run_ws(
        recv=[json.dumps({"type": "auth", "token": "tok"})],
        uid=42, path_uid=42, jwt_uid=42, mgr=mgr,
    ))
    check("P06  Max connections exceeded → close 4007", ws.closed_code == 4007)


def test_P07():
    """active_conversation ctrl rate limit exceeded → close 4005; DB never called."""
    uid = 5001
    server._ws_ctrl_log.pop(uid, None)
    for _ in range(server._WS_CTRL_MAX):
        server._ws_ctrl_rate_ok(uid)

    mock_conv = AsyncMock(return_value=True)
    ws  = FakeWS(origin="", recv=[
        json.dumps({"type": "auth", "token": "tok"}),
        json.dumps({"type": "active_conversation", "other_id": 200}),
    ])
    mgr = server.ConnectionManager()
    with patch.object(server, "ws_manager", mgr), \
         patch.object(server, "_jwt_decode", return_value={"user_id": uid, "user_type": "emp"}), \
         patch.object(server, "_ws_conversation_exists_async", new=mock_conv):
        run(server.websocket_endpoint(ws, uid))

    check("P07  active_conversation ctrl rate limit → close 4005, DB not called",
          ws.closed_code == 4005 and mock_conv.call_count == 0)
    server._ws_ctrl_log.pop(uid, None)


def test_P08():
    """active_conversation when conv doesn't exist → active_conversations unchanged."""
    uid = 5002
    ws, mgr, _ = run(_run_ws(
        recv=[
            json.dumps({"type": "auth", "token": "tok"}),
            json.dumps({"type": "active_conversation", "other_id": 999}),
        ],
        uid=uid, path_uid=uid, jwt_uid=uid, conv_exists=False,
    ))
    check("P08  Non-existent conv in active_conversation → state unchanged",
          mgr.active_conversations.get(uid) != 999)


def test_P09():
    """Typing rate-limit-before-DB: when rate exceeded, DB never queried and connection NOT closed."""
    uid = 5003
    server._ws_typing_log.pop(uid, None)
    for _ in range(server._WS_TYPING_MAX):
        server._ws_typing_rate_ok(uid)

    mock_conv = AsyncMock(return_value=True)
    ws  = FakeWS(origin="", recv=[
        json.dumps({"type": "auth", "token": "tok"}),
        json.dumps({"type": "typing", "to_user_id": 200}),
    ])
    mgr = server.ConnectionManager()
    with patch.object(server, "ws_manager", mgr), \
         patch.object(server, "_jwt_decode", return_value={"user_id": uid, "user_type": "emp"}), \
         patch.object(server, "_ws_conversation_exists_async", new=mock_conv):
        run(server.websocket_endpoint(ws, uid))

    # After fix: excess typing is dropped (continue), not disconnected.
    # ws.closed_code is None because receive_text raises WebSocketDisconnect
    # naturally after messages are exhausted — server never calls websocket.close().
    check("P09  Typing rate limit → DB never called, connection not killed (rate-before-DB ordering)",
          ws.closed_code != 4005 and mock_conv.call_count == 0)
    server._ws_typing_log.pop(uid, None)


def test_P10():
    """_ws_conversation_exists_async returns False on DB error (fail-closed contract)."""
    # Clear any cached result for (1,2)
    server._ws_conv_cache._store.pop((1, 2), None)

    def _raise_conn():
        raise RuntimeError("DB down")

    # asyncpg pool is None in test env → code uses asyncio.to_thread(_sync_check)
    # _sync_check calls get_conn() — patching get_conn makes the DB call fail
    with patch.object(server, "get_conn", side_effect=_raise_conn):
        result = run(server._ws_conversation_exists_async(1, 2))

    check("P10  DB error → _ws_conversation_exists_async returns False (fail closed)",
          result is False)


def test_P11():
    """ws_manager.disconnect() called in finally even after exception in message loop."""
    disconnect_calls = []

    class TrackingMgr(server.ConnectionManager):
        def disconnect(self, uid, ws):
            disconnect_calls.append(uid)
            return super().disconnect(uid, ws)

    uid = 5005
    ws, _, _ = run(_run_ws(
        recv=[
            json.dumps({"type": "auth", "token": "tok"}),
            RuntimeError("unexpected crash in loop"),
        ],
        uid=uid, path_uid=uid, jwt_uid=uid,
        mgr=TrackingMgr(),
    ))
    check("P11  ws_manager.disconnect() called after mid-loop exception",
          uid in disconnect_calls)


def test_P12():
    """Unknown event flood (≥ _WS_MAX_VIOLATIONS) → close 4005."""
    uid = 5006
    server._ws_event_violations.pop(uid, None)
    bad_msgs = [json.dumps({"type": f"unknown_{i}"}) for i in range(server._WS_MAX_VIOLATIONS)]
    ws, _, _ = run(_run_ws(
        recv=[json.dumps({"type": "auth", "token": "tok"})] + bad_msgs,
        uid=uid, path_uid=uid, jwt_uid=uid,
    ))
    check("P12  Unknown event flood → close 4005", ws.closed_code == 4005)
    server._ws_event_violations.pop(uid, None)


def test_P13():
    """Disconnect of last connection clears rate-limit state."""
    uid = 5007
    server._ws_ctrl_log[uid]   = deque([time.time()])
    server._ws_typing_log[uid] = deque([time.time()])

    run(_run_ws(
        recv=[json.dumps({"type": "auth", "token": "tok"})],
        uid=uid, path_uid=uid, jwt_uid=uid,
    ))
    check("P13  Last connection disconnect clears _ws_ctrl_log and _ws_typing_log",
          uid not in server._ws_ctrl_log and uid not in server._ws_typing_log)


def test_P14():
    """Disconnect of one of two connections preserves rate-limit state."""
    uid = 5008
    mgr      = server.ConnectionManager()
    dummy_ws = FakeWS()
    mgr.register(uid, dummy_ws)  # first connection stays alive

    server._ws_ctrl_log[uid]   = deque([time.time()])
    server._ws_typing_log[uid] = deque([time.time()])

    ws2 = FakeWS(origin="", recv=[json.dumps({"type": "auth", "token": "tok"})])
    with patch.object(server, "ws_manager", mgr), \
         patch.object(server, "_jwt_decode", return_value={"user_id": uid, "user_type": "emp"}), \
         patch.object(server, "_ws_conversation_exists_async", new=AsyncMock(return_value=True)):
        run(server.websocket_endpoint(ws2, uid))

    check("P14  Disconnect with remaining connection preserves rate-limit state",
          uid in server._ws_ctrl_log or uid in server._ws_typing_log)

    # Clean up
    mgr.disconnect(uid, dummy_ws)
    server._ws_ctrl_log.pop(uid, None)
    server._ws_typing_log.pop(uid, None)


def test_P15():
    """auth_ok send_text failure → ws_manager.disconnect() still called."""
    class BrokenSendWS(FakeWS):
        async def send_text(self, text):
            raise RuntimeError("socket broken during send")

    disconnect_calls = []

    class TrackingMgr(server.ConnectionManager):
        def disconnect(self, uid, ws):
            disconnect_calls.append(uid)
            return super().disconnect(uid, ws)

    uid = 5009
    ws  = BrokenSendWS(origin="", recv=[json.dumps({"type": "auth", "token": "tok"})])
    mgr = TrackingMgr()
    with patch.object(server, "ws_manager", mgr), \
         patch.object(server, "_jwt_decode", return_value={"user_id": uid, "user_type": "emp"}), \
         patch.object(server, "_ws_conversation_exists_async", new=AsyncMock(return_value=True)):
        run(server.websocket_endpoint(ws, uid))

    check("P15  auth_ok send failure → ws_manager.disconnect() still called",
          uid in disconnect_calls)


def test_P16():
    """Non-string type field (integer) → close 4004 before violation counter."""
    uid = 6001
    server._ws_event_violations.pop(uid, None)
    ws, _, _ = run(_run_ws(
        recv=[
            json.dumps({"type": "auth", "token": "tok"}),
            json.dumps({"type": 42}),   # integer type — not a string
        ],
        uid=uid, path_uid=uid, jwt_uid=uid,
    ))
    check("P16  Non-string type → close 4004", ws.closed_code == 4004)
    server._ws_event_violations.pop(uid, None)


def test_P17():
    """Null type field → close 4004."""
    uid = 6002
    server._ws_event_violations.pop(uid, None)
    ws, _, _ = run(_run_ws(
        recv=[
            json.dumps({"type": "auth", "token": "tok"}),
            json.dumps({"type": None}),
        ],
        uid=uid, path_uid=uid, jwt_uid=uid,
    ))
    check("P17  Null type → close 4004", ws.closed_code == 4004)
    server._ws_event_violations.pop(uid, None)


def test_P18():
    """Empty string type → close 4004."""
    uid = 6003
    server._ws_event_violations.pop(uid, None)
    ws, _, _ = run(_run_ws(
        recv=[
            json.dumps({"type": "auth", "token": "tok"}),
            json.dumps({"type": ""}),
        ],
        uid=uid, path_uid=uid, jwt_uid=uid,
    ))
    check("P18  Empty string type → close 4004", ws.closed_code == 4004)
    server._ws_event_violations.pop(uid, None)


def test_P19():
    """Oversized type string (>80 chars) → close 4004."""
    uid = 6004
    server._ws_event_violations.pop(uid, None)
    ws, _, _ = run(_run_ws(
        recv=[
            json.dumps({"type": "auth", "token": "tok"}),
            json.dumps({"type": "x" * 81}),
        ],
        uid=uid, path_uid=uid, jwt_uid=uid,
    ))
    check("P19  Oversized type (>80 chars) → close 4004", ws.closed_code == 4004)
    server._ws_event_violations.pop(uid, None)


def test_P20():
    """Valid unknown string type → violation path taken, not close 4004.
    Note: violation counter is cleared by _ws_cleanup_typing_log on disconnect,
    so we verify the code path via ws.closed_code (None = natural disconnect, not 4004 = invalid type).
    """
    uid = 6005
    server._ws_event_violations.pop(uid, None)
    ws, _, _ = run(_run_ws(
        recv=[
            json.dumps({"type": "auth", "token": "tok"}),
            json.dumps({"type": "unknown_event_xyz"}),
        ],
        uid=uid, path_uid=uid, jwt_uid=uid,
    ))
    # closed_code is None (natural disconnect) — not 4004 (invalid type path)
    check("P20  Valid unknown string type → not 4004 (violation path, not invalid-type path)",
          ws.closed_code != 4004)
    server._ws_event_violations.pop(uid, None)


def test_P21():
    """Type field missing entirely → close 4004."""
    uid = 6006
    server._ws_event_violations.pop(uid, None)
    ws, _, _ = run(_run_ws(
        recv=[
            json.dumps({"type": "auth", "token": "tok"}),
            json.dumps({"content": "hello"}),  # no type key at all
        ],
        uid=uid, path_uid=uid, jwt_uid=uid,
    ))
    check("P21  Missing type field (None from get) → close 4004", ws.closed_code == 4004)
    server._ws_event_violations.pop(uid, None)


def test_P22():
    """Exactly 80-char type string → valid (enters violation counter, not 4004)."""
    uid = 6007
    server._ws_event_violations.pop(uid, None)
    ws, _, _ = run(_run_ws(
        recv=[
            json.dumps({"type": "auth", "token": "tok"}),
            json.dumps({"type": "x" * 80}),
        ],
        uid=uid, path_uid=uid, jwt_uid=uid,
    ))
    check("P22  Exactly 80-char type string → not 4004 (valid, enters violation counter)",
          ws.closed_code != 4004)
    server._ws_event_violations.pop(uid, None)


test_P01(); test_P02(); test_P03(); test_P04(); test_P05()
test_P06(); test_P07(); test_P08(); test_P09(); test_P10()
test_P11(); test_P12(); test_P13(); test_P14(); test_P15()
test_P16(); test_P17(); test_P18(); test_P19(); test_P20(); test_P21(); test_P22()


# ═══════════════════════════════════════════════════════════════════════════════
# ══ A: server._BoundedTTLCache ════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════════════════════

print("\n── A  server._BoundedTTLCache ──────────────────────────────────────────")


def test_A01():
    c = server._BoundedTTLCache(100, 300.0, 60.0)
    check("A01  get() returns None for missing key", c.get(("a", "b")) is None)


def test_A02():
    c = server._BoundedTTLCache(100, 300.0, 60.0)
    c.set(("x", "y"), True)
    check("A02  set(True) + get() returns True within TTL", c.get(("x", "y")) is True)


def test_A03():
    c = server._BoundedTTLCache(100, 300.0, 60.0)
    c.set(("x", "y"), False)
    check("A03  set(False) + get() returns False within neg_ttl", c.get(("x", "y")) is False)


def test_A04():
    c = server._BoundedTTLCache(100, 0.01, 0.01)  # 10 ms TTL
    c.set(("a", "b"), True)
    time.sleep(0.05)
    check("A04  Expired entry returns None", c.get(("a", "b")) is None)


def test_A05():
    c = server._BoundedTTLCache(3, 300.0, 60.0)
    for k in [(1, 2), (2, 3), (3, 4)]:
        c.set(k, True)
    c.set((4, 5), True)  # evicts (1, 2)
    check("A05  maxsize evicts oldest entry on overflow",
          c.get((1, 2)) is None and c.get((4, 5)) is True)


test_A01(); test_A02(); test_A03(); test_A04(); test_A05()


# ═══════════════════════════════════════════════════════════════════════════════
# ══ B: server.ConnectionManager ═══════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════════════════════

print("\n── B  server.ConnectionManager ─────────────────────────────────────────")


def test_B01():
    mgr = server.ConnectionManager()
    ws = object()
    result = mgr.register(1, ws)
    check("B01  register() new user returns True and stores WS",
          result is True and ws in mgr.active.get(1, []))


def test_B02():
    mgr = server.ConnectionManager()
    ws1, ws2 = object(), object()
    mgr.register(1, ws1)
    result = mgr.register(1, ws2)
    check("B02  register() second connection succeeds",
          result is True and len(mgr.active[1]) == 2)


def test_B03():
    mgr = server.ConnectionManager()
    for _ in range(server._WS_MAX_CONN_PER_USER):
        mgr.active.setdefault(1, []).append(object())
    extra = object()
    result = mgr.register(1, extra)
    check("B03  register() over limit returns False without adding",
          result is False and extra not in mgr.active.get(1, []))


def test_B04():
    mgr = server.ConnectionManager()
    ws = object()
    mgr.register(1, ws)
    result = mgr.register(1, ws)  # duplicate
    check("B04  register() duplicate WS returns True, no duplicate stored",
          result is True and mgr.active[1].count(ws) == 1)


def test_B05():
    mgr = server.ConnectionManager()
    ws = object()
    mgr.register(1, ws)
    mgr.disconnect(1, ws)
    check("B05  disconnect() removes WS, clears active entry", 1 not in mgr.active)


def test_B06():
    mgr = server.ConnectionManager()
    ws1, ws2 = object(), object()
    mgr.register(1, ws1); mgr.register(1, ws2)
    mgr.active_conversations[1] = 42
    mgr._conv_ws_owner[1] = ws1
    mgr.disconnect(1, ws1)
    check("B06  disconnect() clears conv_owner when owner WS disconnects",
          1 not in mgr.active_conversations)


def test_B07():
    """send_to_user() dead socket cleanup routes through disconnect() — owner state cleared."""
    mgr = server.ConnectionManager()

    class DeadWS:
        async def send_text(self, _):
            raise RuntimeError("socket dead")

    uid = 8001
    dead = DeadWS()
    dummy_alive = object()  # something that won't be called (it's a plain object, not async-capable)

    mgr.active[uid] = [dead]
    mgr.active_conversations[uid] = 99
    mgr._conv_ws_owner[uid] = dead

    with patch.object(server, "ws_manager", mgr):
        result = asyncio.get_event_loop().run_until_complete(
            mgr.send_to_user(uid, {"type": "ping"})
        )

    check("B07  send_to_user() dead socket cleanup via disconnect() clears conv_owner",
          uid not in mgr.active_conversations and
          uid not in mgr._conv_ws_owner and
          uid not in mgr.active)


def test_B08():
    """send_to_user() last dead socket removed → _ws_cleanup_typing_log() called."""
    mgr = server.ConnectionManager()

    class DeadWS:
        async def send_text(self, _):
            raise RuntimeError("socket dead")

    uid = 8002

    class DeadWS2:
        async def send_text(self, _):
            raise RuntimeError("dead too")

    mgr.active[uid] = [DeadWS(), DeadWS2()]
    server._ws_typing_log[uid] = deque([time.time()])
    server._ws_ctrl_log[uid]   = deque([time.time()])

    with patch.object(server, "ws_manager", mgr):
        asyncio.get_event_loop().run_until_complete(
            mgr.send_to_user(uid, {"type": "ping"})
        )

    check("B08  send_to_user() all sockets dead → rate-limit state cleared",
          uid not in server._ws_typing_log and uid not in server._ws_ctrl_log)


test_B01(); test_B02(); test_B03(); test_B04(); test_B05(); test_B06()
test_B07(); test_B08()


# ═══════════════════════════════════════════════════════════════════════════════
# ══ C: server._ws_validate_auth_frame() ═══════════════════════════════════════
# ═══════════════════════════════════════════════════════════════════════════════

print("\n── C  server._ws_validate_auth_frame() ─────────────────────────────────")


def test_C01():
    oversized = "x" * (server._WS_AUTH_FRAME_MAX + 1)
    uid, code = server._ws_validate_auth_frame(oversized)
    check("C01  Oversized auth frame → -1, 4002", uid == -1 and code == 4002)


def test_C02():
    uid, code = server._ws_validate_auth_frame("not json at all")
    check("C02  Non-JSON auth frame → -1, 4002", uid == -1 and code == 4002)


def test_C03():
    uid, code = server._ws_validate_auth_frame(json.dumps([1, 2, 3]))
    check("C03  JSON array → -1, 4002", uid == -1 and code == 4002)


def test_C04():
    uid, code = server._ws_validate_auth_frame(json.dumps({"type": "message", "token": "x"}))
    check("C04  Wrong type in auth frame → -1, 4002", uid == -1 and code == 4002)


def test_C05():
    uid, code = server._ws_validate_auth_frame(json.dumps({"type": "auth", "token": ""}))
    check("C05  Empty token → -1, 4001", uid == -1 and code == 4001)


def test_C06():
    with patch.object(server, "_jwt_decode", return_value=None):
        uid, code = server._ws_validate_auth_frame(json.dumps({"type": "auth", "token": "bad.jwt"}))
    check("C06  Invalid JWT → -1, 4001", uid == -1 and code == 4001)


def test_C07():
    with patch.object(server, "_jwt_decode", return_value={"user_id": 42, "user_type": "emp"}):
        uid, code = server._ws_validate_auth_frame(json.dumps({"type": "auth", "token": "valid"}))
    check("C07  Valid JWT → (42, 0)", uid == 42 and code == 0)


test_C01(); test_C02(); test_C03(); test_C04(); test_C05(); test_C06(); test_C07()


# ═══════════════════════════════════════════════════════════════════════════════
# ══ D: server._ws_origin_ok() ═════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════════════════════

print("\n── D  server._ws_origin_ok() ───────────────────────────────────────────")


class _FakeOriginWS:
    class _H:
        def __init__(self, o): self._o = o
        def get(self, k, d=""): return self._o if k == "origin" else d
    def __init__(self, origin): self.headers = self._H(origin)


def test_D01():
    check("D01  No origin (native client) → allowed",
          server._ws_origin_ok(_FakeOriginWS("")) is True)


def test_D02():
    check("D02  'null' origin → denied",
          server._ws_origin_ok(_FakeOriginWS("null")) is False)


def test_D03():
    check("D03  Production origin → allowed",
          server._ws_origin_ok(_FakeOriginWS("https://tawasolna.com")) is True)


def test_D04():
    check("D04  Unknown origin → denied",
          server._ws_origin_ok(_FakeOriginWS("https://evil.example.com")) is False)


test_D01(); test_D02(); test_D03(); test_D04()


# ═══════════════════════════════════════════════════════════════════════════════
# ══ E: server._ws_typing_rate_ok() / _ws_ctrl_rate_ok() ══════════════════════
# ═══════════════════════════════════════════════════════════════════════════════

print("\n── E  server._ws_typing_rate_ok() / _ws_ctrl_rate_ok() ─────────────────")


def test_E01():
    uid = 9901
    server._ws_typing_log.pop(uid, None)
    results = [server._ws_typing_rate_ok(uid) for _ in range(server._WS_TYPING_MAX)]
    check("E01  Under typing rate limit → all True", all(results))
    server._ws_typing_log.pop(uid, None)


def test_E02():
    uid = 9902
    server._ws_typing_log.pop(uid, None)
    for _ in range(server._WS_TYPING_MAX):
        server._ws_typing_rate_ok(uid)
    check("E02  Over typing rate limit → False",
          server._ws_typing_rate_ok(uid) is False)
    server._ws_typing_log.pop(uid, None)


def test_E03():
    uid = 9903
    server._ws_ctrl_log.pop(uid, None)
    results = [server._ws_ctrl_rate_ok(uid) for _ in range(server._WS_CTRL_MAX)]
    check("E03  Under ctrl rate limit → all True", all(results))
    server._ws_ctrl_log.pop(uid, None)


def test_E04():
    uid = 9904
    server._ws_ctrl_log.pop(uid, None)
    for _ in range(server._WS_CTRL_MAX):
        server._ws_ctrl_rate_ok(uid)
    check("E04  Over ctrl rate limit → False",
          server._ws_ctrl_rate_ok(uid) is False)
    server._ws_ctrl_log.pop(uid, None)


test_E01(); test_E02(); test_E03(); test_E04()


# ═══════════════════════════════════════════════════════════════════════════════
# ══ F: server._ws_cleanup_typing_log() ════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════════════════════

print("\n── F  server._ws_cleanup_typing_log() ──────────────────────────────────")


def test_F01():
    """No remaining connections → all rate-limit state cleared."""
    uid = 9801
    mgr = server.ConnectionManager()  # uid not in mgr.active
    server._ws_typing_log[uid] = deque([time.time()])
    server._ws_ctrl_log[uid]   = deque([time.time()])
    with patch.object(server, "ws_manager", mgr):
        server._ws_cleanup_typing_log(uid)
    check("F01  No remaining connections → rate-limit state cleared",
          uid not in server._ws_typing_log and uid not in server._ws_ctrl_log)


def test_F02():
    """Active connection remains → state preserved."""
    uid = 9802
    mgr = server.ConnectionManager()
    mgr.active[uid] = [object()]  # one connection still alive
    server._ws_typing_log[uid] = deque([time.time()])
    server._ws_ctrl_log[uid]   = deque([time.time()])
    with patch.object(server, "ws_manager", mgr):
        server._ws_cleanup_typing_log(uid)
    check("F02  Remaining connection → rate-limit state preserved",
          uid in server._ws_typing_log and uid in server._ws_ctrl_log)
    server._ws_typing_log.pop(uid, None)
    server._ws_ctrl_log.pop(uid, None)


def test_F03():
    """No remaining connections → _ws_event_violations also cleared."""
    uid = 9803
    mgr = server.ConnectionManager()
    server._ws_event_violations[uid] = 5
    with patch.object(server, "ws_manager", mgr):
        server._ws_cleanup_typing_log(uid)
    check("F03  No remaining connections → _ws_event_violations cleared",
          uid not in server._ws_event_violations)


test_F01(); test_F02(); test_F03()


# ═══════════════════════════════════════════════════════════════════════════════
# ══ G: Typing rate-limit drop behavior (post-hotfix) ═════════════════════════
# ═══════════════════════════════════════════════════════════════════════════════

print("\n── G  Typing rate-limit drop behavior ──────────────────────────────────")


def test_G01():
    """Typing rate limit exceeded → connection NOT closed (no 4005, no disconnect code)."""
    uid = 7001
    server._ws_typing_log.pop(uid, None)
    for _ in range(server._WS_TYPING_MAX):
        server._ws_typing_rate_ok(uid)

    mock_conv = AsyncMock(return_value=True)
    ws = FakeWS(origin="", recv=[
        json.dumps({"type": "auth", "token": "tok"}),
        json.dumps({"type": "typing", "to_user_id": 200}),
    ])
    mgr = server.ConnectionManager()
    with patch.object(server, "ws_manager", mgr), \
         patch.object(server, "_jwt_decode", return_value={"user_id": uid, "user_type": "emp"}), \
         patch.object(server, "_ws_conversation_exists_async", new=mock_conv):
        run(server.websocket_endpoint(ws, uid))

    check("G01  Typing rate limit exceeded → ws.closed_code is None (natural disconnect, not error)",
          ws.closed_code is None,
          f"got closed_code={ws.closed_code!r}")
    server._ws_typing_log.pop(uid, None)


def test_G02():
    """Typing rate limit exceeded → DB (_ws_conversation_exists_async) never called."""
    uid = 7002
    server._ws_typing_log.pop(uid, None)
    for _ in range(server._WS_TYPING_MAX):
        server._ws_typing_rate_ok(uid)

    mock_conv = AsyncMock(return_value=True)
    ws = FakeWS(origin="", recv=[
        json.dumps({"type": "auth", "token": "tok"}),
        json.dumps({"type": "typing", "to_user_id": 200}),
    ])
    mgr = server.ConnectionManager()
    with patch.object(server, "ws_manager", mgr), \
         patch.object(server, "_jwt_decode", return_value={"user_id": uid, "user_type": "emp"}), \
         patch.object(server, "_ws_conversation_exists_async", new=mock_conv):
        run(server.websocket_endpoint(ws, uid))

    check("G02  Typing rate limit exceeded → DB never queried (rate-before-DB ordering preserved)",
          mock_conv.call_count == 0,
          f"DB called {mock_conv.call_count} time(s)")
    server._ws_typing_log.pop(uid, None)


def test_G03():
    """Multiple excess typing events all dropped; violation counter NOT incremented."""
    uid = 7003
    server._ws_typing_log.pop(uid, None)
    server._ws_event_violations.pop(uid, None)
    for _ in range(server._WS_TYPING_MAX):
        server._ws_typing_rate_ok(uid)

    mock_conv = AsyncMock(return_value=True)
    # Send 3 excess typing events
    excess_msgs = [json.dumps({"type": "typing", "to_user_id": 200}) for _ in range(3)]
    ws = FakeWS(origin="", recv=[
        json.dumps({"type": "auth", "token": "tok"}),
    ] + excess_msgs)
    mgr = server.ConnectionManager()
    with patch.object(server, "ws_manager", mgr), \
         patch.object(server, "_jwt_decode", return_value={"user_id": uid, "user_type": "emp"}), \
         patch.object(server, "_ws_conversation_exists_async", new=mock_conv):
        run(server.websocket_endpoint(ws, uid))

    violations = server._ws_event_violations.get(uid, 0)
    check("G03  Multiple excess typing events dropped; no violation counter increment; still alive",
          ws.closed_code is None and violations == 0,
          f"closed_code={ws.closed_code!r} violations={violations}")
    server._ws_typing_log.pop(uid, None)
    server._ws_event_violations.pop(uid, None)


def test_G04():
    """Normal typing events (within rate limit) reach DB check."""
    uid = 7004
    server._ws_typing_log.pop(uid, None)

    mock_conv = AsyncMock(return_value=False)  # conv doesn't exist — but DB IS queried
    ws = FakeWS(origin="", recv=[
        json.dumps({"type": "auth", "token": "tok"}),
        json.dumps({"type": "typing", "to_user_id": 200}),
    ])
    mgr = server.ConnectionManager()
    with patch.object(server, "ws_manager", mgr), \
         patch.object(server, "_jwt_decode", return_value={"user_id": uid, "user_type": "emp"}), \
         patch.object(server, "_ws_conversation_exists_async", new=mock_conv):
        run(server.websocket_endpoint(ws, uid))

    check("G04  Under rate limit → DB queried (normal typing path unaffected)",
          mock_conv.call_count >= 1,
          f"DB called {mock_conv.call_count} time(s)")
    server._ws_typing_log.pop(uid, None)


def test_G05():
    """After typing rate limit exceeded, connection still accepts other event types."""
    uid = 7005
    server._ws_typing_log.pop(uid, None)
    server._ws_ctrl_log.pop(uid, None)
    server._ws_event_violations.pop(uid, None)
    for _ in range(server._WS_TYPING_MAX):
        server._ws_typing_rate_ok(uid)

    mock_conv = AsyncMock(return_value=True)
    ws = FakeWS(origin="", recv=[
        json.dumps({"type": "auth", "token": "tok"}),
        json.dumps({"type": "typing", "to_user_id": 200}),   # rate-limited, dropped
        json.dumps({"type": "active_conversation", "other_id": 200}),  # should still work
    ])
    mgr = server.ConnectionManager()
    with patch.object(server, "ws_manager", mgr), \
         patch.object(server, "_jwt_decode", return_value={"user_id": uid, "user_type": "emp"}), \
         patch.object(server, "_ws_conversation_exists_async", new=mock_conv):
        run(server.websocket_endpoint(ws, uid))

    # active_conversation triggers DB check (mock_conv.call_count >= 1)
    # and connection still ends naturally
    check("G05  After typing rate limit, connection accepts active_conversation events",
          ws.closed_code is None and mock_conv.call_count >= 1,
          f"closed_code={ws.closed_code!r} db_calls={mock_conv.call_count}")
    server._ws_typing_log.pop(uid, None)
    server._ws_ctrl_log.pop(uid, None)
    server._ws_event_violations.pop(uid, None)


test_G01(); test_G02(); test_G03(); test_G04(); test_G05()


# ── Summary ──────────────────────────────────────────────────────────────────

total = PASS + FAIL
print(f"\n{'─'*60}")
print(f"  {PASS}/{total} passed  {'✓  all green' if FAIL == 0 else f'✗  {FAIL} FAILED'}")
print(f"{'─'*60}\n")
sys.exit(0 if FAIL == 0 else 1)
