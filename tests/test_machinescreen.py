"""v2.5.0: scan a photo of the press controller screen (TMC 250E ejector / clamp screen) from the job's Scan button.
Auto-detects screen vs paper sheet, reads the boxed values, maps them onto Machine Settings, shows the review grid with box
pictures, flags glare/cursor boxes, applies, puts unmapped values in Notes. Accuracy vs a hand reading of the photo.
Screenshots -> shots/scr-*.png"""
import json, os, sys, time
from playwright.sync_api import sync_playwright
BASE = os.environ.get("TJL_BASE", "http://localhost:8766/")
APP = "/workspace/tooling-job-log-v2/"; SHOTS = APP + "shots/"; FIX = APP + "tests/fixtures/"
PHOTO = FIX + "real-tmc250e-ejclamp.jpg"; TILT = FIX + "real-tmc250e-ejclamp-tilted.jpg"
T = json.load(open(FIX + "real-tmc250e-ejclamp.truth.json"))
FIELDS = {"ej_fwd_press":["ejP1","ejP2","ejP3"], "ej_fwd_speed":["ejS1","ejS2","ejS3"], "ej_fwd_int":["ejT1","ejT2","ejT3"], "ej_strokes":["ejCnt"],
  "open_press":["opP1","opP2","opP3"], "open_int":["opX1","opX2","opX3"], "open_speed":["opS1","opS2","opS3"],
  "close_press":["clP1","clP2","clP3"], "close_int":["clX1","clX2","clX3"], "close_speed":["clS1","clS2","clS3"]}
HARD = {"opP2", "opS2"}  # glare over the box / cursor highlight on the photo
errors = []; results = []
def ok(name, cond, extra=""):
    results.append((name, bool(cond), extra)); print(("PASS " if cond else "FAIL ") + name + (" — " + str(extra)[:500] if extra != "" else ""), flush=True)
def tall_shot(pg, path, sel="#modalRoot .sheet"):
    pg.evaluate("document.getElementById('toastRoot') && (document.getElementById('toastRoot').innerHTML='')")
    h = pg.evaluate("(sel)=>{const s=document.querySelector(sel); return s? s.scrollHeight+140 : document.documentElement.scrollHeight}", sel)
    pg.set_viewport_size({"width":412, "height":min(int(h), 16000)}); time.sleep(0.5)
    pg.locator(sel).screenshot(path=path); pg.set_viewport_size({"width":412, "height":915})
def scan_card(pg, files):
    pg.click("#msCard [data-act=msScan]")
    with pg.expect_file_chooser() as fc: pg.click("[data-act=scanHere][data-kind=img]")
    fc.value.set_files(files); t = time.time()
    pg.wait_for_selector(".sheet h3:has-text('Review')", timeout=300000); time.sleep(0.3)
    return time.time() - t
ROWS = "__tjl.state.modal.ms.rows.map(r=>({id:r.id, vals:r.vals.slice(), conf:r.conf, state:r.state, sel:!!r.selected, crop:(r.crop||'').length}))"
def score(rows):
    by = {r["id"]: r for r in rows}; good = n = 0; wrong = []; wrong_sel = []; hard_flag = []
    for fid, ks in FIELDS.items():
        r = by.get(fid)
        for i, k in enumerate(ks):
            n += 1; g = (r["vals"][i] if r else "").strip()
            if g == T[k]: good += 1
            else:
                wrong.append((fid, i+1, g, T[k]))
                if r and r["sel"]: wrong_sel.append(fid)
            if k in HARD and r: hard_flag.append(not r["sel"])
    return good, n, wrong, wrong_sel, hard_flag

