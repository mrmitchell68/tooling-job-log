"""Synthetic test photo for the Clean up editor: a molded blue plastic part (cap + flange, shaded,
with specular highlights and a contact shadow) sitting on a busy workbench background."""
import random, math
from PIL import Image, ImageDraw, ImageFilter, ImageFont
random.seed(7)
W, H = 1600, 1200
bg = Image.new("RGB", (W, H), (120, 96, 70))
d = ImageDraw.Draw(bg)
# wood grain
for y in range(0, H, 3):
    c = 105 + int(25*math.sin(y/17.0) + 12*math.sin(y/5.3)) + random.randint(-6, 6)
    d.line([(0, y), (W, y + random.randint(-4, 4))], fill=(c+25, c, c-30), width=3)
# clutter: tools, papers, bolts, tape
for _ in range(60):
    x, y = random.randint(-100, W), random.randint(-100, H)
    w, h = random.randint(40, 320), random.randint(20, 200)
    col = random.choice([(200,40,40),(230,190,40),(40,140,70),(30,30,30),(220,220,215),(90,90,100),(240,120,20),(60,90,170)])
    shape = random.random()
    if shape < 0.4: d.rectangle([x, y, x+w, y+h], fill=col, outline=(20,20,20), width=2)
    elif shape < 0.7: d.ellipse([x, y, x+w, y+w], fill=col, outline=(15,15,15), width=3)
    else: d.line([(x, y), (x+w, y+h)], fill=col, width=random.randint(6, 22))
try:
    f = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 34)
    for _ in range(8): d.text((random.randint(0, W-300), random.randint(0, H-40)), random.choice(["LOT 4471", "QC HOLD", "PP-H 3.5", "T-1042", "REJECT"]), fill=(20,20,20), font=f)
except Exception: pass
bg = bg.filter(ImageFilter.GaussianBlur(1.2))
# contact shadow
sh = Image.new("L", (W, H), 0); ds = ImageDraw.Draw(sh)
ds.ellipse([520, 830, 1120, 960], fill=150); sh = sh.filter(ImageFilter.GaussianBlur(28))
bg.paste((25, 20, 15), (0, 0), sh)
# the part: flange (wide ellipse) + cylindrical body + domed top, shaded per-pixel
part = Image.new("RGBA", (W, H), (0, 0, 0, 0)); px = part.load()
cx = 820
def shade(base, t, spec):
    r, g, b = base; k = 0.45 + 0.75*t
    return (min(255, int(r*k + spec)), min(255, int(g*k + spec)), min(255, int(b*k + spec)), 255)
base = (40, 110, 200)
for y in range(300, 930):
    for x in range(430, 1210):
        dx = x - cx
        # flange: ellipse center y=860, rx 360, ry 70
        inF = (dx/360.0)**2 + ((y-860)/70.0)**2 <= 1 and y >= 820 or ((dx/360.0)**2 + ((y-820)/70.0)**2 <= 1)
        inF = inF or (abs(dx) <= 360*math.sqrt(max(0, 1-0)) and 820 <= y <= 860 and (dx/360.0)**2 <= 1)
        # body: cylinder x in [-220,220], y 420..840 ; dome top ellipse center 420 rx 220 ry 90
        inB = (abs(dx) <= 220 and 420 <= y <= 840) or ((dx/220.0)**2 + ((y-420)/90.0)**2 <= 1)
        if inB:
            t = 0.5 + 0.5*math.cos((dx/220.0)*math.pi/2 + 0.6)
            spec = 110*math.exp(-((dx+90)/28.0)**2) if y > 400 else 0
            if y < 420: t = min(1, t + 0.2*(1-(y-330)/90.0))
            px[x, y] = shade(base, t, spec)
        elif inF:
            t = 0.35 + 0.4*(1-abs(dx)/360.0) + (0.2 if y < 845 else -0.1)
            px[x, y] = shade((35, 95, 180), max(0, min(1, t)), 0)
dp = ImageDraw.Draw(part)
# molded ribs + hole
for k in range(-2, 3): dp.line([(cx+k*70, 470), (cx+k*70, 830)], fill=(25, 70, 140, 255), width=6)
dp.ellipse([cx-60, 360, cx+60, 410], fill=(15, 35, 70, 255))
part = part.filter(ImageFilter.SMOOTH)
out = bg.convert("RGBA"); out.alpha_composite(part)
out.convert("RGB").save("/workspace/tooling-job-log-v2/tests/fixtures/cleanup-sample.jpg", quality=90)
# ground-truth mask for accuracy scoring
part.split()[3].point(lambda a: 255 if a > 128 else 0).save("/workspace/tooling-job-log-v2/tests/fixtures/cleanup-sample-mask.png")
print("ok")
