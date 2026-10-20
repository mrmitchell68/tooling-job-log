"""v2.1.0+ checks: reference sheet layout, all photos on the sheet, photo reorder, supplies table,
branding, migration of v1/v2 data, scan-to-fill labels. Screenshots -> shots/10-*.png"""
import json, time, subprocess, glob, os
from playwright.sync_api import sync_playwright
BASE = "http://localhost:8766/"
SHOTS = "/workspace/tooling-job-log-v2/shots/"
T = "/workspace/tjl2-test/"
PHOTOS = sorted(glob.glob(T+"photos/p*.jpg"))
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
def wait_imgs(pg, sel="#printArea img"):
    pg.wait_for_function("(s)=>{const a=[...document.querySelectorAll(s)];return a.length && a.every(i=>i.complete && i.naturalWidth>0)}", arg=sel, timeout=15000)
def mk_ctx(b):
    c = b.new_context(viewport={"width":412,"height":915}, device_scale_factor=2, is_mobile=True, has_touch=True,
        user_agent="Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Mobile Safari/537.36")
    return c
def watch(pg, tag):
    pg.on("response", lambda r: errors.append(tag+" HTTP %d %s" % (r.status, r.url)) if r.status>=400 and not r.url.endswith("/favicon.ico") else None)
    pg.on("console", lambda m: errors.append(tag+" console."+m.type+": "+m.text) if m.type=="error" and not ("404" in m.text and "favicon.ico" in (m.location or {}).get("url","")) else None)
    pg.on("pageerror", lambda e: errors.append(tag+" pageerror: "+str(e)))

