"""task 7.6 — SYSTEMS_INDEX §54f Classification line = server._startup_migrations() (SYSTEMS_INDEX §54f).

Reads server.py with ast (no import → no fastapi / DB) and compares the registry (name, critical) with the
critical / optional / "critical + last" lists of the doc line: same names, same class, same order, and
rls_lockdown is the last entry of the registry.
Run: python -m pytest tests/test_migration_classification_doc.py -q
"""
import ast
import re

NAME = re.compile(r"`([a-z][a-z0-9_]*)`")


def _registry():
    tree = ast.parse(open("server.py", encoding="utf-8").read())
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_startup_migrations")
    ret = next(n for n in ast.walk(fn) if isinstance(n, ast.Return))
    out = []
    for elt in ret.value.elts:
        name, _fn, critical = elt.elts
        out.append((ast.literal_eval(name), ast.literal_eval(critical)))
    return out


def _doc():
    text = open("docs/SYSTEMS_INDEX.md", encoding="utf-8").read()
    sec = text[text.index("### 54f."):]
    line = next(l for l in sec.splitlines() if l.startswith("**Classification:**"))
    m = re.search(r"critical = (.*?) optional = (.*?) critical \+ \*\*last\*\*(.*?)One-time", line)
    assert m, "§54f Classification line: critical = … optional = … critical + **last** … not found"
    return [NAME.findall(g) for g in m.groups()]


def test_doc_matches_registry():
    reg = _registry()
    critical, optional, last = _doc()
    assert reg[-1] == ("rls_lockdown", True), "rls_lockdown must be the last registry entry (critical)"
    assert last == ["rls_lockdown"], last
    assert critical == [n for n, c in reg[:-1] if c is True], "critical list ≠ registry"
    assert optional == [n for n, c in reg[:-1] if c is False], "optional list ≠ registry"
    assert len(set(n for n, _ in reg)) == len(reg), "duplicate migration name"


if __name__ == "__main__":
    test_doc_matches_registry()
    print("ok")
