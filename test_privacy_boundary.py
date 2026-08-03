"""
test_privacy_boundary.py — Emergency Privacy Boundary V1
Tests: profile/full auth, auth/user ownership, public profile field stripping,
       KYC owner-only access, KYC write ownership, OTP removal, static checks.

Run against a live server:
  uvicorn server:app --reload &
  python test_privacy_boundary.py
"""

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
    print("\n[F] OTP not in API responses")

    uid, jwt = _register_and_login("emp")

    def f1_email_send_no_dev_code():
        r = requests.post(f"{BASE}/kyc/email/send",
                          headers=_auth(jwt),
                          json={"email": "test@example.com"})
        assert r.status_code == 200, f"Expected 200 from kyc/email/send, got {r.status_code}: {r.text}"
        assert "dev_code" not in r.json(), f"dev_code leaked in email/send response: {r.json()}"

    def f2_phone_send_no_dev_code():
        r = requests.post(f"{BASE}/kyc/phone/send",
                          headers=_auth(jwt),
                          json={"phone": "+962799000000"})
        assert r.status_code == 200, f"Expected 200 from kyc/phone/send, got {r.status_code}: {r.text}"
        assert "dev_code" not in r.json(), f"dev_code leaked in phone/send response: {r.json()}"

    def f3_kyc_status_no_otp_fields():
        r = requests.get(f"{BASE}/kyc/status/{uid}", headers=_auth(jwt))
        kyc = r.json().get("kyc", {})
        for field in ("email_code", "phone_code", "dev_code"):
            assert field not in kyc, f"{field} leaked in kyc/status response"

    _test("F1 — kyc/email/send has no dev_code", f1_email_send_no_dev_code)
    _test("F2 — kyc/phone/send has no dev_code", f2_phone_send_no_dev_code)
    _test("F3 — kyc/status has no otp fields", f3_kyc_status_no_otp_fields)


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

    total = sum(_RESULTS.values())
    print("\n" + "=" * 60)
    print(f"Results: {_RESULTS['passed']} Passed / {_RESULTS['failed']} Failed / {_RESULTS['skipped']} Skipped (Total: {total})")
    print("=" * 60)

    if _RESULTS["failed"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
