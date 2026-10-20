"""v2.3.2: Allen's real job forms (phone photos) fill the job through the actual scan flow.
Operator Work Instructions, Diverse BOM, NetSuite item record — gallery + Drive/Files pickers, one at a time and all 3 together.
Checks OCR prep, review (incl. conflicts), apply, job detail, reference sheet; version row + Check for update; SW update flow.
Screenshots -> shots/14-*.png"""
import json, time, os, re, shutil, subprocess, socket
from playwright.sync_api import sync_playwright
BASE = "http://localhost:8766/"
APP = "/workspace/tooling-job-log-v2/"
SHOTS = APP + "shots/"
FIX = APP + "tests/fixtures/"
WI, BOM, NS = FIX+"real-work-instructions.jpg", FIX+"real-bom.jpg", FIX+"real-netsuite-item.jpg"
errors = []; results = []
def ok(name, cond, extra=""):
    results.append((name, bool(cond), extra)); print(("PASS " if cond else "FAIL ") + name + (" — " + str(extra) if extra else ""), flush=True)
def watch(pg, tag):
    pg.on("console", lambda m: errors.append(tag+" console."+m.type+": "+m.text) if m.type=="error" and "favicon" not in m.text else None)
    pg.on("pageerror", lambda e: errors.append(tag+" pageerror: "+str(e)))
def mk_ctx(b):
    return b.new_context(viewport={"width":412,"height":915}, device_scale_factor=2, is_mobile=True, has_touch=True,
        user_agent="Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Mobile Safari/537.36")
ITEMS = "__tjl.state.modal.items.map(i=>({l:i.label,k:i.key||'',kind:i.kind||'',v:String(i.value),u:i.unit||'',q:i.qty||'',role:i.role||'',sel:!!i.selected,loose:!!i.loose,comp:i.comp||'',opts:(i.options||[]).map(o=>o.value),doc:i.doc||''}))"
def clear_toast(pg): pg.evaluate("document.getElementById('toastRoot') && (document.getElementById('toastRoot').innerHTML='')")
def scan(pg, kind, files, new=True):
    if new:
        pg.goto(BASE+"#/"); pg.wait_for_selector(".fab"); pg.click(".fab")
        with pg.expect_file_chooser() as fc: pg.click(f"[data-act=scanNew][data-kind={kind}]")
    else:
        pg.click(".bottombar [data-act=scanMenu]")
        with pg.expect_file_chooser() as fc: pg.click(f"[data-act=scanHere][data-kind={kind}]")
    fc.value.set_files(files); t=time.time()
    pg.wait_for_selector(".sheet h3:has-text('Review')", timeout=300000); time.sleep(0.3)
    return pg.evaluate(ITEMS), time.time()-t
def tall_shot(pg, path):
    """review sheet is a scrolling modal: grow the viewport to its content height for one tall screenshot"""
    clear_toast(pg)
    h = pg.evaluate("(()=>{const s=document.querySelector('#modalRoot .sheet'); return s? s.scrollHeight+140 : document.documentElement.scrollHeight})()")
    pg.set_viewport_size({"width":412, "height":min(int(h), 16000)}); time.sleep(0.4)
    if pg.query_selector("#modalRoot .sheet"): pg.locator("#modalRoot .sheet").screenshot(path=path)
    else: pg.screenshot(path=path)
    pg.set_viewport_size({"width":412, "height":915})
def fields(items): return {i["k"] or i["l"]: (i["v"]+(" "+i["u"] if i["u"] else "")) for i in items if not i["loose"] and not i["kind"]}
def has(items, kind, sub, role=None):
    return any(i["kind"]==kind and sub.lower() in i["v"].lower() and (role is None or i["role"]==role) for i in items)
def comp(items, compname, label):
    return next((i["v"] for i in items if i["comp"] and compname.lower() in i["comp"].lower() and i["l"].lower().endswith(label.lower())), None)

