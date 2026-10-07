"""Page Shell security (pre PR-8/B) — static checks.

1. No served HTML/JS/CSS file carries an admin panel slug ("tw-ctrl-…").
   The only allowed occurrence is the fixed login endpoint `/tw-ctrl-login`
   (called by admin.html, which itself is served only behind the secret slug).
   The slug route lives in server.py only.
2. admin-view.html: clean <!DOCTYPE html> (standards mode), no redirect to the
   deleted admin.html.
3. No page loads a script from an external domain / CDN (unpkg, jsdelivr, cdnjs…).
4. static/app-header.js removed (PR 3.9) — header = twMountAppChrome only,
   no legacy page routes.
5. read_html: a missing page file → HTTP 404 (not 200 with an error body).

Run: python -m pytest test_page_shell_security.py -q
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).parent
SKIP_DIRS = {".git", "node_modules", "docs", "__pycache__"}
SERVED_EXT = {".html", ".js", ".css"}


def _served_files():
    for p in ROOT.rglob("*"):
        if p.suffix not in SERVED_EXT or not p.is_file():
            continue
        rel = p.relative_to(ROOT)
        if set(rel.parts) & SKIP_DIRS or rel.name.startswith("test_"):
            continue
        yield p


def _read(p):
    return p.read_text(encoding="utf-8", errors="ignore")


class TestPageShellSecurity(unittest.TestCase):

    def test_no_admin_slug_in_served_files(self):
        bad = []
        for p in _served_files():
            for m in re.finditer(r"tw-ctrl-(?!login\b)", _read(p)):
                bad.append(str(p.relative_to(ROOT)))
        self.assertEqual(bad, [], "admin slug (tw-ctrl-…) in served files")

    def test_admin_slug_route_only_in_server(self):
        src = _read(ROOT / "server.py")
        self.assertIn('@app.get("/tw-ctrl-" + ADMIN_URL_TOKEN', src)

    def test_admin_view_standards_mode(self):
        src = _read(ROOT / "admin-view.html")
        self.assertTrue(src.startswith("<!DOCTYPE html>\n"), "admin-view.html must start with a clean doctype")
        self.assertNotIn("admin.html", src)

    def test_no_external_cdn_scripts(self):
        bad = []
        for p in _served_files():
            if p.suffix != ".html":
                continue
            src = _read(p)
            if re.search(r"<script[^>]+src=[\"'](https?:)?//", src, re.I):
                bad.append(str(p.relative_to(ROOT)))
            if re.search(r"unpkg\.com|jsdelivr|cdnjs", src, re.I):
                bad.append(str(p.relative_to(ROOT)))
        self.assertEqual(bad, [], "external script / CDN in pages")

    def test_login_page_uses_local_lucide(self):
        for name in ("index.html", "profile-showcase.html"):
            self.assertIn('src="/static/vendor/lucide/lucide.min.js"', _read(ROOT / name), name)

    def test_old_app_header_js_removed(self):
        # PR 3.9: the pre-DS-HNAV header helper was loaded by no page — the header is
        # drawn only by twMountAppChrome (tw_shared.js).
        self.assertFalse((ROOT / "static" / "app-header.js").exists())

    def test_read_html_missing_file_is_404(self):
        src = _read(ROOT / "server.py")
        body = src[src.index("def read_html("):src.index("def check_admin(")]
        self.assertIn("raise HTTPException(status_code=404", body)
        self.assertNotIn("الصفحة غير موجودة: {name}", body)


if __name__ == "__main__":
    unittest.main()
