"""
test_privacy_boundary.py — Emergency Privacy Boundary V1
Tests: profile/full auth, auth/user ownership, public profile field stripping,
       KYC owner-only access, KYC write ownership, OTP removal, static checks.

Run against a live server:
  uvicorn server:app --reload &
  python test_privacy_boundary.py
"""

import os
import requests
import json
import random
import string
import re
import sys

BASE = "http://localhost:8000"

_RESULTS = {"passed": 0, "failed": 0, "skipped": 0}


def _rand(n=8):
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=n))


def _register_and_login(user_type="emp"):
    tag = _rand()
    email = f"tw_priv_{tag}@tw-security.test"
    payload = {
        "full_name": f"Priv Test {tag}",
        "email": email,
        "password": "TwTest@9999",
        "user_type": user_type,
        "country_code": "9620",
    }
    r = requests.post(f"{BASE}/auth/register", json=payload)
    assert r.status_code == 200, f"Register failed: {r.text}"
    data = r.json()
    user = data.get("user") or data
    uid = user.get("id") or user.get("user", {}).get("id")
    jwt = data.get("token") or data.get("access_token") or ""
    if not jwt:
        lr = requests.post(f"{BASE}/auth/login", json={"email": email, "password": "TwTest@9999"})
        assert lr.status_code == 200, f"Login failed: {lr.text}"
        ld = lr.json()
        jwt = ld.get("token") or ld.get("access_token") or ""
    return uid, jwt


def _auth(jwt):
    return {"Authorization": f"Bearer {jwt}"}


def _test(name, fn):
    try:
        fn()
        _RESULTS["passed"] += 1
        print(f"  PASS  {name}")
    except AssertionError as e:
        _RESULTS["failed"] += 1
        print(f"  FAIL  {name}: {e}")
    except Exception as e:
        _RESULTS["failed"] += 1
        print(f"  ERROR {name}: {e}")


def _skip(name, reason):
    _RESULTS["skipped"] += 1
    print(f"  SKIP  {name}: {reason}")


# ═══════════════════════════════════════════════════════════════
# A — Full Profile / GET /profile/{id}/full
# ═══════════════════════════════════════════════════════════════

def _test_group_a():
    print("\n[A] GET /profile/{id}/full — JWT required + owner-only")

    uid, jwt = _register_and_login("emp")
    uid2, jwt2 = _register_and_login("emp")

    def a1_no_jwt_returns_401():
        r = requests.get(f"{BASE}/profile/{uid}/full")
        assert r.status_code == 401, f"Expected 401 without JWT, got {r.status_code}"

    def a2_owner_with_jwt_returns_200():
        r = requests.get(f"{BASE}/profile/{uid}/full", headers=_auth(jwt))
        assert r.status_code == 200, f"Expected 200 for owner, got {r.status_code}: {r.text}"

    def a3_other_user_returns_403():
        r = requests.get(f"{BASE}/profile/{uid}/full", headers=_auth(jwt2))
        assert r.status_code == 403, f"Expected 403 for non-owner, got {r.status_code}"

    def a4_owner_profile_has_private_fields():
        # Register a fresh user with a known email so we can verify it round-trips
        known_email = f"tw_a4_{_rand()}@tw-security.test"
        r0 = requests.post(f"{BASE}/auth/register", json={
            "full_name": f"A4 Owner {_rand()}",
            "email": known_email,
            "password": "TwTest@9999",
            "user_type": "emp",
            "country_code": "9620",
        })
        assert r0.status_code == 200, f"A4 register failed: {r0.text}"
        d0 = r0.json()
        a4_uid = (d0.get("user") or d0).get("id")
        a4_jwt = d0.get("token") or d0.get("access_token") or ""
        if not a4_jwt:
            lr = requests.post(f"{BASE}/auth/login", json={"email": known_email, "password": "TwTest@9999"})
            a4_jwt = lr.json().get("token") or lr.json().get("access_token") or ""
        r = requests.get(f"{BASE}/profile/{a4_uid}/full", headers=_auth(a4_jwt))
        assert r.status_code == 200, f"A4 owner /full failed: {r.status_code}"
        profile = r.json().get("profile", {})
        assert "email" in profile, f"Owner profile missing 'email': {list(profile.keys())}"
        assert profile["email"] == known_email, f"email mismatch: got {profile.get('email')!r}, want {known_email!r}"
        assert "id" in profile, f"Owner profile missing 'id': {list(profile.keys())}"

    def a5_private_fields_not_in_public():
        r = requests.get(f"{BASE}/profile/{uid}")
        assert r.status_code == 200
        profile = r.json().get("profile", {})
        assert "email" not in profile, "email leaked in public profile"
        assert "phone" not in profile, "phone leaked in public profile"
        assert "dob" not in profile, "dob leaked in public profile"

    _test("A1 — no JWT → 401", a1_no_jwt_returns_401)
    _test("A2 — owner JWT → 200", a2_owner_with_jwt_returns_200)
    _test("A3 — other user JWT → 403", a3_other_user_returns_403)
    _test("A4 — owner response contains expected fields", a4_owner_profile_has_private_fields)
    _test("A5 — public profile strips email/phone/dob", a5_private_fields_not_in_public)


# ═══════════════════════════════════════════════════════════════
# B — Auth User / GET /auth/user/{id}
# ═══════════════════════════════════════════════════════════════

def _test_group_b():
    print("\n[B] GET /auth/user/{id} — JWT required + owner-only")

    uid, jwt = _register_and_login("emp")
    uid2, jwt2 = _register_and_login("emp")

    def b1_no_jwt_returns_401():
        r = requests.get(f"{BASE}/auth/user/{uid}")
        assert r.status_code == 401, f"Expected 401 without JWT, got {r.status_code}"

    def b2_owner_with_jwt_returns_200():
        r = requests.get(f"{BASE}/auth/user/{uid}", headers=_auth(jwt))
        assert r.status_code == 200, f"Expected 200 for owner, got {r.status_code}: {r.text}"

    def b3_other_user_returns_403():
        r = requests.get(f"{BASE}/auth/user/{uid}", headers=_auth(jwt2))
        assert r.status_code == 403, f"Expected 403 for non-owner, got {r.status_code}"

    def b4_owner_gets_user_object():
        r = requests.get(f"{BASE}/auth/user/{uid}", headers=_auth(jwt))
        assert r.status_code == 200
        data = r.json()
        assert "user" in data, "Response missing 'user' key"
        assert data["user"].get("id") == uid, "User id mismatch"

    _test("B1 — no JWT → 401", b1_no_jwt_returns_401)
    _test("B2 — owner JWT → 200", b2_owner_with_jwt_returns_200)
    _test("B3 — other user JWT → 403", b3_other_user_returns_403)
    _test("B4 — owner gets user object", b4_owner_gets_user_object)


# ═══════════════════════════════════════════════════════════════
# C — Public Profile / GET /profile/{id}
# ═══════════════════════════════════════════════════════════════

def _test_group_c():
    print("\n[C] GET /profile/{id} — public endpoint field containment")

    uid, jwt = _register_and_login("emp")

    def c1_public_returns_200_without_jwt():
        r = requests.get(f"{BASE}/profile/{uid}")
        assert r.status_code == 200, f"Expected 200, got {r.status_code}"

    def c2_no_email_in_public():
        r = requests.get(f"{BASE}/profile/{uid}")
        assert "email" not in r.json().get("profile", {}), "email in public profile"

    def c3_no_phone_in_public():
        r = requests.get(f"{BASE}/profile/{uid}")
        assert "phone" not in r.json().get("profile", {}), "phone in public profile"

    def c4_no_dob_in_public():
        r = requests.get(f"{BASE}/profile/{uid}")
        assert "dob" not in r.json().get("profile", {}), "dob in public profile"

    def c5_no_verify_request_in_public():
        r = requests.get(f"{BASE}/profile/{uid}")
        profile = r.json().get("profile", {})
        assert "verify_request" not in profile, "verify_request in public profile"

    def c6_public_has_expected_fields():
        r = requests.get(f"{BASE}/profile/{uid}")
        profile = r.json().get("profile", {})
        assert "id" in profile, "id missing from public profile"
        assert "full_name" in profile, "full_name missing from public profile"

    def c7_owner_viewing_own_public_profile_still_no_private_fields():
        r = requests.get(f"{BASE}/profile/{uid}", headers=_auth(jwt))
        profile = r.json().get("profile", {})
        assert "email" not in profile, "email leaked to owner on public endpoint"
        assert "phone" not in profile, "phone leaked to owner on public endpoint"

    _test("C1 — public → 200 without JWT", c1_public_returns_200_without_jwt)
    _test("C2 — no email in public profile", c2_no_email_in_public)
    _test("C3 — no phone in public profile", c3_no_phone_in_public)
    _test("C4 — no dob in public profile", c4_no_dob_in_public)
    _test("C5 — no verify_request in public profile", c5_no_verify_request_in_public)
    _test("C6 — public profile has expected fields", c6_public_has_expected_fields)
    _test("C7 — public endpoint strips private fields even for owner", c7_owner_viewing_own_public_profile_still_no_private_fields)