def check_wi(items, tag, merged=False):
    f = fields(items)
    exp = {"customer":"Group Dekko Inc", "part_no":"FP 124", "partName":"Box w/4 sq Holes", "cycle":"67", "material":"PVC Rigid", "pph":"53", "color":"Black",
           "part_wt":"0.288", "shot_wt":"0.299", "cavities":"1", "mach_cycle":"61.2", "toolNumber":"134-4004-02", "machine":"2", "revision":"2026", "pallet_size":"45x45"}
    if merged: exp.pop("mach_cycle"); exp.pop("toolNumber")  # conflicts, checked separately
    for k, v in exp.items(): ok(f"{tag}: {k} ≈ {v}", k in f and v.lower() in f[k].lower(), f.get(k))
    ok(f"{tag}: avg cycle keeps (Semi) + sec", "(Semi)" in f.get("cycle","") and f.get("cycle","").endswith(" s"), f.get("cycle"))
    ok(f"{tag}: part weight has no invented unit", f.get("part_wt")=="0.288", f.get("part_wt"))
    if not merged: ok(f"{tag}: description filled from Part Description", "Box w/4 sq Holes" in f.get("description",""), f.get("description"))
    for c, lab, v in [("Small Box Back","Carton size","12x12x12"),("Small Box Back","Parts per layer","12"),("Small Box Back","Quantity per carton","75"),("Small Box Back","Layers per carton","6 (+ 3 Parts on Top)"),
                      ("Front Plate","Carton size","12x12x9"),("Front Plate","Quantity per carton","150"),("Front Plate","Parts on 1st layer","80 (8 Sets of 10)"),("Front Plate","Parts on 2nd layer","70 (7 Sets of 10)")]:
        got = comp(items, c, lab); ok(f"{tag}: carton {c} / {lab} = {v}", got is not None and v.replace(" ","") in got.replace(" ",""), got)
    ok(f"{tag}: QC 'No shorts, splay, discoloration or burns — Visual / 100%'", has(items,"step","No shorts, splay, discoloration or burns — Visual / 100%","quality"))
    ok(f"{tag}: QC inspection sheet — Manual / every hr.", has(items,"step","inspection sheet","quality") and has(items,"step","every hr","quality"))
    for sub in ["Clip parts from runner","Drill the flash out of the 2 screw holes","Keep 10 parts cooling on table","Place 10 parts in box at a time","Put label with Date & Initial","save 1 part to be kept as sample part"]:
        ok(f"{tag}: work instruction '{sub}' (+ Manual / 100%)", has(items,"step",sub,"instructions") and has(items,"step",sub+"","instructions") and any(sub.lower() in i["v"].lower() and "manual" in i["v"].lower() for i in items if i["kind"]=="step"))
    n_steps = len([i for i in items if i["kind"]=="step"]); ok(f"{tag}: 8 requirement/method rows", n_steps==8, n_steps)
    ok(f"{tag}: packaging description", has(items,"pack","Cartons will be placed on the same pallet 45x45 (White)"))
def check_bom(items, tag):
    f = fields(items)
    for k, v in {"customer":"Group Dekko Inc","part_no":"FP 124","qty_req":"2,000","date":"9/8/2026","machine":"2-250","clamp":"250 ton","material":"PVC - Utility - Black","grade":"Black Rigid Utility Injection Grade PVC"}.items():
        ok(f"{tag}: {k} = {v}", k in f and v.lower() in f[k].lower(), f.get(k))
    sup = [(i["v"], i["q"]) for i in items if i["kind"]=="supply"]
    for sub, q in [("134-4004-01","2,000"),("250-ton machine","120,000"),("Tooling Setup","2,000"),("Operator Labor","120,000"),("PVC - Utility - Black","2,000"),("Box","10"),("Label - Carton 4","10")]:
        ok(f"{tag}: supply '{sub}' qty {q}", any(sub.lower() in v.lower() and qq==q for v, qq in sup), [s for s in sup if sub.lower() in s[0].lower()])
    ok(f"{tag}: default rows reused (Tooling / Machine / Tooling setup / Operator labor)", {i["v"].split(" — ")[0] for i in items if i["kind"]=="supply" and i["v"].startswith(("Tooling —","Machine —"))}=={"Tooling","Machine"})
    loose = [i for i in items if i["loose"]]
    ok(f"{tag}: handwritten work order is an unmatched line, not a filled value", "work_order" not in f and any("work order" in (i["l"]+i["v"]).lower() for i in loose), [i["l"]+"="+i["v"] for i in loose])
    ok(f"{tag}: no garbage selected among loose lines", not any(i["sel"] for i in loose))
