"""v2.2.0 checks: Arrange photos screen (sheet-mirroring grid, touch long-press drag, mouse drag, auto-scroll,
action sheet: move to position / first / last / earlier / later, change label, replace, rotate, delete + undo,
preset sort + undo, persistence, print-sheet order). Screenshots -> shots/11*.png"""
import time, glob
from playwright.sync_api import sync_playwright
BASE = "http://localhost:8766/"
SHOTS = "/workspace/tooling-job-log-v2/shots/"
T = "/workspace/tjl2-test/"
PHOTOS = sorted(glob.glob(T+"photos/p*.jpg"))
P = __import__("json").loads  # noqa
errors = []; results = []
def ok(name, cond, extra=""):
    results.append((name, bool(cond), extra)); print(("PASS " if cond else "FAIL ") + name + (" — " + str(extra) if extra else ""), flush=True)
def clear_toast(pg): pg.evaluate("document.getElementById('toastRoot') && (document.getElementById('toastRoot').innerHTML='')")
def watch(pg, tag):
    pg.on("response", lambda r: errors.append(tag+" HTTP %d %s" % (r.status, r.url)) if r.status>=400 and not r.url.endswith("/favicon.ico") else None)
    pg.on("console", lambda m: errors.append(tag+" console."+m.type+": "+m.text) if m.type=="error" else None)
    pg.on("pageerror", lambda e: errors.append(tag+" pageerror: "+str(e)))
JOB = "__tjl.state.jobs.find(j=>j.id===__tjl.state.route.id)"
def labels(pg): return pg.evaluate(JOB+".photos.map(p=>p.label)")
def ids(pg): return pg.evaluate(JOB+".photos.map(p=>p.id)")
def grid_labels(pg): return pg.evaluate("[...document.querySelectorAll('#arrGrid .arr-cell[data-id] .arr-lab')].map(e=>e.textContent)")
def center(pg, k):
    return pg.evaluate("(k)=>{const r=document.querySelector(`#arrGrid .arr-slot[data-slot='${k}']`).getBoundingClientRect();return [r.left+r.width/2, r.top+r.height/2]}", k)
def doc_center(pg, k):
    return pg.evaluate("(k)=>{const r=document.querySelector(`#arrGrid .arr-slot[data-slot='${k}']`).getBoundingClientRect();return [r.left+r.width/2, r.top+r.height/2+scrollY]}", k)