# ═══════════════════════════════════════════════════════════════
# D — KYC Status / GET /kyc/status/{id}
# ═══════════════════════════════════════════════════════════════

def _test_group_d():
    print("\n[D] GET /kyc/status/{id} — JWT required + owner-only + allowlist")

    uid, jwt = _register_and_login("emp")
    uid2, jwt2 = _register_and_login("emp")

    def d1_no_jwt_returns_401():
        r = requests.get(f"{BASE}/kyc/status/{uid}")
        assert r.status_code == 401, f"Expected 401, got {r.status_code}"

    def d2_owner_returns_200():
        r = requests.get(f"{BASE}/kyc/status/{uid}", headers=_auth(jwt))
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"

    def d3_other_user_returns_403():
        r = requests.get(f"{BASE}/kyc/status/{uid}", headers=_auth(jwt2))
        assert r.status_code == 403, f"Expected 403, got {r.status_code}"

    def d4_no_email_code_in_kyc_response():
        r = requests.get(f"{BASE}/kyc/status/{uid}", headers=_auth(jwt))
        kyc = r.json().get("kyc", {})
        assert "email_code" not in kyc, "email_code leaked in kyc/status response"

    def d5_no_phone_code_in_kyc_response():
        r = requests.get(f"{BASE}/kyc/status/{uid}", headers=_auth(jwt))
        kyc = r.json().get("kyc", {})
        assert "phone_code" not in kyc, "phone_code leaked in kyc/status response"

    def d6_kyc_status_has_safe_fields():
        r = requests.get(f"{BASE}/kyc/status/{uid}", headers=_auth(jwt))
        assert r.status_code == 200, f"Expected 200, got {r.status_code}"
        kyc = r.json().get("kyc", {})
        assert kyc != {}, f"kyc is empty dict — projection or serialization bug: {r.json()}"
        assert "step" in kyc, f"'step' missing from kyc: {list(kyc.keys())}"
        assert "status" in kyc, f"'status' missing from kyc: {list(kyc.keys())}"
        assert "email_code" not in kyc, "email_code must never appear in kyc/status"
        assert "phone_code" not in kyc, "phone_code must never appear in kyc/status"

    _test("D1 — no JWT → 401", d1_no_jwt_returns_401)
    _test("D2 — owner JWT → 200", d2_owner_returns_200)
    _test("D3 — other user JWT → 403", d3_other_user_returns_403)
    _test("D4 — no email_code in response", d4_no_email_code_in_kyc_response)
    _test("D5 — no phone_code in response", d5_no_phone_code_in_kyc_response)
    _test("D6 — kyc response has safe shape", d6_kyc_status_has_safe_fields)


# ═══════════════════════════════════════════════════════════════
# E — KYC Write Ownership
# ═══════════════════════════════════════════════════════════════

def _test_group_e():
    print("\n[E] KYC write endpoints — user_id from JWT only")

    uid, jwt = _register_and_login("emp")
    uid2, jwt2 = _register_and_login("emp")

    def e1_kyc_start_no_jwt_returns_401():
        r = requests.post(f"{BASE}/kyc/start")
        assert r.status_code == 401, f"Expected 401, got {r.status_code}"

    def e2_kyc_start_with_jwt_uses_token_uid():
        r = requests.post(f"{BASE}/kyc/start", headers=_auth(jwt))
        # 200 = started OK; 400 = already started (also fine — not a 422 schema error)
        assert r.status_code in (200, 400), \
            f"Expected 200 or 400, got {r.status_code} — 422 means schema still requires user_id in body: {r.text}"

    def e3_kyc_email_send_ignores_body_user_id():
        # Send body user_id=uid2 with jwt belonging to uid.
        # Server must extract uid from JWT and ignore body user_id entirely.
        r = requests.post(f"{BASE}/kyc/email/send",
                          headers=_auth(jwt),
                          json={"user_id": uid2, "email": "test@example.com"})
        # Must not be 422 (schema no longer requires user_id in body)
        assert r.status_code != 422, f"422 — schema still requires user_id in body: {r.text}"
        # Must not be 403 (server must not auth-check uid2 from body)
        assert r.status_code != 403, f"403 — server may be checking body user_id: {r.text}"
        # Verify uid was affected (not uid2): uid2's KYC must still be not_started
        r2 = requests.get(f"{BASE}/kyc/status/{uid2}", headers=_auth(jwt2))
        if r2.status_code == 200:
            kyc2 = r2.json().get("kyc", {})
            assert kyc2.get("status") in ("not_started", None), \
                f"uid2's KYC was mutated by uid's token request — IDOR: {kyc2}"

    def e4_kyc_phone_verify_no_jwt_returns_401():
        r = requests.post(f"{BASE}/kyc/phone/verify",
                          json={"user_id": uid, "code": "123456"})
        assert r.status_code == 401, f"Expected 401, got {r.status_code}"

    _test("E1 — kyc/start without JWT → 401", e1_kyc_start_no_jwt_returns_401)
    _test("E2 — kyc/start with JWT (no body user_id) → no 422", e2_kyc_start_with_jwt_uses_token_uid)
    _test("E3 — kyc/email/send ignores body user_id, uses token", e3_kyc_email_send_ignores_body_user_id)
    _test("E4 — kyc/phone/verify without JWT → 401", e4_kyc_phone_verify_no_jwt_returns_401)


# ═══════════════════════════════════════════════════════════════
# F — OTP in API response
# ═══════════════════════════════════════════════════════════════

def _test_group_f():
    print("\n[F] OTP Fail-Closed + no OTP in responses")

    uid, jwt = _register_and_login("emp")

    def f1_email_send_returns_503_no_provider():
        r = requests.post(f"{BASE}/kyc/email/send",
                          headers=_auth(jwt),
                          json={"email": "test@example.com"})
        assert r.status_code == 503, \
            f"Expected 503 (no provider — Fail Closed), got {r.status_code}: {r.text}"
        data = r.json()
        detail = data.get("detail", {})
        assert (isinstance(detail, dict) and detail.get("code") == "otp_delivery_unavailable") or \
               detail == "otp_delivery_unavailable", \
            f"Expected code=otp_delivery_unavailable in detail, got: {detail}"
        assert "dev_code" not in data, f"dev_code leaked in 503 response: {data}"

    def f2_phone_send_returns_503_no_provider():
        r = requests.post(f"{BASE}/kyc/phone/send",
                          headers=_auth(jwt),
                          json={"phone": "+962799000000"})
        assert r.status_code == 503, \
            f"Expected 503 (no provider — Fail Closed), got {r.status_code}: {r.text}"
        data = r.json()
        detail = data.get("detail", {})
        assert (isinstance(detail, dict) and detail.get("code") == "otp_delivery_unavailable") or \
               detail == "otp_delivery_unavailable", \
            f"Expected code=otp_delivery_unavailable in detail, got: {detail}"
        assert "dev_code" not in data, f"dev_code leaked in 503 response: {data}"

    def f3_kyc_status_no_otp_fields():
        r = requests.get(f"{BASE}/kyc/status/{uid}", headers=_auth(jwt))
        kyc = r.json().get("kyc", {})
        for field in ("email_code", "phone_code", "dev_code"):
            assert field not in kyc, f"{field} leaked in kyc/status response"

    def f4_email_send_503_no_db_mutation():
        """503 response must not mutate KYC state as if send succeeded."""
        r = requests.post(f"{BASE}/kyc/email/send",
                          headers=_auth(jwt),
                          json={"email": "should_not_store@example.com"})
        assert r.status_code == 503
        # KYC status must not advance to a "sending" state
        r_status = requests.get(f"{BASE}/kyc/status/{uid}", headers=_auth(jwt))
        if r_status.status_code == 200:
            kyc = r_status.json().get("kyc", {})
            step = kyc.get("step", "")
            # Step must not imply a send was completed
            assert step not in ("email_sent", "email_verified"), \
                f"KYC step advanced to '{step}' despite 503 send failure"

    _test("F1 — kyc/email/send returns 503 (no provider, Fail Closed)", f1_email_send_returns_503_no_provider)
    _test("F2 — kyc/phone/send returns 503 (no provider, Fail Closed)", f2_phone_send_returns_503_no_provider)
    _test("F3 — kyc/status has no otp fields", f3_kyc_status_no_otp_fields)
    _test("F4 — 503 on email/send does not mutate KYC state", f4_email_send_503_no_db_mutation)


