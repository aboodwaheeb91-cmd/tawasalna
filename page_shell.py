"""page_shell.py — Page Shell (PR-8 / Phase B · docs/design-system/PAGE-SHELL.md).

The single source for the shared <head> block and shared end-of-body scripts of
every HTML page. read_html() in server.py calls apply_shell() on each page file:

  <!--tw:shell-head-->           → partials/shell-head.html
  <!--tw:shell-scripts-->        → partials/shell-scripts.html
  <!--tw:shell-head:admin-->     → partials/shell-head.admin.html
  <!--tw:shell-scripts:admin-->  → partials/shell-scripts.admin.html

A page without markers is returned byte-for-byte unchanged. The injected text is
fixed (partials + content hashes) — never user data (§54).

{{v:<asset>}} in a partial → short sha256 of that asset file, computed once when
this module is imported (server start). Changing the file changes the hash →
browsers and the service worker fetch the new version (no manual ?v=).
"""
import hashlib
import os

_ROOT = os.path.dirname(os.path.abspath(__file__))

# Shared assets whose ?v= is the content hash. Key = placeholder name.
SHELL_ASSETS = {
    "tw_shared.css": "tw_shared.css",
    "tw_shared.js":  "tw_shared.js",
    "auth-sync.js":  os.path.join("static", "shared", "auth-sync.js"),
}

# variant → (head marker, head partial, scripts marker, scripts partial)
SHELL_VARIANTS = {
    "app":   ("<!--tw:shell-head-->",          "shell-head.html",
              "<!--tw:shell-scripts-->",       "shell-scripts.html"),
    "admin": ("<!--tw:shell-head:admin-->",    "shell-head.admin.html",
              "<!--tw:shell-scripts:admin-->", "shell-scripts.admin.html"),
}

HASH_LEN = 10


def asset_hash(path: str) -> str:
    """Short content hash of one file (sha256, first HASH_LEN hex chars)."""
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()[:HASH_LEN]


def build_shell(root: str = _ROOT) -> dict:
    """Read the partials and fill {{v:<asset>}} → {marker: html}. Fails loudly
    (OSError / ValueError) when a partial or asset is missing (F9)."""
    hashes = {name: asset_hash(os.path.join(root, rel)) for name, rel in SHELL_ASSETS.items()}
    shell = {}
    for head_m, head_f, scripts_m, scripts_f in SHELL_VARIANTS.values():
        for marker, fname in ((head_m, head_f), (scripts_m, scripts_f)):
            with open(os.path.join(root, "partials", fname), "r", encoding="utf-8") as f:
                html = f.read().strip()
            for name, h in hashes.items():
                html = html.replace("{{v:" + name + "}}", h)
            if "{{" in html:
                raise ValueError(f"[page_shell] unknown placeholder in partials/{fname}")
            shell[marker] = html
    return shell


_SHELL = build_shell()


def apply_shell(content: str, name: str = "", shell: dict = None) -> str:
    """Replace the shell markers of one page. No markers → content unchanged.
    A page must use exactly one variant, with each of its two markers once —
    anything else raises ValueError (a half-converted page is a bug, not a page)."""
    shell = _SHELL if shell is None else shell
    if "<!--tw:shell-" not in content:
        return content
    used = []
    for variant, (head_m, _hf, scripts_m, _sf) in SHELL_VARIANTS.items():
        n_head, n_scripts = content.count(head_m), content.count(scripts_m)
        if n_head or n_scripts:
            if n_head != 1 or n_scripts != 1:
                raise ValueError(f"[page_shell] {name}: '{variant}' needs each marker exactly once")
            if content.index(head_m) > content.index(scripts_m):
                raise ValueError(f"[page_shell] {name}: head marker must come before scripts marker")
            used.append(variant)
    if len(used) != 1:
        raise ValueError(f"[page_shell] {name}: unknown or mixed shell markers")
    head_m, _hf, scripts_m, _sf = SHELL_VARIANTS[used[0]]
    return content.replace(head_m, shell[head_m]).replace(scripts_m, shell[scripts_m])
