"""Makes tests/fixtures/scan-mold-sheet.pdf (text layer) + .png (for OCR): a two-column mold setup sheet with common label variants."""
# Generates a realistic mold setup sheet as HTML -> text-layer PDF + PNG image (for OCR)
from playwright.sync_api import sync_playwright
rows1 = [("Customer","Acme Plastics Inc."),("Mold Number","M-2231"),("Part Number","88-1042-A"),("Part Wt. (g)","12.4"),("Shot Weight","52.8 g"),
         ("Resin Type","Polypropylene"),("Material Color","Natural"),("Colorant","Clariant Blue 5501"),("Let-down Ratio","3%"),("Cavities","4")]
rows2 = [("Press / Tonnage","Press 7 / 150 ton"),("Cycle Time","18.5 sec"),("Regrind %","15"),("Dryer Temp","180 °F"),("Dryer Time","2 hrs"),
         ("Nozzle Temp","430 °F"),("Barrel Temps","420 / 410 / 400 °F"),("Mold Temp","110 °F"),("Injection Pressure","1250 psi"),("Hold Time","4.5 sec"),("Cooling Time","12 sec")]
def tbl(rows): return "<table>"+"".join(f"<tr><td class=k>{k}:</td><td>{v}</td></tr>" for k,v in rows)+"</table>"
html = f"""<html><head><style>body{{font-family:Arial;margin:40px;color:#111}} h1{{background:#0d3f7a;color:#fff;padding:8px 12px;font-size:22px}}
.cols{{display:flex;gap:40px}} table{{border-collapse:collapse;font-size:15px}} td{{border:1px solid #333;padding:5px 10px}} td.k{{font-weight:bold;background:#e8eef6}}</style></head>
<body><h1>MOLD SETUP SHEET — Cap, 38mm</h1><div class=cols>{tbl(rows1)}{tbl(rows2)}</div><p>Notes: Check gate vestige every 2 hours.</p></body></html>"""
open("/tmp/scan-mold-sheet.html","w").write(html)
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
    pg = b.new_page(viewport={"width":1100,"height":700}, device_scale_factor=2)
    pg.goto("file:///tmp/scan-mold-sheet.html")
    pg.pdf(path="/workspace/tooling-job-log-v2/tests/fixtures/scan-mold-sheet.pdf", format="Letter", landscape=True, print_background=True)
    pg.screenshot(path="/workspace/tooling-job-log-v2/tests/fixtures/scan-mold-sheet.png", full_page=True)
    b.close()
print("done")
