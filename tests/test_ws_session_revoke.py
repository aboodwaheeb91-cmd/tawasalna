"""
WS Session Revocation (PR 4.0) — behavioral test, no DB / no live server.

Real websocket_endpoint + real PUT /auth/password through Starlette's TestClient;
only the DB helpers (password check / store / password_changed_at lookup) are faked.

  1. open /ws/{uid} with a JWT issued before the change → auth_ok
  2. PUT /auth/password → the open socket is closed with 4008 and ws_manager no
     longer holds it (send_to_user delivers nothing)
  3. reconnect with the old JWT → 4001 · reconnect with the new JWT → auth_ok

Run:  python tests/test_ws_session_revoke.py
"""
import asyncio
import os
import sys
import time

os.environ.setdefault("SUPABASE_DB_URL", "postgres://test:test@localhost/test_db")
os.environ.setdefault("JWT_SECRET",      "test_jwt_secret_for_ws_revoke_tests_32b")
os.environ.setdefault("ADMIN_TOKEN",     "test_admin_token_for_ws_revoke_test_32b")
os.environ.setdefault("ADMIN_URL_TOKEN", "test_admin_url_token")
os.environ.setdefault("APP_ENV",         "development")

import auth    # noqa: E402
import server  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

FAIL = 0


def check(name, cond, detail=""):
    global FAIL
    print(("  PASS  " if cond else "  FAIL  ") + name + ("" if cond else f" — {detail}"))
    if not cond:
        FAIL += 1


UID = 4242
_changed = {"epoch": None}

# DB fakes — the code under test (endpoint, JWT check, ws_manager) is real.
auth.get_password_changed_epoch = lambda uid: _changed["epoch"] if uid == UID else None
server.check_user_password = lambda uid, pw: True


def _fake_set_password(uid, pw):
    _changed["epoch"] = int(time.time())
    return _changed["epoch"]


server.set_user_password = _fake_set_password
server._pwd_changed_cache.clear()

now = int(time.time())
old_jwt = server._jwt_sign({"user_id": UID, "user_type": "emp", "tw_id": "U1",
                            "iat": now - 60, "exp": now + 3600}, server.JWT_SECRET)

client = TestClient(server.app)

print("WS Session Revocation (PR 4.0)")
with client.websocket_connect(f"/ws/{UID}") as ws:
    ws.send_json({"type": "auth", "token": old_jwt})
    msg = ws.receive_json()
    check("old-session socket authenticates", msg.get("type") == "auth_ok", msg)
    check("socket is registered", UID in server.ws_manager.active)

    r = client.put("/auth/password", headers={"Authorization": "Bearer " + old_jwt},
                   json={"current_password": "OldPass#2024x", "new_password": "NewPass#2025y"})
    check("PUT /auth/password → 200", r.status_code == 200, r.text)
    new_jwt = (r.json() or {}).get("token", "")

    # checked first: without the revoke the socket stays registered and receive() would block
    check("ws_manager no longer holds the user", UID not in server.ws_manager.active)
    if FAIL:
        sys.exit(1)
    closed = ws.receive()
    check("open socket closed with 4008 (session revoked)",
          closed.get("type") == "websocket.close" and closed.get("code") == 4008, closed)
    delivered = asyncio.run(server.ws_manager.send_to_user(UID, {"type": "new_message"}))
    check("nothing is delivered after the change", delivered is False)

with client.websocket_connect(f"/ws/{UID}") as ws:
    ws.send_json({"type": "auth", "token": old_jwt})
    closed = ws.receive()
    check("reconnect with the old JWT → 4001",
          closed.get("type") == "websocket.close" and closed.get("code") == 4001, closed)

with client.websocket_connect(f"/ws/{UID}") as ws:
    ws.send_json({"type": "auth", "token": new_jwt})
    msg = ws.receive_json()
    check("reconnect with the new JWT → auth_ok", msg.get("type") == "auth_ok", msg)

check("no socket left → revoke is a no-op", server._ws_revoke_user(UID, "test") == 0)

print("FAILED" if FAIL else "ALL PASSED")
sys.exit(1 if FAIL else 0)
