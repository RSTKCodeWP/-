"""Generate the desktop-app icon (antenna + signal arcs on a dark rounded
square) as an AppIcon.iconset directory; install_desktop_icon.sh compiles it
with iconutil. Usage: python make_icon.py <output-dir>. Requires Pillow."""
from PIL import Image, ImageDraw
import os
import sys

S = 1024
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)

# macOS-style rounded square with margin
m = 90
d.rounded_rectangle([m, m, S - m, S - m], radius=185, fill=(16, 24, 39, 255))

# subtle inner gradient band (simple: darker bottom strip)
grad = Image.new("RGBA", (S, S), (0, 0, 0, 0))
gd = ImageDraw.Draw(grad)
for i in range(S):
    a = int(60 * (i / S))
    gd.line([(0, i), (S, i)], fill=(0, 0, 0, a))
mask = Image.new("L", (S, S), 0)
md = ImageDraw.Draw(mask)
md.rounded_rectangle([m, m, S - m, S - m], radius=185, fill=255)
img.paste(grad, (0, 0), Image.composite(grad, Image.new("RGBA", (S, S), (0, 0, 0, 0)), mask).split()[3])

green = (74, 222, 128, 255)
white = (235, 240, 248, 255)

cx, base_y = S // 2, 745
# mast
d.line([(cx, base_y), (cx, 445)], fill=white, width=34)
# tripod legs
d.line([(cx, base_y - 10), (cx - 130, base_y + 90)], fill=white, width=30)
d.line([(cx, base_y - 10), (cx + 130, base_y + 90)], fill=white, width=30)
# emitter dot
d.ellipse([cx - 46, 400, cx + 46, 492], fill=green)

# signal arcs radiating up from the emitter
ey = 446
for r, w in [(150, 26), (250, 26), (350, 26)]:
    d.arc([cx - r, ey - r, cx + r, ey + r], start=215, end=325, fill=green, width=w)

out = sys.argv[1] if len(sys.argv) > 1 else "."
os.makedirs(f"{out}/AppIcon.iconset", exist_ok=True)
for size in [16, 32, 64, 128, 256, 512, 1024]:
    im = img.resize((size, size), Image.LANCZOS)
    im.save(f"{out}/AppIcon.iconset/icon_{size}x{size}.png")
    if size >= 32:
        im.save(f"{out}/AppIcon.iconset/icon_{size//2}x{size//2}@2x.png")

# Windows shortcut icon (committed as packaging/hackrf_monitor.ico)
img.save(f"{out}/hackrf_monitor.ico",
         sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print(out)
