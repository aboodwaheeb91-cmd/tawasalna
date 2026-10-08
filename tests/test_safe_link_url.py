"""§54 rule 4b — twSafeLinkUrl (tw_shared.js) + _validate_external_url (server.py).

Run: python -m pytest tests/test_safe_link_url.py -q
"""
import json, os, re, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JWT_SECRET", "test-secret-safe-link-" + "x" * 32)
os.environ.setdefault("ADMIN_TOKEN", "a" * 40)

import pytest
from fastapi.testclient import TestClient

import server

client = TestClient(server.app)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

GOOD = ["https://linkedin.com/in/x", "http://example.com", "HTTPS://Example.com/a?b=1#c",
        "https://xn--mgbh0fb.example/مسار"]
BAD = ["javascript:alert(1)", "JaVaScRiPt:alert(1)", "data:text/html,<script>alert(1)</script>",
       "vbscript:msgbox(1)", " javascript:alert(1)", " https://x.com", "//evil.com", "/local",
       "https://", "https:///x", "https:\\\\evil.com", "http:/x.com", "java\tscript:alert(1)",
       "https://x.com/\nabc", "https://x.com/a b", "ftp://x.com", "www.x.com", "",
       "https://x.com/" + "a" * 2050]


def _js_safe_link(values):
    src = open(os.path.join(ROOT, "tw_shared.js"), encoding="utf-8").read()
    fn = re.search(r"function twSafeLinkUrl\(url\) \{.*?\n\}", src, re.S).group(0)
    code = fn + "\nprocess.stdout.write(JSON.stringify(" + json.dumps(values) + ".map(twSafeLinkUrl)));"
    out = subprocess.run(["node", "-e", code], capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def test_js_twSafeLinkUrl_accepts_http_https():
    assert _js_safe_link(GOOD) == GOOD


def test_js_twSafeLinkUrl_rejects_malicious():
    assert _js_safe_link(BAD) == [""] * len(BAD)
    assert _js_safe_link_nonstring() == ["", "", ""]


def _js_safe_link_nonstring():
    src = open(os.path.join(ROOT, "tw_shared.js"), encoding="utf-8").read()
    fn = re.search(r"function twSafeLinkUrl\(url\) \{.*?\n\}", src, re.S).group(0)
    code = fn + "\nprocess.stdout.write(JSON.stringify([null, undefined, 5].map(twSafeLinkUrl)));"
    return json.loads(subprocess.run(["node", "-e", code], capture_output=True, text=True, check=True).stdout)


@pytest.mark.parametrize("good", GOOD)
def test_server_accepts(good):
    assert server._validate_external_url(good, "url") == good


def test_server_strips_and_empty_is_none():
    assert server._validate_external_url("  https://x.com  ", "url") == "https://x.com"
    assert server._validate_external_url("", "certificate_url") is None
    assert server._validate_external_url(None, "certificate_url") is None


# Server strips surrounding whitespace first, so " https://x.com" is accepted there (stored stripped).
@pytest.mark.parametrize("bad", [b for b in BAD if b and b != " https://x.com"])
def test_server_rejects(bad):
    with pytest.raises(server.ExternalUrlError) as e:
        server._validate_external_url(bad, "url", "الرابط")
    assert e.value.field == "url" and "https://" in e.value.message


def test_server_required_empty():
    with pytest.raises(server.ExternalUrlError) as e:
        server._validate_external_url("  ", "url", "الرابط", required=True)
    assert e.value.message == "الرابط مطلوب"


def _h(uid=7, utype="emp"):
    return {"Authorization": "Bearer " + server._jwt_encode({"user_id": uid, "user_type": utype})}


@pytest.mark.parametrize("method,path,body,field", [
    ("post", "/links/7", {"link_type": "website", "url": "javascript:alert(1)"}, "url"),
    ("post", "/course/7", {"title": "دورة", "certificate_url": "javascript:alert(1)"}, "certificate_url"),
    ("put", "/course/1", {"title": "دورة", "certificate_url": "data:text/html,x"}, "certificate_url"),
    ("put", "/profile/7", {"website": "vbscript:x"}, "website"),
])
def test_endpoints_reject_422_before_db(monkeypatch, method, path, body, field):
    monkeypatch.setattr(server, "get_conn", lambda: pytest.fail("DB touched"))
    r = getattr(client, method)(path, json=body, headers=_h())
    assert r.status_code == 422
    j = r.json()
    assert j["detail"]["field"] == field and "https://" in j["detail"]["message"]
    assert j["errors"][0] == {"field": field, "code": "invalid_url", "message": j["detail"]["message"]}


def test_profile_website_valid_saved(monkeypatch):
    saved = {}
    monkeypatch.setattr(server, "update_profile",
                        lambda uid, data, user_type=None: saved.update(data) or {"id": uid})
    r = client.put("/profile/7", json={"website": " https://edu.example "}, headers=_h(7, "edu"))
    assert r.status_code == 200 and saved["website"] == "https://edu.example"


def test_render_sites_use_helper():
    links = open(os.path.join(ROOT, "profile-v2.links.js"), encoding="utf-8").read()
    courses = open(os.path.join(ROOT, "profile-v2.courses.js"), encoding="utf-8").read()
    utils = open(os.path.join(ROOT, "profile-v2.utils.js"), encoding="utf-8").read()
    assert "href=\"' + urlText" not in links and "twSafeLinkUrl(l.url" in links
    assert "href=\"' + curl" not in courses and "twSafeLinkUrl(c.certificate_url" in courses
    assert "function esc(s){ return twEscHtml(s); }" in utils
    page = open(os.path.join(ROOT, "profile-showcase.html"), encoding="utf-8").read()
    assert page.index("/tw_shared.js") < page.index("profile-v2.utils.js")
