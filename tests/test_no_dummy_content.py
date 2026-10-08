"""PR 1.7 — no hardcoded dummy content that lies to visitors.

Static checks only (company-profile + edu-profile).
Run: python -m pytest tests/test_no_dummy_content.py -q
"""
import re

EDU = open("edu-profile.html", encoding="utf-8").read()
CO_HTML = open("company-profile.html", encoding="utf-8").read()
CO_RENDER = open("static/company/company.render.js", encoding="utf-8").read()


def test_company_verified_row_is_data_driven():
    row = re.search(r'<div class="ac-item"[^>]*>(?:(?!</div></div></div>).)*جهة موثقة من تواصلنا', CO_HTML)
    assert row, "verification row missing"
    assert 'id="coAboutVerifiedRow"' in row.group(0)
    assert 'style="display:none"' in row.group(0)
    assert "verifiedRow.style.display = p.is_verified ? '' : 'none'" in CO_RENDER
    assert "غير موثقة" not in CO_HTML


def test_edu_has_no_hardcoded_dummy_content():
    for fake in ("Python للمبتدئين", "React.js", "الذكاء الاصطناعي العملي", "49$", "89$",
                 "4.8", "34 تقييم", "17 طالب", "12 شهادة", "3 دورات", "منذ 3 أيام",
                 "جهة موثقة", "statRating", "statStudents", "enroll-btn\"", "toggleFollow",
                 "followBtn", "سنة التأسيس", "مركز تدريب"):
        assert fake not in EDU, f"dummy content still in edu-profile.html: {fake}"
    assert "صفحات الجهات التعليمية قيد التطوير — قريباً" in EDU


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
