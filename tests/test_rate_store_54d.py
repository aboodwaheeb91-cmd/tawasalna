"""Task 5.4d — _rate_store: one capped section per kind · no sort per request.

Behaviour only (real server functions, no DB):
  1  a store full of login locks never evicts another kind's counter → message_send stops at exactly
     RATES["message_send"][0]
  2  a full login-lock section keeps every running lock (only its window ends it)
  3  a full store costs no sort per request (sorted() never called · hits stay fast)

Run: python -m pytest tests/test_rate_store_54d.py -q
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JWT_SECRET", "test-secret-rate-store-54d-" + "x" * 32)

import pytest

import server as srv
import tw_limits

R = tw_limits.RATES


@pytest.fixture(autouse=True)
def clean_store():
    srv._rate_store.clear()
    yield
    srv._rate_store.clear()


def _fill_login_locks(n, now):
    """n running login locks (each at its max fails, inside its window)."""
    max_fails = R["login_ip"][0]
    for i in range(n):
        srv._rate_store[f"login_ip:198.51.{i // 256}.{i % 256}"] = [now] * max_fails


def test_full_login_locks_never_reset_message_send(monkeypatch):
    cap = 50
    monkeypatch.setitem(tw_limits.LIMITS, "mem_store_max_keys", cap)
    max_hits = R["message_send"][0]
    now = srv._time.time()
    _fill_login_locks(cap * 3, now)                      # lock section far past the cap
    allowed = 0
    for i in range(max_hits + 5):
        if srv._rate_ok("message_send", 7):
            allowed += 1
        srv._login_fail(f"flood{i}@x.com", f"203.0.113.{i}")   # more lock keys between sends
        srv._rate_sweep(force=True)
    assert allowed == max_hits
    assert len(srv._rate_store["message_send:7"]) == max_hits


def test_full_lock_section_keeps_running_locks(monkeypatch):
    cap = 10
    monkeypatch.setitem(tw_limits.LIMITS, "mem_store_max_keys", cap)
    now = srv._time.time()
    _fill_login_locks(cap * 2, now)
    srv._login_fail("new@x.com", "203.0.113.77")         # new key into a full lock section
    srv._rate_sweep(force=True)
    locks = [k for k in srv._rate_store if k.startswith("login_ip:198.51.")]
    assert len(locks) == cap * 2                         # none dropped before its window ends
    assert srv._login_locked("any@x.com", "198.51.0.0")
    for k in locks:                                      # windows end → they go
        srv._rate_store[k] = [now - R["login_ip"][1] - 1]
    srv._rate_sweep(force=True)
    assert not any(k.startswith("login_ip:198.51.") for k in srv._rate_store)


def test_full_store_no_sort_per_request(monkeypatch):
    cap = 20000
    monkeypatch.setitem(tw_limits.LIMITS, "mem_store_max_keys", cap)
    now = srv._time.time()
    _fill_login_locks(cap, now)
    for i in range(cap):
        srv._rate_store[f"mention_search:u{i}"] = [now]

    def no_sort(*a, **k):
        raise AssertionError("sorted() on the request path")
    monkeypatch.setattr(srv, "sorted", no_sort, raising=False)
    t0 = srv._time.perf_counter()
    for i in range(2000):                                # new keys into a full section → eviction
        assert srv._rate_ok("mention_search", f"n{i}")
        srv._login_fail(f"e{i}@x.com", "203.0.113.5")
    elapsed = srv._time.perf_counter() - t0
    assert len(srv._rate_store.section("mention_search")) == cap
    assert elapsed < 2.0, elapsed                        # a sort of 40k keys per hit would take far longer
