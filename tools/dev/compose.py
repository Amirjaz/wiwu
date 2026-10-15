"""Photo | render | blend sheet: each source photo beside the 3D bag rendered from that photo's camera
(tools/compare.mjs) and the two blended, plus a close-up of a detail from each.

    python tools/dev/compose.py [render-dir] [out.jpg]

Defaults: media/3d/compare and <render-dir>/sheet.jpg. Needs pillow.
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
render_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'media' / '3d' / 'compare'
out = Path(sys.argv[2]) if len(sys.argv) > 2 else render_dir / 'sheet.jpg'
PHOTOS = ROOT / 'media' / 'source-photos'
photos = {'side': '1-side-lock.jpg', 'front': '2-front.jpg', 'back': '3-back.jpg'}
# Pixel boxes in the source photos: the bag, and the close-up.
crops = {'side': (230, 230, 620, 980), 'front': (120, 440, 980, 1000), 'back': (0, 300, 900, 920)}
closeups = {'side': (320, 660, 500, 920), 'front': (700, 760, 880, 940), 'back': (640, 420, 820, 780)}

rows = []
for name, file in photos.items():
    photo = Image.open(PHOTOS / file).convert('RGB')
    render = Image.open(render_dir / f'{name}-render.jpg').convert('RGB').resize(photo.size)
    blend = Image.blend(photo, render, 0.5)
    tiles = [im.crop(crops[name]) for im in (photo, render, blend)]
    cb = closeups[name]
    tiles += [im.crop(cb).resize(((cb[2] - cb[0]) * 2, (cb[3] - cb[1]) * 2), Image.LANCZOS) for im in (photo, render)]
    h = 360
    tiles = [t.resize((int(t.width * h / t.height), h)) for t in tiles]
    row = Image.new('RGB', (sum(t.width for t in tiles) + 10 * len(tiles), h + 18), (255, 255, 255))
    x = 0
    for label, t in zip(('photo', 'render', 'blend', 'photo close', 'render close'), tiles):
        row.paste(t, (x, 18))
        ImageDraw.Draw(row).text((x + 4, 3), f'{name}: {label}', fill=(200, 0, 0))
        x += t.width + 10
    rows.append(row)

sheet = Image.new('RGB', (max(r.width for r in rows), sum(r.height + 8 for r in rows)), (255, 255, 255))
y = 0
for r in rows:
    sheet.paste(r, (0, y))
    y += r.height + 8
sheet.save(out, quality=88)
print('wrote', out, sheet.size)