with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
    c = b.new_context(viewport={"width":412,"height":915}, device_scale_factor=2, is_mobile=True, has_touch=True,
        user_agent="Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Mobile Safari/537.36")
    c.route("https://script.google.com/**", lambda r: r.fulfill(status=200, content_type="text/plain", body="no"))
    pg = c.new_page()
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.on("console", lambda m: errors.append(m.text) if m.type=="error" and "favicon" not in m.text and "Failed to load resource" not in m.text else None)
    pg.goto(BASE + "#/"); pg.wait_for_selector(".jobcard")
    ver = pg.evaluate("document.documentElement.innerHTML.match(/APP_VERSION = \"([\\d.]+)\"/)[1]")
    ok("app version " + ver, ver >= "2.5.0" or os.environ.get("TJL_ALLOW_OLD"), ver)
    # fresh job
    pg.click(".fab"); pg.click("[data-act=newBlank]"); pg.wait_for_selector("#h_tool")
    jid = pg.evaluate("__tjl.state.route.id"); pg.fill("#h_tool", "T-TMC250"); time.sleep(0.4)
    pg.goto(BASE + f"#/job/{jid}"); pg.wait_for_selector("#msCard")
    ok("Scan button mentions the machine screen", "machine screen" in pg.get_attribute("#msCard [data-act=msScan]", "aria-label") and "machine’s screen" in pg.inner_text("#msCard"))

    took = scan_card(pg, [PHOTO])
    ok("screen scan finished (%.0f s)" % took, took < 120, round(took))
    M = pg.evaluate("({kind:__tjl.state.modal.ms.kind, screen:__tjl.state.modal.ms.screen, found:__tjl.state.modal.ms.found, total:__tjl.state.modal.ms.total, notes:__tjl.state.modal.ms.screenNotes, hdr:__tjl.state.modal.ms.header})")
    ok("auto-detected as a machine screen (not a paper sheet)", M["kind"] == "screen" and "TMC 250E" in (M["screen"] or ""), M["screen"])
    ok("review heading names the screen", "machine screen" in pg.inner_text("#msRvHd").lower() and pg.query_selector("#msRvScreen") is not None)
    ok("value boxes found ≥ 30 of 37", M["found"] >= 30, (M["found"], M["total"]))
    rows = pg.evaluate(ROWS)
    ok("10 settings rows mapped", sorted(r["id"] for r in rows) == sorted(FIELDS), [r["id"] for r in rows])
    ok("every row has its box picture", all(r["crop"] > 1000 for r in rows))
    ncrop = pg.evaluate("[...document.querySelectorAll('#modalRoot .msr img.crop')].filter(i=>i.complete && i.naturalWidth>50).length")
    ok("box pictures render", ncrop >= 10, ncrop)
    good, n, wrong, wrong_sel, hard = score(rows)
    print("ACCURACY mapped values: %d/%d" % (good, n), wrong)
    ok("mapped values ≥ 26/28 right", good >= 26, (good, n, wrong))
    ok("no wrong value pre-checked", not wrong_sel, wrong_sel)
    ok("glare / cursor boxes flagged (unchecked)", hard and all(hard), hard)
    ok("other values go to Notes (PT K.O. 1500, open PT2 2100, close PT 1450, position 2297)", M["notes"] and all(x in M["notes"]["value"] for x in ["1500", "2100", "1450", "2297"]), M["notes"])
    ok("status-line date read (unchecked for checking)", M["hdr"].get("date") is not None, M["hdr"].get("date", {}).get("value") if M["hdr"].get("date") else None)
    pg.evaluate("(()=>{ const st=document.createElement('style'); st.id='shotcss'; st.textContent='.topbar{position:static!important} .bottombar{display:none!important}'; document.head.appendChild(st); })()")
    pg.screenshot(path=SHOTS + "scr-1-review-top.png")
    tall_shot(pg, SHOTS + "scr-2-review-full.png")
    pg.evaluate("document.getElementById('shotcss').remove()")
    # Allen fixes the two flagged boxes, checks them, applies
    idx = {r["id"]: i for i, r in enumerate(rows)}
    pg.fill(f"[data-msrv='{idx['open_press']}'][data-msri='1']", "050")
    pg.fill(f"[data-msrv='{idx['open_speed']}'][data-msri='1']", "40")
    sel = pg.evaluate(f"[__tjl.state.modal.ms.rows[{idx['open_press']}].selected, __tjl.state.modal.ms.rows[{idx['open_speed']}].selected]")
    ok("typing a fix checks the row", sel == [True, True], sel)
    for r in rows:
        if not r["sel"] and r["id"] not in ("open_press", "open_speed"): pg.check(f"[data-msrchk='{idx[r['id']]}']")
    pg.click("[data-act=rvApply]"); time.sleep(0.8)
    ms = pg.evaluate(f"__tjl.state.jobs.find(j=>j.id==='{jid}').machineSettings")
    exp = {f: [T[k] for k in ks] for f, ks in FIELDS.items()}
    got = {f: (ms["rows"].get(f, {}).get("vals") or [])[:len(exp[f])] for f in FIELDS}
    ok("saved Machine Settings match the screen", all(got[f] == exp[f] for f in FIELDS), {f:(got[f],exp[f]) for f in FIELDS if got[f]!=exp[f]})
    ok("Notes got the other screen values", "TMC 250E" in ms["notes"] and "2297" in ms["notes"], ms["notes"])
    # editor shows them
    pg.goto(BASE + f"#/job/{jid}"); pg.wait_for_selector("#msCard")
    pg.click("#msCard [data-act=msSec][data-sec=clamp]"); time.sleep(0.3)
    v = pg.evaluate("[...document.querySelectorAll('#msCard input[data-msv=close_press]')].slice(0,3).map(e=>e.value)")
    ok("editor shows Closing pressures 050/030/120", v == ["050","030","120"], v)
    pg.evaluate("(()=>{ const st=document.createElement('style'); st.id='shotcss'; st.textContent='.topbar{position:static!important} .bottombar{display:none!important}'; document.head.appendChild(st); })()")
    pg.locator("#msCard").screenshot(path=SHOTS + "scr-3-saved-clamp.png")
    pg.evaluate("document.getElementById('shotcss').remove()")

    # second photo: same screen rotated 4°, smaller, darker, cropped differently
    pg.goto(BASE + f"#/job/{jid}"); pg.wait_for_selector("#msCard")
    scan_card(pg, [TILT])
    rows2 = pg.evaluate(ROWS); good2, n2, wrong2, wsel2, _ = score(rows2)
    print("ACCURACY tilted copy: %d/%d" % (good2, n2), wrong2)
    ok("tilted/smaller copy still read (≥ 24/28) and detected as screen", good2 >= 24 and pg.evaluate("__tjl.state.modal.ms.kind") == "screen", (good2, wrong2))
    ok("tilted copy: no wrong value pre-checked", not wsel2, wsel2)
    pg.click("[data-act=closeModal]")
    ok("no page errors", not [e for e in errors if "Tesseract" not in e], errors[:5])
    b.close()
fails = [r for r in results if not r[1]]
print("\n%d/%d passed" % (len(results)-len(fails), len(results)))
sys.exit(1 if fails else 0)