# ═══════════════════════════════════════════════════════════════
# G — Static frontend checks
# ═══════════════════════════════════════════════════════════════

def _test_group_g():
    print("\n[G] Static — frontend files use JWT for sensitive calls")

    def _read(path):
        with open(path, encoding="utf-8") as f:
            return f.read()

    def g1_home_html_jwt_on_full():
        src = _read("home.html")
        assert "tw_jwt" in src and "/full" in src, "home.html missing JWT on /full call"
        # The /full fetch should have Authorization header
        assert "Authorization" in src, "home.html missing Authorization header on /full call"

    def g2_edu_profile_uses_public_endpoint():
        src = _read("edu-profile.html")
        # Should NOT call /full anymore
        idx = src.find("/profile/")
        while idx >= 0:
            end = src.find("'", idx)
            segment = src[idx:min(idx + 30, len(src))]
            if "/full" in segment:
                # Check if this is the old call we removed
                assert False, f"edu-profile.html still calls /full: ...{segment}..."
            idx = src.find("/profile/", idx + 1)

    def g3_settings_html_kyc_jwt():
        src = _read("settings.html")
        assert "_kycJwt" in src or "tw_jwt" in src, "settings.html missing JWT helper for KYC"
        assert "Authorization" in src, "settings.html missing Authorization header for KYC calls"

    def g4_settings_html_no_dev_code():
        src = _read("settings.html")
        assert "dev_code" not in src, "settings.html still references dev_code"

    def g5_messages_render_tw_id_propagated():
        src = _read("messages.render.js")
        assert "data-twid" in src, "messages.render.js missing data-twid attribute"
        assert "_activeConvMeta" in src and "twId" in src, "messages.render.js missing twId in _activeConvMeta"

    def g6_messages_render_no_cross_user_api_get_user():
        src = _read("messages.render.js")
        # viewConvProfile and copyConvProfileLink must not call apiGetUser
        # (they use _activeConvMeta.twId directly now)
        assert "apiGetUser(_activeConvMeta" not in src, \
            "messages.render.js still calls apiGetUser for cross-user tw_id lookup"

    _test("G1 — home.html uses JWT for /full", g1_home_html_jwt_on_full)
    _test("G2 — edu-profile.html uses public endpoint (not /full)", g2_edu_profile_uses_public_endpoint)
    _test("G3 — settings.html uses JWT for KYC calls", g3_settings_html_kyc_jwt)
    _test("G4 — settings.html has no dev_code reference", g4_settings_html_no_dev_code)
    _test("G5 — messages.render.js propagates tw_id", g5_messages_render_tw_id_propagated)
    _test("G6 — messages.render.js no cross-user apiGetUser", g6_messages_render_no_cross_user_api_get_user)


# ═══════════════════════════════════════════════════════════════
# H — Regression
# ═══════════════════════════════════════════════════════════════

def _test_group_h():
    print("\n[H] Regression — existing functionality still works")

    uid, jwt = _register_and_login("emp")

    def h1_public_profile_still_works():
        r = requests.get(f"{BASE}/profile/{uid}")
        assert r.status_code == 200, f"Public profile broken: {r.status_code}"

    def h2_public_profile_has_name():
        r = requests.get(f"{BASE}/profile/{uid}")
        assert r.json().get("profile", {}).get("full_name"), "full_name missing from public profile"

    def h3_full_profile_owner_returns_profile_key():
        r = requests.get(f"{BASE}/profile/{uid}/full", headers=_auth(jwt))
        assert r.status_code == 200
        data = r.json()
        assert "profile" in data, "'profile' key missing from /full response"

    def h4_register_and_login_still_works():
        uid3, jwt3 = _register_and_login("co")
        assert uid3 and jwt3, "Register/login flow broken"

    def h5_kyc_status_returns_not_started_for_new_user():
        r = requests.get(f"{BASE}/kyc/status/{uid}", headers=_auth(jwt))
        assert r.status_code == 200
        kyc = r.json().get("kyc", {})
        assert kyc.get("status") == "not_started" or "step" in kyc, \
            f"Unexpected kyc shape for new user: {kyc}"

    _test("H1 — public profile endpoint still returns 200", h1_public_profile_still_works)
    _test("H2 — public profile still has full_name", h2_public_profile_has_name)
    _test("H3 — /full owner response has 'profile' key", h3_full_profile_owner_returns_profile_key)
    _test("H4 — register and login still work", h4_register_and_login_still_works)
    _test("H5 — kyc/status returns not_started for new user", h5_kyc_status_returns_not_started_for_new_user)


# ═══════════════════════════════════════════════════════════════
# I — Static regression: owner hydration + messages deep-link
# ═══════════════════════════════════════════════════════════════

