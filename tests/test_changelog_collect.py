"""test_changelog_collect.py — PR 3.11: changelog.d/<task>.md fragments → docs/CHANGELOG.md.

Behaviour (throw-away changelog, not the real one):
  1. --check accepts a valid fragment and rejects a bad heading / task ≠ file name / no bullet
  2. collect puts fragments above the old entries (newest date first, after the index) and
     deletes them; README.md in changelog.d is never treated as a fragment
  3. the real changelog.d fragments are valid

Run: python -m pytest tests/test_changelog_collect.py -q
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import changelog_collect as cc  # noqa: E402

OLD = "# CHANGELOG\n\n## فهرس\n\n- x\n\n## PR 1.0 — old — 2026-01-01\n\n- old\n"


def _setup(tmp_path, monkeypatch, frags):
    d = tmp_path / "changelog.d"; d.mkdir()
    (d / "README.md").write_text("how to", encoding="utf-8")
    for name, body in frags.items():
        (d / f"{name}.md").write_text(body, encoding="utf-8")
    log = tmp_path / "CHANGELOG.md"; log.write_text(OLD, encoding="utf-8")
    monkeypatch.setattr(cc, "FRAG_DIR", str(d)); monkeypatch.setattr(cc, "CHANGELOG", str(log))
    return d, log


def test_check_rejects_bad_fragments(tmp_path, monkeypatch, capsys):
    _setup(tmp_path, monkeypatch, {"3.1": "## PR 3.1 — ok — 2026-10-08\n\n- a\n"})
    assert cc.main(["--check"]) == 0
    for name, body in {"3.2": "PR 3.2 no heading\n- a", "3.3": "## PR 9.9 — x — 2026-10-08\n- a",
                       "3.4": "## PR 3.4 — x — 2026-10-08\n\nno bullet"}.items():
        p = tmp_path / "changelog.d" / f"{name}.md"; p.write_text(body, encoding="utf-8")
        assert cc.main(["--check"]) == 1, name
        p.unlink()
    assert "≠ file name" in capsys.readouterr().out


def test_collect_inserts_newest_first_and_deletes(tmp_path, monkeypatch):
    d, log = _setup(tmp_path, monkeypatch, {
        "3.10": "## PR 3.10 — older — 2026-10-07\n\n- b\n",
        "3.11": "## PR 3.11 — newer — 2026-10-08\n\n- a\n"})
    assert cc.main([]) == 0
    text = log.read_text(encoding="utf-8")
    assert text.index("## فهرس") < text.index("PR 3.11") < text.index("PR 3.10") < text.index("PR 1.0")
    assert sorted(os.listdir(d)) == ["README.md"]
    assert cc.main([]) == 0 and log.read_text(encoding="utf-8") == text   # nothing left → no change


def test_repo_fragments_are_valid():
    assert all(not cc.check_fragment(p) for p in cc.fragments()), [
        (p, cc.check_fragment(p)) for p in cc.fragments()]
