"""
test_server_error_leak.py — PR 1.6: no server internals in error responses.
SYSTEMS_INDEX §54d · CLAUDE.md → Safe Rendering rule 9.
Real FastAPI app; DB helpers mocked.

Run: python -m pytest test_server_error_leak.py -q
"""
import ast, os, sys

sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault("JWT_SECRET", "test-user-secret-" + "u" * 32)

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel
from unittest.mock import MagicMock

import auth
import server as srv

HERE = os.path.dirname(os.path.abspath(__file__))
DB_TEXT = 'duplicate key value violates unique constraint "job_applications_pkey" on table secret_tbl'
client = TestClient(srv.app, raise_server_exceptions=False)


class _M(BaseModel):
    age: int


@srv.app.get("/__test/pr16/dict-detail")
def _t_dict():
    raise HTTPException(422, detail={"status": "error", "message": "اسم المهارة مطلوب", "field": "skill"})

@srv.app.post("/__test/pr16/validate")
def _t_validate(body: _M):
    return {"ok": True}


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setattr(srv, "JWT_SECRET", "test-user-secret-" + "u" * 32)
    monkeypatch.setattr(auth, "get_password_changed_epoch", lambda uid: None)
    srv._pwd_changed_cache.clear()


def _auth_hdr():
    return {"Authorization": "Bearer " + srv._jwt_encode({"user_id": 7, "user_type": "co"})}


# ── runtime ──────────────────────────────────────────────────────────────────

def test_db_error_text_never_reaches_client(monkeypatch, capsys):
    def boom(app_id, company_id):
        raise RuntimeError(DB_TEXT)
    monkeypatch.setattr(srv, "promote_application_to_shortlist", boom)
    r = client.post("/jobs/applications/5/promote", headers=_auth_hdr())
    assert r.status_code == 500
    assert r.json() == {"error": srv._SERVER_ERROR_MSG}
    assert "secret_tbl" not in r.text and "constraint" not in r.text
    assert "secret_tbl" in capsys.readouterr().out   # full details stay in the log


def test_server_error_helper():
    e = srv._server_error("where_x", ValueError(DB_TEXT))
    assert e.status_code == 500 and e.detail == "خطأ في الخادم، حاول مرة أخرى"


def test_auth_profile_interest_hides_db_text(monkeypatch):
    conn = MagicMock()
    conn.run.side_effect = Exception(DB_TEXT)
    monkeypatch.setattr(auth, "get_conn", lambda: conn)
    monkeypatch.setattr(auth, "release_conn", lambda c: None)
    for res in (auth.save_profile_interest(1, 2), auth.remove_profile_interest(1, 2)):
        assert res["success"] is False and "secret_tbl" not in res["error"]


def test_dict_detail_is_real_json_with_error_message():
    r = client.get("/__test/pr16/dict-detail")
    assert r.status_code == 422
    assert r.json() == {"error": "اسم المهارة مطلوب",
                        "detail": {"status": "error", "message": "اسم المهارة مطلوب", "field": "skill"}}


def test_string_detail_shape_unchanged():
    assert srv._http_error_content("المستخدم غير موجود") == {"error": "المستخدم غير موجود"}


def test_validation_returns_field_and_type_only():
    r = client.post("/__test/pr16/validate", json={"age": "SECRET-VALUE-123"})
    assert r.status_code == 422
    assert "SECRET-VALUE-123" not in r.text
    assert r.json() == {"error": "بيانات غير صحيحة",
                        "details": [{"loc": ["body", "age"], "type": "int_parsing"}]}


# ── static: no exception text in any client response ─────────────────────────

_BROAD = {None, "Exception", "BaseException"}

def _refs_var(node, var):
    """str(var) / repr(var) / f"...{var}..." / f"...{str(var)}..." anywhere inside node."""
    for n in ast.walk(node):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in ("str", "repr") \
                and n.args and isinstance(n.args[0], ast.Name) and n.args[0].id == var:
            return True
        if isinstance(n, ast.FormattedValue) and any(
                isinstance(x, ast.Name) and x.id == var for x in ast.walk(n.value)):
            return True
    return False

def _type_names(h):
    if h.type is None:
        return {None}
    elts = h.type.elts if isinstance(h.type, ast.Tuple) else [h.type]
    return {getattr(t, "id", getattr(t, "attr", "?")) for t in elts}

def _call_name(c):
    return getattr(c.func, "id", getattr(c.func, "attr", ""))

def _status(c):
    a = c.args[0] if c.args else next((k.value for k in c.keywords if k.arg == "status_code"), None)
    return a.value if isinstance(a, ast.Constant) and isinstance(a.value, int) else 0

def _violations(fname):
    tree = ast.parse(open(os.path.join(HERE, fname), encoding="utf-8").read())
    out = []
    for h in ast.walk(tree):
        if not isinstance(h, ast.ExceptHandler) or not h.name:
            continue
        broad = bool(_type_names(h) & _BROAD)
        for n in ast.walk(h):
            if isinstance(n, ast.Call) and _call_name(n) == "HTTPException" and _refs_var(n, h.name):
                if broad or _status(n) >= 500:
                    out.append(f"{fname}:{n.lineno} HTTPException with exception text")
            elif broad and isinstance(n, ast.Raise) and isinstance(n.exc, ast.Call) \
                    and _call_name(n.exc) != "HTTPException" and _refs_var(n.exc, h.name):
                out.append(f"{fname}:{n.lineno} re-raised with exception text")
            elif broad and isinstance(n, ast.Dict) and any(v is not None and _refs_var(v, h.name) for v in n.values):
                out.append(f"{fname}:{n.lineno} response dict with exception text")
    return out

def test_no_exception_text_in_responses_static():
    v = _violations("server.py") + _violations("auth.py")
    assert v == [], "\n".join(v)