def _test_group_i():
    print("\n[I] Static — owner hydration wiring + messages double-listener prevention")

    def _read(path):
        with open(path, encoding="utf-8") as f:
            return f.read()

    # ── Owner Profile V2 ──────────────────────────────────────────────────────

    def i1_getOwnerProfile_has_actual_caller():
        """getOwnerProfile must be called somewhere in render.js (not just defined)."""
        src = _read("profile-v2.render.js")
        assert "window.getOwnerProfile" in src, \
            "profile-v2.render.js never calls window.getOwnerProfile — hydration wiring missing"
        # The call must be inside _loadProfile (owner gate), not just the api assignment
        idx = src.find("window.getOwnerProfile(_scProfileId)")
        assert idx != -1, \
            "profile-v2.render.js: window.getOwnerProfile(_scProfileId) call not found"

    def i2_owner_hydration_gated_on_viewer_type():
        """Owner /full call must be conditional on _scViewerType === 'owner'."""
        src = _read("profile-v2.render.js")
        # The call must appear after the viewer_type check
        gate_idx = src.find("_scViewerType === 'owner'")
        assert gate_idx != -1, \
            "profile-v2.render.js: viewer_type=owner gate not found before getOwnerProfile call"
        call_idx = src.find("window.getOwnerProfile(_scProfileId)")
        assert call_idx > gate_idx, \
            "profile-v2.render.js: getOwnerProfile called BEFORE viewer_type check"

    def i3_edit_modal_reads_owner_state():
        """openModal in edit.js must use _scOwnerProfile as data source, not _scProfile alone."""
        src = _read("profile-v2.edit.js")
        assert "_scOwnerProfile" in src, \
            "profile-v2.edit.js: _scOwnerProfile never referenced — edit modal reads wrong state"
        # The var p assignment must prefer _scOwnerProfile
        assert "window._scOwnerProfile || window._scProfile" in src, \
            "profile-v2.edit.js: edit modal data source must be '_scOwnerProfile || _scProfile'"

    def i4_public_state_never_stores_dob():
        """_scProfile must not have dob stored in applyCanonicalProfile."""
        src = _read("profile-v2.edit.js")
        # Find applyCanonicalProfile block and confirm dob is not written to _scProfile
        acp_idx = src.find("function applyCanonicalProfile")
        assert acp_idx != -1, "applyCanonicalProfile function not found in edit.js"
        acp_body = src[acp_idx: acp_idx + 2000]
        # Must NOT contain _scProfile.dob = (private field write to public state)
        import re as _re
        bad_pattern = r"_scProfile\.dob\s*="
        assert not _re.search(bad_pattern, acp_body), \
            "profile-v2.edit.js: applyCanonicalProfile still writes dob to _scProfile (public state)"

    def i5_owner_hydration_promise_used_as_gate():
        """openModal must guard on _scOwnerProfilePromise before opening."""
        src = _read("profile-v2.edit.js")
        assert "_scOwnerProfilePromise" in src, \
            "profile-v2.edit.js: _scOwnerProfilePromise gate not present in openModal"

    # ── Messages deep-link ────────────────────────────────────────────────────

    def i6_renderConvList_placeholder_has_data_twid():
        """renderConvList placeholder must have data-twid attribute set."""
        src = _read("messages.render.js")
        # Find the placeholder section (between renderConvList comments)
        ph_idx = src.find("Placeholder for conversations not yet in DB")
        assert ph_idx != -1, "messages.render.js: placeholder comment not found in renderConvList"
        ph_section = src[ph_idx: ph_idx + 1200]
        assert "data-twid" in ph_section, \
            "messages.render.js: renderConvList placeholder missing data-twid attribute"

    def i7_renderConvList_placeholder_has_all_attributes():
        """renderConvList placeholder must have data-type, data-avatar, data-headline."""
        src = _read("messages.render.js")
        ph_idx = src.find("Placeholder for conversations not yet in DB")
        assert ph_idx != -1, "messages.render.js: placeholder comment not found"
        ph_section = src[ph_idx: ph_idx + 800]
        for attr in ("data-type", "data-avatar", "data-headline"):
            assert attr in ph_section, \
                f"messages.render.js: renderConvList placeholder missing {attr}"

    def i8_renderConvList_placeholder_no_explicit_addEventListener():
        """renderConvList placeholder must NOT have an explicit addEventListener (only the general loop is allowed)."""
        src = _read("messages.render.js")
        ph_idx = src.find("Placeholder for conversations not yet in DB")
        assert ph_idx != -1, "messages.render.js: placeholder comment not found"
        # Scan from the comment to the closing brace of the if-block (generous window)
        ph_section = src[ph_idx: ph_idx + 1200]
        # Find the general loop that handles ALL .conv-item elements
        gen_loop_idx = ph_section.find("querySelectorAll('.conv-item')")
        if gen_loop_idx == -1:
            gen_loop_idx = len(ph_section)
        pre_loop = ph_section[:gen_loop_idx]
        # Strip comments (lines starting with //) before checking for addEventListener
        import re as _re
        pre_loop_no_comments = _re.sub(r'//[^\n]*', '', pre_loop)
        assert "addEventListener" not in pre_loop_no_comments, \
            "messages.render.js: renderConvList placeholder has explicit addEventListener (double-listener bug)"

    def i9_handleWithParam_placeholder_has_data_twid():
        """handleWithParam placeholder must set data-twid from data.tw_id."""
        src = _read("messages.render.js")
        hw_idx = src.find("function handleWithParam")
        assert hw_idx != -1, "messages.render.js: handleWithParam function not found"
        hw_section = src[hw_idx: hw_idx + 1200]
        assert "data-twid" in hw_section, \
            "messages.render.js: handleWithParam placeholder missing data-twid attribute"
        assert "tw_id" in hw_section, \
            "messages.render.js: handleWithParam does not propagate tw_id to placeholder"

    def i10_roadmap_has_global_search_spec():
        """FUTURE_ROADMAP.md must contain Global Search specification section."""
        src = _read("docs/FUTURE_ROADMAP.md")
        assert "Future Feature Notes — Global People & Companies Search" in src, \
            "docs/FUTURE_ROADMAP.md: Global Search spec section missing"
        assert "data-next-appt-id" not in src or "co-cjp-btn" not in src, \
            "Unexpected content check"  # relaxed sanity check
        # Check for button behavior spec
        assert "يبحث عند أول حرف" in src or "أول حرف" in src or "أولى" in src, \
            "docs/FUTURE_ROADMAP.md: Global Search button behavior spec missing"

    def i11_roadmap_has_b2b_spec():
        """FUTURE_ROADMAP.md must contain B2B Business Network spec section."""
        src = _read("docs/FUTURE_ROADMAP.md")
        assert "Future Feature Notes — Company-to-Company Business Network" in src, \
            "docs/FUTURE_ROADMAP.md: B2B spec section missing"
        # Check for lifecycle documentation
        assert "accepted" in src and "rejected" in src, \
            "docs/FUTURE_ROADMAP.md: B2B lifecycle states missing"

    _test("I1  — getOwnerProfile has actual caller in render.js", i1_getOwnerProfile_has_actual_caller)
    _test("I2  — owner hydration gated on viewer_type=owner", i2_owner_hydration_gated_on_viewer_type)
    _test("I3  — edit modal reads _scOwnerProfile not public state", i3_edit_modal_reads_owner_state)
    _test("I4  — applyCanonicalProfile never writes dob to _scProfile", i4_public_state_never_stores_dob)
    _test("I5  — _scOwnerProfilePromise gate present in openModal", i5_owner_hydration_promise_used_as_gate)
    _test("I6  — renderConvList placeholder has data-twid", i6_renderConvList_placeholder_has_data_twid)
    _test("I7  — renderConvList placeholder has data-type/avatar/headline", i7_renderConvList_placeholder_has_all_attributes)
    _test("I8  — renderConvList placeholder no explicit addEventListener", i8_renderConvList_placeholder_no_explicit_addEventListener)
    _test("I9  — handleWithParam placeholder has data-twid", i9_handleWithParam_placeholder_has_data_twid)
    _test("I10 — roadmap has Global Search spec section", i10_roadmap_has_global_search_spec)
    _test("I11 — roadmap has B2B Business Network spec section", i11_roadmap_has_b2b_spec)


# ═══════════════════════════════════════════════════════════════
# J — Static: Fail-Closed + settings.html OTP handling
# ═══════════════════════════════════════════════════════════════

def _test_group_j():
    print("\n[J] Static — OTP Fail-Closed contract + settings.html error handling")

    def _read(path):
        with open(path, encoding="utf-8") as f:
            return f.read()

    def j1_server_has_otp_availability_helpers():
        src = _read("server.py")
        assert "is_email_otp_delivery_available" in src, \
            "server.py: is_email_otp_delivery_available helper not found"
        assert "is_phone_otp_delivery_available" in src, \
            "server.py: is_phone_otp_delivery_available helper not found"

    def j2_helpers_return_false_by_default():
        src = _read("server.py")
        import re as _re
        # Both functions must contain 'return False'
        email_fn = _re.search(
            r'def is_email_otp_delivery_available\(\)[^#\n]*\n(.*?)(?=\ndef |\Z)',
            src, _re.DOTALL)
        phone_fn = _re.search(
            r'def is_phone_otp_delivery_available\(\)[^#\n]*\n(.*?)(?=\ndef |\Z)',
            src, _re.DOTALL)
        assert email_fn and "return False" in email_fn.group(0), \
            "is_email_otp_delivery_available does not return False by default"
        assert phone_fn and "return False" in phone_fn.group(0), \
            "is_phone_otp_delivery_available does not return False by default"

    def j3_email_send_endpoint_checks_availability_before_generate():
        src = _read("server.py")
        # The 503 guard must appear before send_email_code call inside the endpoint
        ep_idx = src.find("def kyc_send_email(")
        assert ep_idx != -1, "server.py: kyc_send_email endpoint not found"
        ep_body = src[ep_idx: ep_idx + 800]
        avail_idx = ep_body.find("is_email_otp_delivery_available")
        generate_idx = ep_body.find("send_email_code")
        assert avail_idx != -1, "kyc_send_email: availability check missing"
        assert generate_idx != -1, "kyc_send_email: send_email_code call missing"
        assert avail_idx < generate_idx, \
            "kyc_send_email: availability check must appear before send_email_code"

    def j4_phone_send_endpoint_checks_availability_before_generate():
        src = _read("server.py")
        ep_idx = src.find("def kyc_send_phone(")
        assert ep_idx != -1, "server.py: kyc_send_phone endpoint not found"
        ep_body = src[ep_idx: ep_idx + 800]
        avail_idx = ep_body.find("is_phone_otp_delivery_available")
        generate_idx = ep_body.find("send_phone_code")
        assert avail_idx != -1, "kyc_send_phone: availability check missing"
        assert generate_idx != -1, "kyc_send_phone: send_phone_code call missing"
        assert avail_idx < generate_idx, \
            "kyc_send_phone: availability check must appear before send_phone_code"

    def j5_server_returns_503_for_unavailable_provider():
        src = _read("server.py")
        # Both endpoints must raise HTTPException(status_code=503)
        assert "503" in src and "otp_delivery_unavailable" in src, \
            "server.py: 503 + otp_delivery_unavailable contract not found"

    def j6_settings_html_handles_otp_delivery_unavailable():
        src = _read("settings.html")
        assert "otp_delivery_unavailable" in src, \
            "settings.html: otp_delivery_unavailable code not handled"
        assert "قريباً" in src or "غير متاحة" in src, \
            "settings.html: user-facing unavailable message missing"

    def j7_settings_html_checks_response_status():
        src = _read("settings.html")
        # Both kycSendEmail and kycSendPhone must read the HTTP status before parsing JSON
        email_idx = src.find("function kycSendEmail")
        phone_idx = src.find("function kycSendPhone")
        assert email_idx != -1 and phone_idx != -1, \
            "settings.html: kycSendEmail or kycSendPhone not found"
        email_body = src[email_idx: email_idx + 600]
        phone_body = src[phone_idx: phone_idx + 600]
        assert "r.status" in email_body or "status" in email_body, \
            "settings.html: kycSendEmail does not check HTTP status"
        assert "r.status" in phone_body or "status" in phone_body, \
            "settings.html: kycSendPhone does not check HTTP status"

    def j8_settings_html_no_success_toast_without_status_check():
        src = _read("settings.html")
        # Must NOT show success toast without checking o.s===200
        # i.e. the success toast must be inside a conditional block checking status
        # Check that 'تم إرسال الرمز' only appears after a status=200 check
        email_idx = src.find("function kycSendEmail")
        phone_idx = src.find("function kycSendPhone")
        if email_idx != -1:
            email_body = src[email_idx: email_idx + 600]
            assert "s===200" in email_body or "status===200" in email_body or "s == 200" in email_body, \
                "settings.html: kycSendEmail shows success without HTTP 200 check"

    def j9_settings_html_handles_401():
        src = _read("settings.html")
        # Must handle 401 (session expired) in OTP send flow
        assert "401" in src, "settings.html: 401 not handled in OTP send flow"

    def j10_no_otp_print_in_server():
        src = _read("server.py")
        import re as _re
        # The success return in kyc_send_email must not include the OTP variable
        ep_email_idx = src.find("def kyc_send_email(")
        if ep_email_idx != -1:
            ep_body = src[ep_email_idx: ep_email_idx + 800]
            # Find the success return statement (after start_kyc/send_email_code calls)
            # It must not contain 'code' as a response key pointing to the OTP variable
            success_return = _re.search(r'return \{[^}]*\}', ep_body)
            if success_return:
                ret = success_return.group(0)
                # The OTP code variable (named 'code' internally) must not be in the return dict value
                # "status": "success" is fine; "code": otp_var would not be fine
                # Simple check: the return dict must not contain the pattern: "code": code
                assert not _re.search(r'"code"\s*:\s*code\b', ret), \
                    "server.py: kyc_send_email success return includes OTP code variable"
        # Also check that _dev_otp_log does not print the code value
        log_fn_idx = src.find("def _dev_otp_log(")
        if log_fn_idx != -1:
            log_body = src[log_fn_idx: log_fn_idx + 300]
            assert "code" not in log_body or "uid=" in log_body, \
                "server.py: _dev_otp_log may log OTP code value"

    def j11_owner_hydration_failure_shows_toast():
        src = _read("profile-v2.edit.js")
        # Both hydration failure paths must call window.toast
        # Path 1: _scOwnerProfile is null after promise resolves
        # Path 2: _scOwnerProfile is null at open time
        assert src.count("window.toast") >= 3, \
            "profile-v2.edit.js: owner hydration failure paths must call window.toast"

    _test("J1  — server.py has otp availability helpers", j1_server_has_otp_availability_helpers)
    _test("J2  — helpers return False by default", j2_helpers_return_false_by_default)
    _test("J3  — kyc_send_email checks availability before generating OTP", j3_email_send_endpoint_checks_availability_before_generate)
    _test("J4  — kyc_send_phone checks availability before generating OTP", j4_phone_send_endpoint_checks_availability_before_generate)
    _test("J5  — server returns 503 for unavailable provider", j5_server_returns_503_for_unavailable_provider)
    _test("J6  — settings.html handles otp_delivery_unavailable", j6_settings_html_handles_otp_delivery_unavailable)
    _test("J7  — settings.html checks HTTP response status", j7_settings_html_checks_response_status)
    _test("J8  — settings.html no success toast without HTTP 200 check", j8_settings_html_no_success_toast_without_status_check)
    _test("J9  — settings.html handles 401 in OTP flow", j9_settings_html_handles_401)
    _test("J10 — server.py does not print OTP in endpoint response", j10_no_otp_print_in_server)
    _test("J11 — owner hydration failure shows visible toast", j11_owner_hydration_failure_shows_toast)


