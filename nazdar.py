#!/usr/bin/env python3
"""Napíše "nazdar" na Sharp Memory LCD 2.7" (400x240) připojený k Raspberry Pi.

Displej obsluhuje kernelový ovladač sharp-drm (viz README.md). Ten vytvoří
framebuffer /dev/fbN; tenhle program si ho sám najde, nakreslí text přes
Pillow a zapíše ho přímo do framebufferu. Nic dalšího není potřeba.

Použití:
    python3 nazdar.py                 # napíše "nazdar"
    python3 nazdar.py "Ahoj světe"    # vlastní text
    python3 nazdar.py --fb /dev/fb1   # framebuffer zadaný ručně
"""

import argparse
import glob
import os
import sys

from PIL import Image, ImageDraw, ImageFont

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def find_sharp_fb():
    """Vrátí cestu k framebufferu, jehož jméno obsahuje 'sharp' (např. sharp_drmdrmfb)."""
    for name_file in sorted(glob.glob("/sys/class/graphics/fb*/name")):
        with open(name_file) as f:
            if "sharp" in f.read().lower():
                return "/dev/" + os.path.basename(os.path.dirname(name_file))
    return None


def fb_info(fb_dev):
    """Načte rozměry a formát framebufferu ze sysfs."""
    sysfs = "/sys/class/graphics/" + os.path.basename(fb_dev)

    def read(attr):
        with open(os.path.join(sysfs, attr)) as f:
            return f.read().strip()

    width, height = (int(v) for v in read("virtual_size").split(","))
    bpp = int(read("bits_per_pixel"))
    stride = int(read("stride"))
    return width, height, bpp, stride


def load_font(size):
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size=size)


def render(text, width, height):
    """Nakreslí text co největším písmem doprostřed bílé plochy (černé písmo)."""
    img = Image.new("L", (width, height), 255)
    draw = ImageDraw.Draw(img)
    size = height
    while size > 8:
        font = load_font(size)
        left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
        if right - left <= width * 0.9 and bottom - top <= height * 0.8:
            break
        size -= 4
    x = (width - (right - left)) // 2 - left
    y = (height - (bottom - top)) // 2 - top
    draw.text((x, y), text, font=font, fill=0)
    return img


def to_fb_bytes(img, bpp, stride):
    """Převede obrázek do formátu framebufferu (32 bit XRGB8888 nebo 16 bit RGB565)."""
    width, height = img.size
    gray = img.tobytes()
    if bpp == 32:
        row_pixels = lambda row: b"".join(bytes((g, g, g, 0)) for g in row)
    elif bpp == 16:
        def row_pixels(row):
            out = bytearray()
            for g in row:
                v = ((g >> 3) << 11) | ((g >> 2) << 5) | (g >> 3)
                out += v.to_bytes(2, "little")
            return bytes(out)
    else:
        raise SystemExit(f"Nepodporovaný formát framebufferu: {bpp} bitů na pixel")

    data = bytearray()
    for y in range(height):
        line = row_pixels(gray[y * width:(y + 1) * width])
        data += line + bytes(stride - len(line))
    return bytes(data)


def main():
    ap = argparse.ArgumentParser(description="Napíše text na Sharp Memory LCD.")
    ap.add_argument("text", nargs="?", default="nazdar")
    ap.add_argument("--fb", help="framebuffer, např. /dev/fb1 (jinak se najde sám)")
    args = ap.parse_args()

    fb = args.fb or find_sharp_fb()
    if not fb:
        sys.exit("Framebuffer displeje Sharp nenalezen. Je načtený ovladač sharp-drm? "
                 "Zkontroluj: cat /sys/class/graphics/fb*/name")

    width, height, bpp, stride = fb_info(fb)
    img = render(args.text, width, height)
    with open(fb, "wb") as f:
        f.write(to_fb_bytes(img, bpp, stride))
    print(f"Hotovo: '{args.text}' -> {fb} ({width}x{height}, {bpp} bit)")


if __name__ == "__main__":
    main()
