#!/usr/bin/env python3
"""Convert icon.svg to various formats for all platforms.
Called from build.yml — requires cairosvg and Pillow installed."""
import os, subprocess, sys

try:
    import cairosvg
    from PIL import Image
    import io
except ImportError:
    print("::group::Install icon converters")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "cairosvg", "Pillow"])
    import cairosvg
    from PIL import Image
    import io

ASSETS = os.path.dirname(os.path.abspath(__file__))
SVG = os.path.join(ASSETS, "icon.svg")
OUT = ASSETS

def gen_png(size, path):
    png_data = cairosvg.svg2png(url=SVG, output_width=size, output_height=size)
    img = Image.open(io.BytesIO(png_data))
    img.save(path)

def gen_ico():
    png_data = cairosvg.svg2png(url=SVG, output_width=256, output_height=256)
    img = Image.open(io.BytesIO(png_data))
    img.save(os.path.join(OUT, "icon.ico"), format="ICO", sizes=[(256, 256)])

def gen_icns():
    png_data = cairosvg.svg2png(url=SVG, output_width=512, output_height=512)
    # Simple: save as PNG at 512 — macOS can use it
    with open(os.path.join(OUT, "icon.png"), "wb") as f:
        f.write(png_data)
    # Try iconutil if on macOS
    if sys.platform == "darwin":
        iconset = os.path.join(ASSETS, "icon.iconset")
        os.makedirs(iconset, exist_ok=True)
        for sz in [16, 32, 64, 128, 256, 512]:
            gen_png(sz, os.path.join(iconset, f"icon_{sz}x{sz}.png"))
            gen_png(sz * 2, os.path.join(iconset, f"icon_{sz}x{sz}@2x.png"))
        subprocess.run(["iconutil", "-c", "icns", iconset, "-o", os.path.join(OUT, "icon.icns")], check=False)

if __name__ == "__main__":
    print("::group::Generating ICO")
    gen_ico()
    print(f"  icon.ico — {os.path.getsize(os.path.join(OUT, 'icon.ico'))} bytes")
    print("::endgroup::")
    print("::group::Generating PNG (512)")
    gen_png(512, os.path.join(OUT, "icon.png"))
    print("  icon.png — done")
    print("::endgroup::")
    print("::group::Generating ICNS (macOS)")
    gen_icns()
    print("  icon.icns / icon.png — done")
    print("::endgroup::")