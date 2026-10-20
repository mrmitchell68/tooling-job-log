"""v2.6.0: Machine Settings section (Allen's machine setup sheet: Clamp, Ejection, Injection, Charging, Temperature, Production).
Real photo of the filled-in sheet (turned 90°) goes through the actual scan flow: form detection, rotation, every typed row found,
review grid with a picture of each cell, low-confidence rows highlighted + unchecked, apply, editor (1/2/3 + =all + 4th), template
defaults → new job, setup checklist, printed tables (reference + process sheet), old-job migration. Per-cell accuracy is measured
against a hand reading of the sheet (fixtures/real-machine-settings.truth.json). Screenshots -> shots/ms-*.png"""
import json, os, re, sys, time
from playwright.sync_api import sync_playwright
BASE = os.environ.get("TJL_BASE", "http://localhost:8766/")
APP = "/workspace/tooling-job-log-v2/"
SHOTS = APP + "shots/"
FIX = APP + "tests/fixtures/"
SHEET = FIX + "real-machine-settings.jpg"
TRUTH = json.load(open(FIX + "real-machine-settings.truth.json"))
BOM = FIX + "real-bom.jpg"
errors = []; results = []; FAILED = []
def ok(name, cond, extra=""):
    results.append((name, bool(cond), extra)); print(("PASS " if cond else "FAIL ") + name + (" — " + str(extra)[:400] if extra != "" else ""), flush=True)
def watch(pg, tag):
    pg.on("console", lambda m: errors.append(tag+" console."+m.type+": "+m.text) if m.type=="error" and "favicon" not in m.text else None)
    pg.on("pageerror", lambda e: errors.append(tag+" pageerror: "+str(e)))
    pg.on("requestfailed", lambda r: FAILED.append((len(results), r.url[:100], r.failure)))
def clear_toast(pg): pg.evaluate("document.getElementById('toastRoot') && (document.getElementById('toastRoot').innerHTML='')")
def tall_shot(pg, path, sel="#modalRoot .sheet"):
    clear_toast(pg)
    h = pg.evaluate("(sel)=>{const s=document.querySelector(sel); return s? s.scrollHeight+140 : document.documentElement.scrollHeight}", sel)
    pg.set_viewport_size({"width":412, "height":min(int(h), 16000)}); time.sleep(0.5)
    if pg.query_selector(sel): pg.locator(sel).screenshot(path=path)
    else: pg.screenshot(path=path, full_page=True)
    pg.set_viewport_size({"width":412, "height":915})
def open_sec(pg, sec):
    if not pg.evaluate("(s)=>document.querySelector('#msCard [data-mssec='+s+']').classList.contains('open')", sec):
        pg.click(f"#msCard [data-act=msSec][data-sec={sec}]")
def scan_here(pg, files):
    pg.click(".bottombar [data-act=scanMenu]")
    with pg.expect_file_chooser() as fc: pg.click("[data-act=scanHere][data-kind=img]")
    fc.value.set_files(files); t = time.time()
    pg.wait_for_selector(".sheet h3:has-text('Review')", timeout=300000); time.sleep(0.3)
    return time.time() - t
MSROWS = "(__tjl.state.modal.ms? __tjl.state.modal.ms.rows : []).map(r=>({id:r.id, vals:r.vals.slice(), extra:r.extra||'', same:!!r.same, conf:r.conf, state:r.state, sel:!!r.selected, crop:(r.crop||'').length}))"
def score(rows):
    """per value slot: 3 stages + 4th for staged rows, 1 for single rows; checkboxes as yes/blank"""
    by = {r["id"]: r for r in rows}; hw_ok = hw_n = bl_ok = bl_n = 0; wrong = []; wrong_sel = []
    for k, tv in TRUTH.items():
        if k == "ej_strokes": continue  # written as the word NONE (not a number) — counted separately
        r = by.get(k)
        if not r: wrong.append((k, "missing")); continue
        if len(tv) >= 3: got = r["vals"] + [r["extra"]]; tvv = tv + ([""] if len(tv) == 3 else [])
        else: got = r["vals"]; tvv = tv
        if k in ("air_blast", "corepull", "intrusion"): got = ["yes" if r["state"] == "check" else ""]
        bad = False
        for i, t in enumerate(tvv):
            g = str(got[i] if i < len(got) else "").strip()
            if t: hw_n += 1; hw_ok += g == t
            else: bl_n += 1; bl_ok += g == ""
            if g != t: bad = True
        if bad:
            wrong.append((k, got, tvv, round(r["conf"], 2)))
            if r["sel"]: wrong_sel.append(k)
    return hw_ok, hw_n, bl_ok, bl_n, wrong, wrong_sel

