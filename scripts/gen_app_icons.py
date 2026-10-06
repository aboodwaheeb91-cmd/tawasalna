"""Generate PWA / favicon icons + the share image from the official logo (single source).

Source : 33333.svg (repo root, served as /static/33333.svg). The logo is two
         PNG layers embedded in the SVG: a luminance mask (layer 0) and the
         color image (layer 1). Only the symbol (two people / heart, left part)
         is used — the wordmark is cropped out.
Output : static/icons/  (served at root URLs by server.py → _APP_ICON_FILES)
         static/og-image.png (1200×630 share image — og:image / twitter:image of
         landing.html): the FULL logo (symbol + wordmark) centered on the site
         background --color-surface-page, read from tw_shared.css (DS-COLOR).

Re-run whenever the logo changes:
    python scripts/gen_app_icons.py
Requires Pillow (dev-only; not a runtime dependency).
"""
import base64
import io
import os
import re

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "33333.svg")
OUT = os.path.join(ROOT, "static", "icons")
OG_OUT = os.path.join(ROOT, "static", "og-image.png")
OG_SIZE = (1200, 630)
OG_LOGO_WIDTH = 0.70   # logo box = 70% of the image width (centered)

# Symbol column range inside the embedded 1448px layers (gap to wordmark at x≈534–605).
SYMBOL_X_MAX = 570
ALPHA_THRESHOLD = 8


def load_logo():
    """The full logo (color layer + luminance mask as alpha), uncropped."""
    svg = open(SRC, encoding="utf-8").read()
    layers = re.findall(r"base64,([A-Za-z0-9+/=]+)", svg)
    if len(layers) != 2:
        raise SystemExit(f"expected 2 embedded PNG layers, found {len(layers)}")
    mask = Image.open(io.BytesIO(base64.b64decode(layers[0]))).convert("L")
    color = Image.open(io.BytesIO(base64.b64decode(layers[1]))).convert("RGBA")
    color.putalpha(mask)
    return color


def _trim(img):
    bbox = img.getchannel("A").point(lambda a: 255 if a > ALPHA_THRESHOLD else 0).getbbox()
    if not bbox:
        raise SystemExit("logo not found")
    return img.crop(bbox)


def surface_page_rgb():
    """--color-surface-page from tw_shared.css (follows one var() hop to the hex)."""
    css = open(os.path.join(ROOT, "tw_shared.css"), encoding="utf-8").read()

    def val(token):
        m = re.search(r"--" + re.escape(token) + r":\s*([^;]+);", css)
        if not m:
            raise SystemExit(f"--{token} not found in tw_shared.css")
        return m.group(1).strip()

    v = val("color-surface-page")
    ref = re.fullmatch(r"var\(--([\w-]+)\)", v)
    v = val(ref.group(1)) if ref else v
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", v):
        raise SystemExit(f"--color-surface-page is not a 6-digit hex: {v}")
    return tuple(int(v[i:i + 2], 16) for i in (1, 3, 5))


def render_og(logo, background):
    """Full logo centered on a 1200×630 canvas of `background` (RGB)."""
    w_img, h_img = OG_SIZE
    scale = min(w_img * OG_LOGO_WIDTH / logo.width, h_img * 0.6 / logo.height)
    w, h = round(logo.width * scale), round(logo.height * scale)
    sym = logo.convert("RGBa").resize((w, h), Image.LANCZOS).convert("RGBA")
    canvas = Image.new("RGBA", OG_SIZE, background + (255,))
    canvas.alpha_composite(sym, ((w_img - w) // 2, (h_img - h) // 2))
    return canvas.convert("RGB")


def load_symbol():
    color = load_logo()
    left = color.crop((0, 0, SYMBOL_X_MAX, color.height))
    bbox = left.getchannel("A").point(lambda a: 255 if a > ALPHA_THRESHOLD else 0).getbbox()
    if not bbox:
        raise SystemExit("symbol not found in logo")
    return left.crop(bbox)


def render(symbol, size, margin, background):
    """Center `symbol` in a size×size square leaving `margin` (fraction) on each side."""
    box = size * (1 - 2 * margin)
    scale = box / max(symbol.size)
    w, h = max(1, round(symbol.width * scale)), max(1, round(symbol.height * scale))
    sym = symbol.convert("RGBa").resize((w, h), Image.LANCZOS).convert("RGBA")
    canvas = Image.new("RGBA", (size, size), background)
    canvas.alpha_composite(sym, ((size - w) // 2, (size - h) // 2))
    return canvas


def main():
    os.makedirs(OUT, exist_ok=True)
    sym = load_symbol()
    white = (255, 255, 255, 255)
    clear = (0, 0, 0, 0)
    # purpose "any": ~11% safe margin on white
    render(sym, 192, 0.11, white).convert("RGB").save(os.path.join(OUT, "icon-192.png"), optimize=True)
    render(sym, 512, 0.11, white).convert("RGB").save(os.path.join(OUT, "icon-512.png"), optimize=True)
    # purpose "maskable": symbol inside the 80% safe circle → ~20% margin
    render(sym, 512, 0.20, white).convert("RGB").save(os.path.join(OUT, "icon-maskable-512.png"), optimize=True)
    render(sym, 180, 0.11, white).convert("RGB").save(os.path.join(OUT, "apple-touch-icon.png"), optimize=True)
    # favicon: transparent, multi-size .ico (16 + 32)
    fav32 = render(sym, 32, 0.03, clear)
    fav16 = render(sym, 16, 0.03, clear)
    fav32.save(os.path.join(OUT, "favicon.ico"), format="ICO", sizes=[(16, 16), (32, 32)],
               append_images=[fav16])
    print("icons written to", OUT)
    render_og(_trim(load_logo()), surface_page_rgb()).save(OG_OUT, optimize=True)
    print("share image written to", OG_OUT)


if __name__ == "__main__":
    main()