# ═══════════════════════════════════════════════════════════════
# K — Mock Provider unit tests (no live server, no DB)
# ═══════════════════════════════════════════════════════════════

import unittest
from unittest.mock import patch, MagicMock

class TestKYCOTPMockProvider(unittest.TestCase):
    """Unit tests for KYC OTP send endpoints using mocked delivery provider and DB.

    Uses FastAPI's app.dependency_overrides to bypass verify_token (no JWT_SECRET needed),
    and unittest.mock.patch to isolate OTP generation. No real DB or credentials touched.
    """

    def setUp(self):
        from fastapi.testclient import TestClient
        import server as srv
        self.srv = srv
        self.client = TestClient(srv.app, raise_server_exceptions=False)

    def tearDown(self):
        # Always clear dependency overrides after each test
        self.srv.app.dependency_overrides.clear()

    def _override_token(self, uid=42):
        """Override verify_token dependency to return a fixed payload."""
        payload = {"valid": True, "user_id": uid, "user_type": "emp"}
        self.srv.app.dependency_overrides[self.srv.verify_token] = lambda: payload

    def test_k1_email_send_returns_503_when_provider_unavailable(self):
        """Default state: no provider → 503, no OTP generated."""
        self._override_token(uid=42)
        with patch.object(self.srv, "is_email_otp_delivery_available", return_value=False):
            r = self.client.post("/kyc/email/send", json={"email": "test@example.com"})
        self.assertEqual(r.status_code, 503,
                         f"Expected 503 (Fail Closed), got {r.status_code}: {r.text}")
        detail = r.json().get("detail", {})
        self.assertEqual(detail.get("code"), "otp_delivery_unavailable")
        self.assertNotIn("dev_code", r.json())

    def test_k2_phone_send_returns_503_when_provider_unavailable(self):
        """Default state: no provider → 503."""
        self._override_token(uid=43)
        with patch.object(self.srv, "is_phone_otp_delivery_available", return_value=False):
            r = self.client.post("/kyc/phone/send", json={"phone": "+962799000000"})
        self.assertEqual(r.status_code, 503)
        detail = r.json().get("detail", {})
        self.assertEqual(detail.get("code"), "otp_delivery_unavailable")

    def test_k3_email_send_success_with_mock_provider(self):
        """With mocked provider + mocked DB: returns 200, OTP not in response."""
        self._override_token(uid=10)
        mock_code = "123456"
        with patch.object(self.srv, "is_email_otp_delivery_available", return_value=True), \
             patch.object(self.srv, "start_kyc", return_value=None), \
             patch.object(self.srv, "send_email_code", return_value=mock_code) as mock_send:
            r = self.client.post("/kyc/email/send", json={"email": "user@example.com"})
        self.assertEqual(r.status_code, 200,
                         f"Expected 200 with mocked provider, got {r.status_code}: {r.text}")
        data = r.json()
        self.assertEqual(data.get("status"), "success")
        # OTP code must NOT appear in HTTP response
        self.assertNotIn(mock_code, str(data))
        self.assertNotIn("dev_code", data)
        # Delivery function called with correct uid
        mock_send.assert_called_once()
        self.assertEqual(mock_send.call_args[0][0], 10)

    def test_k4_phone_send_success_with_mock_provider(self):
        """With mocked provider + mocked DB: returns 200, OTP not in response."""
        self._override_token(uid=20)
        mock_code = "654321"
        with patch.object(self.srv, "is_phone_otp_delivery_available", return_value=True), \
             patch.object(self.srv, "send_phone_code", return_value=mock_code) as mock_send:
            r = self.client.post("/kyc/phone/send", json={"phone": "+966500000001"})
        self.assertEqual(r.status_code, 200,
                         f"Expected 200 with mocked provider, got {r.status_code}: {r.text}")
        data = r.json()
        self.assertEqual(data.get("status"), "success")
        self.assertNotIn(mock_code, str(data))
        self.assertNotIn("dev_code", data)
        mock_send.assert_called_once()
        self.assertEqual(mock_send.call_args[0][0], 20)

    def test_k5_503_does_not_call_send_email_code(self):
        """503 path: send_email_code must NOT be called (no OTP generated or stored)."""
        self._override_token()
        with patch.object(self.srv, "is_email_otp_delivery_available", return_value=False), \
             patch.object(self.srv, "send_email_code") as mock_send:
            r = self.client.post("/kyc/email/send", json={"email": "test@example.com"})
        self.assertEqual(r.status_code, 503)
        mock_send.assert_not_called()

    def test_k6_503_does_not_call_send_phone_code(self):
        """503 path: send_phone_code must NOT be called (no OTP generated or stored)."""
        self._override_token()
        with patch.object(self.srv, "is_phone_otp_delivery_available", return_value=False), \
             patch.object(self.srv, "send_phone_code") as mock_send:
            r = self.client.post("/kyc/phone/send", json={"phone": "+962799000000"})
        self.assertEqual(r.status_code, 503)
        mock_send.assert_not_called()

    def test_k7_user_isolation_email_send(self):
        """Two separate users both get 503; send_email_code never called for either."""
        # Test calls are sequential so we can override per-call
        call_count = [0]
        uids = [1, 2]
        def dynamic_token():
            uid = uids[min(call_count[0], len(uids)-1)]
            call_count[0] += 1
            return {"valid": True, "user_id": uid, "user_type": "emp"}
        self.srv.app.dependency_overrides[self.srv.verify_token] = dynamic_token

        with patch.object(self.srv, "is_email_otp_delivery_available", return_value=False), \
             patch.object(self.srv, "send_email_code") as mock_send:
            r_a = self.client.post("/kyc/email/send", json={"email": "a@example.com"})
            r_b = self.client.post("/kyc/email/send", json={"email": "b@example.com"})
        self.assertEqual(r_a.status_code, 503)
        self.assertEqual(r_b.status_code, 503)
        mock_send.assert_not_called()


