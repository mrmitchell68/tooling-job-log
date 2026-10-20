from PIL import Image, ImageDraw, ImageFont
import glob
fonts = glob.glob("/usr/share/fonts/**/DejaVuSans.ttf", recursive=True) + glob.glob("/usr/share/fonts/**/*.ttf", recursive=True)
f = ImageFont.truetype(fonts[0], 34); fb = ImageFont.truetype(fonts[0], 44)
lines = ["PROCESS SETUP SHEET", "Tool #: T-3307   Press: Press 5", "Customer: Delta Medical", "Part Name: Luer cap",
 "Material: Polycarbonate", "Dryer Temp: 250F   Dry Time: 4 hrs", "Cavities: 4", "Cycle Time: 18.5 sec",
 "Nozzle 560F", "Barrel Zone 1: 555F", "Zone 2: 545 F", "Zone 3: 530F", "Zone 4: 510F", "A Side 180F   B Side 175F",
 "Inj Press 1800 psi", "Hold 1100 psi", "Hold Time 6 sec", "Back Press 90 psi", "Screw RPM 80", "Cooling 12 s"]
im = Image.new("RGB", (1240, 1754), "white"); d = ImageDraw.Draw(im)
y = 80
for i, l in enumerate(lines):
    d.text((90, y), l, fill="black", font=fb if i == 0 else f); y += 72
im.save("sheet.png")
# page 2 as image PDF (2 pages: page1 minor, page2 has temps) -> tests all pages
p1 = Image.new("RGB", (1240, 1754), "white"); d1 = ImageDraw.Draw(p1)
for i, l in enumerate(["JOB TRAVELER", "Tool #: T-4410", "Part Name: Hinge clip", "Customer: Orbit Hardware"]):
    d1.text((90, 80 + i*72), l, fill="black", font=fb if i == 0 else f)
p2 = Image.new("RGB", (1240, 1754), "white"); d2 = ImageDraw.Draw(p2)
for i, l in enumerate(["PAGE 2 - PROCESS", "Material: Acetal (POM)", "Nozzle: 400F", "Hold Pressure: 700 psi", "Cooling Time: 9 s"]):
    d2.text((90, 80 + i*72), l, fill="black", font=fb if i == 0 else f)
p1.save("scan2p.pdf", save_all=True, append_images=[p2], resolution=150)
print("ok")
