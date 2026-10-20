"""v2.6.0: Yizumi-HPM UN540 A5-N (Machine 3) screen photos → Machine Settings. Six screens scanned at once from the job's Scan
button, auto-detected (not TMC, not paper), merged into one review grid with box pictures, applied, extras into Notes.
Accuracy per screen on replica photos (normal + hard: more blur / tilt). Screenshots -> shots/yz-*.png"""
import json, os, sys, time, base64
from playwright.sync_api import sync_playwright
BASE = os.environ.get("TJL_BASE", "http://localhost:8766/")
APP = "/workspace/tooling-job-log-v2/"; SHOTS = APP + "shots/"; FIX = APP + "tests/fixtures/"
SCR = ["mold", "injection", "plasticize", "heating", "ejector", "nozzle"]
T = {
 "mold": {"cl1.0":"580","cl1.1":"50","cl1.2":"12.00","cl2.0":"580","cl2.1":"55","cl2.2":"3.15","cl3.0":"580","cl3.1":"55","cl3.2":"0.59","clpr.0":"500","clpr.1":"40","clpr.2":"0.31","clhp.0":"2520","clhp.1":"50",
   "prot.0":"0.11","prot.1":"3.00","protFT.0":"0.59","protFT.1":"0.31","force.0":"559.6","force.1":"520.0","op1.0":"800","op1.1":"50","op1.2":"12.00","op2.0":"700","op2.1":"50","op2.2":"19.00","opE.0":"600","opE.1":"50","opE.2":"20.00"},
 "injection": {"in1.0":"1700","in1.1":"21","in1.2":"2.50","in2.0":"1700","in2.1":"20","in2.2":"1.00","inE.0":"1700","inE.1":"19","stroke.0":"9.70","allow.0":"2538","coPos.0":"1.10","coTime.0":"11.50","coPress.0":"1679","coAct.0":"2.00"},
 "plasticize": {"plE.0":"75","plE.1":"50","plE.2":"9.40","dly.0":"0.80","dly.1":"0.80","decA.0":"500","decA.1":"50","decA.2":"0.30"},
 "heating": {"set.%d"%i:"400.0" for i in range(7)} | {"tolH.0":"50.0","tolL.0":"50.0","stby.0":"275","oil.0":"90"},
 "ejector": {"efE.0":"500","efE.1":"20","efE.2":"4.20","shake.0":"1","ebE.0":"350","ebE.1":"60","ebE.2":"0.25"},
 "nozzle": {"bf.0":"750","bf.1":"25","af.0":"500","af.1":"10","af.2":"0.00","af.3":"0.00","cf.0":"250","cf.1":"25","bu.0":"0.00","bu.1":"0.10","bk.0":"363","bk.1":"20","bk.2":"7.57","bk.3":"2.00"}}
IDS = {"mold":"yz-mold","injection":"yz-inject","plasticize":"yz-plast","heating":"yz-heat","ejector":"yz-eject","nozzle":"yz-nozzle"}
EXP = {"close_press":["580","580","580"],"close_speed":["50","55","55"],"close_int":["12.00","3.15","0.59"],"open_press":["800","700","600"],"open_speed":["50","50","50"],"open_int":["12.00","19.00","20.00"],
  "clamp_tonnage":["520.0"],"inj_press":["1700","1700","1700"],"inj_speed":["21","20","19"],"inj_int":["2.50","1.00",""],"switchover":["1.10"],
  "back_press":["75","",""],"screw_speed":["50","",""],"screw_int":["9.40","",""],"charge_delay":["0.80","",""],"suck_back":["0.30"],
  **{"zone%d"%i:["400.0"] for i in range(1,8)},
  "ej_fwd_press":["500","",""],"ej_fwd_speed":["20","",""],"ej_fwd_int":["4.20","",""],"ej_strokes":["1"],"ej_back_press":["350"],"ej_back_speed":["60"],"ej_back_set":["0.25"]}
errors = []; results = []
def ok(name, cond, extra=""):
    results.append((name, bool(cond), extra)); print(("PASS " if cond else "FAIL ") + name + (" — " + str(extra)[:600] if extra != "" else ""), flush=True)
def tall_shot(pg, path, sel="#modalRoot .sheet"):
    pg.evaluate("document.getElementById('toastRoot') && (document.getElementById('toastRoot').innerHTML='')")
    h = pg.evaluate("(sel)=>{const s=document.querySelector(sel); return s? s.scrollHeight+140 : document.documentElement.scrollHeight}", sel)
    pg.set_viewport_size({"width":412, "height":min(int(h), 16000)}); time.sleep(0.5)
    pg.locator(sel).screenshot(path=path); pg.set_viewport_size({"width":412, "height":915})
