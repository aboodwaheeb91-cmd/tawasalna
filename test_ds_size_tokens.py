"""
DS-SIZE Phase 1 static checks — PR-5 / Phase B (F36 · docs/design-system/SIZE-SYSTEM.md)

  S1  every DS-SIZE token is defined exactly once in tw_shared.css, with its documented value
  S2  tw_shared.css defines no --size-* / --radius-* / --space-* outside the documented set
  S3  no other CSS / HTML / JS file defines --size-* / --radius-* / --space-*
  S4  vs origin/main: no CSS / HTML file other than tw_shared.css adds a DS-SIZE consumer (no migration)

Run:  python test_ds_size_tokens.py
"""

import os
import re
import subprocess
import sys

_ROOT = os.path.dirname(os.path.abspath(__file__))
_SKIP_DIRS = {'.git', 'node_modules', 'vendor', '__pycache__'}

EXPECTED = {
    # font (SIZE-02)
    '--size-font-3xs': '.6rem', '--size-font-2xs': '.65rem', '--size-font-xs': '.72rem',
    '--size-font-sm': '.78rem', '--size-font-md': '.82rem', '--size-font-lg': '.9rem',
    '--size-font-xl': '.95rem', '--size-font-2xl': '1rem', '--size-font-3xl': '1.2rem',
    '--size-font-4xl': '1.4rem', '--size-font-5xl': '1.6rem', '--size-font-display': '2rem',
    # radius (SIZE-03)
    '--radius-2xs': '4px', '--radius-xs': '6px', '--radius-sm': '8px', '--radius-md': '10px',
    '--radius-lg': '12px', '--radius-xl': '14px', '--radius-2xl': '16px', '--radius-3xl': '20px',
    '--radius-pill': '999px', '--radius-circle': '50%', '--radius-control': 'var(--radius-md)',
    # spacing (SIZE-04)
    '--space-1': '2px', '--space-2': '4px', '--space-3': '6px', '--space-4': '8px',
    '--space-5': '10px', '--space-6': '12px', '--space-7': '14px', '--space-8': '16px',
    '--space-9': '18px', '--space-10': '20px', '--space-11': '24px', '--space-12': '32px',
    '--space-13': '40px',
    # icons + controls (SIZE-06)
    '--size-icon-xs': '12px', '--size-icon-sm': '14px', '--size-icon-md': '16px',
    '--size-icon-lg': '18px', '--size-icon-xl': '20px', '--size-icon-2xl': '22px',
    '--size-control-icon-xs': '28px', '--size-control-icon-sm': '30px',
    '--size-control-icon-md': '32px', '--size-control-icon-lg': '40px',
    '--size-control-sm': '28px', '--size-control-md': '40px', '--size-touch-min': '44px',
    # avatar / logo box (DS-IMAGE IMG-02 · F38)
    '--size-avatar-md': '40px', '--size-avatar-lg': '48px', '--size-avatar-xl': '88px',
    '--size-avatar-2xl': '106px',
}

# A custom-property *definition* (not a var() reference)
_DEF_RE = re.compile(r'(?<![\w(-])(--(?:size|radius|space)-[\w-]+)\s*:\s*([^;}]+)')

failures = []


def check(name, ok, detail=''):
    print(('PASS ' if ok else 'FAIL ') + name + ((' — ' + detail) if detail and not ok else ''))
    if not ok:
        failures.append(name)


def _defs(text):
    return [(m.group(1), m.group(2).split('/*')[0].strip()) for m in _DEF_RE.finditer(text)]


shared = open(os.path.join(_ROOT, 'tw_shared.css'), encoding='utf-8').read()
shared_defs = _defs(shared)

# S1
for tok, val in EXPECTED.items():
    found = [v for t, v in shared_defs if t == tok]
    check(f'S1 {tok} defined once = {val}', found == [val], f'found {found}')

# S2
extra = sorted({t for t, _ in shared_defs} - set(EXPECTED))
check('S2 no undocumented DS-SIZE token in tw_shared.css', not extra, ', '.join(extra))

# S3
outside = []
for dirpath, dirnames, filenames in os.walk(_ROOT):
    dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
    for fn in filenames:
        if not fn.endswith(('.css', '.html', '.js')):
            continue
        path = os.path.join(dirpath, fn)
        rel = os.path.relpath(path, _ROOT)
        if rel == 'tw_shared.css':
            continue
        try:
            text = open(path, encoding='utf-8').read()
        except (UnicodeDecodeError, OSError) as e:
            check(f'S3 readable {rel}', False, str(e))
            continue
        for tok, _ in _defs(text):
            outside.append(f'{rel}: {tok}')
check('S3 no --size-*/--radius-*/--space-* defined outside tw_shared.css', not outside,
      '; '.join(outside[:10]))

# S4 — no page migration: no CSS/HTML file other than tw_shared.css gains a DS-SIZE consumer
# (a version-string bump or unrelated HTML change is not a migration)
_USE_RE = re.compile(r'var\(\s*--(?:size|radius|space)-')
try:
    base = subprocess.run(['git', 'merge-base', 'origin/main', 'HEAD'], cwd=_ROOT,
                          capture_output=True, text=True, check=True).stdout.strip()
    diff = subprocess.run(['git', 'diff', '-U0', base, '--', '*.css', '*.html', ':!tw_shared.css'],
                          cwd=_ROOT, capture_output=True, text=True, check=True).stdout
    untracked = subprocess.run(['git', 'ls-files', '--others', '--exclude-standard'], cwd=_ROOT,
                               capture_output=True, text=True, check=True).stdout.split()
    added = [l for l in diff.splitlines() if l.startswith('+') and not l.startswith('+++')]
    for f in untracked:
        if f.endswith(('.css', '.html')) and f != 'tw_shared.css':
            added += open(os.path.join(_ROOT, f), encoding='utf-8').read().splitlines()
    consumers = [l.strip()[:80] for l in added if _USE_RE.search(l)]
    check('S4 no DS-SIZE consumer added outside tw_shared.css vs origin/main', not consumers,
          '; '.join(consumers[:5]))
except (subprocess.CalledProcessError, FileNotFoundError) as e:
    check('S4 git diff vs origin/main available', False, str(e))

print(f'\n{len(EXPECTED) + 3 - len(failures)}/{len(EXPECTED) + 3} passed'
      if not failures else f'\n{len(failures)} FAILED')
sys.exit(1 if failures else 0)