def _run_group_k():
    print("\n[K] Mock Provider unit tests (TestClient + unittest.mock)")
    suite = unittest.TestLoader().loadTestsFromTestCase(TestKYCOTPMockProvider)
    runner = unittest.TextTestRunner(stream=open(os.devnull, 'w'), verbosity=0)
    result = runner.run(suite)
    for test, err in result.failures + result.errors:
        _RESULTS["failed"] += 1
        print(f"  FAIL  {test}: {err.splitlines()[-1] if err else 'unknown'}")
    passed = result.testsRun - len(result.failures) - len(result.errors)
    _RESULTS["passed"] += passed
    for i in range(passed):
        pass  # count already accumulated
    # Print summary
    for test in suite:
        name = str(test).split(" ")[0]
        is_fail = any(str(t) == str(test) for t, _ in result.failures + result.errors)
        if not is_fail:
            print(f"  PASS  {name}")


# ═══════════════════════════════════════════════════════════════
# Group L — Derived Age: calculate_age_from_dob + projection tests
# ═══════════════════════════════════════════════════════════════

import unittest as _unittest_l
from datetime import date as _date_l, timedelta as _td_l


class _FakeConn:
    """Minimal fake DB connection for update_profile() mock tests.

    Returns appropriate row lists based on SQL content:
    - SELECT id FROM profiles  → [(1,)]  (profile row exists → trigger UPDATE path)
    - UPDATE … RETURNING id    → [(1,)]  (UPDATE succeeded)
    - Everything else          → []      (BEGIN / COMMIT / ROLLBACK / users queries)
    """
    def __init__(self):
        self.columns = []
        self._sqls = []

    def run(self, sql, **kw):
        normalized = sql.strip()
        self._sqls.append(normalized)
        if "RETURNING id" in normalized:
            self.columns = [{"name": "id"}]
            return [(1,)]
        if "SELECT id FROM profiles" in normalized:
            self.columns = [{"name": "id"}]
            return [(1,)]
        if "SELECT tw_id FROM users" in normalized:
            self.columns = [{"name": "tw_id"}]
            return []
        self.columns = []
        return []


