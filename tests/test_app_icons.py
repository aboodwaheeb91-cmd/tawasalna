"""App icons (PWA + favicon) — SYSTEMS_INDEX §32.

Checks: icon files exist with correct dimensions, manifest points to existing
files with correct sizes/purpose, server.py serves the files (no placeholder,
no inline-generated favicon), SW allowlist covers /icon-*.png.
Run: python tests/test_app_icons.py
"""
import json
import os
import re
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ICONS = os.path.join(ROOT, "static", "icons")
results = []


def check(name, ok):
    results.append((name, bool(ok)))
    print(("PASS " if ok else "FAIL ") + name)


def size_of(name):
    """PNG width/height from the IHDR chunk (no Pillow dependency)."""
    with open(os.path.join(ICONS, name), "rb") as f:
        head = f.read(24)
    assert head[:8] == b"\x89PNG\r\n\x1a\n", name + " is not a PNG"
    return struct.unpack(">II", head[16:24])


def ico_sizes(path):
    with open(path, "rb") as f:
        data = f.read()
    _, typ, count = struct.unpack("<HHH", data[:6])
    out = set()
    for i in range(count):
        w, h = data[6 + 16 * i], data[7 + 16 * i]
        out.add((w or 256, h or 256))
    return typ, out


expected = {"icon-192.png": (192, 192), "icon-512.png": (512, 512),
            "icon-maskable-512.png": (512, 512), "apple-touch-icon.png": (180, 180)}
for f, dim in expected.items():
    path = os.path.join(ICONS, f)
    check(f"{f} exists", os.path.isfile(path))
    check(f"{f} is {dim[0]}x{dim[1]}", os.path.isfile(path) and size_of(f) == dim)

ico = os.path.join(ICONS, "favicon.ico")
check("favicon.ico exists", os.path.isfile(ico))
if os.path.isfile(ico):
    typ, sizes = ico_sizes(ico)
    check("favicon.ico is an ICO with 16x16 + 32x32", typ == 1 and {(16, 16), (32, 32)} <= sizes)

# Real icons, not the old 1x1 placeholder (~70 bytes)
for f in expected:
    check(f"{f} is a real image (>2KB)", os.path.getsize(os.path.join(ICONS, f)) > 2048)

manifest = json.load(open(os.path.join(ROOT, "manifest.json"), encoding="utf-8"))
server = open(os.path.join(ROOT, "server.py"), encoding="utf-8").read()
m = re.search(r"_APP_ICON_FILES = \{(.*?)\n\}", server, re.S)
check("server.py has _APP_ICON_FILES allowlist", m)
mapping = dict(re.findall(r'"(/[^"]+)":\s*\("([^"]+)"', m.group(1))) if m else {}
for icon in manifest.get("icons", []):
    src, sizes = icon["src"], icon["sizes"]
    fname = mapping.get(src)
    check(f"manifest {src} is served by server.py", fname)
    if fname:
        w, h = size_of(fname)
        check(f"manifest {src} sizes={sizes} matches file", sizes == f"{w}x{h}")
purposes = {i.get("purpose") for i in manifest.get("icons", [])}
check("manifest has purpose any + maskable", {"any", "maskable"} <= purposes)
check("manifest theme_color = --color-brand-primary (#00c896)", manifest.get("theme_color") == "#00c896")
check("manifest background_color = --color-surface-page (#070b18)", manifest.get("background_color") == "#070b18")

for path in ("/favicon.ico", "/apple-touch-icon.png"):
    check(f"server.py serves {path} from file", path in mapping and f'@app.get("{path}"' in server)
check("no 1x1 placeholder PNG in server.py", "1x1 green pixel" not in server and "iVBORw0KGgoAAAANSUhEUgAAAAEAAAAB" not in server)
check("no inline-generated favicon SVG in server.py", 'font-family="sans-serif">ت<' not in server)

sw = open(os.path.join(ROOT, "sw.js"), encoding="utf-8").read()
rx = re.search(r"/\^\\/icon-\[A-Za-z0-9_-\]\+\\\.png\$/", sw)
check("sw.js allowlist covers /icon-*.png", rx)
if rx:
    pat = re.compile(r"^/icon-[A-Za-z0-9_-]+\.png$")
    for src in mapping:
        if src.startswith("/icon-"):
            check(f"sw allowlist matches {src}", pat.match(src))

failed = [n for n, ok in results if not ok]
print(f"\n{len(results) - len(failed)}/{len(results)} passed")
sys.exit(1 if failed else 0)