def durl(f): return "data:image/jpeg;base64," + base64.b64encode(open(f, "rb").read()).decode()
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
    c = b.new_context(viewport={"width":412,"height":915}, device_scale_factor=2, is_mobile=True, has_touch=True,
        user_agent="Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Mobile Safari/537.36")
    c.route("https://script.google.com/**", lambda r: r.fulfill(status=200, content_type="text/plain", body="no"))
    pg = c.new_page()
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(BASE + "#/"); pg.wait_for_selector(".jobcard")
    ver = pg.evaluate("document.documentElement.innerHTML.match(/APP_VERSION = \"([\\d.]+)\"/)[1]")
    ok("app version " + ver, ver >= "2.6.0" or os.environ.get("TJL_ALLOW_OLD"), ver)
    # detection: Yizumi look vs TMC LCD vs paper forms
    det = {}
    for f in ["yizumi-mold.jpg", "yizumi-heating-hard.jpg", "real-tmc250e-ejclamp.jpg", "real-machine-settings.jpg", "real-work-instructions.jpg", "real-bom.jpg", "real-netsuite-item.jpg", "scan-mold-sheet.png"]:
        det[f] = pg.evaluate("async(d)=>{const im=new Image(); im.src=d; await im.decode(); return [__tjl.ms.screenLooks(im), __tjl.ms.yzLooks(im)]}", durl(FIX + f))
    ok("Yizumi photos look like a Yizumi screen", all(det[f][1] and not det[f][0] for f in ["yizumi-mold.jpg", "yizumi-heating-hard.jpg"]), det)
    ok("TMC photo and paper forms are not taken for Yizumi", not any(det[f][1] for f in det if not f.startswith("yizumi")), det)
    # accuracy per screen, direct reader
    acc = {}
    for var in ["", "-hard"]:
        for s in SCR:
            r = pg.evaluate("async(d)=>{const im=new Image(); im.src=d; await im.decode(); const t=performance.now(); const r=await __tjl.ms.yzRead(im); return {ms:performance.now()-t, scr:r.screen&&r.screen.id, slots:r.slots||{}, date:r.header.date&&r.header.date.value}}", durl(FIX + f"yizumi-{s}{var}.jpg"))
            good = [k for k, v in T[s].items() if (r["slots"].get(k) or {}).get("v") == v]
            bad = {k: ((r["slots"].get(k) or {}).get("v"), v, (r["slots"].get(k) or {}).get("c")) for k, v in T[s].items() if k not in good}
            wrong_sure = {k: x for k, x in bad.items() if x[0] and (x[2] or 0) >= 0.6}
            acc[s + var] = (len(good), len(T[s]), r["scr"] == IDS[s], round(r["ms"] / 1000, 1), bad, wrong_sure, r["date"])
            print("ACCURACY %-16s %2d/%2d screen=%s %.1fs date=%s wrong=%s confident-wrong=%s" % (s + var, len(good), len(T[s]), r["scr"], r["ms"]/1000, r["date"], bad, wrong_sure), flush=True)
    ok("every screen type identified (normal + hard)", all(a[2] for a in acc.values()), {k: a[2] for k, a in acc.items()})
    tg = sum(acc[s][0] for s in SCR); tn = sum(acc[s][1] for s in SCR)
    ok("normal photos ≥ 95%% of values right (%d/%d)" % (tg, tn), tg >= tn * 0.95)
    th = sum(acc[s + "-hard"][0] for s in SCR)
    ok("hard photos ≥ 85%% right (%d/%d)" % (th, tn), th >= tn * 0.85)
    ok("normal photos: no wrong value with high confidence", not any(acc[s][5] for s in SCR), {s: acc[s][5] for s in SCR})
    ok("status-bar date read", acc["mold"][6] == "10/20/26", acc["mold"][6])
    # full flow: six photos at once from the job's Scan button
    pg.click(".fab"); pg.click("[data-act=newBlank]"); pg.wait_for_selector("#h_tool")
    jid = pg.evaluate("__tjl.state.route.id"); pg.fill("#h_tool", "T-YZ540"); time.sleep(0.4)
    pg.goto(BASE + f"#/job/{jid}"); pg.wait_for_selector("#msCard")
    pg.click("#msCard [data-act=msScan]")
    with pg.expect_file_chooser() as fc: pg.click("[data-act=scanHere][data-kind=img]")
    fc.value.set_files([FIX + f"yizumi-{s}.jpg" for s in SCR]); t0 = time.time()
    pg.wait_for_selector(".sheet h3:has-text('Review')", timeout=600000); time.sleep(0.3)
    took = time.time() - t0
    ok("six screens scanned in one go (%.0f s)" % took, took < 300, round(took))
    M = pg.evaluate("({kind:__tjl.state.modal.ms.kind, screen:__tjl.state.modal.ms.screen, found:__tjl.state.modal.ms.found, total:__tjl.state.modal.ms.total, notes:__tjl.state.modal.ms.screenNotes, hdr:__tjl.state.modal.ms.header})")
    ok("auto-detected as machine screens, all six merged", M["kind"] == "screen" and all(x in (M["screen"] or "") for x in ["Mold", "Injection", "Plasticize", "Heating", "Ejector", "Nozzle"]), M["screen"])
    rows = pg.evaluate("__tjl.state.modal.ms.rows.map(r=>({id:r.id, vals:r.vals.slice(), conf:r.conf, sel:!!r.selected, crop:(r.crop||'').length}))")
    by = {r["id"]: r for r in rows}
    ok("all %d mapped settings present" % len(EXP), all(f in by for f in EXP), [f for f in EXP if f not in by])
    right = [f for f in EXP if f in by and by[f]["vals"][:len(EXP[f])] == EXP[f]]
    print("ACCURACY review rows: %d/%d" % (len(right), len(EXP)), {f: (by.get(f, {}).get("vals"), EXP[f]) for f in EXP if f not in right})
    ok("review rows ≥ %d/%d right" % (len(EXP) - 2, len(EXP)), len(right) >= len(EXP) - 2)
    ok("no wrong row pre-checked", not [f for f in EXP if f in by and f not in right and by[f]["sel"]])
    ok("every row has its box picture", all(r["crop"] > 800 for r in rows), [r["id"] for r in rows if r["crop"] <= 800])
    nv = (M["notes"] or {}).get("value", "")
    ok("extras go to Notes (protect, cut off, decompression, tolerance, nozzle)", all(x in nv for x in ["2520", "1679", "Decompression", "Standby", "363", "Continuous", "559.6"]), nv)
    pg.evaluate("(()=>{ const st=document.createElement('style'); st.id='shotcss'; st.textContent='.topbar{position:static!important} .bottombar{display:none!important}'; document.head.appendChild(st); })()")
    pg.screenshot(path=SHOTS + "yz-1-review-top.png")
    tall_shot(pg, SHOTS + "yz-2-review-full.png")
    pg.evaluate("document.getElementById('shotcss').remove()")
    idx = {r["id"]: i for i, r in enumerate(rows)}
    for f in EXP:
        if f in by and f not in right:
            for i, v in enumerate(EXP[f]):
                if v and pg.query_selector(f"[data-msrv='{idx[f]}'][data-msri='{i}']"): pg.fill(f"[data-msrv='{idx[f]}'][data-msri='{i}']", v)
    for r in pg.evaluate("__tjl.state.modal.ms.rows.map(r=>!!r.selected)") and rows:
        pass
    for i, s_ in enumerate(pg.evaluate("__tjl.state.modal.ms.rows.map(r=>!!r.selected)")):
        if not s_: pg.check(f"[data-msrchk='{i}']")
    pg.click("[data-act=rvApply]"); time.sleep(0.8)
    ms = pg.evaluate(f"__tjl.state.jobs.find(j=>j.id==='{jid}').machineSettings")
    got = {f: (ms["rows"].get(f, {}).get("vals") or [])[:len(EXP[f])] for f in EXP}
    ok("saved Machine Settings match the screens", all(got[f] == EXP[f] for f in EXP), {f: (got[f], EXP[f]) for f in EXP if got[f] != EXP[f]})
    ok("Notes saved with Machine 3 extras", "Machine 3" in ms["notes"] and "Nozzle" in ms["notes"], ms["notes"][:300])
    pg.goto(BASE + f"#/job/{jid}"); pg.wait_for_selector("#msCard")
    pg.evaluate("(()=>{ const st=document.createElement('style'); st.id='shotcss'; st.textContent='.topbar{position:static!important} .bottombar{display:none!important}'; document.head.appendChild(st); })()")
    for sec in ["clamp", "injection", "temperature"]:
        pg.click(f"#msCard [data-act=msSec][data-sec={sec}]"); time.sleep(0.2)
    pg.locator("#msCard").screenshot(path=SHOTS + "yz-3-saved.png")
    ok("no page errors", not [e for e in errors if "Tesseract" not in e], errors[:5])
    json.dump({k: list(v[:4]) + [v[4]] for k, v in acc.items()}, open("/tmp/yz_acc.json", "w"), indent=1)
    b.close()
fails = [r for r in results if not r[1]]
print("\n%d/%d passed" % (len(results)-len(fails), len(results)))
sys.exit(1 if fails else 0)