class TestDerivedAge(_unittest_l.TestCase):
    """Group L — static tests (no DB, no server).

    L1-L8:   calculate_age_from_dob() unit tests
    L9-L14:  project_public_profile() — age present, dob absent
    L15-L18: project_owner_profile()  — dob present, age added
    L19-L22: update_profile() real function + mocked DB — age injected when dob updated
    L23-L32: Frontend contract static checks (render.js / edit.js source)
    L33-L40: Privacy regression — dob never leaks in public projection
    L41-L48: Edge case date inputs for calculate_age_from_dob
    L49-L52: Documentation consistency checks
    L53-L54: get_public_profile() pipeline structural checks
    """

    def setUp(self):
        import auth as _auth
        self._auth = _auth

    # ── L1-L8: calculate_age_from_dob ──────────────────────────

    def test_l1_none_input_returns_none(self):
        self.assertIsNone(self._auth.calculate_age_from_dob(None))

    def test_l2_empty_string_returns_none(self):
        self.assertIsNone(self._auth.calculate_age_from_dob(""))

    def test_l3_iso_string_returns_correct_age(self):
        today = _date_l.today()
        # birthday exactly 30 years ago today → age 30
        birth = today.replace(year=today.year - 30)
        result = self._auth.calculate_age_from_dob(birth.isoformat())
        self.assertEqual(result, 30)

    def test_l4_pre_birthday_this_year_returns_age_minus_one(self):
        today = _date_l.today()
        # birthday is tomorrow — not yet occurred this year
        try:
            birth_this_year = today.replace(month=today.month, day=today.day + 1)
        except ValueError:
            import calendar as _cal
            # last day of month: move to next month
            next_m = today.month % 12 + 1
            next_y = today.year + (1 if today.month == 12 else 0)
            birth_this_year = _date_l(next_y, next_m, 1)
        birth = birth_this_year.replace(year=birth_this_year.year - 30)
        result = self._auth.calculate_age_from_dob(birth.isoformat())
        self.assertEqual(result, 29)

    def test_l5_future_date_returns_none(self):
        future = _date_l.today() + _td_l(days=365)
        self.assertIsNone(self._auth.calculate_age_from_dob(future.isoformat()))

    def test_l6_pre_min_year_returns_none(self):
        self.assertIsNone(self._auth.calculate_age_from_dob("1920-01-01"))

    def test_l7_age_below_min_returns_none(self):
        # 10 years old → below _DOB_MIN_AGE = 15
        today = _date_l.today()
        birth = today.replace(year=today.year - 10)
        self.assertIsNone(self._auth.calculate_age_from_dob(birth.isoformat()))

    def test_l8_invalid_string_returns_none(self):
        self.assertIsNone(self._auth.calculate_age_from_dob("not-a-date"))

    # ── L9-L14: project_public_profile ─────────────────────────

    def test_l9_public_profile_contains_age_when_dob_valid(self):
        today = _date_l.today()
        birth = today.replace(year=today.year - 25)
        raw = {"tw_id": "U001", "full_name": "Test", "dob": birth.isoformat()}
        result = self._auth.project_public_profile(raw)
        self.assertIn("age", result)
        self.assertEqual(result["age"], 25)

    def test_l10_public_profile_never_contains_dob(self):
        today = _date_l.today()
        birth = today.replace(year=today.year - 25)
        raw = {"tw_id": "U001", "full_name": "Test", "dob": birth.isoformat()}
        result = self._auth.project_public_profile(raw)
        self.assertNotIn("dob", result)

    def test_l11_public_profile_no_age_when_dob_missing(self):
        raw = {"tw_id": "U001", "full_name": "Test"}
        result = self._auth.project_public_profile(raw)
        self.assertNotIn("age", result)

    def test_l12_public_profile_no_age_when_dob_null(self):
        raw = {"tw_id": "U001", "full_name": "Test", "dob": None}
        result = self._auth.project_public_profile(raw)
        self.assertNotIn("age", result)

    def test_l13_public_profile_strips_phone(self):
        raw = {"tw_id": "U001", "full_name": "Test", "phone": "+962799000000"}
        result = self._auth.project_public_profile(raw)
        self.assertNotIn("phone", result)

    def test_l14_public_profile_strips_email(self):
        raw = {"tw_id": "U001", "full_name": "Test", "email": "a@test.com"}
        result = self._auth.project_public_profile(raw)
        self.assertNotIn("email", result)

    # ── L15-L18: project_owner_profile ─────────────────────────

    def test_l15_owner_profile_contains_dob(self):
        today = _date_l.today()
        birth = today.replace(year=today.year - 25)
        raw = {"tw_id": "U001", "full_name": "Test", "dob": birth.isoformat(), "phone": "+962"}
        result = self._auth.project_owner_profile(raw)
        self.assertIn("dob", result)

    def test_l16_owner_profile_also_contains_age(self):
        today = _date_l.today()
        birth = today.replace(year=today.year - 25)
        raw = {"tw_id": "U001", "full_name": "Test", "dob": birth.isoformat()}
        result = self._auth.project_owner_profile(raw)
        self.assertIn("age", result)
        self.assertEqual(result["age"], 25)

    def test_l17_owner_profile_contains_phone(self):
        raw = {"tw_id": "U001", "full_name": "Test", "phone": "+962799000000"}
        result = self._auth.project_owner_profile(raw)
        self.assertIn("phone", result)

    def test_l18_owner_profile_no_age_when_dob_invalid(self):
        raw = {"tw_id": "U001", "full_name": "Test", "dob": "bad-date"}
        result = self._auth.project_owner_profile(raw)
        self.assertNotIn("age", result)

    # ── L19-L22: update_profile() real function + mocked DB ─────────────────────

    def test_l19_update_profile_with_dob_returns_age(self):
        """Real update_profile() with mocked DB — dob update returns computed age."""
        from unittest.mock import patch
        today = _date_l.today()
        try:
            dob_str = today.replace(year=today.year - 25).isoformat()
        except ValueError:
            self.skipTest("Cannot construct dob 25 years ago (Feb 29 edge case)")
        fake = _FakeConn()
        with patch.object(self._auth, 'get_conn', return_value=fake), \
             patch.object(self._auth, 'release_conn'), \
             patch.object(self._auth, '_cache_del'):
            resp = self._auth.update_profile(99, {"dob": dob_str, "headline": "test"}, user_type="emp")
        self.assertIn("age", resp)
        self.assertEqual(resp["age"], 25)
        self.assertNotIn("password_hash", resp)

    def test_l20_update_profile_without_dob_has_no_age(self):
        """Real update_profile() with mocked DB — headline-only update returns no age."""
        from unittest.mock import patch
        fake = _FakeConn()
        with patch.object(self._auth, 'get_conn', return_value=fake), \
             patch.object(self._auth, 'release_conn'), \
             patch.object(self._auth, '_cache_del'):
            resp = self._auth.update_profile(99, {"headline": "test"}, user_type="emp")
        self.assertNotIn("age", resp)
        self.assertNotIn("dob", resp)

    def test_l21_update_profile_sql_never_sets_age_column(self):
        """Real update_profile() — UPDATE SQL must not contain 'age' in the SET clause."""
        from unittest.mock import patch
        import re as _re
        today = _date_l.today()
        try:
            dob_str = today.replace(year=today.year - 25).isoformat()
        except ValueError:
            self.skipTest("Cannot construct dob 25 years ago (Feb 29 edge case)")
        fake = _FakeConn()
        with patch.object(self._auth, 'get_conn', return_value=fake), \
             patch.object(self._auth, 'release_conn'), \
             patch.object(self._auth, '_cache_del'):
            self._auth.update_profile(99, {"dob": dob_str, "headline": "test"}, user_type="emp")
        update_sqls = [s for s in fake._sqls if s.upper().startswith("UPDATE PROFILES")]
        self.assertTrue(update_sqls, "No UPDATE profiles SQL was executed")
        for sql in update_sqls:
            m = _re.search(r'SET\s+(.*?)\s+WHERE', sql, _re.IGNORECASE | _re.DOTALL)
            if m:
                set_clause = m.group(1)
                self.assertNotIn("age", set_clause.lower(),
                                 f"'age' found in UPDATE SET clause — age is derived, never stored: {set_clause}")

    def test_l22_update_profile_clears_dob_returns_none_age(self):
        """Real update_profile() — clearing dob (None) returns age=None in response."""
        from unittest.mock import patch
        fake = _FakeConn()
        with patch.object(self._auth, 'get_conn', return_value=fake), \
             patch.object(self._auth, 'release_conn'), \
             patch.object(self._auth, '_cache_del'):
            resp = self._auth.update_profile(99, {"dob": None}, user_type="emp")
        self.assertIsNone(resp.get("age"),
                          "Clearing dob must produce age=None (calculate_age_from_dob(None) returns None)")

    # ── L23-L32: Frontend static checks ─────────────────────────

    def test_l23_render_js_no_p_dob_reference(self):
        with open("profile-v2.render.js", encoding="utf-8") as f:
            src = f.read()
        self.assertNotIn("p.dob", src, "render.js must not reference p.dob — age comes from p.age")

    def test_l24_render_js_has_render_profile_age_helper(self):
        with open("profile-v2.render.js", encoding="utf-8") as f:
            src = f.read()
        self.assertIn("_renderProfileAge", src)

    def test_l25_render_js_uses_p_age(self):
        with open("profile-v2.render.js", encoding="utf-8") as f:
            src = f.read()
        self.assertIn("p.age", src)

    def test_l26_render_js_helper_is_window_exposed(self):
        with open("profile-v2.render.js", encoding="utf-8") as f:
            src = f.read()
        self.assertIn("window._renderProfileAge", src)

    def test_l27_edit_js_no_dob_to_age_computation(self):
        with open("profile-v2.edit.js", encoding="utf-8") as f:
            src = f.read()
        # The old pattern: Math.floor(...)  / (365.25*24*3600*1000) for age
        self.assertNotIn("365.25*24*3600*1000", src,
                         "edit.js must not compute age from dob using millisecond division")

    def test_l28_edit_js_uses_profile_age(self):
        with open("profile-v2.edit.js", encoding="utf-8") as f:
            src = f.read()
        self.assertIn("profile.age", src)

    def test_l29_edit_js_calls_render_profile_age(self):
        with open("profile-v2.edit.js", encoding="utf-8") as f:
            src = f.read()
        self.assertIn("_renderProfileAge", src)

    def test_l30_edit_js_syncs_age_to_sc_profile(self):
        with open("profile-v2.edit.js", encoding="utf-8") as f:
            src = f.read()
        self.assertIn("_scProfile.age", src)

    def test_l31_render_js_does_not_use_365_25_approximation(self):
        with open("profile-v2.render.js", encoding="utf-8") as f:
            src = f.read()
        self.assertNotIn("365.25", src,
                         "render.js must not compute age via millisecond/365.25 approximation")

    def test_l32_profile_showcase_html_version_updated(self):
        with open("profile-showcase.html", encoding="utf-8") as f:
            src = f.read()
        self.assertIn("derived-age", src,
                      "profile-showcase.html version strings must reference derived-age")

    # ── L33-L40: Privacy regression ─────────────────────────────

    def test_l33_public_projection_never_returns_dob(self):
        raw = {
            "tw_id": "U001", "full_name": "Test",
            "dob": "1990-05-15", "phone": "+962", "email": "x@x.com",
            "password_hash": "hashed"
        }
        result = self._auth.project_public_profile(raw)
        self.assertNotIn("dob", result)

    def test_l34_public_projection_never_returns_birth_year(self):
        raw = {"tw_id": "U001", "full_name": "Test", "dob": "1990-05-15", "birth_year": 1990}
        result = self._auth.project_public_profile(raw)
        self.assertNotIn("birth_year", result)

    def test_l35_public_projection_never_returns_phone(self):
        raw = {"tw_id": "U001", "full_name": "Test", "phone": "+962799000001"}
        result = self._auth.project_public_profile(raw)
        self.assertNotIn("phone", result)

    def test_l36_public_projection_never_returns_email(self):
        raw = {"tw_id": "U001", "full_name": "Test", "email": "priv@test.com"}
        result = self._auth.project_public_profile(raw)
        self.assertNotIn("email", result)

    def test_l37_public_projection_never_returns_password_hash(self):
        raw = {"tw_id": "U001", "full_name": "Test", "password_hash": "$2b$12$xxx"}
        result = self._auth.project_public_profile(raw)
        self.assertNotIn("password_hash", result)

    def test_l38_age_is_derived_not_raw_allowlisted(self):
        # age must be COMPUTED at projection time, not passed through _PUBLIC_PROFILE_FIELDS.
        # Proof: raw dict with age=999 → projected age is computed from dob (25), not 999.
        from auth import _PUBLIC_PROFILE_FIELDS
        today = _date_l.today()
        try:
            birth = today.replace(year=today.year - 25)
        except ValueError:
            self.skipTest("Cannot construct birth date (Feb 29 edge case)")
        raw = {"tw_id": "U001", "full_name": "Test", "age": 999, "dob": birth.isoformat()}
        result = self._auth.project_public_profile(raw)
        self.assertEqual(result.get("age"), 25,
                         "age in public profile must be computed from dob (25), not passed through raw value (999)")
        self.assertNotIn("dob", result)
        self.assertNotIn("age", _PUBLIC_PROFILE_FIELDS,
                         "age must NOT be in _PUBLIC_PROFILE_FIELDS — it is injected after the allowlist filter")

    def test_l39_two_profiles_different_dob_get_correct_ages(self):
        today = _date_l.today()
        raw_a = {"tw_id": "UA", "dob": today.replace(year=today.year - 30).isoformat()}
        raw_b = {"tw_id": "UB", "dob": today.replace(year=today.year - 40).isoformat()}
        res_a = self._auth.project_public_profile(raw_a)
        res_b = self._auth.project_public_profile(raw_b)
        self.assertEqual(res_a.get("age"), 30)
        self.assertEqual(res_b.get("age"), 40)
        self.assertNotIn("dob", res_a)
        self.assertNotIn("dob", res_b)

    def test_l40_owner_profile_age_consistent_with_public_age(self):
        today = _date_l.today()
        birth = today.replace(year=today.year - 22)
        raw = {"tw_id": "U001", "full_name": "Test", "dob": birth.isoformat()}
        pub = self._auth.project_public_profile(raw)
        own = self._auth.project_owner_profile(raw)
        self.assertEqual(pub.get("age"), own.get("age"))

    # ── L41-L48: Edge case date inputs ──────────────────────────

    def test_l41_birthday_today_gives_correct_age(self):
        """Birthday is exactly today → age is exactly N years."""
        from datetime import date as _d
        today = _d.today()
        try:
            birth = today.replace(year=today.year - 20)
        except ValueError:
            self.skipTest("Feb 29 leap day today — cannot construct test date")
        result = self._auth.calculate_age_from_dob(birth)
        self.assertEqual(result, 20)

    def test_l42_birthday_tomorrow_gives_age_minus_one(self):
        """Birthday is tomorrow → age is N-1 (birthday not yet occurred this year)."""
        from datetime import date as _d, timedelta as _td
        tomorrow = _d.today() + _td(days=1)
        try:
            birth = tomorrow.replace(year=tomorrow.year - 30)
        except ValueError:
            self.skipTest(f"Cannot construct date 30 years before {tomorrow}")
        result = self._auth.calculate_age_from_dob(birth.isoformat())
        self.assertEqual(result, 29)

    def test_l43_birthday_already_passed_this_year_gives_correct_age(self):
        """Birthday was yesterday → age is N (birthday already occurred this year)."""
        from datetime import date as _d, timedelta as _td
        yesterday = _d.today() - _td(days=1)
        try:
            birth = yesterday.replace(year=yesterday.year - 30)
        except ValueError:
            self.skipTest(f"Cannot construct date 30 years before {yesterday}")
        result = self._auth.calculate_age_from_dob(birth.isoformat())
        self.assertEqual(result, 30)

    def test_l44_feb29_leap_year_dob_does_not_crash(self):
        """Feb 29 leap year DOB — must not raise regardless of today's date."""
        result = self._auth.calculate_age_from_dob("2000-02-29")
        self.assertTrue(result is None or isinstance(result, int),
                        "Feb 29 leap year DOB must not raise — must return int or None")

    def test_l45_datetime_object_input(self):
        """datetime object input — must be accepted and converted via .date()."""
        from datetime import datetime as _dt
        born = _dt(1991, 11, 10, 0, 0, 0)
        result = self._auth.calculate_age_from_dob(born)
        self.assertIsInstance(result, int)
        self.assertGreaterEqual(result, 15)

    def test_l46_date_object_input(self):
        """date object input — must be accepted directly."""
        from datetime import date as _d
        born = _d(1991, 11, 10)
        result = self._auth.calculate_age_from_dob(born)
        self.assertIsInstance(result, int)
        self.assertGreaterEqual(result, 15)

    def test_l47_iso_datetime_string(self):
        """ISO datetime string (with time component) — must parse via dob[:10]."""
        result = self._auth.calculate_age_from_dob("1991-11-10T00:00:00")
        self.assertIsInstance(result, int)
        self.assertGreaterEqual(result, 15)

    def test_l48_invalid_type_int_returns_none(self):
        """Non-date type (int) — must return None, not raise."""
        result = self._auth.calculate_age_from_dob(12345)
        self.assertIsNone(result)

    # ── L49-L52: Documentation consistency checks ────────────────

    def test_l49_tier1_docs_do_not_list_verify_request_as_returned(self):
        """verify_request must not be in _PUBLIC_PROFILE_FIELDS or listed as a returned Tier 1 field.

        It is acceptable — and correct — for it to appear in a 'Never in Tier 1' exclusion note.
        """
        import re as _re
        from auth import _PUBLIC_PROFILE_FIELDS
        # Definitive runtime check
        self.assertNotIn("verify_request", _PUBLIC_PROFILE_FIELDS,
                         "verify_request must not be in _PUBLIC_PROFILE_FIELDS — it is owner-only")
        with open("docs/security/PROFILE-DATA-VISIBILITY.md", encoding="utf-8") as f:
            src = f.read()
        t1_m = _re.search(r'### Tier 1.*?(?=### Tier 2)', src, _re.DOTALL)
        self.assertIsNotNone(t1_m, "Tier 1 section not found in PROFILE-DATA-VISIBILITY.md")
        t1_text = t1_m.group(0)
        if "verify_request" in t1_text:
            # verify_request may only appear inside a "Never" exclusion clause
            self.assertIn("Never in Tier 1", t1_text,
                          "verify_request appears in Tier 1 without a 'Never in Tier 1' exclusion guard")
            never_idx = t1_text.find("Never in Tier 1")
            self.assertIn("verify_request", t1_text[never_idx:],
                          "verify_request appears in Tier 1 positive fields section — must only be in the 'Never' list")

    def test_l50_tier3_docs_match_kyc_owner_fields(self):
        """Tier 3 Fields: line must contain exactly _KYC_OWNER_FIELDS; forbidden fields not in Fields: line.

        kyc_status / docs_submitted may appear in an explicit exclusion note — that is correct
        documentation. They must NOT appear as listed returned fields.
        """
        import re as _re
        from auth import _KYC_OWNER_FIELDS
        with open("docs/security/PROFILE-DATA-VISIBILITY.md", encoding="utf-8") as f:
            src = f.read()
        t3_m = _re.search(r'### Tier 3.*?(?=### Tier 4)', src, _re.DOTALL)
        self.assertIsNotNone(t3_m, "Tier 3 section not found in PROFILE-DATA-VISIBILITY.md")
        t3_text = t3_m.group(0)
        # All real KYC fields must appear in the section
        for field in _KYC_OWNER_FIELDS:
            self.assertIn(field, t3_text,
                          f"'{field}' from _KYC_OWNER_FIELDS missing from Tier 3 documentation")
        # Forbidden fields must NOT appear in the 'Fields:' positive list
        fields_line_m = _re.search(r'Fields:\s*(.*)', t3_text)
        if fields_line_m:
            fields_line = fields_line_m.group(1)
            for forbidden in ("kyc_status", "docs_submitted"):
                self.assertNotIn(f"`{forbidden}`", fields_line,
                                 f"'{forbidden}' must not appear in Tier 3 Fields: line — not in _KYC_OWNER_FIELDS")

    def test_l51_docs_use_langs_not_languages(self):
        """PROFILE-DATA-VISIBILITY.md must use langs[] not languages[] (matches runtime key)."""
        with open("docs/security/PROFILE-DATA-VISIBILITY.md", encoding="utf-8") as f:
            src = f.read()
        self.assertNotIn("languages[]", src,
                         "docs must use langs[] not languages[] — runtime JSON key is langs")

    def test_l52_render_js_comment_accurate_about_owner_dob(self):
        """render.js must not claim dob is absent from owner responses — dob IS in Tier 2."""
        with open("profile-v2.render.js", encoding="utf-8") as f:
            src = f.read()
        self.assertNotIn(
            "dob is never included in public or owner responses",
            src,
            "render.js has wrong comment — dob IS present in owner full response (Tier 2)"
        )

    # ── L53-L54: get_public_profile() pipeline structural checks ──

    def test_l53_get_public_profile_sql_fetches_dob(self):
        """get_public_profile() SQL must include p.dob — proof dob is available for age derivation."""
        import inspect
        src = inspect.getsource(self._auth.get_public_profile)
        self.assertIn("p.dob", src,
                      "get_public_profile SQL must fetch p.dob to derive age at the projection boundary")

    def test_l54_get_public_profile_returns_through_projection(self):
        """get_public_profile() must return via project_public_profile() — never raw dict."""
        import inspect
        src = inspect.getsource(self._auth.get_public_profile)
        self.assertIn("return project_public_profile(", src,
                      "get_public_profile must RETURN the result of project_public_profile — not bypass it")


