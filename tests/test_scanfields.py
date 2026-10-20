"""v2.3.1 checks: scanned / uploaded job info reaches the printed sheet.
Label variants (paste, PDF text layer, OCR image, Allen's template PDF), review screen (unmatched lines + assign),
apply, job detail, both print layouts (Material & Process + Other specs blocks, page-2 overflow), migration of old-style jobs,
"Re-check notes" helper. Screenshots -> shots/13-*.png"""
import json, time, subprocess, glob, os
from playwright.sync_api import sync_playwright
BASE = "http://localhost:8766/"
SHOTS = "/workspace/tooling-job-log-v2/shots/"
FIX = "/workspace/tooling-job-log-v2/tests/fixtures/"
T = "/workspace/tjl2-test/"; os.makedirs(T, exist_ok=True)
ALLEN = glob.glob("/home/box/agent-data/agents/*/attachments/ddc49ee628d0a2bb017c5df2d8b5d27362785b72f2d635965bccb48458e5ffa0.pdf")
errors = []; results = []
def ok(name, cond, extra=""):
    results.append((name, bool(cond), extra)); print(("PASS " if cond else "FAIL ") + name + (" — " + str(extra) if extra else ""), flush=True)
def clear_toast(pg): pg.evaluate("document.getElementById('toastRoot') && (document.getElementById('toastRoot').innerHTML='')")
def pdf_pages(path):
    out = subprocess.run(["pdfinfo", path], capture_output=True, text=True).stdout
    return int([l for l in out.splitlines() if l.startswith("Pages")][0].split()[-1])
def make_pdf(pg, path):
    pg.emulate_media(media="print"); pg.pdf(path=path, format="Letter", print_background=True, prefer_css_page_size=True); pg.emulate_media(media="screen")
    return pdf_pages(path)
def watch(pg, tag):
    pg.on("response", lambda r: errors.append(tag+" HTTP %d %s" % (r.status, r.url)) if r.status>=400 and not r.url.endswith("/favicon.ico") else None)
    pg.on("console", lambda m: errors.append(tag+" console."+m.type+": "+m.text) if m.type=="error" and not ("404" in m.text and "favicon.ico" in (m.location or {}).get("url","")) else None)
    pg.on("pageerror", lambda e: errors.append(tag+" pageerror: "+str(e)))
def mk_ctx(b):
    return b.new_context(viewport={"width":412,"height":915}, device_scale_factor=2, is_mobile=True, has_touch=True,
        user_agent="Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Mobile Safari/537.36")
JOB = "__tjl.state.jobs.find(j=>j.id===__tjl.state.route.id)"
ITEMS = "__tjl.state.modal.items.map(i=>({l:i.label,v:i.value,u:i.unit,sel:i.selected,loose:!!i.loose,un:!!i.unmatched,t:i.target||'',src:i.src}))"
ROWS = "Object.fromEntries([...document.querySelectorAll('#printArea .rs-kv tr')].map(tr=>[tr.cells[0].textContent.replace(/:$/,''), tr.cells[1].textContent]))"

