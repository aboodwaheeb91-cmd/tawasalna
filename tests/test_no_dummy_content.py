"""PR 1.7 — no hardcoded dummy content that lies to visitors.

Static checks only (company-profile + edu-profile).
Run: python -m pytest tests/test_no_dummy_content.py -q
"""
import json
import re

EDU = open("edu-profile.html", encoding="utf-8").read()
CO_HTML = open("company-profile.html", encoding="utf-8").read()
CO_RENDER = open("static/company/company.render.js", encoding="utf-8").read()


def test_company_verified_row_is_data_driven():
    # PR 4.3a: the verification card starts hidden and is shown only by renderProfile when the
    # API says is_verified (behaviour: tests/test_company_profile_page_runtime.js B5).
    card = re.search(r'<div[^>]*id="coAboutVerifiedRow"[^>]*>', CO_HTML)
    assert card, "verification card missing"
    assert " hidden" in card.group(0)
    assert "غير موثقة" not in CO_HTML
    # no hard-coded About values / fake job cards (PR 4.3a)
    assert re.search(r'<div id="jobsList">\s*</div>', CO_HTML), "jobs list must start empty (no fake job cards)"
    assert "0 توثيق معتمد" not in CO_HTML
    assert 'class="ac-val" id="aboutType">—' not in CO_HTML


def test_edu_has_no_hardcoded_dummy_content():
    for fake in ("Python للمبتدئين", "React.js", "الذكاء الاصطناعي العملي", "49$", "89$",
                 "4.8", "34 تقييم", "17 طالب", "12 شهادة", "3 دورات", "منذ 3 أيام",
                 "جهة موثقة", "statRating", "statStudents", "enroll-btn\"", "toggleFollow",
                 "followBtn", "سنة التأسيس", "مركز تدريب"):
        assert fake not in EDU, f"dummy content still in edu-profile.html: {fake}"
    # PR 4.7: the «قريباً» card is the only content block — its text comes from a twT key that exists
    soon = re.search(r'id="eduSoon"[^>]*>(.*?)</div>', EDU, re.S)
    assert soon, "«قريباً» card missing"
    keys = re.findall(r'data-tw-t="([\w.]+)"', soon.group(1))
    strings = json.load(open("tw_strings.json", encoding="utf-8"))["ar"]
    assert keys and all(k in strings for k in keys), keys


def test_edu_contact_and_session_sources():
    assert "/admin/message" not in EDU
    assert "tw_adm_token" not in EDU
    assert "X-Admin-Token" not in EDU
    assert "tw_user" not in EDU
    assert "/messages?with=" in EDU


def test_edu_cover_not_stored_locally():
    assert "tw_cover_edu" not in EDU
    assert "FileReader" not in EDU
    assert "readAsDataURL" not in EDU
    assert "coverUploadBtn" not in EDU
