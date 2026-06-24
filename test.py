"""
اختبار الـ Matching Engine
شغّل السيرفر أولاً: uvicorn server:app --reload
"""

import requests
import json
import random
import string

BASE = "http://localhost:8000"


def _rand(n=8):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=n))


def _register_and_login(user_type):
    """Helper: register a throwaway user and return their JWT."""
    tag = _rand()
    email = f"twtest_{tag}@tw-security.test"
    payload = {
        "full_name": f"test_{user_type}_{tag}",
        "email": email,
        "password": "TwTest@9999",
        "user_type": user_type,
        "country_code": "9620"
    }
    reg = requests.post(f"{BASE}/auth/register", json=payload)
    assert reg.status_code == 200, f"Register failed ({user_type}): {reg.text}"
    token = reg.json().get("token", "")
    assert token, f"No token in register response for {user_type}"
    return token, reg.json().get("user", {})


def test_company_jobs_security():
    """
    Security tests for GET /company/jobs — P0.1 (JWT + ownership)

    Tests:
      1. No token          → 401
      2. emp token         → 403
      3. Isolation         → Company A cannot see Company B's jobs
      4. Static: company.html sends no X-User-Id header
    """
    print(f"\n{'═'*55}")
    print("🔒  Security: GET /company/jobs — P0.1 JWT & Ownership")
    print(f"{'═'*55}")

    # ── Test 1: no token → 401 ──────────────────────────────
    print("\n[1] GET /company/jobs without Authorization → 401")
    r = requests.get(f"{BASE}/company/jobs")
    assert r.status_code == 401, f"Expected 401, got {r.status_code}: {r.text}"
    print("    ✅ 401 — unauthenticated request blocked")

    # ── Test 2: emp token → 403 ──────────────────────────────
    print("\n[2] GET /company/jobs with emp token → 403")
    emp_jwt, _ = _register_and_login("emp")
    r = requests.get(
        f"{BASE}/company/jobs",
        headers={"Authorization": f"Bearer {emp_jwt}"}
    )
    assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text}"
    print("    ✅ 403 — employee cannot access company jobs endpoint")

    # ── Test 3: isolation — Company A cannot see Company B's jobs ───
    print("\n[3] Company A cannot see Company B's jobs")

    jwt_a, _ = _register_and_login("co")
    jwt_b, _ = _register_and_login("co")

    # Post a distinctive job as Company A
    unique_title = f"SECURITY_TEST_JOB_{_rand(12)}"
    post_r = requests.post(
        f"{BASE}/company/jobs",
        headers={"Authorization": f"Bearer {jwt_a}", "Content-Type": "application/json"},
        json={"title": unique_title, "description": "test", "location": "test",
              "job_type": "full_time", "salary_min": None, "salary_max": None, "skills": []}
    )
    assert post_r.status_code == 200, f"POST job failed: {post_r.text}"

    # Company B fetches its own jobs — must NOT see Company A's job
    r_b = requests.get(
        f"{BASE}/company/jobs",
        headers={"Authorization": f"Bearer {jwt_b}"}
    )
    assert r_b.status_code == 200, f"Company B GET /company/jobs failed: {r_b.text}"
    b_titles = [j.get("title") for j in r_b.json().get("jobs", [])]
    assert unique_title not in b_titles, (
        f"ISOLATION BREACH: Company B can see Company A's job '{unique_title}'"
    )
    print("    ✅ Company B's response does not contain Company A's job")

    # Company A fetches its own jobs — must see its job
    r_a = requests.get(
        f"{BASE}/company/jobs",
        headers={"Authorization": f"Bearer {jwt_a}"}
    )
    a_titles = [j.get("title") for j in r_a.json().get("jobs", [])]
    assert unique_title in a_titles, "Company A cannot see its own posted job"
    print("    ✅ Company A sees its own job correctly")

    # ── Test 4: static — company.html sends no X-User-Id ────
    print("\n[4] company.html contains no X-User-Id header")
    with open("company.html", encoding="utf-8") as f:
        html = f.read()
    assert "X-User-Id" not in html, "FAIL: X-User-Id still present in company.html"
    print("    ✅ X-User-Id is absent from company.html")

    print(f"\n{'─'*55}")
    print("✅  All P0.1 security tests passed")


def test_match(cv_text, label=""):
    print(f"\n{'─'*50}")
    print(f"🧪 {label}")
    print(f"CV: {cv_text}")

    res = requests.post(f"{BASE}/match", json={
        "cv_text": cv_text,
        "top_k": 3
    })

    data = res.json()
    print("\n📊 أفضل وظائف:")
    for m in data["matches"]:
        bar = "█" * int(m["match_percent"] / 10)
        print(f"  {m['match_percent']:5.1f}% {bar:<10} {m['title']} - {m['company']}")

def test_feedback():
    print(f"\n{'─'*50}")
    print("📝 اختبار تسجيل الـ Feedback")

    res = requests.post(f"{BASE}/feedback", json={
        "cv_text": "اشتغلت فني تكييف 3 سنوات",
        "job_id": 3,
        "score": 0.87,
        "action": "applied"
    })
    print(f"✅ {res.json()}")

def test_stats():
    print(f"\n{'─'*50}")
    res = requests.get(f"{BASE}/stats")
    print(f"📈 Stats: {json.dumps(res.json(), ensure_ascii=False, indent=2)}")

if __name__ == "__main__":
    test_company_jobs_security()

    # اختبار حالات مختلفة
    test_match("اشتغلت فني تكييف 3 سنوات وبعرف صيانة أجهزة التبريد", "فني تكييف")
    test_match("عندي خبرة بالمحاسبة والـ Excel وإعداد التقارير المالية", "محاسب")
    test_match("مطور React و Python خبرة 4 سنوات", "مطور")
    test_match("ممرضة شهادة تمريض 5 سنوات خبرة بالمستشفيات", "ممرضة")

    test_feedback()
    test_stats()

    print(f"\n{'═'*50}")
    print("✅ كل الاختبارات اشتغلت!")