SAMPLES = {
 "colon": ("MOLD SETUP SHEET\nCustomer: Acme Plastics Inc.\nMold #: M-2231\nPart No: 88-1042-A\nPart Wt. (g): 12.4\nShot Wt: 52.8 g\nMaterial Type: Polypropylene\nGrade: Pro-fax 6523\nColour: Natural\nMasterbatch: Clariant Blue 5501\nLet-down ratio: 3%\nCycle Time: 18.5 sec\nCavities: 4\nPress: 7\nTonnage: 150 tons\nRegrind %: 15\nDryer Temp: 180 F\nDryer Time: 2 hrs\nNozzle Temp: 430 F\nMold Temp: 110 F\nInjection Pressure: 1250 psi\nHold Time: 4.5 s\nCooling Time: 12 s\nScrew dia: 40 mm\nWeight 12.9 grams",
   {"Tool #":"M-2231","Customer":"Acme Plastics Inc.","Part number":"88-1042-A","Part weight":"12.4 g","Shot weight":"52.8 g","Material":"Polypropylene","Material grade":"Pro-fax 6523",
    "Color":"Natural","Colorant / masterbatch":"Clariant Blue 5501","Let-down ratio":"3%","Avg. cycle time":"18.5 s","Number of cavities":"4","Press":"Press 7","Clamp tonnage":"150 ton",
    "Regrind":"15 %","Dryer temp/time":"180 °F / 2 hr","Nozzle":"430 °F","Mold temp":"110 °F","Injection pressure":"1250 psi","Hold time":"4.5 s","Cooling time":"12 s"}),
 "nocolon_noise": ("PROCESS CARD\nPiece weight 0.44 oz\nShot size 1.9 oz\nResin type ABS\nMaterial Color Black\nColorant Carbon black MB\nLDR 2%\nMold no 4471\nCavitation 8\nCycle 22 sec\nRegrind 10 %\nBarrel temps 440 / 430 / 420 / 410 F\nMold temperature 120F\nInj. press 1400 psi\nHold time 3 sec\nCool time 14 sec\nClamp tonnage 250 ton\nPart weiqht: 0.44 oz\nMateria1: ABS",
   {"Part weight":"0.44 oz","Shot weight":"1.9 oz","Material":"ABS","Color":"Black","Colorant / masterbatch":"Carbon black MB","Let-down ratio":"2%","Tool #":"4471","Number of cavities":"8",
    "Avg. cycle time":"22 s","Regrind":"10 %","Barrel temps":"440 / 430 / 420 / 410 F","Mold temp":"120 °F","Injection pressure":"1400 psi","Hold time":"3 s","Cooling time":"14 s","Clamp tonnage":"250 ton"}),
 "nextline": ("MOLD / PART INFORMATION\nCustomer:\nC.U.E. of WV, LLC\nPart Weight:\n3.269 lbs\nShot Weight:\n3.314 Ibs\nMaterial:\nTPU-85 Durometer\nColor:\nBlack\nNumber of Cavities:\n1",
   {"Customer":"C.U.E. of WV, LLC","Part weight":"3.269 lb","Shot weight":"3.314 lb","Material":"TPU-85 Durometer","Color":"Black","Number of cavities":"1"}),
 "header_table": ("Part Wt    Shot Wt    Resin    Colour\n12.4 g    52.8 g    HDPE    White\nCycle Time    Cavities    Press    Mold Temp\n18 s    2    Press 5    90 F",
   {"Part weight":"12.4 g","Shot weight":"52.8 g","Material":"HDPE","Color":"White","Avg. cycle time":"18 s","Number of cavities":"2","Press":"Press 5","Mold temp":"90 °F"}),
 "two_column": ("Part Weight: 1.2 lb          Cycle Time: 45 s\nMaterial: Nylon 6/6          Cavities: 2\nColor: Natural               Tonnage: 300 ton\nShot Weight: 2.6 lb          Regrind: 0%\nDryer: 175 F / 4 hr          Mold Temp: 180 F",
   {"Part weight":"1.2 lb","Avg. cycle time":"45 s","Material":"Nylon 6/6","Number of cavities":"2","Color":"Natural","Clamp tonnage":"300 ton","Shot weight":"2.6 lb","Regrind":"0 %","Dryer temp/time":"175 F / 4 hr","Mold temp":"180 °F"}),
 "resins_units": ("Resin: LDPE\nPart weight - 8.2 grams\nMaterial Grade: Dow 722\nColor: Red\nShot size 34 g\nCustomer - Northside Mfg\nPiece wt: 0.02 kg",
   {"Material":"LDPE","Part weight":"8.2 g","Material grade":"Dow 722","Color":"Red","Shot weight":"34 g","Customer":"Northside Mfg"}),
}
MAT_SAMPLES = [("Material: PP","PP"),("Resin: HDPE","HDPE"),("Material Type: Polycarbonate","Polycarbonate"),("Resin type - Nylon 6/6","Nylon 6/6"),("MATERIAL  PC","PC"),("Mat'l: ABS","ABS")]

def new_job(pg, tool):
    pg.goto(BASE+"#/"); pg.wait_for_selector(".fab"); pg.click(".fab"); pg.click("[data-act=newBlank]"); pg.wait_for_selector("#h_tool")
    pg.fill("#h_tool", tool); pg.locator("#h_tool").blur(); time.sleep(0.15)
def paste_scan(pg, text):
    pg.click(".bottombar [data-act=scanMenu]"); pg.click("[data-act=scanHere][data-kind=paste]"); pg.fill("#pasteBox", text); pg.click("[data-act=pasteGo]")
    pg.wait_for_selector(".sheet h3:has-text('Review')"); time.sleep(0.2)
    return pg.evaluate(ITEMS)
def file_scan(pg, path, timeout=240000):
    pg.click(".bottombar [data-act=scanMenu]")
    with pg.expect_file_chooser() as fc: pg.click("[data-act=scanHere][data-kind=files]")
    fc.value.set_files(path); pg.wait_for_selector(".sheet h3:has-text('Review')", timeout=timeout); time.sleep(0.2)
    return pg.evaluate(ITEMS)
def as_map(items): return {i["l"]:(i["v"]+(" "+i["u"] if i["u"] else "")) for i in items if not i["loose"]}
def open_print(pg, layout="reference"):
    pg.goto(BASE+"#/job/"+pg.evaluate("__tjl.state.route.id")+"/print"); pg.wait_for_selector("#printArea")
    if pg.evaluate("__tjl.state.meta.printLayout||'reference'")!=layout: pg.click(f"[data-act=setLayout][data-v={layout}]")
    pg.wait_for_selector("#printArea .rs-page" if layout=="reference" else "#printArea .ps"); time.sleep(0.4)