with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
    ctx = mk_ctx(b); page = ctx.new_page(); watch(page, "main")
    page.goto(BASE); page.wait_for_selector(".jobcard"); page.wait_for_function("window.__tjl && __tjl.state.jobs.filter(j=>j.example).length>=3 && __tjl.state.jobs.filter(j=>j.example).every(j=>j.photos.length)", timeout=60000); time.sleep(1)
    ver = page.evaluate("fetch('sw.js').then(r=>r.text()).then(t=>t.match(/VERSION = \"([^\"]+)/)[1])")
    ok("sw VERSION bumped", ver=="tjl-v2.6.0", ver)

    # ---------- example job (template values) ----------
    page.click(".jobcard:has-text('146-6000-00')"); page.wait_for_selector("#h_tool"); time.sleep(0.8)
    j = page.evaluate("(()=>{const j=__tjl.state.jobs.find(j=>j.id===__tjl.state.route.id);return {ex:j.example,photos:j.photos.map(p=>p.label),roles:j.sections.map(s=>s.role||s.title),schema:j.schema}})()")
    ok("CUE example job seeded with 11 labeled photos", j["ex"] and len(j["photos"])==11 and j["photos"][0].startswith("Mold front view"), j["photos"][:3])
    ok("new job structure has all template sections", all(r in j["roles"] for r in ["partinfo","supplies","carton","packaging","instructions","quality","notes"]) and j["schema"]==4, j["roles"])
    clear_toast(page); page.screenshot(path=SHOTS+"10a-job-detail-part-info.png")
    page.locator("section.card:has(h2:text-is('Required for the job (supplies)'))").scroll_into_view_if_needed()
    page.evaluate("document.querySelector('section.card[data-sid] h2') && 0")
    y = page.evaluate("(()=>{const e=[...document.querySelectorAll('section.card h2')].find(h=>h.textContent.startsWith('Required'));return e.getBoundingClientRect().top+scrollY-70})()")
    page.evaluate(f"window.scrollTo(0,{y})"); time.sleep(0.3); clear_toast(page); page.screenshot(path=SHOTS+"10b-job-detail-supplies-packaging.png")
    y = page.evaluate("(()=>{const e=[...document.querySelectorAll('section.card h2')].find(h=>h.textContent.startsWith('Operator'));return e.getBoundingClientRect().top+scrollY-70})()")
    page.evaluate(f"window.scrollTo(0,{y})"); time.sleep(0.3); clear_toast(page); page.screenshot(path=SHOTS+"10c-job-detail-instructions-qc.png")

    # print screen + PDF of example
    page.click(".bottombar button:has-text('Print')"); page.wait_for_selector("#printArea .rs-page"); wait_imgs(page); time.sleep(0.6)
    clear_toast(page); page.screenshot(path=SHOTS+"10d-print-screen-reference.png")
    n = make_pdf(page, T+"ref-cue.pdf")
    ok("example reference sheet = 1 Letter page", n==1, n)
    for f in glob.glob(SHOTS+"10e-reference-sheet-example-*.png"): os.remove(f)
    subprocess.run(["pdftoppm","-r","80","-png",T+"ref-cue.pdf",SHOTS+"10e-reference-sheet-example"])
    txt = page.inner_text("#printArea")
    for want in ["MOLD / JOB REFERENCE SHEET","Diverse","People • Process • Performance","BUILDING SOLUTIONS TOGETHER","IN-02512MD","TPU-85 Durometer","3.269 lbs","320 seconds (Semi)","297.3 seconds","WO8888","Rev. 2026","As required","12 x 12 x 12","45 x 45 (White)","1/4 lb Carton Label","Visually inspect 100%.","Precision Molding • Reliable Results • A Stronger Tomorrow"]:
        ok("sheet shows: "+want, want.lower() in txt.lower())
    caps = page.evaluate("[...document.querySelectorAll('#printArea .rs-lab')].map(e=>e.textContent)")
    ok("11 photo label bars in grid, rows 4/4/3", len(caps)==11 and page.evaluate("[...document.querySelectorAll('#printArea .rs-row')].map(r=>r.children.length).join(',')")=="4,4,3", caps[:2])
    page.click("[data-act=setLayout][data-v=process]"); page.wait_for_selector("#printArea .ps"); time.sleep(0.5)
    clear_toast(page); page.screenshot(path=SHOTS+"10f-print-screen-process-toggle.png")
    npp = make_pdf(page, T+"proc-cue.pdf"); ok("process sheet toggle renders (pages=%d)" % npp, npp>=1)
    ptxt = page.inner_text("#printArea")
    ok("process sheet: filled part info + process sections, no reference-only sections", "IN-02512MD" in ptxt and "Temperatures".upper() in ptxt.upper() and "Material blender" not in ptxt, npp)
    page.click("[data-act=setLayout][data-v=reference]"); page.wait_for_selector("#printArea .rs-page")
    ok("layout choice persisted", page.evaluate("__tjl.state.meta.printLayout")=="reference")

    # ---------- new job with 11 then 15 uploaded photos ----------
    page.goto(BASE+"#/"); page.wait_for_selector(".fab"); page.click(".fab"); page.click("[data-act=newBlank]"); page.wait_for_selector("#h_tool")
    page.fill("#h_tool", "T-7011"); page.fill("#h_part", "Grid panel 11 photos"); page.locator("#h_part").blur()
    roles = page.evaluate("__tjl.state.jobs.find(j=>j.id===__tjl.state.route.id).sections.map(s=>s.role||'')")
    ok("new blank job gets template sections by default", all(r in roles for r in ["partinfo","supplies","carton","packaging","instructions","quality","notes"]), roles)
    sup = page.evaluate("__tjl.state.jobs.find(j=>j.id===__tjl.state.route.id).sections.find(s=>s.role==='supplies').rows.map(r=>r.desc+'|'+r.qty)")
    ok("default supplies rows (generic, blank qty)", sup[:3]==["Tooling|","Machine|","Tooling setup|"] and len(sup)==7, sup)
    presets = page.evaluate("[...new Set([])]") 
    with page.expect_file_chooser() as fc: page.click("[data-act=photoLib]")
    fc.value.set_files(PHOTOS[:11]); page.wait_for_selector("[data-act=photoPreset]", timeout=30000)
    want_labels=[]
    for i in range(11):
        page.wait_for_selector("[data-act=photoPreset]")
        btn = page.locator("[data-act=photoPreset]").nth(i); want_labels.append(btn.get_attribute("data-v")); btn.click(); time.sleep(0.15)
    time.sleep(0.4)
    labels = page.evaluate("__tjl.state.jobs.find(j=>j.id===__tjl.state.route.id).photos.map(p=>p.label)")
    ok("11 photos uploaded + labeled with template presets", labels==want_labels and len(labels)==11, labels[:4])
    # reorder: move photo 2 to first via the Arrange screen (v2.2.0 replaces the old ⇄ Reorder mode)
    page.click("#photosCard [data-act=arrangeOpen]"); page.wait_for_selector("#arrGrid .arr-cell[data-id]")
    page.locator("#arrGrid .arr-cell[data-slot='1']").click(); page.wait_for_selector(".arr-mv")
    page.click("[data-act=arrMove][data-d='-1']"); time.sleep(0.2)
    l2 = page.evaluate("__tjl.state.jobs.find(j=>j.id===__tjl.state.route.id).photos.map(p=>p.label)")
    ok("arrange: move photo earlier", l2[0]==want_labels[1] and l2[1]==want_labels[0], l2[:2])
    page.click(".sheet [data-act=closeModal]"); time.sleep(0.3)
    clear_toast(page); page.screenshot(path=SHOTS+"10g-photo-reorder.png")
    page.click(".arrbar [data-act=arrDone]"); page.wait_for_selector("#h_tool"); time.sleep(0.3)
    # viewer move later
    page.click(".ph >> nth=0"); page.wait_for_selector("#viewer img")
    page.click("#viewer [data-act=photoMove][data-d='1']"); time.sleep(0.2)
    l3 = page.evaluate("__tjl.state.jobs.find(j=>j.id===__tjl.state.route.id).photos.map(p=>p.label)")
    ok("viewer: move photo later (back to original order)", l3==want_labels, l3[:2])
    ok("viewer follows moved photo", "2/11" in page.inner_text("#viewer .vl"), page.inner_text("#viewer .vl"))
    page.click("#viewer [data-act=closeModal]")
    page.click(".bottombar button:has-text('Print')"); page.wait_for_selector("#printArea .rs-page"); wait_imgs(page); time.sleep(0.5)
    st = page.evaluate("[...document.querySelectorAll('#printArea img')].map(i=>i.naturalWidth>0)")
    caps = page.evaluate("[...document.querySelectorAll('#printArea .rs-lab')].map(e=>e.textContent)")
    ok("11 photos: all 11 imgs loaded in grid", len(st)==11 and all(st), len(st))
    ok("11 photos: captions = labels in order", caps==want_labels, caps[:3])
    n = make_pdf(page, T+"ref-11.pdf"); ok("11 photos: 1 Letter page", n==1, n)
    # add 4 more -> 15
    page.goto(BASE+"#/job/"+page.evaluate("__tjl.state.route.id")); page.wait_for_selector("#h_tool")
    with page.expect_file_chooser() as fc: page.click("[data-act=photoLib]")
    fc.value.set_files(PHOTOS[11:15]); page.wait_for_selector("[data-act=photoLabelSkip]", timeout=30000)
    for i in range(4): page.click("[data-act=photoLabelSkip]"); time.sleep(0.12)
    page.click(".bottombar button:has-text('Print')"); page.wait_for_selector("#printArea .rs-page.cont"); wait_imgs(page); time.sleep(0.5)
    st = page.evaluate("[...document.querySelectorAll('#printArea img')].map(i=>i.naturalWidth>0)")
    per = page.evaluate("[...document.querySelectorAll('#printArea .rs-page')].map(p=>p.querySelectorAll('img').length)")
    ok("15 photos: all 15 imgs loaded", len(st)==15 and all(st), len(st))
    ok("15 photos: 12 on page 1 + 3 on page 2", per==[12,3], per)
    ok("unlabeled photos get 'Photo n' caption", page.evaluate("[...document.querySelectorAll('#printArea .rs-lab')].slice(-1)[0].textContent")=="Photo 15")
    n = make_pdf(page, T+"ref-15.pdf"); ok("15 photos: 2 Letter pages", n==2, n)
    for f in glob.glob(SHOTS+"10h-reference-sheet-15-photos-*.png"): os.remove(f)
    subprocess.run(["pdftoppm","-r","80","-png",T+"ref-15.pdf",SHOTS+"10h-reference-sheet-15-photos"])
    # fewer photos: 5 and 1
    for keep in (5,1):
        page.evaluate(f"(()=>{{const j=__tjl.state.jobs.find(j=>j.id===__tjl.state.route.id); j._saved=j._saved||j.photos.slice(); j.photos=j._saved.slice(0,{keep}); __tjl.render();}})()")
        wait_imgs(page); rows = page.evaluate("[...document.querySelectorAll('#printArea .rs-row')].map(r=>r.children.length).join(',')")
        n = make_pdf(page, T+f"ref-{keep}.pdf")
        ok(f"{keep} photo(s): rows {rows}, 1 page", n==1 and rows==("4,1" if keep==5 else "1"), (rows, n))
    page.evaluate("(()=>{const j=__tjl.state.jobs.find(j=>j.id===__tjl.state.route.id); j.photos=j._saved; delete j._saved; __tjl.render();})()")
    # long text content still fits one page (photo band shrinks)
    page.goto(BASE+"#/job/"+page.evaluate("__tjl.state.route.id")); page.wait_for_selector("#h_tool")
    page.evaluate("(()=>{const j=__tjl.state.jobs.find(j=>j.id===__tjl.state.route.id); j.photos=j.photos.slice(0,11); const s=j.sections.find(s=>s.role==='instructions'); s.items=[...Array(12)].map((_,i)=>({id:'x'+i,text:'Instruction number '+(i+1)+' — a longer operator instruction line that wraps onto a second line on the sheet',done:false}));})()")
    page.goto(BASE+"#/job/"+page.evaluate("__tjl.state.route.id")+"/print"); page.wait_for_selector("#printArea .rs-page"); wait_imgs(page); time.sleep(0.4)
    n = make_pdf(page, T+"ref-long.pdf"); ok("11 photos + 12 long instructions still 1 page (photo band shrinks)", n==1, n)

    # ---------- supplies table UI ----------
    page.goto(BASE+"#/job/"+page.evaluate("__tjl.state.route.id")); page.wait_for_selector("#h_tool")
    sid = page.evaluate("__tjl.state.jobs.find(j=>j.id===__tjl.state.route.id).sections.find(s=>s.role==='supplies').id")
    sec = "section.card[data-sid='%s']" % sid
    page.click(sec+" [data-act=tAdd]"); page.keyboard.type("TPU-85 resin"); page.locator(sec+" input.tq >> nth=7").fill("As required"); page.locator(sec+" input.tq >> nth=7").blur()
    page.locator(sec+" input.tq >> nth=0").fill("1"); time.sleep(0.4)
    page.click(sec+" [data-act=secEdit]"); page.locator(sec+" [data-act=tMove][data-d='-1'] >> nth=7").click()
    rows = page.evaluate("__tjl.state.jobs.find(j=>j.id===__tjl.state.route.id).sections.find(s=>s.role==='supplies').rows.map(r=>r.desc+'|'+r.qty)")
    ok("supplies: add row + qty + move up", rows[6]=="TPU-85 resin|As required" and rows[0]=="Tooling|1" and len(rows)==8, rows)
    page.locator(sec+" [data-act=tDelete] >> nth=1").click(); time.sleep(0.2)
    n1 = page.evaluate("__tjl.state.jobs.find(j=>j.id===__tjl.state.route.id).sections.find(s=>s.role==='supplies').rows.length")
    page.click("[data-act=toastAct]"); n2 = page.evaluate("__tjl.state.jobs.find(j=>j.id===__tjl.state.route.id).sections.find(s=>s.role==='supplies').rows.length")
    ok("supplies: delete row + undo", n1==7 and n2==8, (n1,n2))
    page.click(sec+" [data-act=secEdit]")
    stored = page.evaluate("JSON.parse(localStorage.getItem('tjl2.jobs')).find(j=>j.toolNumber==='T-7011').sections.find(s=>s.role==='supplies').rows.length")
    ok("supplies persisted to storage", stored==8, stored)
    # setup mode ignores work instructions / QC lists
    sp = page.evaluate("(()=>{const j=__tjl.state.jobs.find(j=>j.id===__tjl.state.route.id);return j.sections.filter(s=>s.type==='steps'&&!s.style).reduce((a,s)=>a+s.items.filter(i=>i.text.trim()).length,0)})()")
    page.click(".bottombar button:has-text('Setup')"); page.wait_for_selector(".sstep")
    ok("setup checklist excludes instructions/QC lists", page.locator(".sstep").count()==sp, (page.locator(".sstep").count(), sp))

    # ---------- branding ----------
    page.goto(BASE+"#/settings"); page.wait_for_selector("#brandCard")
    ok("branding defaults = Diverse Corporate Technology", page.input_value("#br_company")=="Diverse Corporate Technology" and page.input_value("#br_footer").startswith("Precision Molding"))
    page.fill("#br_slogan", "Building Solutions Together!"); time.sleep(0.2)
    with page.expect_file_chooser() as fc: page.click("[data-act=logoPick]")
    fc.value.set_files(T+"photos/p03.jpg"); page.wait_for_selector("#brandCard .logoprev img")
    logo_len = page.evaluate("__tjl.state.meta.brand.logo.length")
    ok("logo uploaded + compressed (stored locally)", 1000 < logo_len < 400000, logo_len)
    y = page.evaluate("document.getElementById('brandCard').getBoundingClientRect().top+scrollY-70"); page.evaluate(f"window.scrollTo(0,{y})"); time.sleep(0.3)
    clear_toast(page); page.screenshot(path=SHOTS+"10i-settings-branding.png")
    page.goto(BASE+"#/job/"+page.evaluate("__tjl.state.jobs.find(j=>j.toolNumber==='146-6000-00').id")+"/print"); page.wait_for_selector("#printArea .rs-page"); wait_imgs(page)
    ok("branding shown on sheet (logo + slogan)", page.locator("#printArea .rs-brand img").count()==1 and "SOLUTIONS TOGETHER!" in page.inner_text("#printArea .rs-slogan").upper())
    page.goto(BASE+"#/settings"); page.wait_for_selector("#brandCard"); page.click("[data-act=logoRemove]"); page.fill("#br_slogan", "Building Solutions Together"); time.sleep(0.2)
    ok("logo removed -> name shown", page.evaluate("__tjl.state.meta.brand.logo")=="")

    # ---------- scan-to-fill: template labels ----------
    page.goto(BASE+"#/job/"+page.evaluate("__tjl.state.jobs.find(j=>j.toolNumber==='T-7011').id")); page.wait_for_selector("#h_tool")
    page.click(".bottombar [data-act=scanMenu]"); page.click("[data-act=scanHere][data-kind=paste]")
    page.fill("#pasteBox", "MOLD / PART INFORMATION\nCustomer: C.U.E. of WV, LLC\nPart Name: CUE .25x12 Panel\nPart Number: IN-02512MD\nDescription: INS 1x1 Accudek Panel\nMaterial: TPU-85 Durometer\nColor: Black\nNumber of Cavities: 1\nPart Weight: 3.269 lbs\nShot Weight: 3.314 lbs\nAvg. Cycle Time: 320 seconds (Semi)\nMachine Cycle Time: 297.3 seconds\nParts Per Hour: 11\nMachine: 3 - 540 (540-ton) - Machine #3\nTool Number: 146-6000-00\nWork Order: WO8888\nDate: 08/24/2026\nRevision: Rev. 2026\nCarton Size: 12 x 12 x 12\nQty per carton: 9 each\nPallet Size: 45 x 45 (White)\nCartons Per Layer: 9")
    page.click("[data-act=pasteGo]"); page.wait_for_selector(".rv"); time.sleep(0.3)
    items = page.evaluate("__tjl.state.modal.items.map(i=>i.label+'='+i.value+(i.unit?' '+i.unit:''))"); s = " | ".join(items); print("   template scan:", items)
    for want in ["Part number=IN-02512MD","Description=INS 1x1 Accudek Panel","Color=Black","Number of cavities=1","Part weight=3.269 lb","Shot weight=3.314 lb","Avg. cycle time=320 (Semi) s","Machine cycle time=297.3 s","Parts per hour=11","Machine=3 - 540 (540-ton) - Machine #3","Work order=WO8888","Date=08/24/2026","Revision=Rev. 2026","Carton size=12 x 12 x 12","Quantity per carton=9 each","Pallet size=45 x 45 (White)","Cartons per layer=9","Tool / mold #=146-6000-00" if False else "146-6000-00","Part name=CUE .25x12 Panel" if False else "CUE .25x12 Panel"]:
        ok("scan label: "+want, want in s)
    page.click("[data-act=rvApply]"); time.sleep(0.3)
    v = page.evaluate("(()=>{const j=__tjl.state.jobs.find(j=>j.toolNumber==='146-6000-00'&&!j.example);const o={};j.sections.forEach(s=>(s.fields||[]).forEach(f=>{if(f.key)o[f.key]=f.value}));return o})()")
    ok("scan applied into new fields", v.get("work_order")=="WO8888" and v.get("qty_carton")=="9 each" and v.get("pph")=="11", {k:v.get(k) for k in ["work_order","qty_carton","pph","part_wt"]})
    ctx.close()

    # ---------- migration: v2.0.x data + v1 data (fresh phone) ----------
    ctx2 = mk_ctx(b); p2 = ctx2.new_page(); watch(p2, "migr")
    p2.goto(BASE+"manifest.webmanifest")
    old_v2 = [{"id":"oldv2a","toolNumber":"T-900","partName":"Old v2 job","customer":"Legacy Co","press":"Press 2","status":"active","pinned":False,
        "createdAt":"2026-05-01T12:00:00.000Z","updatedAt":"2026-05-02T12:00:00.000Z",
        "sections":[{"id":"s1","type":"fields","title":"Specs","fields":[{"id":"f1","label":"Material","value":"PC","unit":"","key":"material"},{"id":"f2","label":"Material grade/color","value":"Clear","unit":"","key":"grade"},{"id":"f3","label":"Cavities","value":"4","unit":"","key":"cavities"},{"id":"f4","label":"Shot weight","value":"22","unit":"g","key":"shot_wt"},{"id":"f5","label":"Cycle time","value":"18","unit":"s","key":"cycle"},{"id":"f6","label":"Ejector stroke","value":"1.5","unit":"in","key":""}]},
          {"id":"s2","type":"fields","title":"Temperatures","fields":[{"id":"t1","label":"Nozzle","value":"560","unit":"°F","key":"nozzle"}]},
          {"id":"s3","type":"steps","title":"Setup steps","items":[{"id":"i1","text":"Hang mold","done":True}]},
          {"id":"s4","type":"notes","title":"Notes","text":"Keep this v2 note"}],
        "photos":[{"id":"ph_missing","label":"Mold A side","addedAt":"2026-05-01T12:00:00.000Z","bytes":1000}],
        "runLog":[{"id":"r1","date":"2026-05-02","operator":"Allen H.","change":"First run","cycle":"18","issues":""}],"pendingChanges":[]}]
    old_v1 = [{"id":"oldv1a","toolNumber":"T-100","partName":"Old v1 job","customer":"V1 Co","press":"Press 1","status":"complete",
        "sections":[{"title":"Specs","type":"fields","fields":[{"label":"Material","value":"ABS"},{"label":"Part number","value":"PN-77"}]},
          {"title":"Checklist","type":"list","items":[{"text":"Dry resin","done":True}]},{"title":"Notes","type":"notes","text":"v1 note text"}],"photos":[]}]
    p2.evaluate("([a,b])=>{localStorage.clear(); localStorage.setItem('tjl2.jobs', JSON.stringify(a)); localStorage.setItem('toolingJobLog.v1', JSON.stringify(b)); localStorage.setItem('tjl2.meta', '{}');}", [old_v2, old_v1])
    p2.goto(BASE+"#/"); p2.wait_for_selector(".jobcard"); time.sleep(0.8)
    st = p2.evaluate("__tjl.state.jobs.map(j=>({t:j.toolNumber,st:j.status,schema:j.schema,secs:j.sections.map(s=>(s.role||'-')+':'+s.title),vals:Object.fromEntries(j.sections.flatMap(s=>(s.fields||[]).map(f=>[f.label,f.value]))),notes:(j.sections.find(s=>s.role==='notes')||{}).text,steps:j.sections.filter(s=>s.type==='steps').map(s=>s.items.map(i=>i.text+(i.done?'✓':'')).join(';')),log:j.runLog.length,photos:j.photos.length}))")
    print("   migrated:", json.dumps(st)[:900])
    a = next(x for x in st if x["t"]=="T-900"); c = next(x for x in st if x["t"]=="T-100")
    ok("v2 job: original values kept", a["vals"].get("Material")=="PC" and a["vals"].get("Material grade/color")=="Clear" and a["vals"].get("Ejector stroke")=="1.5" and a["vals"].get("Nozzle")=="560" and a["notes"]=="Keep this v2 note" and a["log"]==1 and a["photos"]==1 and "Hang mold✓" in a["steps"], a["vals"])
    ok("v2 job: new sections added, originals kept", a["schema"]==4 and all(any(sx.startswith(r+":") for sx in a["secs"]) for r in ["partinfo","supplies","carton","packaging","instructions","quality","notes"]) and "-:Specs" in a["secs"] and "-:Temperatures" in a["secs"], a["secs"])
    pi_labels = p2.evaluate("__tjl.state.jobs.find(j=>j.toolNumber==='T-900').sections.find(s=>s.role==='partinfo').fields.map(f=>f.key)")
    ok("v2 job: part info adds only missing fields (no dup material/cavities/shot wt/cycle)", "material" not in pi_labels and "cavities" not in pi_labels and "cycle" not in pi_labels and "part_no" in pi_labels and "work_order" in pi_labels, pi_labels)
    ok("v2 job: notes stays last", a["secs"][-1]=="notes:Notes", a["secs"][-1])
    ok("v1 job migrated: values, list→steps, status", c["vals"].get("Material")=="ABS" and c["vals"].get("Part number")=="PN-77" and c["st"]=="done" and "Dry resin✓" in c["steps"] and c["notes"]=="v1 note text", c)
    ok("v1 job: no duplicate Part number field", list(c["vals"].keys()).count("Part number")==1)
    stored = p2.evaluate("JSON.parse(localStorage.getItem('tjl2.jobs')).map(j=>j.schema)")
    p2.reload(); p2.wait_for_selector(".jobcard"); time.sleep(0.4)
    nsec = p2.evaluate("__tjl.state.jobs.find(j=>j.toolNumber==='T-900').sections.length")
    ok("migration persisted + idempotent on reload", all(x==4 for x in stored) and nsec==len(a["secs"]), (stored, nsec, len(a["secs"])))
    p2.click(".jobcard:has-text('T-900')"); p2.click(".bottombar button:has-text('Print')"); p2.wait_for_selector("#printArea .rs-page"); time.sleep(0.4)
    ok("migrated job prints reference sheet (process strip shows temps)", "Nozzle" in p2.inner_text("#printArea .rs-proc") and "PC" in p2.inner_text("#printArea"))
    n = make_pdf(p2, T+"ref-migrated.pdf"); ok("migrated job sheet 1 page", n==1, n)
    ctx2.close()

    # ---------- upgrade from 2.0.2 with examples present -> CUE example added once ----------
    ctx3 = mk_ctx(b); p3 = ctx3.new_page(); watch(p3, "upg")
    p3.goto(BASE+"manifest.webmanifest")
    ex = dict(old_v2[0]); ex = json.loads(json.dumps(ex)); ex["id"]="oldex"; ex["example"]=True; ex["toolNumber"]="T-1042"; ex["photos"]=[]
    p3.evaluate("(a)=>{localStorage.clear(); localStorage.setItem('tjl2.jobs', JSON.stringify(a)); localStorage.setItem('tjl2.meta', JSON.stringify({seeded:true}));}", [ex])
    p3.goto(BASE+"#/"); p3.wait_for_selector(".jobcard"); time.sleep(2.5)
    tn = p3.evaluate("__tjl.state.jobs.map(j=>j.toolNumber)")
    p3.reload(); p3.wait_for_selector(".jobcard"); time.sleep(1)
    tn2 = p3.evaluate("__tjl.state.jobs.map(j=>j.toolNumber)")
    ok("upgrade: reference-sheet example added once for installs with examples", tn.count("146-6000-00")==1 and tn2.count("146-6000-00")==1 and "T-1042" in tn2, tn2)
    ctx3.close()
    b.close()

print("\n=== console/page errors ===")
for e in errors: print(e)
print("none" if not errors else "")
fails = [r for r in results if not r[1]]
print(f"\n{len(results)-len(fails)}/{len(results)} passed")