def check_ns(items, tag):
    f = fields(items)
    for k, v in {"part_no":"134-4004-01","toolNumber":"134-4003-00","machine":"2-250","cavities":"1","mach_cycle":"60","customer":"Group Dekko Inc","description":"Group DEKKO - 5 1/2 Box w/ 4 square hole face plate"}.items():
        ok(f"{tag}: {k} = {v}", k in f and v.lower() in f[k].lower(), f.get(k))
    ok(f"{tag}: NetSuite boilerplate ignored (internal id / units / subsidiary)", not any(re.search(r"internal|purchase unit|subsidiary|consolidated", i["l"]+" "+i["v"], re.I) for i in items))

with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
    ctx = mk_ctx(b); page = ctx.new_page(); watch(page, "main")
    page.goto(BASE); page.wait_for_selector(".jobcard"); page.wait_for_function("window.__tjl && __tjl.state.jobs.filter(j=>j.example).length>=3", timeout=60000); time.sleep(0.5)

    # ---------- version + update button ----------
    ver = page.evaluate("fetch('sw.js').then(r=>r.text()).then(t=>t.match(/VERSION = \"([^\"]+)/)[1])")
    ok("sw VERSION = tjl-v2.6.0", ver=="tjl-v2.6.0", ver)
    page.goto(BASE+"#/settings"); page.wait_for_selector("#versionCard")
    first_card = page.evaluate("document.querySelector('#app .card').id")
    ok("version card is the first card in Settings", first_card=="versionCard", first_card)
    ok("'App version 2.6.0' row", page.inner_text("#versionCard .vtitle").strip()=="App version 2.6.0", page.inner_text("#versionCard .vtitle"))
    ok("Check for update button", page.is_visible("#checkUpdBtn") and "Check for update" in page.inner_text("#checkUpdBtn"))
    page.wait_for_function("navigator.serviceWorker && navigator.serviceWorker.controller", timeout=20000)
    page.click("#checkUpdBtn"); page.wait_for_function("/latest version|online|Downloading/.test(document.getElementById('updStatus').textContent)", timeout=20000)
    ok("Check for update → 'You have the latest version (2.6.0)'", "latest version (2.6.0)" in page.inner_text("#updStatus"), page.inner_text("#updStatus"))
    page.screenshot(path=SHOTS+"14-settings-version.png")

    # ---------- each document alone: gallery (img) and Drive/Files (files) ----------
    timings = {}
    for tag, kind, path, chk in [("WI/gallery","img",WI,check_wi), ("BOM/files","files",BOM,check_bom), ("NetSuite/files","files",NS,check_ns), ("WI/files","files",WI,check_wi)]:
        items, dt = scan(page, kind, [path]); timings[tag]=round(dt,1)
        chk(items, tag)
        prep = page.evaluate("window.__lastScan && __lastScan.pages[0].prep")
        ok(f"{tag}: OCR prep ran (crop/deskew/upscale/line removal)", prep and prep.get("w",0)>=2000 and prep.get("linePx",0)>0 and not prep.get("err"), prep)
        if tag!="WI/files":
            tall_shot(page, SHOTS+"14-review-%s.png" % tag.split("/")[0].lower().replace("netsuite","ns"))
        page.click("[data-act=closeModal]")
    print("OCR+parse seconds per scan:", timings)

    # ---------- all three together (Drive/Files multi-select), conflicts ----------
    items, dt = scan(page, "files", [WI, BOM, NS]); print("3 documents:", round(dt,1), "s")
    check_wi(items, "merged", merged=True)
    f = fields(items)
    tool = next(i for i in items if i["k"]=="toolNumber"); mc = next(i for i in items if i["k"]=="mach_cycle")
    ok("merged: Tool # conflict 134-4004-02 vs 134-4003-00 shown", sorted(tool["opts"])==["134-4003-00","134-4004-02"], tool["opts"])
    ok("merged: machine cycle conflict 61.2 vs 60 shown", sorted(mc["opts"])==["60","61.2"], mc["opts"])
    pn = next(i for i in items if i["k"]=="part_no")
    ok("merged: part number FP 124 pre-selected (2 documents agree)", pn["v"]=="FP 124" and "134-4004-01" in pn["opts"], (pn["v"], pn["opts"], pn["doc"]))
    ok("merged: machine 2 vs 2-250 is not a conflict", f.get("machine")=="2-250" and not next(i for i in items if i["k"]=="machine")["opts"], f.get("machine"))
    ok("merged: customer agreed by all 3 docs (no conflict)", not next(i for i in items if i["k"]=="customer")["opts"])
    ok("merged: BOM supplies present", len([i for i in items if i["kind"]=="supply"])==7)
    ok("merged: NetSuite description present", "Group DEKKO" in f.get("description",""), f.get("description"))
    ok("merged: conflict banner", page.is_visible("#rvConflicts") and "3 values differ" in page.inner_text("#rvConflicts"), page.inner_text("#rvConflicts") if page.is_visible("#rvConflicts") else "")
    tall_shot(page, SHOTS+"14-review-merged.png")
    # pick: tool # from the work instructions, cycle 61.2 from the work instructions
    ti = page.evaluate("__tjl.state.modal.items.findIndex(i=>i.key==='toolNumber')"); mi = page.evaluate("__tjl.state.modal.items.findIndex(i=>i.key==='mach_cycle')")
    page.click(f".rv[data-rvrow='{mi}'] .rv-opt:has-text('61.2')"); page.click(f".rv[data-rvrow='{ti}'] .rv-opt:has-text('134-4004-02')")
    ok("picking a conflict option sets the value", page.evaluate(f"__tjl.state.modal.items[{mi}].value")=="61.2" and page.evaluate(f"__tjl.state.modal.items[{ti}].value")=="134-4004-02")
    page.click("[data-act=rvApply]"); page.wait_for_selector("#h_tool"); time.sleep(0.5)
    job = page.evaluate("__tjl.state.jobs.find(j=>j.id===__tjl.state.route.id)")
    def jf(key):
        for s in job["sections"]:
            for x in s.get("fields",[]) or []:
                if x.get("key")==key and str(x.get("value","")).strip(): return x["value"]+(" "+x["unit"] if x.get("unit") else "")
        return None
    def sec(role): return next((s for s in job["sections"] if s.get("role")==role), None)
    ok("applied: header Tool # / part / customer", job["toolNumber"]=="134-4004-02" and "Box w/4 sq Holes" in job["partName"] and job["customer"].startswith("Group Dekko Inc"), (job["toolNumber"], job["partName"], job["customer"]))
    for k, v in {"part_no":"FP 124","material":"PVC Rigid","color":"Black","cavities":"1","part_wt":"0.288","shot_wt":"0.299","cycle":"67 (Semi) s","mach_cycle":"61.2 s","pph":"53","machine":"2-250","revision":"2026","qty_req":"2,000","date":"9/8/2026","grade":"Black Rigid Utility Injection Grade PVC","clamp":"250 ton","pallet_size":"45x45 (White)"}.items():
        ok(f"applied: {k} = {v}", jf(k)==v, jf(k))
    car = sec("carton"); cl = {x["label"]:x["value"] for x in car["fields"]}
    ok("applied: carton section has both components", cl.get("FP 124 Small Box Back — Carton size")=="12x12x12" and cl.get("FP 124 Front Plate — Carton size")=="12x12x9" and cl.get("FP 124 Front Plate — Parts on 2nd layer","").startswith("70"), cl)
    ok("applied: empty single-carton fields replaced by component rows", not any(x["key"] in ("carton_size","qty_carton","cartons_layer") and not x["value"] for x in car["fields"]))
    qc = [i["text"] for i in sec("quality")["items"]]; ins = [i["text"] for i in sec("instructions")["items"]]
    ok("applied: quality checks replaced stock list", len(qc)==2 and qc[0].startswith("No shorts"), qc)
    ok("applied: 6 work instructions with methods", len(ins)==6 and all("Manual" in t for t in ins), ins)
    rows = [(r["desc"], r["qty"]) for r in sec("supplies")["rows"]]
    ok("applied: supplies filled with quantities", ("Operator Labor","120,000") in [(d.split(" (")[0], q) for d, q in rows] and any(d.startswith("Tooling — 134-4004-01") and q=="2,000" for d, q in rows) and any(d.startswith("Label - Carton") and q=="10" for d, q in rows), rows)
    ok("applied: packaging description", "Cartons will be placed on the same pallet 45x45 (White)" in sec("packaging")["text"], sec("packaging")["text"])
    # job detail shows it
    page.goto(BASE+"#/job/"+job["id"]); page.wait_for_selector("#h_tool"); time.sleep(0.5)
    body = page.inner_text("#app")
    vals = [page.input_value(sel) for sel in ["#h_tool"]] + page.evaluate("[...document.querySelectorAll('#app input,#app textarea')].map(e=>e.value)")
    blob = body + "\n" + "\n".join(vals)
    for v in ["134-4004-02","FP 124","PVC Rigid","0.288","61.2","12x12x9","No shorts, splay","Clip parts from runner","Operator Labor","120,000","Cartons will be placed"]:
        ok(f"job detail shows '{v}'", v in blob)
    clear_toast(page); h = page.evaluate("document.documentElement.scrollHeight")
    page.set_viewport_size({"width":412,"height":min(h,16000)}); time.sleep(0.4); page.screenshot(path=SHOTS+"14-job-detail.png"); page.set_viewport_size({"width":412,"height":915})
    # reference sheet prints it
    page.goto(BASE+"#/job/"+job["id"]+"/print"); page.wait_for_selector("#printArea")
    if page.evaluate("__tjl.state.meta.printLayout||'reference'")!="reference": page.click("[data-act=setLayout][data-v=reference]")
    page.wait_for_selector("#printArea .rs-page"); time.sleep(0.6)
    rs = page.evaluate("Object.fromEntries([...document.querySelectorAll('#printArea .rs-kv tr')].map(tr=>[tr.cells[0].textContent.replace(/:$/,''), tr.cells[1].textContent]))")
    for k, v in {"Customer":"Group Dekko Inc","Part Number":"FP 124","Material":"PVC Rigid","Color":"Black","Number of Cavities":"1","Part Weight":"0.288","Shot Weight":"0.299","Machine Cycle Time":"61.2","Parts Per Hour":"53","Machine":"2-250","Tool Number":"134-4004-02","Revision":"2026","Quantity required":"2,000","FP 124 Small Box Back — Quantity per carton":"75","FP 124 Front Plate — Parts on 1st layer":"80 (8 Sets of 10)","Pallet size":"45x45 (White)"}.items():
        ok(f"sheet: {k} = {v}", v in (rs.get(k) or ""), rs.get(k))
    ok("sheet: Avg. Cycle Time 67 … (Semi)", re.match(r"67 (s|sec|seconds) \(Semi\)", rs.get("Avg. Cycle Time","")), rs.get("Avg. Cycle Time"))
    sheet = page.inner_text("#printArea")
    for v in ["No shorts, splay, discoloration or burns — Visual / 100%","Put label with Date & Initial","Operator Labor","120,000","Label - Carton 4 x 6","Cartons will be placed on the same pallet 45x45 (White)","Black Rigid Utility Injection Grade PVC","250 ton"]:
        ok(f"sheet prints '{v}'", v in sheet)
    page.evaluate("window.scrollTo(0,0)"); clear_toast(page)
    h = page.evaluate("document.documentElement.scrollHeight"); page.set_viewport_size({"width":412,"height":min(h,16000)}); time.sleep(0.5)
    page.screenshot(path=SHOTS+"14-sheet.png"); page.set_viewport_size({"width":412,"height":915})
    page.emulate_media(media="print"); page.pdf(path="/workspace/tjl2-test/realforms-sheet.pdf", format="Letter", print_background=True, prefer_css_page_size=True); page.emulate_media(media="screen")

    # ---------- rescan NetSuite into the finished job: no blanks overwrite, same values skipped ----------
    page.goto(BASE+"#/job/"+job["id"]); page.wait_for_selector("#h_tool")
    items, _ = scan(page, "files", [NS], new=False)
    keys = [i["k"] for i in items if not i["loose"] and not i["kind"]]
    ok("rescan into job: unchanged values not offered again (customer, cavities, machine)", not any(k in keys for k in ["customer","cavities","machine"]), keys)
    tn = next((i for i in items if i["k"]=="toolNumber"), None)
    ok("rescan into job: differing Tool # shows the current value", tn is not None and page.evaluate("__tjl.state.modal.items.find(i=>i.key==='toolNumber').prev")=="134-4004-02")
    page.evaluate("__tjl.state.modal.items.forEach(i=>{ if(i.key==='toolNumber'||i.key==='mach_cycle'||i.key==='part_no') i.selected=false; })")
    page.click("[data-act=rvApply]"); time.sleep(0.4)
    job2 = page.evaluate("__tjl.state.jobs.find(j=>j.id===%s)" % json.dumps(job["id"]))
    def jf2(key):
        for s in job2["sections"]:
            for x in s.get("fields",[]) or []:
                if x.get("key")==key and str(x.get("value","")).strip(): return x["value"]
    ok("rescan into job: good values kept (color, material, part wt, tool #)", jf2("color")=="Black" and jf2("material")=="PVC Rigid" and jf2("part_wt")=="0.288" and job2["toolNumber"]=="134-4004-02")

    # ---------- all three from the gallery picker too ----------
    items, dt = scan(page, "img", [WI, BOM, NS])
    ok("gallery multi-select: 3 documents merged", page.evaluate("__tjl.state.modal.docs.length")==3 and len([i for i in items if i["kind"]=="supply"])==7 and len([i for i in items if i["kind"]=="step"])==8)
    page.click("[data-act=closeModal]")

    ctx.close()

    # ---------- update flow: installed 2.6.0 → new version published → Check for update moves to it ----------
    D = "/workspace/tjl2-test/upd/"; shutil.rmtree(D, ignore_errors=True); shutil.copytree(APP, D, ignore=shutil.ignore_patterns("tests","shots"))
    sock = socket.socket(); sock.bind(("127.0.0.1",0)); port = sock.getsockname()[1]; sock.close()
    srv = subprocess.Popen(["python3","-m","http.server",str(port)], cwd=D, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); time.sleep(1)
    try:
        U = f"http://localhost:{port}/"
        c2 = mk_ctx(b); p2 = c2.new_page(); watch(p2, "upd")
        p2.goto(U+"#/settings"); p2.wait_for_selector("#versionCard")
        p2.wait_for_function("navigator.serviceWorker && navigator.serviceWorker.controller", timeout=30000)
        p2.reload(); p2.wait_for_selector("#versionCard")
        ok("update: installed app shows 2.6.0", "2.6.0" in p2.inner_text("#appVersion"))
        # publish "2.5.1" (index + sw) on the server
        for fn, a, z in [("index.html",'var APP_VERSION = "2.6.0";','var APP_VERSION = "2.5.1";'), ("sw.js",'const VERSION = "tjl-v2.6.0";','const VERSION = "tjl-v2.5.1";')]:
            t = open(D+fn).read(); assert a in t; open(D+fn,"w").write(t.replace(a, z))
        with p2.expect_navigation(timeout=40000): p2.click("#checkUpdBtn")
        p2.wait_for_selector("#versionCard"); time.sleep(0.5)
        ok("update: Check for update installed and reloaded into 2.5.1", "2.5.1" in p2.inner_text("#appVersion"), p2.inner_text("#appVersion"))
        swv = p2.evaluate("caches.keys()")
        ok("update: old shell cache removed, new one active", "tjl-v2.5.1-shell" in swv and "tjl-v2.6.0-shell" not in swv, swv)
        p2.screenshot(path=SHOTS+"14-settings-after-update.png")
        # automatic path: new version published while the app is open → banner on the list, tap Update
        for fn, a, z in [("index.html",'var APP_VERSION = "2.5.1";','var APP_VERSION = "2.5.2";'), ("sw.js",'const VERSION = "tjl-v2.5.1";','const VERSION = "tjl-v2.5.2";')]:
            t = open(D+fn).read(); open(D+fn,"w").write(t.replace(a, z))
        p2.goto(U+"#/"); p2.reload(); p2.wait_for_selector("[data-act=applyUpdate]", timeout=40000)
        ok("update: 'A new version is ready' banner on the job list", p2.is_visible("[data-act=applyUpdate]"))
        with p2.expect_navigation(timeout=40000): p2.click("[data-act=applyUpdate]")
        p2.goto(U+"#/settings"); p2.wait_for_selector("#versionCard")
        ok("update: banner Update moved the app to 2.5.2", "2.5.2" in p2.inner_text("#appVersion"), p2.inner_text("#appVersion"))
        c2.close()
    finally:
        srv.terminate()
    b.close()

bad = [e for e in errors if "Failed to load resource" not in e]
ok("no page errors / console errors", not bad, bad[:5])
fails = [r for r in results if not r[1]]
print("\n%d checks, %d failed" % (len(results), len(fails)))
for f in fails: print("FAILED:", f[0], "—", f[2])