with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
    ctx = mk_ctx(b); page = ctx.new_page(); watch(page, "main")
    page.goto(BASE); page.wait_for_selector(".jobcard"); page.wait_for_function("window.__tjl && __tjl.state.jobs.filter(j=>j.example).length>=3 && __tjl.state.jobs.filter(j=>j.example).every(j=>j.photos.length)", timeout=60000); time.sleep(1)
    ver = page.evaluate("fetch('sw.js').then(r=>r.text()).then(t=>t.match(/VERSION = \"([^\"]+)/)[1])")
    ok("sw VERSION = tjl-v2.6.0", ver=="tjl-v2.6.0", ver)
    page.goto(BASE+"#/settings"); page.wait_for_selector("#brandCard"); ok("APP_VERSION 2.6.0 in settings", "v2.6.0" in page.inner_text("#app"))

    # ---------- 1. label variants (paste) ----------
    for name, (text, want) in SAMPLES.items():
        new_job(page, "SF-"+name)
        items = paste_scan(page, text); got = as_map(items)
        bad = {k:(v, got.get(k)) for k,v in want.items() if got.get(k)!=v}
        ok(f"variants [{name}]: {len(want)} fields parsed with value+unit", not bad, bad or len(want))
        unsel = [i["l"] for i in items if not i["loose"] and i["l"] in want and not i["sel"]]
        ok(f"variants [{name}]: all expected values pre-checked", not unsel, unsel)
        if name=="colon":
            clear_toast(page); page.screenshot(path=SHOTS+"13a-review-material-fields.png")
            loose = [i for i in items if i["loose"]]
            ok("review: unknown 'Screw dia: 40 mm' kept as Other spec (checked)", any(i["l"]=="Screw dia" and i["t"]=="other" and i["sel"] for i in loose), loose)
            ok("review: unmatched line 'Weight 12.9 grams' listed for assignment", any(i["un"] and "Weight 12.9" in i["src"] for i in loose), [i["src"] for i in loose])
            ok("review: 'Not matched' section visible", page.locator("#rvLoose").is_visible() and "Not matched" in page.inner_text("#rvLoose"))
            # assign the unmatched line to Shot weight via the dropdown
            idx = page.evaluate("__tjl.state.modal.items.findIndex(i=>i.unmatched && /Weight 12.9/.test(i.src))")
            page.select_option(f"[data-rvtarget='{idx}']", "shot_wt"); time.sleep(0.2)
            it = page.evaluate(f"__tjl.state.modal.items[{idx}]")
            ok("assign: unmatched line → Shot weight parses 12.9 g and is checked", it["key"]=="shot_wt" and it["value"]=="12.9" and it["unit"]=="g" and it["selected"], {k:it[k] for k in ["key","value","unit","selected"]})
            page.select_option(f"[data-rvtarget='{idx}']", ""); time.sleep(0.15)
            ok("assign: back to Ignore unchecks it", not page.evaluate(f"__tjl.state.modal.items[{idx}].selected"))
            page.locator("#rvLoose").scroll_into_view_if_needed(); time.sleep(0.2); clear_toast(page); page.screenshot(path=SHOTS+"13b-review-unmatched-assign.png")
            page.click("[data-act=rvApply]"); time.sleep(0.4)
            j = page.evaluate(f"(()=>{{const j={JOB};return {{sec:Object.fromEntries(j.sections.flatMap(s=>(s.fields||[]).filter(f=>f.value).map(f=>[f.key||f.label,(s.role||s.title)+'|'+f.value+(f.unit?' '+f.unit:'')]))),tool:j.toolNumber,press:j.press,cust:j.customer}}}})()")
            s = j["sec"]
            ok("apply: part weight / shot weight / material / color saved in Mold / part info", s.get("part_wt")=="partinfo|12.4 g" and s.get("shot_wt")=="partinfo|52.8 g" and s.get("material")=="partinfo|Polypropylene" and s.get("color")=="partinfo|Natural", {k:s.get(k) for k in ["part_wt","shot_wt","material","color"]})
            ok("apply: colorant / LDR / regrind / tonnage saved in Specs", s.get("colorant")=="Specs|Clariant Blue 5501" and s.get("ldr")=="Specs|3%" and s.get("regrind")=="Specs|15 %" and s.get("clamp")=="Specs|150 ton", {k:s.get(k) for k in ["colorant","ldr","regrind","clamp"]})
            ok("apply: mold temp in Temperatures, other spec kept with its label", s.get("mold_temp")=="Temperatures|110 °F" and s.get("Screw dia")=="Specs|40 mm", (s.get("mold_temp"), s.get("Screw dia")))
            ok("apply: header fields (tool / press / customer)", j["tool"]=="M-2231" and j["press"]=="Press 7" and j["cust"]=="Acme Plastics Inc.", j)
            # detail screen shows them
            page.wait_for_selector("#h_tool")
            vals = page.evaluate("Object.fromEntries([...document.querySelectorAll('.frow')].map(r=>[r.querySelector('.lab').textContent, r.querySelector('input').value+(r.querySelector('.unit')?' '+r.querySelector('.unit').textContent:'')]))")
            ok("detail screen: Part weight / Shot weight / Material / Color / Let-down ratio visible", vals.get("Part weight")=="12.4 g" and vals.get("Shot weight")=="52.8 g" and vals.get("Material")=="Polypropylene" and vals.get("Color")=="Natural" and vals.get("Let-down ratio")=="3%", {k:vals.get(k) for k in ["Part weight","Shot weight","Material","Color","Let-down ratio"]})
            clear_toast(page); page.screenshot(path=SHOTS+"13c-detail-part-info.png")
            # reference sheet
            open_print(page, "reference")
            rows = page.evaluate(ROWS); txt = page.inner_text("#printArea")
            ok("reference sheet: Mold/Part rows — Part Weight 12.4 g, Shot Weight 52.8 g, Material, Color", rows.get("Part Weight")=="12.4 g" and rows.get("Shot Weight")=="52.8 g" and rows.get("Material")=="Polypropylene" and rows.get("Color")=="Natural" and rows.get("Number of Cavities")=="4" and rows.get("Avg. Cycle Time")=="18.5 seconds", {k:rows.get(k) for k in ["Part Weight","Shot Weight","Material","Color","Number of Cavities","Avg. Cycle Time"]})
            mp = page.inner_text("#printArea .rs-proc[data-mv=proc]") if page.locator("#printArea .rs-page.first .rs-proc[data-mv=proc]").count() else ""
            want_mp = ["MATERIAL & PROCESS","Material grade: Pro-fax 6523","Colorant / masterbatch: Clariant Blue 5501","Let-down ratio: 3%","Regrind: 15 %","Clamp tonnage: 150 ton","Dryer temp/time: 180 °F / 2 hr","Nozzle: 430 °F","Mold temp: 110 °F","Injection pressure: 1250 psi","Hold time: 4.5 seconds","Cooling time: 12 seconds"]
            miss = [w for w in want_mp if w.lower() not in mp.lower()]
            ok("reference sheet: Material & Process block has grade/colorant/LDR/regrind/tonnage/dryer/temps/pressures/times", not miss, miss)
            ok("reference sheet: Other specs block prints 'Screw dia: 40 mm'", "Screw dia: 40 mm" in page.inner_text("#printArea .rs-other"))
            n = make_pdf(page, T+"sf-ref.pdf"); ok("reference sheet with scan data = 1 Letter page", n==1, n)
            for f in glob.glob(SHOTS+"13d-reference-sheet-scanned-*.png"): os.remove(f)
            subprocess.run(["pdftoppm","-r","110","-png",T+"sf-ref.pdf",SHOTS+"13d-reference-sheet-scanned"])
            pt = subprocess.run(["pdftotext","-layout",T+"sf-ref.pdf","-"], capture_output=True, text=True).stdout
            ok("printed PDF text contains Part Weight / Shot Weight / Material / Color values", all(x in pt for x in ["12.4 g","52.8 g","Polypropylene","Natural","Clariant Blue 5501","Let-down ratio"]), [x for x in ["12.4 g","52.8 g","Polypropylene","Natural","Clariant Blue 5501","Let-down ratio"] if x not in pt])
            page.evaluate("window.scrollTo(0,0)"); clear_toast(page); page.screenshot(path=SHOTS+"13e-print-screen-reference.png")
            open_print(page, "process"); pt2 = page.inner_text("#printArea")
            miss2 = [x for x in ["12.4","52.8","Polypropylene","Natural","Pro-fax 6523","Clariant Blue 5501","3%","150","110","Screw dia","40"] if x not in pt2]
            ok("process sheet: same values print (part info + specs + temps)", not miss2, miss2)
            n2 = make_pdf(page, T+"sf-proc.pdf"); ok("process sheet renders (%d page)" % n2, n2>=1)
            page.click("[data-act=setLayout][data-v=reference]"); page.wait_for_selector("#printArea .rs-page")
        else:
            page.click("[data-act=rvApply]"); time.sleep(0.3)
            open_print(page, "reference"); txt = page.inner_text("#printArea").lower()
            miss = []
            for k, v in want.items():
                num = v.split(" ")[0].lower()
                if num not in txt: miss.append(k+"="+v)
            ok(f"variants [{name}]: every applied value prints on the reference sheet", not miss, miss)

    # material words
    new_job(page, "SF-MAT")
    for line, want in MAT_SAMPLES:
        items = paste_scan(page, line); got = as_map(items).get("Material")
        ok(f"material label '{line}' → {want}", got==want, got); page.click("[data-act=closeModal]")
    # OCR-ish noise / unit variants
    new_job(page, "SF-UNITS")
    items = paste_scan(page, "Part Wt 3.269 Ibs\nShot wt 1.2 1bs\nPart weight (oz) 0.5\nShot Weight 45 grams\nCycle time (sec) 30\nNozzle (F) 450\nMold temp 60 C"); got = as_map(items)
    ok("units: Ibs/1bs → lb, unit in label '(oz)', '(sec)', '(F)', °C", got.get("Part weight") in ("3.269 lb","0.5 oz") and got.get("Shot weight") in ("1.2 lb","45 g") and got.get("Avg. cycle time")=="30 s" and got.get("Nozzle")=="450 °F" and got.get("Mold temp")=="60 °C", got)
    page.click("[data-act=closeModal]")
    items = paste_scan(page, "Part weight: 3.3 xyz"); got = as_map(items)
    ok("unknown unit kept visible instead of guessing grams", got.get("Part weight","").startswith("3.3 xyz"), got)
    page.click("[data-act=closeModal]")
    items = paste_scan(page, "Verify part weight and dimensions\nEnsure color is consistent (black).\nMOLD / PART INFORMATION"); got = as_map(items)
    ok("prose / headings don't fill fields (no color, tool #, part name)", not any(i["sel"] and not i["loose"] for i in items), got)
    page.click("[data-act=closeModal]")

    # ---------- 2. files: PDF text layer, OCR image, Allen's template ----------
    new_job(page, "SF-PDF")
    items = file_scan(page, FIX+"scan-mold-sheet.pdf"); got = as_map(items)
    want = {"Part weight":"12.4 g","Shot weight":"52.8 g","Material":"Polypropylene","Color":"Natural","Colorant / masterbatch":"Clariant Blue 5501","Let-down ratio":"3%","Regrind":"15 %","Clamp tonnage":"150 ton","Mold temp":"110 °F","Barrel temps":"420 / 410 / 400 °F","Number of cavities":"4","Avg. cycle time":"18.5 s","Injection pressure":"1250 psi","Hold time":"4.5 s","Cooling time":"12 s","Dryer temp/time":"180 °F / 2 hr","Tool #":"M-2231","Part number":"88-1042-A"}
    bad = {k:(v, got.get(k)) for k,v in want.items() if got.get(k)!=v}
    ok("PDF text layer (two-column table): %d fields" % len(want), not bad, bad)
    page.click("[data-act=rvApply]"); time.sleep(0.3); open_print(page); rows = page.evaluate(ROWS)
    ok("PDF → reference sheet rows", rows.get("Part Weight")=="12.4 g" and rows.get("Material")=="Polypropylene" and rows.get("Color")=="Natural", rows)
    new_job(page, "SF-OCR")
    items = file_scan(page, FIX+"scan-mold-sheet.png"); got = as_map(items)
    print("   OCR image items:", got)
    hit = [k for k,v in {"Nozzle":"430 °F","Injection pressure":"1250 psi","Mold temp":"110 °F","Clamp tonnage":"150 ton","Tool #":"M-2231"}.items() if got.get(k)==v]
    ok("OCR image of the sheet: key values read (>=4 of 5)", len(hit)>=4, hit)
    page.click("[data-act=closeModal]")
    if ALLEN:
        new_job(page, "SF-ALLEN")
        items = file_scan(page, ALLEN[0]); got = as_map(items)
        print("   Allen template OCR:", {k:got.get(k) for k in ["Part weight","Shot weight","Material","Color","Number of cavities","Tool #"]})
        ok("Allen's template (image PDF, OCR): Part weight 3.269 lb + Shot weight 3.314 lb (lbs read as lb, not g)", got.get("Part weight")=="3.269 lb" and got.get("Shot weight")=="3.314 lb", (got.get("Part weight"), got.get("Shot weight")))
        ok("Allen's template: Material TPU-85 Durometer, Color Black", got.get("Material")=="TPU-85 Durometer" and got.get("Color")=="Black", (got.get("Material"), got.get("Color")))
        sel = {i["l"] for i in items if i["sel"] and not i["loose"]}
        ok("Allen's template: those four are pre-checked", {"Part weight","Shot weight","Material","Color"} <= sel, sel)
        clear_toast(page); page.screenshot(path=SHOTS+"13f-review-allen-template-ocr.png")
        page.click("[data-act=rvApply]"); time.sleep(0.3); open_print(page); rows = page.evaluate(ROWS)
        ok("Allen's template → reference sheet: Part Weight 3.269 lbs, Shot Weight 3.314 lbs", rows.get("Part Weight")=="3.269 lbs" and rows.get("Shot Weight")=="3.314 lbs", (rows.get("Part Weight"), rows.get("Shot Weight")))
    else:
        ok("Allen's template PDF present", False, "attachment not found")

    # ---------- 3. custom sections / specs print; overflow to page 2 ----------
    new_job(page, "SF-CUSTOM")
    page.evaluate(f"""(()=>{{const j={JOB};
      const sp=j.sections.find(s=>s.title==='Specs'); sp.fields.push({{id:'cx1',label:'Ejector stroke',value:'1.5',unit:'in',key:''}});
      j.sections.splice(3,0,{{id:'cs1',type:'notes',title:'Hot runner notes',text:'Zone 3 thermocouple is flaky — check at start-up.'}});
      j.sections.splice(3,0,{{id:'cs2',type:'steps',title:'Mold change checklist',items:[{{id:'a',text:'Blow out water lines',done:false}},{{id:'b',text:'Grease leader pins',done:false}}]}});
      __tjl.render();}})()""")
    open_print(page); txt = page.inner_text("#printArea")
    ok("custom field prints under Other specs", "Ejector stroke: 1.5 in" in page.inner_text("#printArea .rs-other"))
    ok("custom notes + checklist sections print on the reference sheet", "Hot runner notes".upper() in txt.upper() and "Zone 3 thermocouple" in txt and "Grease leader pins" in txt)
    ok("stock setup-steps checklist not printed (Process sheet only)", "Hang mold, set clamp" not in txt)
    n = make_pdf(page, T+"sf-custom.pdf"); ok("custom sections fit 1 page", n==1, n)
    # lots of content → continues on page 2
    page.evaluate(f"""(()=>{{const j={JOB}; for(let k=0;k<16;k++) j.sections.splice(3,0,{{id:'big'+k,type:'notes',title:'Extra notes '+(k+1),text:('Long operator note line number '+k+' that wraps across the column. ').repeat(9)}}); __tjl.render();}})()""")
    page.goto(BASE+"#/job/"+page.evaluate("__tjl.state.route.id")+"/print"); page.wait_for_selector("#printArea .rs-page"); time.sleep(0.5)
    pages = page.evaluate("[...document.querySelectorAll('#printArea .rs-page')].map(p=>p.className)")
    ok("overflow: other specs / sections move to a continuation page", len(pages)==2 and "more" in pages[1], pages)
    ok("overflow: footer says Page 1 of 2 / 2 of 2", "Page 1 of 2" in page.inner_text("#printArea .rs-page.first .rs-ft") and "Page 2 of 2" in page.inner_text("#printArea .rs-page.more .rs-ft"))
    ok("overflow: page count hint updated", "2 pages" in page.inner_text("#rsPageCount"))
    n = make_pdf(page, T+"sf-overflow.pdf"); ok("overflow sheet = 2 Letter pages", n==2, n)
    pt = subprocess.run(["pdftotext","-f","2","-l","2",T+"sf-overflow.pdf","-"], capture_output=True, text=True).stdout
    ok("page 2 has Other specs + extra sections", "Ejector stroke" in pt and "Extra notes 16" in pt.replace("EXTRA NOTES","Extra notes"), pt[:200])
    for f in glob.glob(SHOTS+"13g-reference-overflow-*.png"): os.remove(f)
    subprocess.run(["pdftoppm","-r","70","-png",T+"sf-overflow.pdf",SHOTS+"13g-reference-overflow"])
    # re-fit is idempotent (resize)
    page.set_viewport_size({"width":400,"height":900}); time.sleep(0.5)
    ok("re-fit keeps 2 pages (no duplicate page)", page.locator("#printArea .rs-page").count()==2)

    # ---------- 4. Re-check notes helper ----------
    new_job(page, "SF-NOTES")
    page.evaluate(f"""(()=>{{const j={JOB}; j.sections.find(s=>s.role==='notes').text='— Scanned 2026-09-20 —\\nPart Weight: 5.5 g\\nMaterial Type: PETG\\nColour: Clear'; __tjl.render();}})()""")
    page.click("[data-act=jobMenu]"); page.click("[data-act=rescanNotes]"); page.wait_for_selector(".sheet h3:has-text('Review')")
    got = as_map(page.evaluate(ITEMS))
    ok("Re-check notes: finds part weight / material / color in saved scan text", got.get("Part weight")=="5.5 g" and got.get("Material")=="PETG" and got.get("Color")=="Clear", got)
    page.click("[data-act=rvApply]"); time.sleep(0.3); open_print(page); rows = page.evaluate(ROWS)
    ok("Re-check notes → prints", rows.get("Part Weight")=="5.5 g" and rows.get("Material")=="PETG", rows)
    ctx.close()

    # ---------- 5. migration of old-style jobs (no re-scan) ----------
    ctx2 = mk_ctx(b); p2 = ctx2.new_page(); watch(p2, "migr")
    p2.goto(BASE+"manifest.webmanifest")
    v20 = {"id":"oldAllen","toolNumber":"146-6000-00","partName":"CUE panel (old)","customer":"C.U.E.","press":"Press 3","status":"active","pinned":False,
        "createdAt":"2026-09-10T12:00:00.000Z","updatedAt":"2026-09-11T12:00:00.000Z",
        "sections":[{"id":"s1","type":"fields","title":"Specs","fields":[
            {"id":"f1","label":"Material","value":"","unit":"","key":"material"},
            {"id":"f2","label":"Material grade/color","value":"Black","unit":"","key":"grade"},
            {"id":"f3","label":"Cavities","value":"1","unit":"","key":"cavities"},
            {"id":"f4","label":"Shot weight","value":"3.314","unit":"lb","key":"shot_wt"},
            {"id":"f5","label":"Part Wt.","value":"3.269","unit":"lb","key":""},
            {"id":"f6","label":"Resin type","value":"TPU-85 Durometer","unit":"","key":""},
            {"id":"f7","label":"Let-down ratio","value":"3%","unit":"","key":""},
            {"id":"f8","label":"Screw dia","value":"40","unit":"mm","key":""}]},
          {"id":"s2","type":"fields","title":"Temperatures","fields":[{"id":"t1","label":"Nozzle","value":"420","unit":"°F","key":"nozzle"},{"id":"t2","label":"Mold Temp","value":"90","unit":"°F","key":""}]},
          {"id":"s3","type":"steps","title":"Setup steps","items":[{"id":"i1","text":"Hang mold","done":True}]},
          {"id":"s4","type":"notes","title":"Notes","text":"old note"}],
        "photos":[],"runLog":[],"pendingChanges":[]}
    v21 = {"id":"old21","toolNumber":"T-555","partName":"v2.1 job","customer":"X","press":"P1","status":"active","schema":3,
        "createdAt":"2026-09-20T12:00:00.000Z","updatedAt":"2026-09-21T12:00:00.000Z",
        "sections":[{"id":"pi","type":"fields","role":"partinfo","title":"Mold / part information","fields":[
            {"id":"a1","label":"Part number","value":"PN-1","unit":"","key":"part_no"},{"id":"a2","label":"Material","value":"","unit":"","key":"material"},
            {"id":"a3","label":"Color","value":"","unit":"","key":"color"},{"id":"a4","label":"Part weight","value":"","unit":"g","key":"part_wt"},{"id":"a5","label":"Shot weight","value":"","unit":"g","key":"shot_wt"}]},
          {"id":"sp","type":"fields","title":"Specs","fields":[{"id":"b1","label":"Material grade","value":"","unit":"","key":"grade"},
            {"id":"b2","label":"Colour","value":"Blue","unit":"","key":""},{"id":"b3","label":"Part Wt. (g)","value":"12.4","unit":"g","key":""},
            {"id":"b4","label":"Shot size","value":"50","unit":"g","key":""},{"id":"b5","label":"Resin","value":"ABS","unit":"","key":""},{"id":"b6","label":"Regrind %","value":"15","unit":"%","key":""},
            {"id":"b7","label":"Material","value":"ABS (dup)","unit":"","key":""}]},
          {"id":"nt","type":"notes","role":"notes","title":"Notes","text":""}],
        "photos":[],"runLog":[],"pendingChanges":[]}
    p2.evaluate("(a)=>{localStorage.clear(); localStorage.setItem('tjl2.jobs', JSON.stringify(a)); localStorage.setItem('tjl2.meta', JSON.stringify({seeded:true,cueSeeded:true}));}", [v20, v21])
    p2.goto(BASE+"#/"); p2.wait_for_selector(".jobcard"); time.sleep(0.6)
    def allvals(tool):
        return p2.evaluate(f"__tjl.state.jobs.find(j=>j.toolNumber==='{tool}').sections.flatMap(s=>(s.fields||[]).filter(f=>String(f.value).trim()).map(f=>f.value+(f.unit?' '+f.unit:'')))")
    before20 = [f["value"]+(" "+f["unit"] if f["unit"] else "") for s in v20["sections"] for f in s.get("fields",[]) if f["value"]]
    before21 = [f["value"]+(" "+f["unit"] if f["unit"] else "") for s in v21["sections"] for f in s.get("fields",[]) if f["value"]]
    a20 = allvals("146-6000-00"); a21 = allvals("T-555")
    ok("migration: no value lost (v2.0 job)", all(v in a20 for v in before20), [v for v in before20 if v not in a20])
    ok("migration: no value lost (v2.1 job)", all(v in a21 for v in before21 if v!="ABS" or True), [v for v in before21 if v not in a21])
    info = p2.evaluate("""(()=>{const j=__tjl.state.jobs.find(j=>j.toolNumber==='T-555'); const pi=j.sections.find(s=>s.role==='partinfo'); return {schema:j.schema, pi:Object.fromEntries(pi.fields.map(f=>[f.key||f.label, f.value+(f.unit?' '+f.unit:'')])), specs:j.sections.find(s=>s.title==='Specs').fields.map(f=>(f.key||'-')+':'+f.label+'='+f.value), notes:j.migrationNotes}})()""")
    print("   v2.1 migrated:", json.dumps(info)[:700])
    ok("migration v2.1: Colour/Part Wt./Resin moved into empty part-info fields", info["pi"].get("color")=="Blue" and info["pi"].get("part_wt")=="12.4 g" and info["pi"].get("material")=="ABS" and info["schema"]==4, info["pi"])
    ok("migration v2.1: Regrind % / Shot size get keys; duplicate 'Material' kept as custom", any(x.startswith("regrind:") for x in info["specs"]) and any(x.startswith("shot_size:") for x in info["specs"]) and "-:Material=ABS (dup)" in info["specs"], info["specs"])
    p2.click(".jobcard:has-text('T-555')"); p2.click(".bottombar button:has-text('Print')"); p2.wait_for_selector("#printArea .rs-page"); time.sleep(0.4)
    rows = p2.evaluate(ROWS); txt = p2.inner_text("#printArea")
    ok("v2.1 job prints Part Weight / Material / Color rows without re-scan", rows.get("Part Weight")=="12.4 g" and rows.get("Material")=="ABS" and rows.get("Color")=="Blue", rows)
    ok("v2.1 job: Regrind + Shot size in Material & Process, duplicate Material under Other specs", "Regrind: 15 %" in txt and "Shot size: 50 g" in txt and "Material: ABS (dup)" in p2.inner_text("#printArea .rs-other"))
    p2.goto(BASE+"#/"); p2.wait_for_selector(".jobcard"); p2.click(".jobcard:has-text('146-6000-00')"); p2.wait_for_selector("#h_tool")
    clear_toast(p2); p2.screenshot(path=SHOTS+"13h-migrated-old-job-detail.png")
    p2.click(".bottombar button:has-text('Print')"); p2.wait_for_selector("#printArea .rs-page"); time.sleep(0.4)
    rows = p2.evaluate(ROWS); txt = p2.inner_text("#printArea")
    print("   v2.0 rows:", {k:rows.get(k) for k in ["Material","Color","Part Weight","Shot Weight","Number of Cavities"]})
    ok("v2.0 job prints Part Weight 3.269 lbs, Shot Weight 3.314 lbs, Material TPU-85, Color Black (from 'Material grade/color')", rows.get("Part Weight")=="3.269 lbs" and rows.get("Shot Weight")=="3.314 lbs" and rows.get("Material")=="TPU-85 Durometer" and rows.get("Color")=="Black" and rows.get("Number of Cavities")=="1", rows)
    ok("v2.0 job: Let-down ratio + Mold Temp in Material & Process, Screw dia in Other specs", "Let-down ratio: 3%" in txt and "Mold Temp: 90 °F" in txt and "Screw dia: 40 mm" in p2.inner_text("#printArea .rs-other"), txt[-600:])
    n = make_pdf(p2, T+"sf-migrated.pdf"); ok("migrated old job sheet = 1 page", n==1, n)
    for f in glob.glob(SHOTS+"13i-migrated-old-job-sheet-*.png"): os.remove(f)
    subprocess.run(["pdftoppm","-r","110","-png",T+"sf-migrated.pdf",SHOTS+"13i-migrated-old-job-sheet"])
    stored = p2.evaluate("JSON.parse(localStorage.getItem('tjl2.jobs')).map(j=>[j.schema, j.sections.reduce((a,s)=>a+(s.fields||[]).length,0)])")
    p2.goto(BASE+"#/"); p2.reload(); p2.wait_for_selector(".jobcard"); time.sleep(0.4)
    again = p2.evaluate("__tjl.state.jobs.map(j=>[j.schema, j.sections.reduce((a,s)=>a+(s.fields||[]).length,0)])")
    ok("migration persisted (schema 4) + idempotent on reload", all(x[0]==4 for x in stored) and stored==again, (stored, again))
    ctx2.close()
    b.close()

print("\n=== console/page errors ===")
for e in errors: print(e)
print("none" if not errors else "")
fails = [r for r in results if not r[1]]
print(f"\n{len(results)-len(fails)}/{len(results)} passed")