def _run_group_l():
    print("\n[L] Derived Age — calculate_age_from_dob + projection + edge cases + docs consistency (L1-L54)")
    suite = _unittest_l.TestLoader().loadTestsFromTestCase(TestDerivedAge)
    runner = _unittest_l.TextTestRunner(stream=open(os.devnull, 'w'), verbosity=0)
    result = runner.run(suite)
    for test, err in result.failures + result.errors:
        _RESULTS["failed"] += 1
        name = str(test).split(" ")[0]
        print(f"  FAIL  {name}: {err.splitlines()[-1] if err else 'unknown'}")
    passed = result.testsRun - len(result.failures) - len(result.errors)
    _RESULTS["passed"] += passed
    for test in suite:
        name = str(test).split(" ")[0]
        is_fail = any(str(t) == str(test) for t, _ in result.failures + result.errors)
        if not is_fail:
            print(f"  PASS  {name}")


# ═══════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════

def main():
    print("=" * 60)
    print("Privacy Boundary V1 — Security Tests")
    print("=" * 60)

    _test_group_a()
    _test_group_b()
    _test_group_c()
    _test_group_d()
    _test_group_e()
    _test_group_f()
    _test_group_g()
    _test_group_h()
    _test_group_i()
    _test_group_j()
    _run_group_k()
    _run_group_l()

    total = sum(_RESULTS.values())
    print("\n" + "=" * 60)
    print(f"Results: {_RESULTS['passed']} Passed / {_RESULTS['failed']} Failed / {_RESULTS['skipped']} Skipped (Total: {total})")
    print("=" * 60)

    if _RESULTS["failed"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
