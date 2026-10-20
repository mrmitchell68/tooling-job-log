import json, sys, time, os, subprocess
from playwright.sync_api import sync_playwright
BASE = "http://localhost:8766/"
SHOTS = "/workspace/tooling-job-log-v2/shots/"
errors = []; results = []
def ok(name, cond, extra=""):
    results.append((name, bool(cond), extra)); print(("PASS " if cond else "FAIL ") + name + (" — " + str(extra) if extra else ""), flush=True)

def clear_toast(pg):
    pg.evaluate("document.getElementById('toastRoot') && (document.getElementById('toastRoot').innerHTML='')")

with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
    ctx = b.new_context(viewport={"width":412,"height":915}, device_scale_factor=2, is_mobile=True, has_touch=True,
        user_agent="Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Mobile Safari/537.36", accept_downloads=True)
    page = ctx.new_page()
    page.on("console", lambda m: errors.append("console."+m.type+": "+m.text) if m.type=="error" else None)
    page.on("pageerror", lambda e: errors.append("pageerror: "+str(e)))
    page.goto(BASE); page.wait_for_selector(".jobcard")
    sw = page.evaluate("navigator.serviceWorker.ready.then(r=>!!r.active)")
    ok("service worker registers & activates", sw)
    page.reload(); page.wait_for_selector(".jobcard")
    ctrl = page.evaluate("!!navigator.serviceWorker.controller")
    ok("page controlled by SW after reload", ctrl)
    man = page.evaluate("fetch(document.querySelector('link[rel=manifest]').href).then(r=>r.json())")
    req = all(k in man for k in ["name","short_name","start_url","display","theme_color","icons"])
    ok("manifest valid", req and man["short_name"]=="Job Log" and man["start_url"]=="./" and man["display"]=="standalone", {k:man[k] for k in ["name","short_name","start_url","display","theme_color"]})
    sizes = page.evaluate("""Promise.all(%s.map(i=>new Promise(r=>{const im=new Image();im.onload=()=>r(i.sizes+'='+im.naturalWidth+'x'+im.naturalHeight);im.onerror=()=>r(i.src+' FAIL');im.src=i.src;})))""" % json.dumps(man["icons"]))
    ok("manifest icons load with right size", all(s.split("=")[0]==s.split("=")[1] for s in sizes), sizes)
    cached = page.evaluate("caches.keys().then(ks=>Promise.all(ks.map(k=>caches.open(k).then(c=>c.keys()).then(r=>k+':'+r.length))))")
    ok("SW caches shell + libs", len(cached)>=2, cached)
    time.sleep(1.2)
    clear_toast(page); page.screenshot(path=SHOTS+"01-job-list.png")
    # search
    page.fill("#searchInput", "polypropylene"); n0 = page.locator(".jobcard").count()
    page.fill("#searchInput", "PP homo"); n1 = page.locator(".jobcard").count()
    page.fill("#searchInput", "press 3"); n2 = page.locator(".jobcard").count()
    page.fill("#searchInput", "ABS"); n3 = page.locator(".jobcard").count()
    ok("search across fields (material/press)", n1==1 and n2==1 and n3==1, (n0,n1,n2,n3))
    page.click(".search .clr") if page.locator(".search .clr").count() else page.fill("#searchInput","")
    page.fill("#searchInput",""); page.dispatch_event("#searchInput","input")
    page.click("[data-act=fStatus][data-v=setup]"); ok("status filter chip", page.locator(".jobcard").count()==1)
    page.click("[data-act=fStatus][data-v=all]")
    page.click("[data-act=fPress][data-v='Press 3']"); ok("press filter chip", page.locator(".jobcard").count()==1 and "T-2210" in page.inner_text(".jobcard"))
    page.click("[data-act=fPress][data-v=all]")
    first = page.inner_text(".jobcard >> nth=0"); ok("pinned job first (reference-sheet example, most recent pinned)", "146-6000-00" in first and "EXAMPLE" in first.upper(), first[:60])
    ok("pinned T-1042 before unpinned", page.locator(".jobcard.pinned:has-text('T-1042')").count()==1)

    # detail
    page.click(".jobcard:has-text('T-1042')"); page.wait_for_selector("#h_tool"); time.sleep(0.6)
    clear_toast(page); page.screenshot(path=SHOTS+"02-job-detail.png")
    page.evaluate("window.scrollTo(0, 900)"); time.sleep(0.3); clear_toast(page); page.screenshot(path=SHOTS+"02b-job-detail-temps.png")
    page.evaluate("window.scrollTo(0, 0)")
    # change a value -> pending change
    inp = page.locator("[data-fval]").filter(has=page.locator("xpath=.")).nth(0)
    hp = page.locator(".frow:has(label:text-is('Hold pressure')) input")
    hp.click(); hp.fill("900"); page.locator(".frow:has(label:text-is('Hold time')) input").click()
    time.sleep(0.2)
    ok("pending change recorded on value edit", "Hold pressure 850 → 900" in page.inner_text("#pendingBox"), page.inner_text("#pendingBox")[:120])

    # setup mode
    page.click(".bottombar button:has-text('Setup')"); page.wait_for_selector(".sstep"); time.sleep(0.4)
    clear_toast(page); page.screenshot(path=SHOTS+"03-setup-mode.png")
    before = page.inner_text(".bigprog .n")
    page.click(".sstep.next"); after = page.inner_text(".bigprog .n")
    ok("checklist toggles + progress", before!=after, (before, after))
    page.click(".setupbar [data-act=resetChecklist]"); ok("reset checklist", page.inner_text(".bigprog .n").startswith("0 /"), page.inner_text(".bigprog .n"))
    page.click("[data-act=toastAct]"); ok("undo reset", not page.inner_text(".bigprog .n").startswith("0 /"))
    # log run from setup
    page.click(".setupbar [data-act=addLog]"); page.wait_for_selector("#lgChg")
    ok("run log prefilled with pending changes", "Hold pressure 850 → 900" in page.input_value("#lgChg"), page.input_value("#lgChg"))
    page.fill("#lgOp", "Allen H."); page.fill("#lgCycle", "12.3"); page.fill("#lgIss", "Short shot cav 6 at start-up")
    page.click("[data-act=logSave]"); page.wait_for_selector(".entry"); time.sleep(0.3)
    ok("run log entry saved", page.locator(".entry").count()==4)
    clear_toast(page); page.screenshot(path=SHOTS+"04-run-log.png")
    cyc = page.evaluate("(()=>{const j=__tjl.state.jobs.find(j=>j.toolNumber==='T-1042');let v;j.sections.forEach(s=>(s.fields||[]).forEach(f=>{if(f.key==='cycle')v=f.value}));return [v,j.pendingChanges.length]})()")
    ok("cycle time pushed to sheet & pending cleared", cyc==["12.3",0], cyc)

    # scan review via paste on T-2210
    page.goto(BASE+"#/"); page.wait_for_selector(".jobcard")
    page.click(".jobcard:has-text('T-2210')"); page.wait_for_selector("#h_tool")
    page.click(".bottombar [data-act=scanMenu]"); page.click("[data-act=scanHere][data-kind=paste]")
    page.fill("#pasteBox", "MOLD PROCESS SHEET\nTool # T-2210   Press: Press 3\nMaterial: ABS  Grade: Black UL94 HB\nDryer temp 185F  Dry time 3 hrs\nNozzle 475F\nBarrel zone 1: 470 F   Zone 2 460F\nZone 3 445°F  Zone 4: 425F\nA-side 145F  B side 135F\nInj Press 1650 psi\nHold 975psi   Hold time 5.5 sec\nBack press 110 psi\nScrew RPM 95\nCooling 13 s\nCycle 27.5 s\nCushion: 0.25 in\nEjector stroke: 1.5 in")
    page.click("[data-act=pasteGo]"); page.wait_for_selector(".rv"); time.sleep(0.3)
    items = page.evaluate("__tjl.state.modal.items.map(i=>i.label+'='+i.value+(i.unit?' '+i.unit:'')+' ('+Math.round(i.conf*100)+(i.selected?'':' off')+')')")
    print("   review items:", items)
    labels = " | ".join(items)
    for want in ["Hold pressure=975 psi","Hold time=5.5 s","Injection pressure=1650 psi","Zone 1=470 °F","Mold A side=145 °F","Back pressure=110 psi","Screw RPM=95 rpm","Cooling time=13 s","Dryer temp/time=185 °F / 3 hr","Cushion=0.25 in"]:
        ok("paste parse: "+want, want in labels)
    clear_toast(page); page.screenshot(path=SHOTS+"05-scan-review.png")
    page.click("[data-act=rvApply]"); time.sleep(0.3)
    v = page.evaluate("(()=>{const j=__tjl.state.jobs.find(j=>j.toolNumber==='T-2210');const o={};j.sections.forEach(s=>(s.fields||[]).forEach(f=>o[f.label]=f.value));return o})()")
    ok("review applied to sheet", v.get("Hold pressure")=="975" and v.get("Zone 3")=="445" and v.get("Cushion")=="0.25", {k:v.get(k) for k in ["Hold pressure","Zone 3","Cushion","Ejector stroke"]})

    # print sheet
    page.click(".bottombar button:has-text('Print')"); page.wait_for_selector("#printArea .rs-page"); time.sleep(0.8)
    clear_toast(page); page.screenshot(path=SHOTS+"06-print-sheet.png")
    page.emulate_media(media="print")
    page.pdf(path="/workspace/tjl2-test/print-T2210.pdf", format="Letter", print_background=True, prefer_css_page_size=True)
    page.emulate_media(media="screen")
    pages = subprocess.run(["pdfinfo","/workspace/tjl2-test/print-T2210.pdf"],capture_output=True,text=True).stdout
    np_ = [l for l in pages.splitlines() if l.startswith("Pages")]
    ok("print sheet fits one page (reference layout)", np_ and np_[0].split()[-1]=="1", np_)
    page.click("[data-act=setLayout][data-v=process]"); page.wait_for_selector("#printArea .ps"); time.sleep(0.4)
    page.emulate_media(media="print"); page.pdf(path="/workspace/tjl2-test/print-T2210-process.pdf", format="Letter", print_background=True, prefer_css_page_size=True); page.emulate_media(media="screen")
    npp = [l for l in subprocess.run(["pdfinfo","/workspace/tjl2-test/print-T2210-process.pdf"],capture_output=True,text=True).stdout.splitlines() if l.startswith("Pages")]
    ok("process sheet (old layout) still available & fits one page", npp and npp[0].split()[-1]=="1", npp)
    ok("process sheet has temps/pressures", "Hold pressure" in page.inner_text("#printArea") and "Zone 3" in page.inner_text("#printArea"))
    page.click("[data-act=setLayout][data-v=reference]"); page.wait_for_selector("#printArea .rs-page")
    # also T-1042 (more content, photos, log)
    page.goto(BASE+"#/"); page.wait_for_selector(".jobcard"); page.click(".jobcard:has-text('T-1042')"); page.click(".bottombar button:has-text('Print')"); page.wait_for_selector("#printArea img"); time.sleep(0.8)
    clear_toast(page); page.screenshot(path=SHOTS+"06b-print-sheet-T1042.png", full_page=True)
    page.emulate_media(media="print"); page.pdf(path="/workspace/tjl2-test/print-T1042.pdf", format="Letter", print_background=True, prefer_css_page_size=True); page.emulate_media(media="screen")
    np2 = [l for l in subprocess.run(["pdfinfo","/workspace/tjl2-test/print-T1042.pdf"],capture_output=True,text=True).stdout.splitlines() if l.startswith("Pages")]
    ok("T-1042 print sheet page count", np2 and np2[0].split()[-1]=="1", np2)

    # create blank job, template flows, duplicate
    page.goto(BASE+"#/"); page.wait_for_selector(".fab"); page.click(".fab"); page.click("[data-act=newBlank]"); page.wait_for_selector("#h_tool")
    page.fill("#h_tool", "T-5001"); page.fill("#h_part", "Test bracket"); page.fill("#h_press", "Press 9"); page.locator("#h_press").blur()
    page.locator(".frow:has(label:text-is('Material')) input").fill("Nylon 6/6"); page.locator(".frow:has(label:text-is('Material')) input").blur()
    time.sleep(0.4)
    ok("blank job created with default process sheet", page.locator("section.card").count()>=6 and page.locator("[data-fval]").count()>=22, page.locator("[data-fval]").count())
    page.click("[data-act=jobMenu]"); page.click(".menu [data-act=saveTemplate]"); page.fill("#tplName", "T-5001 bracket base"); page.click("[data-act=saveTemplateGo]")
    tcount = page.evaluate("__tjl.state.templates.length"); ok("save as template", tcount==2, tcount)
    page.goto(BASE+"#/"); page.click(".fab"); page.click(".menu [data-act=useTemplate]:has-text('T-5001 bracket base')"); page.wait_for_selector("#h_tool")
    ok("new job from template", page.input_value("#h_tool")=="T-5001" and page.input_value(".frow:has(label:text-is('Material')) input")=="Nylon 6/6" and page.input_value("#h_press")=="")
    page.click("[data-act=jobMenu]"); page.click(".menu [data-act=duplicate]"); time.sleep(0.5)
    ok("duplicate job", page.evaluate("__tjl.state.jobs.length")==6, page.evaluate("__tjl.state.jobs.length"))
    # edit section: add field w/ unit, delete field + undo
    page.click("section.card:has(h2:text-is('Pressures & speeds')) [data-act=fAdd]"); page.fill("#nfLabel","Cushion"); page.fill("#nfVal","0.2"); page.fill("#nfUnit","in"); page.click("[data-act=fAddGo]")
    ok("add custom field with unit", page.locator(".frow:has(label:text-is('Cushion')) .unit").inner_text()=="in")
    page.click("section.card:has(h2:text-is('Pressures & speeds')) [data-act=secEdit]"); page.click("section.card [data-act=fDelete] >> nth=0"); page.click("[data-act=toastAct]")
    ok("delete field + undo", page.locator("section.card:has(input[value='Pressures & speeds']) [data-flabel]").count()==7)

    # photo upload + label + viewer
    page.goto(BASE+"#/"); page.click(".jobcard:has-text('Test bracket') >> nth=0"); page.wait_for_selector("#h_tool")
    with page.expect_file_chooser() as fc: page.click("[data-act=photoLib]")
    fc.value.set_files("/workspace/tjl2-test/sheet.png"); page.wait_for_selector("[data-act=photoPreset]")
    page.click("[data-act=photoPreset][data-v='Setup sheet']"); time.sleep(0.4)
    ph = page.evaluate("(()=>{const j=__tjl.state.jobs.find(j=>j.id===__tjl.state.route.id);return j.photos.map(p=>[p.label,p.bytes,p.w,p.h])})()")
    ok("photo compressed + labeled", ph and ph[0][0]=="Setup sheet" and ph[0][1] < 400000 and max(ph[0][2],ph[0][3])<=1280, ph)
    page.click(".ph"); page.wait_for_selector("#viewer img"); time.sleep(0.4); ok("fullscreen viewer", page.locator("#viewer").count()==1)
    clear_toast(page); page.screenshot(path=SHOTS+"08-photo-viewer.png"); page.click("#viewer [data-act=closeModal]")

    # OCR: image
    page.click(".bottombar [data-act=scanMenu]")
    with page.expect_file_chooser() as fc: page.click("[data-act=scanHere][data-kind=img]")
    fc.value.set_files("/workspace/tjl2-test/sheet.png")
    try:
        page.wait_for_selector(".rv", timeout=120000)
        items = page.evaluate("__tjl.state.modal.items.map(i=>i.label+'='+i.value+(i.unit?' '+i.unit:'')+' ('+Math.round(i.conf*100)+')')")
        print("   OCR image items:", items); s=" | ".join(items)
        hits = sum(1 for w in ["Injection pressure=1800 psi","Hold pressure=1100 psi","Nozzle=560 °F","Zone 1=555 °F","Cooling time=12 s","Material=Polycarbonate","Cavities=4","Tool #=T-3307"] if w in s)
        ok("OCR image → fields (>=6 of 8 key values)", hits>=6, hits)
        clear_toast(page); page.screenshot(path=SHOTS+"05b-scan-review-ocr.png")
        page.click("[data-act=closeModal]")
    except Exception as e:
        ok("OCR image", False, str(e)[:200])
    # OCR: 2-page image PDF (new job)
    page.goto(BASE+"#/"); page.click(".fab")
    with page.expect_file_chooser() as fc: page.click("[data-act=scanNew][data-kind=pdf]")
    fc.value.set_files("/workspace/tjl2-test/scan2p.pdf")
    try:
        page.wait_for_selector(".rv", timeout=180000)
        items = page.evaluate("__tjl.state.modal.items.map(i=>i.label+'='+i.value+(i.unit?' '+i.unit:''))"); summ = page.inner_text(".sheet .sub")
        print("   PDF items:", items, summ); s=" | ".join(items)
        ok("PDF all pages OCR (page1 tool#, page2 hold press)", "T-4410" in s and "Hold pressure=700 psi" in s, summ)
        page.click("[data-act=rvApply]"); page.wait_for_selector("#h_tool"); ok("new job created from PDF scan", page.input_value("#h_tool")=="T-4410")
    except Exception as e:
        ok("PDF OCR", False, str(e)[:200])

    # Export full backup
    page.goto(BASE+"#/settings"); page.wait_for_selector("[data-act=backupDownload]")
    with page.expect_download() as dl: page.click("[data-act=backupDownload]")
    path = "/workspace/tjl2-test/backup.json"; dl.value.save_as(path)
    bk = json.load(open(path)); ok("export backup (jobs+photos+templates)", bk["app"]=="tooling-job-log" and len(bk["jobs"])>=6 and len(bk["photos"])>=4 and len(bk["templates"])==2, (len(bk["jobs"]), len(bk["photos"]), len(bk["templates"]), os.path.getsize(path)))
    ok("lastBackupAt recorded", page.evaluate("!!__tjl.state.meta.lastBackupAt"))
    clear_toast(page); page.screenshot(path=SHOTS+"07-backup-settings.png")
    # per-job export
    page.goto(BASE+"#/"); page.click(".jobcard:has-text('T-1042')"); page.click("[data-act=jobMenu]")
    with page.expect_download() as dl2: page.click(".menu [data-act=exportJob]")
    jp="/workspace/tjl2-test/job.json"; dl2.value.save_as(jp); jj=json.load(open(jp)); ok("per-job export", len(jj["jobs"])==1 and len(jj["photos"])==2)

    # Import into a fresh context (simulates a new phone)
    ctx2 = b.new_context(viewport={"width":412,"height":915}, device_scale_factor=2, is_mobile=True, has_touch=True)
    p2 = ctx2.new_page(); p2.on("pageerror", lambda e: errors.append("pageerror(ctx2): "+str(e)))
    p2.goto(BASE+"#/settings"); p2.wait_for_selector("[data-act=importPick]")
    with p2.expect_file_chooser() as fc: p2.click("[data-act=importPick]")
    fc.value.set_files(path); p2.wait_for_selector(".sheet h3:text('Import complete')")
    summary = p2.inner_text(".sheet"); print("   import:", summary.replace("\n"," / "))
    n = p2.evaluate("__tjl.state.jobs.length")
    ok("import/merge backup into fresh phone", n==len(bk["jobs"]), (n, len(bk["jobs"])))
    p2.click("[data-act=closeModal]"); p2.goto(BASE+"#/"); p2.wait_for_selector(".jobcard"); time.sleep(0.8)
    imgs = p2.evaluate("Array.from(document.querySelectorAll('.thumb img')).filter(i=>i.naturalWidth>0).length")
    ok("imported photos render", imgs>=2, imgs)
    # re-import same file -> all skipped
    p2.goto(BASE+"#/settings"); p2.wait_for_selector("[data-act=importPick]")
    with p2.expect_file_chooser() as fc: p2.click("[data-act=importPick]")
    fc.value.set_files(path); p2.wait_for_selector(".sheet h3:text('Import complete')")
    ok("re-import merges without duplicates", p2.evaluate("__tjl.state.jobs.length")==n)
    ctx2.close()

    # backup reminder: fake old lastBackupAt
    page.evaluate("__tjl.state.meta.lastBackupAt=new Date(Date.now()-20*864e5).toISOString(); localStorage.setItem('tjl2.meta', JSON.stringify(__tjl.state.meta))")
    page.goto(BASE+"#/templates"); page.goto(BASE+"#/"); page.wait_for_selector(".jobcard")
    ok("14-day backup reminder banner", "No backup in 20 days" in page.inner_text("#app"))
    # delete job + undo
    c0 = page.evaluate("__tjl.state.jobs.length")
    page.click(".jobcard:has-text('T-5001') >> nth=0"); page.click("[data-act=jobMenu]"); page.click(".menu [data-act=deleteJob]"); page.wait_for_selector(".jobcard")
    c1 = page.evaluate("__tjl.state.jobs.length"); page.click("[data-act=toastAct]"); c2 = page.evaluate("__tjl.state.jobs.length")
    ok("delete job + undo", c1==c0-1 and c2==c0, (c0,c1,c2))
    # dark mode screenshot of list
    page.evaluate("localStorage.setItem('tjl2.theme','\"dark\"')"); page.reload(); page.wait_for_selector(".jobcard"); time.sleep(0.8)
    clear_toast(page); page.screenshot(path=SHOTS+"09-job-list-dark.png")
    page.evaluate("localStorage.setItem('tjl2.theme','\"\"')")
    # offline: reload with network off
    ctx.set_offline(True); page.reload(); page.wait_for_selector(".jobcard", timeout=10000)
    ok("works offline after first load (SW)", page.locator(".jobcard").count()>=5)
    ctx.set_offline(False)
    b.close()

print("\n=== console/page errors ===")
for e in errors: print(e)
print("none" if not errors else "")
fails = [r for r in results if not r[1]]
print(f"\n{len(results)-len(fails)}/{len(results)} passed")