with sync_playwright() as p:
    b = p.chromium.launch(channel="chrome", args=["--no-sandbox"])
    c = b.new_context(viewport={"width":412,"height":915}, device_scale_factor=2, is_mobile=True, has_touch=True,
        user_agent="Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Mobile Safari/537.36")
    c.route("https://script.google.com/**", lambda r: r.fulfill(status=200, content_type="text/plain", body="no"))
    pg = c.new_page(); watch(pg, "main")
    pg.goto(BASE + "#/"); pg.wait_for_selector(".jobcard")
    ok("app is 2.6.0", pg.evaluate("document.documentElement.innerHTML.indexOf('APP_VERSION = \"2.6.0\"')>=0"))
    sw = pg.evaluate("fetch('sw.js').then(r=>r.text())")
    ok("sw VERSION tjl-v2.6.0 + digit model precached", 'VERSION = "tjl-v2.6.0"' in sw and "./vendor/digits.json" in sw)
    ok("digit model served", pg.evaluate("fetch('vendor/digits.json').then(r=>r.json()).then(j=>Object.keys(j).length)") == 8)

    # ---------- 1. migration: an old job (saved before 2.6.0) has no machineSettings ----------
    pg.evaluate("""() => { const jobs = __tjl.state.jobs; const o = JSON.parse(JSON.stringify(jobs[0]));
        o.id = 'oldjob240'; o.toolNumber = 'OLD-1'; delete o.machineSettings; o.example = false; jobs.push(o);
        jobs.forEach(j => { delete j.machineSettings; }); localStorage.setItem('tjl2.jobs', JSON.stringify(jobs)); }""")
    before = pg.evaluate("JSON.parse(localStorage.getItem('tjl2.jobs')).find(j=>j.id==='oldjob240')")
    pg.reload(); pg.wait_for_selector(".jobcard")
    mig = pg.evaluate("__tjl.state.jobs.find(j=>j.id==='oldjob240')")
    ok("migration: old job gets an empty machineSettings", mig.get("machineSettings") and mig["machineSettings"]["rows"] == {} and mig["machineSettings"]["header"] == {"partNumber":"","machine":"","date":""}, mig.get("machineSettings"))
    ok("migration: everything else unchanged", all(json.dumps(mig[k], sort_keys=True) == json.dumps(before[k], sort_keys=True) for k in before if k not in ("machineSettings",)),
       [k for k in before if json.dumps(mig.get(k), sort_keys=True) != json.dumps(before[k], sort_keys=True)])
    ok("migration: every job normalized", pg.evaluate("__tjl.state.jobs.every(j=>j.machineSettings && j.machineSettings.rows)"))

    # old job: print layouts unchanged (no machine-settings page / block when nothing is filled)
    pg.goto(BASE + "#/job/oldjob240/print"); pg.wait_for_selector("#printArea .rs-page")
    ok("old job reference sheet: no machine settings page", pg.query_selector(".rs-page.msp") is None and pg.query_selector(".ms-sheet") is None)
    pg.click("[data-act=setLayout][data-v=process]"); pg.wait_for_selector(".ps")
    ok("old job process sheet: no machine settings block", pg.query_selector(".ps-ms") is None)
    pg.click("[data-act=setLayout][data-v=reference]")

    # ---------- 2. job detail: card + editor ----------
    pg.goto(BASE + "#/job/oldjob240"); pg.wait_for_selector("#msCard")
    order = pg.evaluate("[...document.querySelectorAll('#app section.card')].map(s=>s.id||'')")
    ok("Machine settings card sits right above Photos", "msCard" in order and order.index("msCard") == order.index("photosCard") - 1, order)
    secs = pg.evaluate("[...document.querySelectorAll('#msCard .ms-sec .ms-sh .t')].map(e=>e.textContent)")
    ok("6 sections in sheet order", secs == ["Clamp","Ejection","Injection","Charging","Temperature","Production"], secs)
    ok("accordion starts closed", pg.evaluate("document.querySelectorAll('#msCard .ms-sec.open').length") == 0)
    pg.click("#msCard [data-act=msSec][data-sec=clamp]")
    ok("tap opens Clamp", pg.evaluate("document.querySelector('#msCard [data-mssec=clamp]').classList.contains('open')"))
    nrows = pg.evaluate("[...document.querySelectorAll('#msCard [data-mssec]')].map(s=>s.querySelectorAll('.ms-row').length)")
    ok("rows per section match the sheet (9/7/8/5/12/7)", nrows == [9,7,8,5,12,7], nrows)
    staged_inputs = pg.evaluate("document.querySelectorAll('#msCard [data-mssec=clamp] .ms-row.st').length && document.querySelectorAll('#msCard [data-msv=open_press]').length")
    ok("staged rows have 1/2/3 inputs", staged_inputs == 3, staged_inputs)
    for i, v in enumerate(["35", "20", "20"]):
        pg.fill(f"#msCard input[data-msv=open_press][data-msi='{i}']", v)
    pg.fill("#msCard input[data-msv=mold_open_time][data-msi='0']", "5.0")
    time.sleep(0.8)
    st = pg.evaluate("__tjl.state.jobs.find(j=>j.id==='oldjob240').machineSettings.rows")
    ok("typed values saved", st.get("open_press", {}).get("vals") == ["35","20","20"] and st.get("mold_open_time", {}).get("vals") == ["5.0","",""], st)
    # same for all
    open_sec(pg, "injection")
    pg.fill("#msCard input[data-msv=inj_speed][data-msi='0']", "15")
    pg.click("#msCard [data-act=msSame][data-p=inj_speed]"); time.sleep(0.3)
    r = pg.evaluate("__tjl.state.jobs.find(j=>j.id==='oldjob240').machineSettings.rows.inj_speed")
    ok("=all copies stage 1 to 2 and 3", r["vals"] == ["15","15","15"] and r["same"], r)
    ok("=all button shows on + accordion stays open after re-render", pg.evaluate("document.querySelector('[data-act=msSame][data-p=inj_speed]').classList.contains('on') && document.querySelector('[data-mssec=injection]').classList.contains('open')"))
    pg.fill("#msCard input[data-msv=inj_speed][data-msi='0']", "18"); time.sleep(0.6)
    r = pg.evaluate("__tjl.state.jobs.find(j=>j.id==='oldjob240').machineSettings.rows.inj_speed")
    shown = pg.evaluate("[...document.querySelectorAll('#msCard input[data-msv=inj_speed]')].map(e=>e.value)")
    ok("while =all is on, editing stage 1 updates all three", r["vals"] == ["18","18","18"] and shown[:3] == ["18","18","18"], (r, shown))
    pg.fill("#msCard input[data-msv=inj_speed][data-msi='2']", "20"); time.sleep(0.6)
    r = pg.evaluate("__tjl.state.jobs.find(j=>j.id==='oldjob240').machineSettings.rows.inj_speed")
    ok("changing one stage turns =all off", r["vals"] == ["18","18","20"] and not r["same"], r)
    # 4th value
    open_sec(pg, "charging")
    pg.click("#msCard [data-act=msAdd4][data-p=back_press]")
    ok("＋4th opens the 4th value input", pg.query_selector("#msCard input[data-msv=back_press][data-msi=x]") is not None)
    pg.fill("#msCard input[data-msv=back_press][data-msi=x]", "70")
    for i in range(3): pg.fill(f"#msCard input[data-msv=back_press][data-msi='{i}']", "0")
    # checkbox + single + notes
    open_sec(pg, "production")
    pg.check("#msCard input[data-mschk=corepull]")
    pg.fill("#msCard input[data-msv=cooling][data-msi='0']", "55.0")
    pg.fill("#msCard [data-msh=partNumber]", "PSP 36")
    open_sec(pg, "ejection")
    pg.fill("#msCard textarea[data-msnote=corePull]", "OUT 600 psi, PT 2900, speed 60, timer 200")
    time.sleep(0.8)
    ms = pg.evaluate("__tjl.state.jobs.find(j=>j.id==='oldjob240').machineSettings")
    ok("4th value, checkbox, single value, header, core pull note saved", ms["rows"]["back_press"]["extra"] == "70" and ms["rows"]["back_press"]["vals"] == ["0","0","0"] and ms["rows"]["corepull"]["vals"] == ["yes"]
       and ms["rows"]["cooling"]["vals"] == ["55.0"] and ms["header"]["partNumber"] == "PSP 36" and "600 psi" in ms["corePull"], ms)
    ok("section counts update live", pg.evaluate("document.querySelector('[data-mssec=clamp] .ms-sh .n').textContent") == "2/9 set")
    # editing an existing value → unlogged change (like other sheet fields)
    pg.click("#msCard input[data-msv=open_press][data-msi='1']"); pg.fill("#msCard input[data-msv=open_press][data-msi='1']", "25"); pg.press("#msCard input[data-msv=open_press][data-msi='1']", "Tab"); time.sleep(0.5)
    pc = pg.evaluate("__tjl.state.jobs.find(j=>j.id==='oldjob240').pendingChanges")
    ok("editing a set value records an unlogged change", any("Opening pressures" in c["label"] and c["from"] == "35 / 20 / 20" and c["to"] == "35 / 25 / 20" for c in pc), pc)
    pg.reload(); pg.wait_for_selector("#msCard")
    ok("values survive reload", pg.evaluate("document.querySelector('#msCard input[data-msv=open_press][data-msi=\"1\"]').value") == "25")
    pg.goto(BASE + "#/"); pg.wait_for_selector("#searchInput"); pg.fill("#searchInput", "psp 36"); time.sleep(0.4)
    ok("job search finds machine settings values", "OLD-1" in pg.inner_text("#jobList"), pg.inner_text("#jobList")[:200])
    pg.fill("#searchInput", ""); time.sleep(0.2)
    pg.goto(BASE + "#/job/oldjob240"); pg.wait_for_selector("#msCard")
    # phone screenshot of the editor
    open_sec(pg, "clamp"); open_sec(pg, "charging"); time.sleep(0.3)
    pg.evaluate("(()=>{ const st=document.createElement('style'); st.id='shotcss'; st.textContent='.topbar{position:static!important} .bottombar{display:none!important}'; document.head.appendChild(st); })()")
    pg.locator("#msCard").screenshot(path=SHOTS + "ms-1-editor-phone.png")
    pg.evaluate("document.getElementById('shotcss').remove()")

    # ---------- 3. scan the real sheet photo into a fresh job ----------
    pg.goto(BASE + "#/"); pg.wait_for_selector(".fab"); pg.click(".fab"); pg.click("[data-act=newBlank]"); pg.wait_for_selector("#h_tool")
    jid = pg.evaluate("__tjl.state.route.id")
    pg.fill("#h_tool", "T-PSP36"); time.sleep(0.4)
    took = scan_here(pg, [SHEET])
    ok("scan finished (%.0f s)" % took, took < 240, round(took))
    last = pg.evaluate("window.__lastScan")
    ok("form detected as machine settings sheet", pg.evaluate("!!__tjl.state.modal.ms") and pg.query_selector("#msRvHd") is not None)
    ok("photo turned 90° detected → rotated 270° to read", last["pages"][0]["rot"] == 270, last["pages"][0])
    M = pg.evaluate("({found:__tjl.state.modal.ms.found, total:__tjl.state.modal.ms.total})")
    ok("every typed row found (48/48)", M["found"] == 48 and M["total"] == 48, M)
    rows = pg.evaluate(MSROWS)
    ok("review has all 48 rows", len(rows) == 48, len(rows))
    ok("every row has its cell picture", all(r["crop"] > 500 for r in rows), [r["id"] for r in rows if r["crop"] <= 500])
    ncrop = pg.evaluate("[...document.querySelectorAll('#modalRoot .msr img.crop')].filter(i=>i.complete && i.naturalWidth>50).length")
    ok("cell pictures render in the review grid", ncrop >= 40, ncrop)
    hw_ok, hw_n, bl_ok, bl_n, wrong, wrong_sel = score(rows)
    print("ACCURACY handwritten values %d/%d (%.0f%%), blank/n.a. cells %d/%d" % (hw_ok, hw_n, 100.0*hw_ok/hw_n, bl_ok, bl_n), flush=True)
    for w in wrong: print("  MISREAD", w, flush=True)
    print("  wrong but pre-checked:", wrong_sel, flush=True)
    ok("handwritten numbers: at least 80% of value cells read right", hw_ok >= 0.8*hw_n, "%d/%d" % (hw_ok, hw_n))
    ok("blank / crossed-out cells never get a value", bl_ok == bl_n, "%d/%d" % (bl_ok, bl_n))
    ok("at most 2 misread rows are pre-checked (the rest are flagged)", len(wrong_sel) <= 2, wrong_sel)
    lo = pg.evaluate("[...document.querySelectorAll('#modalRoot .msr.lo[data-p]')].map(e=>({p:e.getAttribute('data-p'), chk:e.querySelector('input[data-msrchk]').checked}))")
    ok("low-confidence rows highlighted red and unchecked", len(lo) > 0 and all(not x["chk"] for x in lo), lo)
    ok("warning tells how many rows are unchecked", pg.query_selector("#msRvWarn") is not None)
    by = {r["id"]: r for r in rows}
    ok("blank Ejection rows are blank", all(by[k]["state"] in ("blank", "na") and not by[k]["sel"] for k in ["ej_fwd_press","ej_fwd_int","ej_fwd_speed","ej_back_set","ej_back_press","ej_back_speed"]))
    ok("slashed zones 5–8 = n/a, not saved", all(by["zone%d" % z]["state"] in ("na","blank","unread") and not by["zone%d" % z]["sel"] for z in (5,6,7,8)), [by["zone%d" % z]["state"] for z in (5,6,7,8)])
    ok("arrow ← 70 → read as same for all", by["inj_press"]["same"] and by["inj_press"]["vals"] == ["70","70","70"], by["inj_press"])
    ok("4th value after '/' (backpressure 0 0 0 / 70)", by["back_press"]["vals"] == ["0","0","0"] and by["back_press"]["extra"] == "70", by["back_press"])
    ok("corepull checkmark read as checked", by["corepull"]["state"] == "check", by["corepull"])
    hdr = pg.evaluate("__tjl.state.modal.items.filter(i=>i.msHeader).map(i=>({k:i.msHeader, v:i.value, crop:(i.crop||'').length, sel:i.selected}))")
    ok("header part number read (PSP 36) with its picture", any(h["k"] == "partNumber" and h["v"] == "PSP 36" and h["crop"] > 500 for h in hdr), hdr)
    ok("header rows shown with crops in the review list", pg.evaluate("document.querySelectorAll('#modalRoot .rv img.crop').length") >= 1)
    tall_shot(pg, SHOTS + "ms-2-review-grid.png")
    # fix the misread rows like Allen would (type over them), check them
    def set_row(pid, vals, extra=None):
        i = next(n for n, r in enumerate(rows) if r["id"] == pid)
        pg.evaluate("(i)=>{ const d=document.querySelector('.msr-empty'); if(d) d.open=true; }", i)
        for k, v in enumerate(vals):
            sel = f"#modalRoot input[data-msrv='{i}'][data-msri='{k}']"
            if pg.query_selector(sel): pg.fill(sel, v)
        if extra is not None: pg.fill(f"#modalRoot input[data-msrv='{i}'][data-msri=x]", extra)
        return i
    fixes = {}
    for w in wrong:
        k = w[0]; tv = TRUTH[k]
        if k in ("air_blast","corepull","intrusion"): continue
        if not any(tv): continue
        if len(tv) >= 3: set_row(k, tv[:3], tv[3] if len(tv) == 4 else ""); fixes[k] = tv
        else: set_row(k, tv[:1]); fixes[k] = tv
    ok("'NONE' (a word, not a number) kept as text and not pre-checked", by["ej_strokes"]["state"] == "text" and by["ej_strokes"]["vals"][0].upper() == "NONE" and not by["ej_strokes"]["sel"], by["ej_strokes"])
    unchecked_ok = pg.evaluate("__tjl.state.modal.ms.rows.map((r,i)=>[r,i]).filter(([r])=>!r.selected && (r.state==='read'||r.state==='check'||r.state==='text')).map(([r,i])=>i)")
    for i in unchecked_ok: pg.check(f"#modalRoot input[data-msrchk='{i}']")
    ok("checking a correct but low-confidence row selects it", all(pg.evaluate(f"__tjl.state.modal.ms.rows[{i}].selected") for i in unchecked_ok), unchecked_ok)
    ok("editing a row in the review checks it", all(pg.evaluate(f"__tjl.state.modal.ms.rows.find(r=>r.id==='{k}').selected") for k in fixes), list(fixes))
    # same-for-all button in the review
    i_hs = next(n for n, r in enumerate(rows) if r["id"] == "inj_speed")
    if not by["inj_speed"]["same"]:
        pg.fill(f"#modalRoot input[data-msrv='{i_hs}'][data-msri='0']", "15"); pg.click(f"#modalRoot [data-act=msrSame][data-i='{i_hs}']"); time.sleep(0.3)
    ok("review =all sets the row to the same value", pg.evaluate(f"(r=>r.same && r.vals.join()==='15,15,15')(__tjl.state.modal.ms.rows[{i_hs}])"))
    # header: uncheck nothing; part number goes to job
    pg.click("[data-act=rvApply]"); time.sleep(0.8)
    j = pg.evaluate(f"__tjl.state.jobs.find(j=>j.id==='{jid}')")
    msj = j["machineSettings"]
    got = {k: msj["rows"].get(k, {}).get("vals") for k in TRUTH}
    exact = 0; n_hw = 0
    for k, tv in TRUTH.items():
        if k in ("ej_strokes",): continue
        if not any(tv) or k in ("air_blast","corepull","intrusion"): continue
        n_hw += 1
        r = msj["rows"].get(k)
        if r and [v for v in r["vals"]] == tv[:len(r["vals"])] and (len(tv) < 4 or r["extra"] == tv[3]): exact += 1
    ok("after the fixes every handwritten row on the job matches the sheet", exact == n_hw, "%d/%d" % (exact, n_hw))
    ok("crossed-out / blank rows not saved", all(not any(msj["rows"].get(k, {"vals":[""]})["vals"]) for k in ["zone5","zone6","zone7","zone8","hot_runner","ej_fwd_press","cushion"]))
    ok("corepull saved as checked", msj["rows"].get("corepull", {}).get("vals") == ["yes"])
    ok("header part number on the sheet + job Part Number field", msj["header"]["partNumber"] == "PSP 36" and pg.evaluate(f"(()=>{{ const j=__tjl.state.jobs.find(j=>j.id==='{jid}'); let v=''; j.sections.forEach(s=>(s.fields||[]).forEach(f=>{{ if(f.key==='part_no') v=f.value; }})); return v; }})()") == "PSP 36")
    ok("tool # untouched by the scan", j["toolNumber"] == "T-PSP36")
    ok("generic fields not polluted by page OCR of the sheet", not any(f.get("key") in ("inj_press","hold_press","nozzle","zone1","back_press") and f.get("value") for s in j["sections"] for f in (s.get("fields") or [])))
    # blank never erases: rescan with one value pre-set that the sheet leaves blank
    pg.evaluate(f"(()=>{{ const j=__tjl.state.jobs.find(j=>j.id==='{jid}'); j.machineSettings.rows.cushion={{vals:['0.25','',''],extra:'',same:false}}; j.machineSettings.header.partNumber='PSP 36'; }})()")
    pg.goto(BASE + f"#/job/{jid}"); pg.wait_for_selector("#msCard")
    # job already has a different part number → conflict
    pg.evaluate(f"(()=>{{ const j=__tjl.state.jobs.find(j=>j.id==='{jid}'); j.sections.forEach(s=>(s.fields||[]).forEach(f=>{{ if(f.key==='part_no') f.value='PSP-99'; }})); }})()")
    scan_here(pg, [SHEET])
    cf = pg.evaluate("__tjl.state.modal.items.filter(i=>i.msHeader==='partNumber').map(i=>({c:!!i.conflict, v:i.value, o:(i.options||[]).map(o=>o.value+'|'+o.doc)}))")
    ok("header conflict: job value vs handwritten value, job value pre-picked", cf and cf[0]["c"] and cf[0]["v"] == "PSP-99" and any("PSP 36|This sheet" in o for o in cf[0]["o"]), cf)
    rows2 = pg.evaluate("__tjl.state.modal.ms.rows.map(r=>({id:r.id, d:!!r.differs, sel:!!r.selected, vals:r.vals.join('|')}))")
    dif = [r for r in rows2 if r["d"]]
    ok("rescan: rows that differ from the job's (fixed) values are flagged and NOT pre-checked", dif and all(not r["sel"] for r in dif) and any(r["id"] == "mold_open_time" for r in dif), dif)
    pg.click("[data-act=rvApply]"); time.sleep(0.6)
    j2 = pg.evaluate(f"__tjl.state.jobs.find(j=>j.id==='{jid}')")
    ok("a blank cell on the sheet never erases a value the job has", j2["machineSettings"]["rows"]["cushion"]["vals"][0] == "0.25", j2["machineSettings"]["rows"]["cushion"])
    ok("rescan did not overwrite the fixed values", j2["machineSettings"]["rows"]["mold_open_time"]["vals"][0] == "5.0" and j2["machineSettings"]["rows"]["ej_strokes"]["vals"][0].upper() == "NONE", (j2["machineSettings"]["rows"]["mold_open_time"], j2["machineSettings"]["rows"]["ej_strokes"]))

    # ---------- 4. setup mode ----------
    pg.goto(BASE + f"#/job/{jid}/setup"); pg.wait_for_selector("#msSetup")
    n_items = pg.evaluate("document.querySelectorAll('#msSetup .ms-step').length")
    ok("setup checklist lists every set machine setting", n_items >= 30, n_items)
    sp_before = pg.evaluate("document.querySelector('.bigprog .n').textContent")
    pg.click("#msSetup [data-act=msVerify][data-p=open_press]"); time.sleep(0.3)
    ok("tap marks a setting checked", pg.evaluate("document.querySelector('#msSetup [data-p=open_press]').classList.contains('on')") and "1/" in pg.inner_text("#msSetup .sec-hd .meta"))
    ok("setup step progress unchanged by machine settings", pg.evaluate("document.querySelector('.bigprog .n').textContent") == sp_before)
    pg.evaluate("document.querySelector('#msSetup').scrollIntoView()"); time.sleep(0.2)
    pg.screenshot(path=SHOTS + "ms-5-setup.png")
    pg.click(".setupbar [data-act=resetChecklist]"); time.sleep(0.3)
    ok("Reset clears the machine settings checks too", pg.evaluate("!document.querySelector('#msSetup .ms-step.on')"))

    # ---------- 5. print ----------
    pg.goto(BASE + f"#/job/{jid}/print"); pg.wait_for_selector("#printArea .rs-page"); time.sleep(1.0)
    ok("reference sheet: machine settings page", pg.query_selector(".rs-page.msp") is not None)
    ok("two tables side by side", pg.evaluate("document.querySelectorAll('.rs-page.msp .ms-t').length") == 2 and pg.evaluate("(()=>{ const t=document.querySelectorAll('.rs-page.msp .ms-t'); const a=t[0].getBoundingClientRect(), b=t[1].getBoundingClientRect(); return b.left>a.right-1 && Math.abs(a.top-b.top)<2; })()"))
    ok("Value(s) header spans 3 sub-columns", pg.evaluate("[...document.querySelectorAll('.rs-page.msp .ms-t th')].some(th=>th.textContent==='Value(s)' && th.colSpan===3)"))
    ok("Function / Parameter rows like the form (48 rows)", pg.evaluate("document.querySelectorAll('.rs-page.msp .ms-t tbody tr').length") == 48)
    cells = pg.evaluate("(()=>{ const out={}; document.querySelectorAll('.rs-page.msp .ms-t tbody tr').forEach(tr=>{ const p=tr.querySelector('td.p').textContent; out[p]=[...tr.querySelectorAll('td.v')].map(td=>td.textContent); }); return out; })()")
    ok("staged row → 3 cells (opening pressures 35 | 20 | 20)", cells.get("opening pressures") == ["35","20","20"], cells.get("opening pressures"))
    ok("4th value printed after '/' (backpressure 0 | 0 | 0 / 70)", cells.get("backpressure") == ["0","0","0 / 70"], cells.get("backpressure"))
    ok("same for all printed as one merged cell", cells.get("injection pressures") == ["← 70 →"], cells.get("injection pressures"))
    ok("blank rows print blank (3 empty sub-cells / 1 empty cell)", cells.get("forward pressures") in ([""], ["","",""]) and cells.get("setpoint: zone 5") == [""], (cells.get("forward pressures"), cells.get("setpoint: zone 5")))
    ok("checkbox printed ✓", cells.get("corepull?") == ["✓"], cells.get("corepull?"))
    ok("header line: part number / machine / date (part number as picked in the conflict)", "PSP-99" in pg.inner_text(".rs-page.msp .ms-sh-hd"), pg.inner_text(".rs-page.msp .ms-sh-hd"))
    pages = pg.evaluate("[...document.querySelectorAll('.rs-page')].map(p=>p.className)")
    ok("page 1 still first; settings page numbered", pages[0].startswith("rs-page first") and "Page" in pg.inner_text(".rs-page.msp .rs-ft"), pages)
    pg.evaluate("document.querySelector('.rs-page.msp').scrollIntoView()")
    pg.set_viewport_size({"width": 816, "height": 1056}); time.sleep(0.8); clear_toast(pg)
    pg.evaluate("(()=>{ const w=document.getElementById('printArea'); })()")
    pg.locator(".rs-page.msp").screenshot(path=SHOTS + "ms-3-printed-settings.png")
    pg.set_viewport_size({"width": 412, "height": 915})
    pg.click("[data-act=setLayout][data-v=process]"); pg.wait_for_selector(".ps"); time.sleep(0.5)
    ok("process sheet: machine settings block with the two tables", pg.query_selector(".ps-ms .ms-t") is not None and pg.evaluate("document.querySelectorAll('.ps-ms .ms-t').length") == 2)
    pg.click("[data-act=setLayout][data-v=reference]")

    # ---------- 6. template defaults ----------
    pg.goto(BASE + f"#/job/{jid}"); pg.wait_for_selector("#msCard")
    pg.click("[data-act=saveTemplate]"); pg.wait_for_selector("#tplName"); pg.fill("#tplName", "PSP 36 on 1-250"); pg.click("[data-act=saveTemplateGo]"); time.sleep(0.5)
    t = pg.evaluate("__tjl.state.templates.find(t=>t.name==='PSP 36 on 1-250')")
    ok("template stores the machine settings", t and t["data"]["machineSettings"]["rows"]["open_press"]["vals"] == ["35","20","20"], t and t["data"].get("machineSettings", {}).get("rows", {}).get("open_press"))
    ok("template has no setup checks", t and "verified" not in t["data"]["machineSettings"])
    pg.goto(BASE + "#/templates"); pg.wait_for_selector(".jobcard")
    ok("templates list shows machine-settings count + ⚙️ Settings", "machine settings" in pg.inner_text("#app") and pg.query_selector(f"[data-act=tplMs][data-id='{t['id']}']") is not None)
    pg.click(f"[data-act=tplMs][data-id='{t['id']}']"); pg.wait_for_selector("#msCard")
    ok("template editor opens (#/templates/<id>/ms)", "/ms" in pg.url and "Machine settings" in pg.inner_text("#app"))
    open_sec(pg, "clamp")
    pg.fill("#msCard input[data-msv=clamp_tonnage][data-msi='0']", "185")
    pg.fill("#msCard [data-msh=date]", "10/15/26"); time.sleep(0.8)
    t = pg.evaluate(f"__tjl.state.templates.find(t=>t.id==='{t['id']}')")
    ok("template editor saves defaults", t["data"]["machineSettings"]["rows"]["clamp_tonnage"]["vals"] == ["185","",""], t["data"]["machineSettings"]["rows"].get("clamp_tonnage"))
    open_sec(pg, "injection"); time.sleep(0.3)
    tall_shot(pg, SHOTS + "ms-4-template-editor.png", "#app")
    pg.reload(); pg.wait_for_selector("#msCard")
    ok("template editor survives reload", pg.evaluate("document.querySelector('#msCard input[data-msv=clamp_tonnage]').value") == "185")
    pg.goto(BASE + "#/templates"); pg.wait_for_selector(".jobcard")
    pg.click(f"[data-act=useTemplate][data-id='{t['id']}']"); pg.wait_for_selector("#msCard"); time.sleep(0.4)
    nj = pg.evaluate("__tjl.state.jobs.find(j=>j.id===__tjl.state.route.id)")
    ok("new job from template copies the defaults", nj["machineSettings"]["rows"]["clamp_tonnage"]["vals"] == ["185","",""] and nj["machineSettings"]["rows"]["inj_press"]["same"], nj["machineSettings"]["rows"].get("clamp_tonnage"))
    ok("…but not the date", nj["machineSettings"]["header"]["date"] == "")
    pg.fill("#msCard input[data-msv=clamp_tonnage][data-msi='0']", "190") if pg.is_visible("#msCard input[data-msv=clamp_tonnage][data-msi='0']") else (open_sec(pg, "clamp"), pg.fill("#msCard input[data-msv=clamp_tonnage][data-msi='0']", "190"))
    time.sleep(0.6)
    t = pg.evaluate(f"__tjl.state.templates.find(t=>t.id==='{t['id']}')")
    ok("editing the new job doesn't change the template", t["data"]["machineSettings"]["rows"]["clamp_tonnage"]["vals"] == ["185","",""])
    # save-as-template without values clears machine settings too
    pg.click("[data-act=saveTemplate]"); pg.wait_for_selector("#tplName"); pg.fill("#tplName", "Blank PSP"); pg.uncheck("#tplVals"); pg.click("[data-act=saveTemplateGo]"); time.sleep(0.4)
    tb = pg.evaluate("__tjl.state.templates.find(t=>t.name==='Blank PSP')")
    ok("template without values: machine settings left empty", tb and tb["data"]["machineSettings"]["rows"] == {})

    # ---------- 7. other documents still scan the old way ----------
    pg.goto(BASE + "#/"); pg.wait_for_selector(".fab"); pg.click(".fab"); pg.click("[data-act=newBlank]"); pg.wait_for_selector("#h_tool")
    scan_here(pg, [BOM])
    ok("BOM photo: not taken for a machine settings sheet", pg.evaluate("!__tjl.state.modal.ms") and pg.query_selector("#msRvHd") is None)
    ok("BOM photo: normal review items as before", pg.evaluate("__tjl.state.modal.items.length") >= 3)
    ok("BOM photo: upright page not rotated", pg.evaluate("window.__lastScan.pages[0].rot") == 0)
    pg.click("[data-act=closeModal]")

    # ---------- 8. other turns of the same sheet (in-page, same scan code path) ----------
    for deg in (90, 180, 270):
        res = pg.evaluate("""async ([deg]) => {
          const b = await (await fetch('tests/fixtures/real-machine-settings.jpg')).blob();
          const im = await new Promise(r => { const i = new Image(); i.onload = () => r(i); i.src = URL.createObjectURL(b); });
          const c = document.createElement('canvas'); const q = deg % 180 ? 1 : 0;
          c.width = q ? im.height : im.width; c.height = q ? im.width : im.height;
          const g = c.getContext('2d'); g.translate(c.width/2, c.height/2); g.rotate(deg*Math.PI/180); g.drawImage(im, -im.width/2, -im.height/2);
          const r = await __tjl.ms.scan(c, 'turned'); return {rot:r.rot, found:r.ms? r.ms.found : 0};
        }""", [deg])
        need = (270 - deg) % 360   # the photo needs 270°; turning it by `deg` first changes what the app must do
        ok(f"photo turned another {deg}° → app turns it {need}° and finds all 48 rows", res["rot"] == need and res["found"] == 48, res)
    bad = [e for e in errors if "Failed to load resource" not in e]  # same rule as the other suites (OCR warm-up fetch races)
    ok("no page errors / console errors", not bad, (bad[:5], FAILED[:5]))
    b.close()
n = sum(1 for r in results if r[1]); print("%d checks, %d passed, %d failed" % (len(results), n, len(results)-n))
sys.exit(0 if n == len(results) else 1)
