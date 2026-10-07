"""
test_db_conn_async_safety.py — PR 2A: DB connection release + no sync work in async def.
CLAUDE.md → DB Connection & Async Rules · SYSTEMS_INDEX §54e.

Run: python -m pytest test_db_conn_async_safety.py -q
"""
import ast, os, sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault("JWT_SECRET", "test-user-secret-" + "u" * 32)

import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

import auth
import server as srv

HERE = os.path.dirname(os.path.abspath(__file__))
client = TestClient(srv.app, raise_server_exceptions=False)


def _tree(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as f:
        return ast.parse(f.read())


def _call_name(c):
    return getattr(c.func, "id", getattr(c.func, "attr", ""))


# ── static 1: every get_conn() has release_conn(<var>) in a finally ─────────

def _releases(stmts, var):
    return any(isinstance(n, ast.Call) and _call_name(n) == "release_conn" and n.args
               and isinstance(n.args[0], ast.Name) and n.args[0].id == var
               for s in stmts for n in ast.walk(s))


def _harmless(s):
    """Statements allowed between `conn = get_conn()` and its `try:` (cannot raise)."""
    if not isinstance(s, (ast.Assign, ast.AnnAssign)):
        return False
    v = s.value
    if isinstance(v, (ast.Constant, ast.Name, ast.Dict, ast.List, ast.Set)):
        return True
    return isinstance(v, ast.Call) and _call_name(v) in ("perf_counter", "time", "monotonic")


def _unreleased(tree):
    parents = {c: p for p in ast.walk(tree) for c in ast.iter_child_nodes(p)}
    bad = []
    for n in ast.walk(tree):
        if not (isinstance(n, ast.Call) and _call_name(n) == "get_conn"):
            continue
        st = parents[n]
        if not (isinstance(st, ast.Assign) and isinstance(st.targets[0], ast.Name)):
            bad.append(n.lineno)
            continue
        var, ok = st.targets[0].id, False
        par = parents[st]
        for field in ("body", "orelse", "finalbody"):
            lst = getattr(par, field, None)
            if isinstance(lst, list) and st in lst:
                j = lst.index(st) + 1
                while j < len(lst) and _harmless(lst[j]):
                    j += 1
                if j < len(lst) and isinstance(lst[j], ast.Try) and _releases(lst[j].finalbody, var):
                    ok = True
        cur = st
        while not ok and cur in parents:
            p = parents[cur]
            if isinstance(p, ast.Try) and cur in p.body and _releases(p.finalbody, var):
                ok = True
            if isinstance(p, (ast.FunctionDef, ast.AsyncFunctionDef)):
                break
            cur = p
        if not ok:
            bad.append(n.lineno)
    return bad


@pytest.mark.parametrize("fname", ["server.py", "auth.py"])
def test_every_get_conn_released_in_finally(fname):
    assert _unreleased(_tree(fname)) == [], f"{fname}: get_conn() without release_conn in finally"


# ── static 2: no async def runs a DB connection / known sync DB helper directly ──

_SYNC_DB = {"get_conn", "db_conn", "release_conn", "get_messages", "set_site_setting",
            "get_site_setting", "ensure_site_settings_table", "ensure_reports_table",
            "_current_image_urls", "_mig_run", "set_user_password"}


def _direct_calls(fn):
    out = set()
    stack = list(ast.iter_child_nodes(fn))
    while stack:
        c = stack.pop()
        if isinstance(c, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            continue   # nested sync helper handed to asyncio.to_thread
        if isinstance(c, ast.Call):
            out.add(_call_name(c))
        stack.extend(ast.iter_child_nodes(c))
    return out


def test_no_async_def_does_sync_db_work():
    bad = [(n.name, sorted(_direct_calls(n) & _SYNC_DB))
           for n in ast.walk(_tree("server.py")) if isinstance(n, ast.AsyncFunctionDef)
           if _direct_calls(n) & _SYNC_DB]
    assert bad == []


def test_fixed_endpoints_are_sync():
    names = {"submit_report", "update_user_name", "change_user_type",
             "verify_user", "admin_reset_password"}
    async_ = {n.name for n in ast.walk(_tree("server.py")) if isinstance(n, ast.AsyncFunctionDef)}
    assert names & async_ == set()


# ── runtime ──────────────────────────────────────────────────────────────────

@pytest.fixture
def fake_db(monkeypatch):
    monkeypatch.setattr(srv, "JWT_SECRET", "test-user-secret-" + "u" * 32)
    monkeypatch.setattr(auth, "get_password_changed_epoch", lambda uid: None)
    srv._pwd_changed_cache.clear()
    conn = MagicMock()
    released = []
    monkeypatch.setattr(auth, "get_conn", lambda: conn)
    monkeypatch.setattr(auth, "release_conn", released.append)
    return conn, released


def _hdr(uid, utype):
    return {"Authorization": "Bearer " + srv._jwt_encode({"user_id": uid, "user_type": utype})}


def test_edu_name_change_ok_and_conn_released(fake_db):
    conn, released = fake_db
    r = client.put("/auth/user/9/name", headers=_hdr(9, "edu"),
                   json={"full_name": "  جامعة   النور  "})
    assert r.status_code == 200 and r.json() == {"success": True}
    assert conn.run.call_args.kwargs == {"name": "جامعة النور", "uid": 9}
    assert released == [conn]


def test_emp_name_change_uses_g_contract(fake_db):
    conn, _ = fake_db
    r = client.put("/auth/user/9/name", headers=_hdr(9, "emp"), json={"full_name": "x y"})
    assert r.status_code == 422
    assert r.json()["errors"][0]["code"] == "emp_name_mutation_forbidden"
    conn.run.assert_not_called()


def test_rating_with_comment_returns_200(fake_db, monkeypatch):
    conn, released = fake_db
    ts = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    conn.run.side_effect = [[[4.0, 1]], [[4, 1]], [[4, "ممتازة", ts]]]
    monkeypatch.setattr(srv, "_resolve_company_id", lambda cid: 5)
    r = client.get("/company/5/ratings")
    assert r.status_code == 200
    assert r.json()["recent_comments"][0]["created_at"] == ts.isoformat()
    assert released == [conn]
