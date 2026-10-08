"""test_page_audit.py — PR 3.11: tools/page_audit.py counts page debt and fails only when it grows.

Behaviour (a throw-away page tree, not the real pages):
  1. each metric counts what it should (raw fetch, colors, tw_user/tw_jwt, native dialogs,
     «فرص», local helpers, missing shell / header) — shared files are not counted
  2. compare(): above baseline → worse (run fails) · below → better (prints «حدّث الـ baseline»)
  3. a page missing from the baseline starts at 0 for every metric
  4. the real repo is at or below its committed baseline

Run: python -m pytest tests/test_page_audit.py -q
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import page_audit  # noqa: E402

PAGE = """<!doctype html><html><head>
<link rel="stylesheet" href="/static/p.css?v=1"><script src="/tw_shared.js"></script>
<script src="/static/shared/x.js"></script><script src="/static/p.js?v=2"></script></head>
<body><div style="color:#ff0000">فرص العمل</div></body></html>"""
PAGE_JS = """
fetch('/api/a'); twApi('/api/b'); TwAdminSession.fetch('/admin/x');
localStorage.getItem('tw_jwt'); localStorage.getItem('other');
alert('x'); window.confirm('y'); twConfirm({}); prompt('z');
function esc(s){ return s; } var showToast = function(){}; function render(){}
"""
CLEAN = """<!doctype html><html><head><!--tw:shell-head--></head>
<body><header data-tw-header></header></body></html>"""


def _tree(tmp_path, monkeypatch):
    (tmp_path / "static" / "shared").mkdir(parents=True)
    (tmp_path / "page.html").write_text(PAGE, encoding="utf-8")
    (tmp_path / "clean.html").write_text(CLEAN, encoding="utf-8")
    (tmp_path / "p.js").write_text(PAGE_JS, encoding="utf-8")            # /static/p.js → root fallback
    (tmp_path / "static" / "p.css").write_text("a{color:rgb(1,2,3)}", encoding="utf-8")
    (tmp_path / "tw_shared.js").write_text("fetch('/x'); alert(1);", encoding="utf-8")       # shared → not counted
    (tmp_path / "static" / "shared" / "x.js").write_text("fetch('/y');", encoding="utf-8")   # shared → not counted
    monkeypatch.setattr(page_audit, "ROOT", str(tmp_path))


def test_metrics_count_the_page_and_its_own_assets_only(tmp_path, monkeypatch):
    _tree(tmp_path, monkeypatch)
    row = page_audit.audit_page("page.html")
    assert row == {"fetch": 1, "colors": 2, "ls_session": 1, "dialogs": 3, "forsa": 1,
                   "helpers": 2, "no_shell": 1, "no_header": 1}
    assert page_audit.audit_page("clean.html") == dict.fromkeys(page_audit.METRICS, 0)


def test_compare_fails_only_on_growth_and_new_pages_start_at_zero(tmp_path, monkeypatch):
    _tree(tmp_path, monkeypatch)
    cur = page_audit.audit()
    base = {"page.html": dict(cur["page.html"], fetch=5, dialogs=0)}
    worse, better = page_audit.compare(cur, base)
    assert ("page.html", "dialogs", 0, 3) in worse          # grew → fail
    assert ("page.html", "fetch", 5, 1) in better           # dropped → «حدّث الـ baseline»
    assert all(p != "clean.html" for p, *_ in worse)        # new clean page: 0 = 0
    bad = dict(cur, **{"new.html": dict.fromkeys(page_audit.METRICS, 0, ) | {"fetch": 1}})
    assert ("new.html", "fetch", 0, 1) in page_audit.compare(bad, base)[0]


def test_main_exit_code(tmp_path, monkeypatch, capsys):
    _tree(tmp_path, monkeypatch)
    bl = tmp_path / "baseline.json"
    monkeypatch.setattr(page_audit, "BASELINE", str(bl))
    assert page_audit.main(["--update"]) == 0 and json.loads(bl.read_text())["page.html"]["fetch"] == 1
    assert page_audit.main([]) == 0
    data = json.loads(bl.read_text()); data["page.html"]["fetch"] = 0
    bl.write_text(json.dumps(data))
    assert page_audit.main([]) == 1 and "fetch زاد 0 → 1" in capsys.readouterr().out


def test_repo_is_within_its_committed_baseline():
    worse, _ = page_audit.compare(page_audit.audit(), json.load(open(page_audit.BASELINE, encoding="utf-8")))
    assert worse == [], worse