with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
    ctx = b.new_context(viewport={"width":412,"height":915}, device_scale_factor=2, is_mobile=True, has_touch=True,
        user_agent="Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Mobile Safari/537.36")
    page = ctx.new_page(); watch(page, "main")
    cdp = ctx.new_cdp_session(page)
    def touch(kind, x=0, y=0):
        cdp.send("Input.dispatchTouchEvent", {"type":kind, "touchPoints":[] if kind=="touchEnd" else [{"x":x, "y":y, "id":1}]})
    def touch_drag(a, bxy, hold=0.4, steps=10, shot=None, release=True):
        touch("touchStart", *a); time.sleep(hold)
        for i in range(1, steps+1):
            touch("touchMove", a[0]+(bxy[0]-a[0])*i/steps, a[1]+(bxy[1]-a[1])*i/steps); time.sleep(0.03)
        time.sleep(0.15)
        if shot: clear_toast(page); page.screenshot(path=shot)
        if release: touch("touchEnd"); time.sleep(0.3)

    page.goto(BASE); page.wait_for_selector(".jobcard"); page.wait_for_function("window.__tjl && __tjl.state.jobs.filter(j=>j.example).length>=3 && __tjl.state.jobs.filter(j=>j.example).every(j=>j.photos.length)", timeout=60000); time.sleep(1)
    ver = page.evaluate("fetch('sw.js').then(r=>r.text()).then(t=>t.match(/VERSION = \"([^\"]+)/)[1])")
    ok("sw VERSION = tjl-v2.6.0", ver=="tjl-v2.6.0", ver)
    page.goto(BASE+"#/settings"); page.wait_for_selector(".hint")
    ok("APP_VERSION 2.6.0 shown in settings", "v2.6.0" in page.inner_text("#app"))

    # ---------- job with 6 uploaded photos, labeled out of template order ----------
    page.goto(BASE+"#/"); page.wait_for_selector(".fab"); page.click(".fab"); page.click("[data-act=newBlank]"); page.wait_for_selector("#h_tool")
    page.fill("#h_tool", "T-8800"); page.fill("#h_part", "Arrange test panel"); page.locator("#h_part").blur()
    with page.expect_file_chooser() as fc: page.click("[data-act=photoLib]")
    fc.value.set_files(PHOTOS[:6]); page.wait_for_selector("[data-act=photoPreset]", timeout=30000)
    order = [4, 0, 8, 1, 2, 10]   # preset indices: top, front A, finished top, rear B, side left, front edge
    want = []
    for k in order:
        page.wait_for_selector("[data-act=photoPreset]"); btn = page.locator("[data-act=photoPreset]").nth(k)
        want.append(btn.get_attribute("data-v")); btn.click(); time.sleep(0.15)
    time.sleep(0.4)
    ok("6 photos uploaded + labeled", labels(page)==want, labels(page))
    ok("Photos section has ↕ Arrange button (old ⇄ Reorder gone)", page.locator("#photosCard [data-act=arrangeOpen]").count()==1 and page.locator("[data-act=photoReorder]").count()==0)
    page.click("#photosCard [data-act=arrangeOpen]"); page.wait_for_selector("#arrGrid .arr-cell[data-id]"); time.sleep(0.6)
    ok("arrange route", page.evaluate("location.hash").endswith("/arrange"), page.evaluate("location.hash"))
    rows = page.evaluate("[...document.querySelectorAll('#arrGrid .arr-row')].map(r=>r.children.length).join(',')")
    ok("grid mirrors sheet rows (6 -> 4,2)", rows=="4,2", rows)
    nums = page.evaluate("[...document.querySelectorAll('#arrGrid .arr-num')].map(e=>e.textContent).join(',')")
    ok("big position numbers 1..6", nums=="1,2,3,4,5,6", nums)
    ok("grid labels = job order", grid_labels(page)==want)
    tgt = page.evaluate("(()=>{const r=document.querySelector('#arrGrid .arr-cell[data-id]').getBoundingClientRect();const b=[...document.querySelectorAll('.arrbar .btn')].map(e=>e.getBoundingClientRect().height);return [r.width, Math.min(...b)]})()")
    ok("big touch targets (cell >= 80px wide, bar buttons >= 56px)", tgt[0]>=80 and tgt[1]>=56, tgt)
    clear_toast(page); page.screenshot(path=SHOTS+"11a-arrange-grid.png")

    # ---------- quick swipe on the grid must NOT pick a photo up ----------
    a = center(page, 1)
    touch("touchStart", *a)
    for i in range(1, 8): touch("touchMove", a[0], a[1]-i*30); time.sleep(0.012)
    touch("touchEnd"); time.sleep(0.5)
    ok("quick swipe doesn't start a drag (scroll wins)", labels(page)==want and page.locator(".arr-ghost").count()==0 and page.locator(".arr-ph").count()==0)
    page.evaluate("window.scrollTo(0,0)"); time.sleep(0.2)

    # ---------- touch long-press drag: #1 -> #4 ----------
    a = center(page, 0); bb = center(page, 3)
    touch_drag(a, bb, shot=SHOTS+"11b-arrange-dragging.png", release=False)
    ph = page.evaluate("(()=>{const e=document.querySelector('#arrGrid .arr-ph');return e? +e.dataset.slot : -1})()")
    ok("while dragging: ghost follows finger + placeholder at drop spot #4", page.locator(".arr-ghost").count()==1 and ph==3, ph)
    touch("touchEnd"); time.sleep(0.4)
    exp = want[1:4]+[want[0]]+want[4:]
    ok("touch drag #1 -> #4 reorders", labels(page)==exp, labels(page))
    ok("no ghost left after drop", page.locator(".arr-ghost").count()==0)
    ok("saved immediately to storage", page.evaluate("JSON.parse(localStorage.getItem('tjl2.jobs')).find(j=>j.toolNumber==='T-8800').photos.map(p=>p.label)")==exp)
    ok("tap after drag didn't open action sheet", page.locator(".arr-mv").count()==0)
    # undo drag via bottom bar
    page.click(".arrbar [data-act=arrUndo]"); time.sleep(0.3)
    ok("Undo (bottom bar) reverts drag", labels(page)==want, labels(page))
    # touch drag backwards #6 -> #2
    touch_drag(center(page, 5), center(page, 1))
    exp = [want[0], want[5]]+want[1:5]
    ok("touch drag #6 -> #2 (across rows)", labels(page)==exp, labels(page))
    cur = labels(page)

    # ---------- tap -> action sheet -> Move to position ----------
    page.locator("#arrGrid .arr-cell[data-slot='4']").click(); page.wait_for_selector(".arr-mv"); time.sleep(0.3)
    ok("tap opens photo action sheet (#5)", "#5" in page.inner_text(".sheet .pos"), page.inner_text(".sheet .pos"))
    clear_toast(page); page.screenshot(path=SHOTS+"11c-photo-actions.png")
    page.click("[data-act=arrMoveTo]"); page.wait_for_selector(".arr-nums"); time.sleep(0.3)
    ok("number picker lists 1..6, current highlighted", page.locator(".arr-nums button").count()==6 and page.inner_text(".arr-nums button.sel")=="5")
    clear_toast(page); page.screenshot(path=SHOTS+"11d-move-to-position.png")
    page.click(".arr-nums button[data-v='2']"); time.sleep(0.4)
    exp = [cur[0], cur[4], cur[1], cur[2], cur[3], cur[5]]
    ok("Move to position 5 -> 2", labels(page)==exp, labels(page))
    ok("moved photo flashes", page.locator("#arrGrid .arr-cell.flash").count()==1)
    cur = labels(page)
    # earlier / later keep the sheet open
    page.locator("#arrGrid .arr-cell[data-slot='2']").click(); page.wait_for_selector(".arr-mv")
    page.click("[data-act=arrMove][data-d='1']"); time.sleep(0.3)
    ok("Later: #3 -> #4, sheet stays open on #4", labels(page)==[cur[0],cur[1],cur[3],cur[2],cur[4],cur[5]] and "#4" in page.inner_text(".sheet .pos"))
    page.click("[data-act=arrMove][data-d='-1']"); time.sleep(0.3)
    ok("Earlier: back to #3", labels(page)==cur)
    page.click("[data-act=arrMove][data-d='last']"); time.sleep(0.3)
    ok("Move last", labels(page)==[cur[0],cur[1],cur[3],cur[4],cur[5],cur[2]] and page.locator(".arr-mv").count()==0)
    page.locator("#arrGrid .arr-cell[data-slot='5']").click(); page.wait_for_selector(".arr-mv")
    page.click("[data-act=arrMove][data-d='first']"); time.sleep(0.3)
    ok("Move first", labels(page)==[cur[2],cur[0],cur[1],cur[3],cur[4],cur[5]])
    page.click("[data-act=toastAct]"); time.sleep(0.3)
    ok("toast UNDO reverts Move first", labels(page)==[cur[0],cur[1],cur[3],cur[4],cur[5],cur[2]])
    cur = labels(page)

    # ---------- change label (custom + preset) ----------
    page.locator("#arrGrid .arr-cell[data-slot='1']").click(); page.wait_for_selector(".arr-mv")
    page.click("[data-act=arrLabel]"); page.wait_for_selector("#plCustom")
    page.fill("#plCustom", "Gate close-up"); page.click("[data-act=photoLabelGo]"); time.sleep(0.3)
    ok("change label (custom text), position kept", labels(page)[1]=="Gate close-up" and grid_labels(page)[1]=="Gate close-up", labels(page))
    page.locator("#arrGrid .arr-cell[data-slot='1']").click(); page.wait_for_selector(".arr-mv")
    page.click("[data-act=arrLabel]"); page.click("[data-act=photoPreset][data-v='Mold insert detail']"); time.sleep(0.3)
    ok("change label (preset)", labels(page)[1]=="Mold insert detail")
    page.click(".arrbar [data-act=arrUndo]"); time.sleep(0.2)
    ok("undo label change", labels(page)[1]=="Gate close-up")
    page.click(".arrbar [data-act=arrUndo]"); time.sleep(0.2)
    ok("undo again -> original label", labels(page)==cur, labels(page))

    # ---------- replace picture (gallery) ----------
    before_ids = ids(page); lab2 = labels(page)[2]
    page.locator("#arrGrid .arr-cell[data-slot='2']").click(); page.wait_for_selector(".arr-mv")
    page.click("[data-act=arrReplace]"); page.wait_for_selector("[data-act=arrReplacePick]")
    with page.expect_file_chooser() as fc: page.click("[data-act=arrReplacePick][data-kind=lib]")
    fc.value.set_files(PHOTOS[9]); page.wait_for_function("(id)=>"+JOB+".photos[2].id!==id", arg=before_ids[2], timeout=15000); time.sleep(0.3)
    after_ids = ids(page)
    ok("replace picture: new image id at same position, label kept, others untouched", after_ids[2]!=before_ids[2] and labels(page)[2]==lab2 and after_ids[:2]==before_ids[:2] and after_ids[3:]==before_ids[3:])
    loaded = page.evaluate("(id)=>{const i=document.querySelector(`#arrGrid img[data-pid='${id}']`);return !!i && i.complete && i.naturalWidth>0}", after_ids[2])
    ok("replaced picture renders in grid", loaded)
    replaced_old = before_ids[2]
    # camera + drive options configure the picker
    page.locator("#arrGrid .arr-cell[data-slot='2']").click(); page.click("[data-act=arrReplace]")
    with page.expect_file_chooser() as fc: page.click("[data-act=arrReplacePick][data-kind=files]")
    acc = page.evaluate("[document.getElementById('inReplace').accept, document.getElementById('inReplace').hasAttribute('capture')]")
    ok("Drive/Files option opens document picker (broad accept, no capture)", "application/pdf" in acc[0] and not acc[1], acc)
    fc.value.set_files([]); time.sleep(0.2)
    page.locator("#arrGrid .arr-cell[data-slot='2']").click(); page.click("[data-act=arrReplace]")
    with page.expect_file_chooser() as fc: page.click("[data-act=arrReplacePick][data-kind=cam]")
    ok("Camera option sets capture=environment", page.evaluate("document.getElementById('inReplace').getAttribute('capture')")=="environment")
    fc.value.set_files([]); time.sleep(0.2)
    ok("cancelled pickers change nothing", ids(page)==after_ids)

    # ---------- rotate 90° ----------
    wh0 = page.evaluate(JOB+".photos[3]"); lab3 = wh0["label"]
    page.locator("#arrGrid .arr-cell[data-slot='3']").click(); page.wait_for_selector(".arr-mv")
    page.click("[data-act=arrRotate]"); page.wait_for_function("(id)=>"+JOB+".photos[3].id!==id", arg=wh0["id"], timeout=15000); time.sleep(0.4)
    wh1 = page.evaluate(JOB+".photos[3]")
    ok("rotate 90°: new compressed image, w/h swapped, label/position kept", wh1["w"]==wh0["h"] and wh1["h"]==wh0["w"] and wh1["label"]==lab3 and wh1["bytes"]<400000, (wh0["w"],wh0["h"],wh1["w"],wh1["h"],wh1["bytes"]))
    real = page.evaluate("(id)=>new Promise(r=>{const q=indexedDB.open('toolingJobLogPhotos');q.onsuccess=()=>{const g=q.result.transaction('photos').objectStore('photos').get(id);g.onsuccess=()=>{const u=URL.createObjectURL(g.result);const im=new Image();im.onload=()=>r([im.naturalWidth,im.naturalHeight,g.result.type]);im.src=u;}}})", wh1["id"])
    ok("stored rotated JPEG has swapped dimensions", real[0]==wh1["w"] and real[1]==wh1["h"] and real[2]=="image/jpeg", real)
    ok("action sheet stays open on the rotated photo", page.locator(".arr-mv").count()==1 and "#4" in page.inner_text(".sheet .pos"))
    page.click(".sheet [data-act=closeModal]"); time.sleep(0.2)
    rotated_old = wh0["id"]

    # ---------- delete + undo ----------
    cur = labels(page); cur_ids = ids(page)
    page.locator("#arrGrid .arr-cell[data-slot='0']").click(); page.wait_for_selector(".arr-mv")
    page.click("[data-act=arrDelete]"); time.sleep(0.3)
    ok("delete photo", labels(page)==cur[1:] and page.locator("#arrGrid .arr-cell[data-id]").count()==5)
    page.click("[data-act=toastAct]"); time.sleep(0.3)
    ok("undo delete restores photo at #1", ids(page)==cur_ids)

    # ---------- sort by preset order ----------
    page.click(".arrbar [data-act=arrSort]"); time.sleep(0.3)
    srt = labels(page)
    rank = page.evaluate("(()=>{const P=['Mold front view (A - cavity side)','Mold rear view (B - core side)','Mold side view (left)','Mold side view (right)','Mold top view','Mold bottom view','Mold insert detail','Side profile view','Finished part - top view','Finished part - bottom view','Finished part - front edge view'];return "+JOB+".photos.map(p=>{const i=P.indexOf(p.label);return i<0?99:i})})()")
    ok("Sort by preset order follows template views, others last", rank==sorted(rank) and srt[0].startswith("Mold front view"), srt)
    page.click("[data-act=toastAct]"); time.sleep(0.3)
    ok("undo sort", labels(page)==cur, labels(page))
    page.click(".arrbar [data-act=arrSort]"); time.sleep(0.3)
    final = labels(page); final_ids = ids(page)

    # ---------- Done -> job photos grid + print sheet match ----------
    page.click(".arrbar [data-act=arrDone]"); page.wait_for_selector("#h_tool"); time.sleep(0.5)
    ok("Done returns to job", page.evaluate("location.hash").endswith(page.evaluate("__tjl.state.route.id")))
    caps = page.evaluate("[...document.querySelectorAll('#photosCard .ph .cap')].map(e=>e.textContent)")
    ok("job Photos grid shows the new order", caps==[l or "Photo" for l in final], caps)
    time.sleep(0.5)
    gone = page.evaluate("(ids)=>new Promise(r=>{const q=indexedDB.open('toolingJobLogPhotos');q.onsuccess=()=>{const st=q.result.transaction('photos').objectStore('photos');const out=[];let n=ids.length;ids.forEach(id=>{const g=st.get(id);g.onsuccess=()=>{out.push(g.result?1:0);if(!--n)r(out)}})}})", [replaced_old, rotated_old])
    ok("replaced/rotated originals cleaned from storage after Done", gone==[0,0], gone)
    page.click(".bottombar button:has-text('Print')"); page.wait_for_selector("#printArea .rs-page")
    page.wait_for_function("()=>[...document.querySelectorAll('#printArea img')].every(i=>i.complete&&i.naturalWidth>0)", timeout=15000)
    pcaps = page.evaluate("[...document.querySelectorAll('#printArea .rs-lab')].map(e=>e.textContent)")
    pids = page.evaluate("[...document.querySelectorAll('#printArea .rs-ph img')].map(e=>e.dataset.pid)")
    ok("print reference sheet captions = arranged order", pcaps==final, pcaps)
    ok("print reference sheet pictures = arranged order (incl. replaced/rotated)", pids==final_ids)
    # print screen -> Arrange photos -> Done -> back on print
    ok("print screen has 'Arrange photos' button", page.locator("#app [data-act=arrangeOpen]").count()==1)
    page.click("#app [data-act=arrangeOpen]"); page.wait_for_selector("#arrGrid .arr-cell[data-id]")
    touch_drag(center(page, 5), center(page, 0))
    moved = labels(page)
    page.click(".arrbar [data-act=arrDone]"); page.wait_for_selector("#printArea .rs-page"); time.sleep(0.4)
    ok("Done from print-launched arrange returns to print screen", page.evaluate("location.hash").endswith("/print"))
    ok("print sheet updated after drag", page.evaluate("[...document.querySelectorAll('#printArea .rs-lab')].map(e=>e.textContent)")==moved and moved[0]==final[5])

    # ---------- 16 photos: page-2 divider, auto-scroll drag ----------
    page.goto(BASE+"#/job/"+page.evaluate("__tjl.state.route.id")); page.wait_for_selector("#h_tool")
    with page.expect_file_chooser() as fc: page.click("[data-act=photoLib]")
    fc.value.set_files(PHOTOS[:10]); page.wait_for_selector("[data-act=photoLabelSkip]", timeout=30000)
    for i in range(10): page.click("[data-act=photoLabelSkip]"); time.sleep(0.1)
    page.click("#photosCard [data-act=arrangeOpen]"); page.wait_for_selector("#arrGrid .arr-cell[data-id]"); time.sleep(0.5)
    pg_hdr = page.evaluate("[...document.querySelectorAll('#arrGrid .arr-page')].map(e=>e.textContent)")
    rows = page.evaluate("[...document.querySelectorAll('#arrGrid .arr-rows')].map(g=>[...g.children].map(r=>r.children.length).join(','))")
    ok("16 photos: 'Page 2' divider after #12, rows 4,4,4 | 4", len(pg_hdr)==2 and "Page 2" in pg_hdr[1] and "13" in pg_hdr[1] and rows==["4,4,4","4"], (pg_hdr, rows))
    unl = page.evaluate("[...document.querySelectorAll('#arrGrid .arr-lab')].slice(-1)[0].textContent")
    ok("unlabeled photos show 'Photo n'", unl=="Photo 16", unl)
    H = 560; page.set_viewport_size({"width":412, "height":H}); time.sleep(0.3)   # short screen so the grid must scroll
    page.evaluate("window.scrollTo(0,0)"); time.sleep(0.2)
    maxs = page.evaluate("document.documentElement.scrollHeight-innerHeight")
    l16 = labels(page); first_lab = l16[0]
    a = center(page, 0)
    touch("touchStart", *a); time.sleep(0.4)
    for i in range(1, 11): touch("touchMove", a[0], a[1]+(H-40-a[1])*i/10); time.sleep(0.03)
    t0 = time.time()
    while time.time()-t0 < 6:
        vis = page.evaluate("(()=>{const r=document.querySelector(`#arrGrid .arr-slot[data-slot='14']`).getBoundingClientRect();return r.bottom < innerHeight-130})()")
        if vis: break
        time.sleep(0.1)
    sy = page.evaluate("scrollY")
    c14 = center(page, 14)
    for i in range(1, 6): touch("touchMove", a[0]+(c14[0]-a[0])*i/5, (H-40)+(c14[1]-(H-40))*i/5); time.sleep(0.05)
    time.sleep(0.2); touch("touchEnd"); time.sleep(0.4)
    ok("auto-scroll while dragging near bottom edge", maxs>150 and sy>150, (maxs, sy))
    page.set_viewport_size({"width":412, "height":915})
    got = labels(page)
    ok("long drag #1 -> #15 onto page 2", got[14]==first_lab and got[:14]==l16[1:15] and got[15]==l16[15], (got.index(first_lab)+1))
    page.click(".arrbar [data-act=arrDone]"); page.wait_for_selector("#h_tool")
    page.click(".bottombar button:has-text('Print')"); page.wait_for_selector("#printArea .rs-page.cont")
    per = page.evaluate("[...document.querySelectorAll('#printArea .rs-page')].map(p=>p.querySelectorAll('img').length)")
    pc = page.evaluate("[...document.querySelectorAll('#printArea .rs-lab')].map(e=>e.textContent)")
    ok("print: 12 on page 1 + 4 on page 2, captions in arranged order", per==[12,4] and pc==[l or "Photo %d"%(i+1) for i,l in enumerate(got)], per)

    # ---------- dark mode ----------
    page.evaluate("localStorage.setItem('tjl2.theme','\"dark\"')"); page.goto(BASE+"#/job/"+page.evaluate("__tjl.state.route.id")+"/arrange"); page.reload(); page.wait_for_selector("#arrGrid .arr-cell[data-id]"); time.sleep(0.8)
    bg = page.evaluate("getComputedStyle(document.body).backgroundColor"); cell = page.evaluate("getComputedStyle(document.querySelector('.arr-cell')).backgroundColor")
    ok("dark mode styles apply on arrange screen", bg=="rgb(14, 19, 24)" and cell=="rgb(22, 29, 36)", (bg, cell))
    clear_toast(page); page.screenshot(path=SHOTS+"11e-arrange-dark.png")
    page.click(".arrbar [data-act=arrDone]"); page.wait_for_selector("#h_tool")
    ok("Done after reload on arrange falls back to job screen", page.evaluate("location.hash").endswith(page.evaluate("__tjl.state.route.id")))
    page.evaluate("localStorage.setItem('tjl2.theme','\"\"')")
    jid = page.evaluate("__tjl.state.route.id")
    ctx.close()

    # ---------- desktop mouse drag ----------
    dctx = b.new_context(viewport={"width":1280,"height":900})
    dp = dctx.new_page(); watch(dp, "desk")
    dp.goto(BASE); dp.wait_for_selector(".jobcard"); time.sleep(2)
    dp.click(".jobcard:has-text('146-6000-00')"); dp.wait_for_selector("#h_tool")
    dp.click("#photosCard [data-act=arrangeOpen]"); dp.wait_for_selector("#arrGrid .arr-cell[data-id]"); time.sleep(0.5)
    L0 = labels(dp)
    a = center(dp, 0); bb = center(dp, 6)
    dp.mouse.move(*a); dp.mouse.down(); dp.mouse.move(a[0]+10, a[1]+5, steps=3)
    dp.mouse.move(*bb, steps=12); time.sleep(0.15)
    ghost = dp.locator(".arr-ghost").count()
    dp.mouse.up(); time.sleep(0.4)
    L1 = labels(dp)
    ok("mouse drag #1 -> #7 on desktop", ghost==1 and L1[6]==L0[0] and L1[:6]==L0[1:7], L1[:7])
    ok("mouse click still opens action sheet", (dp.locator("#arrGrid .arr-cell[data-slot='2']").click() or True) and dp.wait_for_selector(".arr-mv") is not None)
    dp.keyboard.press("Escape"); time.sleep(0.2)
    dp.focus("#arrGrid .arr-cell[data-slot='1']"); dp.keyboard.press("Enter"); time.sleep(0.2)
    ok("keyboard Enter on a photo opens action sheet", dp.locator(".arr-mv").count()==1)
    dctx.close()
    b.close()

print("\n=== console/page errors ===")
for e in errors: print(e)
print("none" if not errors else "")
fails = [r for r in results if not r[1]]
print(f"\n{len(results)-len(fails)}/{len(results)} passed")
