"""v2.3.0 checks: ✨ Clean up editor — REAL on-device background removal (@imgly/background-removal, ISNet quint8)
in headless Chrome on a synthetic busy-background photo and a real CC0 photo, model caching by the service worker
(works offline afterwards), offline first-use error, all entry points (offer after adding, Arrange sheet, viewer,
batch), backgrounds, touch-ups, crop, rotate/straighten, mask brush (touch + pinch zoom), before/after, save keeps
label + position + original, print sheet uses the edited image, revert, cancel, transparent PNG, dark mode,
Settings toggle, backup includes originals, migration. Screenshots -> shots/12*.png"""
import time, glob, json, os
from playwright.sync_api import sync_playwright
from PIL import Image
BASE = "http://localhost:8766/"
SHOTS = "/workspace/tooling-job-log-v2/shots/"
FIX = "/workspace/tooling-job-log-v2/tests/fixtures/"
SAMPLE = FIX+"cleanup-sample.jpg"; REAL = FIX+"real-stapler-cc0.jpg"
PHOTOS = sorted(glob.glob("/workspace/tjl2-test/photos/p*.jpg"))
errors = []; results = []; requests = []
def ok(name, cond, extra=""):
    results.append((name, bool(cond), extra)); print(("PASS " if cond else "FAIL ") + name + (" — " + str(extra) if extra else ""), flush=True)
def clear_toast(pg): pg.evaluate("document.getElementById('toastRoot') && (document.getElementById('toastRoot').innerHTML='')")
def mk_ctx(b):
    return b.new_context(viewport={"width":412,"height":915}, device_scale_factor=2, is_mobile=True, has_touch=True, accept_downloads=True,
        user_agent="Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Mobile Safari/537.36")
IGNORE = ("favicon.ico",)
OFF = {"on": False}   # while the context is offline, font files that were never fetched before 504 (pre-existing, harmless)
def watch(pg, tag):
    pg.on("response", lambda r: errors.append(tag+" HTTP %d %s" % (r.status, r.url)) if r.status>=400 and not any(x in r.url for x in IGNORE) and not (OFF["on"] and r.status==504) else None)
    pg.on("console", lambda m: errors.append(tag+" console."+m.type+": "+m.text) if m.type=="error" and not ("404" in m.text) and not ("Failed to load resource" in m.text and (tag=="offline" or OFF["on"])) else None)
    pg.on("pageerror", lambda e: errors.append(tag+" pageerror: "+str(e)))
    pg.on("request", lambda r: requests.append((tag, r.method, r.url, len(r.post_data_buffer or b""))))
JOB = "__tjl.state.jobs.find(j=>j.id===__tjl.state.route.id)"
def photos(pg): return pg.evaluate(JOB+".photos")
def px(pg, fx, fy):  # RGBA of the editor canvas at a fractional position
    return pg.evaluate("([fx,fy])=>{const c=document.getElementById('ceCanvas');return [...c.getContext('2d').getImageData(Math.min(c.width-1,Math.floor(c.width*fx)),Math.min(c.height-1,Math.floor(c.height*fy)),1,1).data]}", [fx, fy])
def canvas_sig(pg):  # small fingerprint of the preview
    return pg.evaluate("(()=>{const c=document.getElementById('ceCanvas'),g=c.getContext('2d'),d=g.getImageData(0,0,c.width,c.height).data;let s=0,l=0;for(let i=0;i<d.length;i+=40){s+=d[i]*3+d[i+1]*5+d[i+2]*7+d[i+3];l+=d[i]*.299+d[i+1]*.587+d[i+2]*.114}return {w:c.width,h:c.height,sig:s,lum:l/(d.length/40)}})()")
def set_range(pg, k, v):
    pg.evaluate("([k,v])=>{const e=document.querySelector(`[data-ce='${k}']`);e.value=v;e.dispatchEvent(new Event('input',{bubbles:true}));e.dispatchEvent(new Event('change',{bubbles:true}))}", [k, v])
def settle(pg, t=0.35): time.sleep(t)
def canvas_rect(pg): return pg.evaluate("(()=>{const r=document.getElementById('ceCanvas').getBoundingClientRect();return [r.left,r.top,r.width,r.height]})()")
def mask_alpha_at_canvas(pg, fx, fy):  # mask alpha under a canvas point (brush tab: canvas = frame)
    return pg.evaluate("""([fx,fy])=>{const C=__tjl.ce(),d=C.doc,cv=document.getElementById('ceCanvas');const f=(d.s.rot%2)?{w:d.H,h:d.W}:{w:d.W,h:d.H};
      const M=new DOMMatrix().translate(f.w/2,f.h/2).rotate(d.s.rot*90+d.s.angle).translate(-d.W/2,-d.H/2).inverse();const p=M.transformPoint(new DOMPoint(fx*f.w,fy*f.h));
      return d.mask.getContext('2d').getImageData(Math.round(p.x),Math.round(p.y),1,1).data[3]}""", [fx, fy])
IOU_JS = """async(url)=>{const d=__tjl.ce().doc; const gt=await new Promise(r=>{const i=new Image(); i.onload=()=>r(i); i.src=url;});
  const c=document.createElement('canvas'); c.width=d.W; c.height=d.H; const g=c.getContext('2d'); g.drawImage(gt,0,0,d.W,d.H); const G=g.getImageData(0,0,d.W,d.H).data;
  const m=d.mask.getContext('2d').getImageData(0,0,d.W,d.H).data; let I=0,U=0,fg=0; for(let k=0;k<G.length;k+=4){const a=G[k]>128,b=m[k+3]>128; if(a&&b) I++; if(a||b) U++; if(b) fg++;} return {iou:I/U, fg:fg/(G.length/4)};}"""
def open_viewer_clean(pg, i):
    pg.locator("#photosCard .ph").nth(i).click(); pg.wait_for_selector("#viewer"); settle(pg)
    pg.click("#viewer [data-act=ceFromViewer]"); pg.wait_for_selector("#ceCanvas"); settle(pg, 0.6)

with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
    ctx = mk_ctx(b); page = ctx.new_page(); watch(page, "main")
    cdp = ctx.new_cdp_session(page)
    def touch(kind, pts=()):
        cdp.send("Input.dispatchTouchEvent", {"type":kind, "touchPoints":[{"x":x, "y":y, "id":i} for i,(x,y) in enumerate(pts)]})
    page.goto(BASE); page.wait_for_selector(".jobcard"); page.wait_for_function("window.__tjl && __tjl.state.jobs.filter(j=>j.example).length>=3 && __tjl.state.jobs.filter(j=>j.example).every(j=>j.photos.length)", timeout=60000); time.sleep(1)
    ver = page.evaluate("fetch('sw.js').then(r=>r.text()).then(t=>t.match(/VERSION = \"([^\"]+)/)[1])")
    ok("sw VERSION = tjl-v2.6.0", ver=="tjl-v2.6.0", ver)
    page.goto(BASE+"#/settings"); page.wait_for_selector(".hint")
    ok("APP_VERSION 2.6.0 in settings", "v2.6.0" in page.inner_text("#app"))
    ok("Settings toggle 'Offer cleanup after adding photos' default ON", page.is_checked("#prefOfferClean"))
    ok("Settings shows background remover not downloaded yet", "not downloaded yet" in page.inner_text("#bgStatus"), page.inner_text("#bgStatus"))
    page.wait_for_function("navigator.serviceWorker.controller!==null", timeout=15000)

    # ---------- entry (a): offer after adding 3 photos -> one by one ----------
    page.goto(BASE+"#/"); page.wait_for_selector(".fab"); page.click(".fab"); page.click("[data-act=newBlank]"); page.wait_for_selector("#h_tool")
    page.fill("#h_tool", "T-7700"); page.fill("#h_part", "Clean-up test cap"); page.locator("#h_part").blur()
    with page.expect_file_chooser() as fc: page.click("[data-act=photoLib]")
    fc.value.set_files([SAMPLE, PHOTOS[0], PHOTOS[1]]); page.wait_for_selector("[data-act=photoPreset]", timeout=30000)
    for k in (8, 0, 1):
        page.wait_for_selector("[data-act=photoPreset]"); page.locator("[data-act=photoPreset]").nth(k).click(); time.sleep(0.2)
    page.wait_for_selector(".toast.offer", timeout=5000); settle(page)
    txt = page.inner_text(".toast")
    ok("after adding 3 photos: toast offers 'Clean up 3 new photos?' with ONE BY ONE / SKIP ALL", "3 new photos" in txt and "ONE BY ONE" in txt and "SKIP ALL" in txt, txt.replace("\n"," | "))
    page.screenshot(path=SHOTS+"12a-offer-toast.png")
    P0 = photos(page); labels0 = [q["label"] for q in P0]
    page.click("[data-act=toastAct]"); page.wait_for_selector("#ceCanvas"); settle(page, 0.8)
    ok("ONE BY ONE opens the editor on photo 1 of 3", "Photo 1 of 3" in page.text_content(".ce-top") and page.locator("[data-act=ceSkipRest]").count()==1, page.inner_text(".ce-top").replace("\n"," | "))
    big = page.evaluate("(()=>{const t=[...document.querySelectorAll('.ce-tabs button,#ceRemoveBtn,#ceSaveBtn,.ce-sw>*')].map(e=>e.getBoundingClientRect().height);return Math.min(...t)})()")
    ok("big touch targets in editor (tabs/buttons/swatches >= 48px)", big>=48, big)
    page.screenshot(path=SHOTS+"12b-editor.png")

    # ---------- REAL background removal (downloads the model on first use) ----------
    n_before = len(requests); t0 = time.time()
    page.click("#ceRemoveBtn")
    seen = set()
    for _ in range(600):
        el = page.query_selector("#ceBusyText")
        if el:
            t = el.inner_text(); seen.add(t)
            if "Downloading" in t and " of " in t and "12c" not in str(seen):
                page.screenshot(path=SHOTS+"12c-downloading.png"); seen.add("12c")
        if page.query_selector(".ce-done"): break
        time.sleep(0.2)
    dt = time.time()-t0
    ok("REAL background removal finished in headless Chrome", page.query_selector(".ce-done") is not None, "%.1fs incl. first download" % dt)
    ok("download progress shown in MB, then processing progress", any("Downloading background remover" in s and "MB" in s for s in seen) and any("Finding the part" in s for s in seen), sorted(x for x in seen if x!="12c")[:4])
    settle(page, 0.8)
    r = page.evaluate(IOU_JS, "tests/fixtures/cleanup-sample-mask.png")
    ok("cutout of the synthetic part is sensible (IoU vs ground truth >= 0.6)", r["iou"]>=0.6, "IoU %.2f, foreground %.0f%%" % (r["iou"], r["fg"]*100))
    ok("after removal the background defaults to White", page.evaluate("__tjl.ce().doc.s.bg")=="white" and px(page, 0.02, 0.02)[:3]==[255,255,255])
    ok("part is centered + fit with padding (corners white, center is the part)", px(page, 0.5, 0.5)[2] > px(page, 0.5, 0.5)[0]+40, px(page, 0.5, 0.5))
    clear_toast(page); page.screenshot(path=SHOTS+"12d-removed-white.png")
    ext = [r for r in requests[n_before:] if r[0]=="main" and not r[2].startswith(BASE) and not r[2].startswith("blob:") and not r[2].startswith("data:")]
    hosts = sorted(set(u.split("/")[2] for _, m, u, n in ext))
    ok("privacy: only GET downloads of the model/runtime (no uploads, no POST/PUT anywhere)", all(m=="GET" and n==0 for _, m, u, n in ext) and set(hosts) <= {"cdn.jsdelivr.net", "cdnjs.cloudflare.com", "staticimgly.com", "fonts.googleapis.com", "fonts.gstatic.com"}, hosts)
    ok("no request of any kind carries a body", all(n==0 for _,_,_,n in requests), [x for x in requests if x[3]][:2])
    bgc = page.evaluate("caches.open('tjl-bgmodel-v1').then(c=>c.keys()).then(k=>k.length)")
    shell = page.evaluate("caches.keys().then(ks=>Promise.all(ks.filter(k=>k.startsWith('tjl-v')).map(k=>caches.open(k).then(c=>c.keys()).then(r=>r.map(x=>x.url))))).then(a=>a.flat())")
    ok("SW cached the model/runtime chunks in their own cache (tjl-bgmodel-v1)", bgc>=10, "%d entries" % bgc)
    ok("precache stays small: no model files in the app-shell cache, bgworker.js is precached", not any("staticimgly" in u for u in shell) and any(u.endswith("/bgworker.js") for u in shell), len(shell))
    sizes = page.evaluate("caches.open('tjl-bgmodel-v1').then(c=>c.keys().then(ks=>Promise.all(ks.map(k=>c.match(k).then(r=>r.blob()).then(b=>b.size))))).then(a=>a.reduce((x,y)=>x+y,0))")
    libs = page.evaluate("caches.open('tjl-libs-v1').then(c=>c.keys().then(ks=>Promise.all(ks.filter(k=>/background-removal|onnxruntime|lodash|zod|ndarray|is-buffer|iota|jsdelivr.*\\+esm/.test(k.url)).map(k=>c.match(k).then(r=>r.blob()).then(b=>b.size))))).then(a=>a.reduce((x,y)=>x+y,0))")
    ok("first-download size measured", sizes>40e6, "model+runtime %.1f MB (Cache API) + JS %.2f MB" % (sizes/1048576, libs/1048576))
    FIRST_MB = (sizes+libs)/1048576

    # ---------- background picker ----------
    def pick(k):
        page.click(f".ce-sw [data-bg='{k}']"); settle(page, 0.45)
    pick("navy"); ok("Navy background = brand navy #0d3f7a", px(page, 0.02, 0.02)[:3]==[13,63,122], px(page, 0.02, 0.02))
    pick("gray"); ok("Light gray background", px(page, 0.02, 0.02)[:3]==[228,232,236], px(page, 0.02, 0.02))
    pick("studio"); c1, c2 = px(page, 0.5, 0.03), px(page, 0.01, 0.99)
    ok("Studio gradient: light center, darker corners", c1[0]>c2[0]+15 and c2[0]>180, (c1, c2))
    pick("transparent"); ok("None = transparent (alpha 0 at corner)", px(page, 0.02, 0.02)[3]==0)
    page.evaluate("(()=>{const e=document.querySelector(\"[data-ce='custom']\");e.value='#ff8800';e.dispatchEvent(new Event('input',{bubbles:true}));e.dispatchEvent(new Event('change',{bubbles:true}))})()"); settle(page, 0.45)
    ok("Custom color picker background", px(page, 0.02, 0.02)[:3]==[255,136,0] and page.evaluate("__tjl.ce().doc.s.bg")=="custom", px(page, 0.02, 0.02))
    with page.expect_file_chooser() as fc: page.click(".ce-sw [data-bg='photo']")
    fc.value.set_files(PHOTOS[3]); page.wait_for_function("__tjl.ce().doc.s.bg==='photo'"); settle(page, 0.5)
    ok("Picked-photo background + Blur toggle shown", page.locator("[data-ce=blur]").count()==1)
    s_blur = canvas_sig(page); page.click("label:has([data-ce=blur])"); settle(page, 0.45); s_sharp = canvas_sig(page)
    ok("Blur toggle changes the photo background", s_blur["sig"]!=s_sharp["sig"] and not page.is_checked("[data-ce=blur]"))
    pick("white"); s0 = canvas_sig(page)
    page.click("label:has([data-ce=shadow])"); settle(page, 0.45); s1 = canvas_sig(page)
    ok("Soft shadow toggle darkens around/under the part", s1["lum"] < s0["lum"] - 0.3, "%.1f -> %.1f" % (s0["lum"], s1["lum"]))
    clear_toast(page); page.evaluate("document.getElementById('cePanel').scrollTop=0"); page.screenshot(path=SHOTS+"12e-background-picker.png")
    page.click("label:has([data-ce=shadow])"); settle(page, 0.3)
    page.click("label:has([data-ce=fit])"); settle(page, 0.45)
    ok("'Center & fit' off keeps the part where it was", page.evaluate("__tjl.ce().doc.s.fit")==False and canvas_sig(page)["sig"]!=s0["sig"])
    page.click("label:has([data-ce=fit])"); settle(page, 0.3)

    # ---------- touch-ups ----------
    page.click("[data-act=ceTab][data-v=tone]"); settle(page)
    base = canvas_sig(page)
    set_range(page, "bri", 40); settle(page, 0.45); b1 = canvas_sig(page)
    ok("Brightness slider brightens", b1["lum"] > base["lum"] + 3 and page.inner_text("#ceV_bri")=="+40", "%.1f -> %.1f" % (base["lum"], b1["lum"]))
    set_range(page, "bri", 0); set_range(page, "con", 45); settle(page, 0.45); c1s = canvas_sig(page)
    ok("Contrast slider changes the image", c1s["sig"]!=base["sig"])
    set_range(page, "con", 0); set_range(page, "sharp", 80); settle(page, 0.5); sh = canvas_sig(page)
    ok("Sharpness slider changes the image", sh["sig"]!=base["sig"])
    set_range(page, "sharp", 0); page.click("[data-act=ceAuto]"); settle(page, 0.5); au = canvas_sig(page)
    ok("Auto enhance toggles on and changes the image", page.evaluate("__tjl.ce().doc.s.auto") and au["sig"]!=base["sig"] and "Auto enhance on" in page.inner_text("#cePanel"))
    set_range(page, "angle", 6); settle(page, 0.5); an = canvas_sig(page)
    ok("Straighten slider (+6.0°) rotates slightly", an["sig"]!=au["sig"] and page.inner_text("#ceV_angle")=="+6.0°")
    set_range(page, "angle", 0)
    w0 = canvas_sig(page); page.click("[data-act=ceRot]"); settle(page, 0.5); w1 = canvas_sig(page)
    ok("Rotate 90° swaps width/height", (w0["w"], w0["h"])==(w1["h"], w1["w"]), (w0["w"], w0["h"], w1["w"], w1["h"]))
    page.click("[data-act=ceRot]"); page.click("[data-act=ceRot]"); page.click("[data-act=ceRot]"); settle(page, 0.4)
    clear_toast(page); page.screenshot(path=SHOTS+"12f-touch-up.png")

    # ---------- crop ----------
    page.click("[data-act=ceTab][data-v=crop]"); settle(page)
    page.click("[data-act=ceAspect][data-v='1:1']"); settle(page, 0.4)
    cr = page.evaluate("__tjl.ce().doc.s.crop"); fw = canvas_sig(page)
    ok("Crop 1:1 preset makes a centered square", abs(cr["w"]*fw["w"] - cr["h"]*fw["h"]) < 3, cr)
    L, T, W, H = canvas_rect(page)
    cx1, cy1 = L + W*(cr["x"]+cr["w"]) - 2, T + H*(cr["y"]+cr["h"]) - 2
    touch("touchStart", [(cx1, cy1)])
    for i in range(1, 9): touch("touchMove", [(cx1 - i*9, cy1 - i*9)]); time.sleep(0.02)
    touch("touchEnd"); settle(page)
    cr2 = page.evaluate("__tjl.ce().doc.s.crop")
    ok("dragging the crop corner (touch) shrinks it and keeps 1:1", cr2["w"] < cr["w"]-0.03 and abs(cr2["w"]*fw["w"] - cr2["h"]*fw["h"]) < 3, cr2)
    clear_toast(page); page.screenshot(path=SHOTS+"12g-crop.png")
    page.click("[data-act=ceTab][data-v=bg]"); settle(page, 0.4); sq = canvas_sig(page)
    ok("outside the crop tab the preview is cropped (square)", abs(sq["w"]-sq["h"]) <= 2, (sq["w"], sq["h"]))
    page.click("[data-act=ceTab][data-v=crop]"); page.click("[data-act=ceAspect][data-v='4:3']"); settle(page, 0.3)
    cr3 = page.evaluate("__tjl.ce().doc.s.crop"); ok("4:3 preset", abs(cr3["w"]*fw["w"]/(cr3["h"]*fw["h"]) - 4/3) < 0.02, cr3)
    page.click("[data-act=ceCropReset]"); settle(page, 0.3)
    ok("Reset crop", page.evaluate("__tjl.ce().doc.s.crop") is None)

    # ---------- mask brush: erase / restore with touch, undo, pinch zoom ----------
    page.click("[data-act=ceTab][data-v=brush]"); settle(page, 0.5)
    L, T, W, H = canvas_rect(page)
    a0 = mask_alpha_at_canvas(page, 0.5, 0.45)
    ok("brush view shows the part in place (not fit): part pixel is opaque in mask", a0 > 200, a0)
    set_range(page, "brush", 30); ok("brush size slider", page.evaluate("__tjl.ce().brush")==30)
    touch("touchStart", [(L+W*0.40, T+H*0.45)])
    for i in range(1, 11): touch("touchMove", [(L+W*(0.40+0.02*i), T+H*0.45)]); time.sleep(0.02)
    touch("touchEnd"); settle(page)
    a1 = mask_alpha_at_canvas(page, 0.5, 0.45)
    ok("Erase stroke (touch) removes the part under the brush", a1 == 0, "%d -> %d" % (a0, a1))
    page.click("[data-act=ceBrushMode][data-v=restore]")
    touch("touchStart", [(L+W*0.48, T+H*0.45)]); touch("touchMove", [(L+W*0.52, T+H*0.45)]); touch("touchEnd"); settle(page)
    a2 = mask_alpha_at_canvas(page, 0.5, 0.45)
    ok("Restore stroke brings it back", a2 == 255, a2)
    page.click("[data-act=ceStrokeUndo]"); settle(page)
    ok("Undo stroke", mask_alpha_at_canvas(page, 0.5, 0.45) == 0)
    page.click("[data-act=ceMaskReset]"); settle(page)
    ok("'Auto cutout' resets the mask to the model result", mask_alpha_at_canvas(page, 0.5, 0.45) > 200)
    cxm, cym = L+W/2, T+H/2
    touch("touchStart", [(cxm-40, cym), (cxm+40, cym)])
    for i in range(1, 9): touch("touchMove", [(cxm-40-i*12, cym), (cxm+40+i*12, cym)]); time.sleep(0.02)
    touch("touchEnd"); settle(page)
    z = page.evaluate("__tjl.ce().z")
    ok("two-finger pinch zooms the photo (and doesn't paint)", z > 1.8 and mask_alpha_at_canvas(page, 0.5, 0.45) > 200, round(z, 2))
    page.click("[data-act=ceBrushMode][data-v=erase]")
    L, T, W, H = canvas_rect(page)
    touch("touchStart", [(L+W*0.30, T+H*0.30)])
    for i in range(1, 6): touch("touchMove", [(L+W*(0.30+0.01*i), T+H*(0.30+0.01*i))]); time.sleep(0.02)
    clear_toast(page); page.screenshot(path=SHOTS+"12h-brush.png")
    touch("touchEnd"); settle(page)
    page.click("[data-act=ceZoom][data-d='1']"); z2 = page.evaluate("__tjl.ce().z"); page.click("[data-act=ceZoom][data-d='0']")
    ok("zoom buttons (+ / reset)", z2 > z and page.evaluate("__tjl.ce().z")==1)
    page.click("[data-act=ceStrokeUndo]")

    # ---------- before / after ----------
    page.click("[data-act=ceTab][data-v=bg]"); settle(page, 0.4)
    clear_toast(page); page.screenshot(path=SHOTS+"12i-after.png")
    bb = page.locator("#ceCmp").bounding_box()
    touch("touchStart", [(bb["x"]+bb["width"]/2, bb["y"]+bb["height"]/2)]); time.sleep(0.6)
    held = page.evaluate("!document.getElementById('ceBadge').hidden"); corner = px(page, 0.02, 0.02)
    clear_toast(page); page.screenshot(path=SHOTS+"12i-before.png")
    touch("touchEnd"); settle(page)
    ok("press & hold shows the original (BEFORE badge, busy background back)", held and corner[:3]!=[255,255,255], corner)
    ok("release goes back to the edited version", page.evaluate("document.getElementById('ceBadge').hidden") and px(page, 0.02, 0.02)[:3]==[255,255,255])
    page.click("#ceCmp"); settle(page)
    ok("quick tap = sticky before/after toggle", page.evaluate("__tjl.ce().sticky") and not page.evaluate("document.getElementById('ceBadge').hidden"))
    page.click("#ceCmp"); settle(page)
    a_img, b_img = Image.open(SHOTS+"12i-before.png"), Image.open(SHOTS+"12i-after.png")
    combo = Image.new("RGB", (a_img.width*2+20, a_img.height), "white"); combo.paste(a_img, (0, 0)); combo.paste(b_img, (a_img.width+20, 0)); combo.save(SHOTS+"12i-before-after.png")

    # ---------- save: label + position kept, original kept, queue moves on ----------
    old = P0[0]
    page.click("#ceSaveBtn"); page.wait_for_function("document.querySelector('.ce-top') && document.querySelector('.ce-top').textContent.includes('Photo 2 of 3')", timeout=15000); settle(page, 0.6)
    P1 = photos(page)
    ok("Save replaces the photo: new picture id, same label, same position #1", P1[0]["id"]!=old["id"] and P1[0]["label"]==labels0[0] and [q["label"] for q in P1]==labels0, [q["label"] for q in P1])
    ok("original kept: origId = old picture, still in IndexedDB", P1[0].get("origId")==old["id"] and page.evaluate("(id)=>__tjl.getPhoto(id).then(b=>!!b)", old["id"]), {k:P1[0].get(k) for k in ("origId","origBytes","bytes")})
    ok("saved as compressed JPEG (white background)", page.evaluate("(id)=>__tjl.getPhoto(id).then(b=>b.type)", P1[0]["id"])=="image/jpeg" and P1[0]["bytes"] < 400000, P1[0]["bytes"])
    ok("queue: editor moved on to photo 2 of 3", "Photo 2 of 3" in page.text_content(".ce-top"))
    page.click("[data-act=ceSkipRest]"); settle(page, 0.5)
    ok("'Skip rest' closes the editor", page.locator("#ceEditor").count()==0 and photos(page)[1]["id"]==P0[1]["id"])

    # ---------- print sheet shows the edited image ----------
    jid = page.evaluate("__tjl.state.route.id")
    page.goto(BASE+"#/job/"+jid+"/print"); page.wait_for_selector("#printArea img"); time.sleep(1.2)
    pr = page.evaluate("(id)=>{const i=document.querySelector(`#printArea img[data-pid='${id}']`);return i? {ok:i.complete&&i.naturalWidth>0, w:i.naturalWidth}:null}", P1[0]["id"])
    ok("print sheet uses the edited image", pr and pr["ok"] and page.locator(f"#printArea img[data-pid='{old['id']}']").count()==0, pr)
    page.screenshot(path=SHOTS+"12j-print-sheet.png")
    page.goto(BASE+"#/job/"+jid); page.wait_for_selector("#photosCard"); settle(page)

    # ---------- REAL removal on a real CC0 photo (black shiny stapler on a counter) ----------
    with page.expect_file_chooser() as fc: page.click("[data-act=photoLib]")
    fc.value.set_files(REAL); page.wait_for_selector("[data-act=photoPreset]"); page.locator("[data-act=photoPreset]").nth(11).click()
    page.wait_for_selector(".toast.offer"); ok("single photo: toast offers CLEAN UP / SKIP", "CLEAN UP" in page.inner_text(".toast") and "SKIP" in page.inner_text(".toast"))
    page.click("[data-act=toastAct]"); page.wait_for_selector("#ceRemoveBtn"); settle(page, 0.5)
    t0 = time.time(); page.click("#ceRemoveBtn"); page.wait_for_selector(".ce-done", timeout=120000); dt2 = time.time()-t0; settle(page, 0.6)
    fg = page.evaluate("(()=>{const d=__tjl.ce().doc,m=d.mask.getContext('2d').getImageData(0,0,d.W,d.H).data;let f=0,e=0;for(let i=3;i<m.length;i+=4){if(m[i]>128)f++;}const W=d.W,H=d.H;for(let x=0;x<W;x+=4){if(m[(x+W*2)*4+3]>128)e++;}return {fg:f/(W*H), topEdge:e}})()")
    ok("real photo: second run uses the cached model (fast) and cuts out one object", dt2 < 60 and 0.05 < fg["fg"] < 0.6, "%.1fs, foreground %.0f%%, top-edge fg px %d" % (dt2, fg["fg"]*100, fg["topEdge"]))
    clear_toast(page); page.screenshot(path=SHOTS+"12k-real-photo-removed.png")
    page.click("#ceSaveBtn"); page.wait_for_selector("#ceEditor", state="detached"); settle(page, 0.5)

    # ---------- works OFFLINE afterwards (new page load from SW cache, fresh worker) ----------
    ctx.set_offline(True); OFF["on"] = True
    page.reload(); page.wait_for_selector("#photosCard", timeout=15000); settle(page, 1)
    ok("offline: app shell still loads from the service worker", page.locator("#photosCard .ph").count()==4)
    open_viewer_clean(page, 1)
    t0 = time.time(); page.click("#ceRemoveBtn")
    page.wait_for_function("document.querySelector('.ce-done') || document.querySelector('.scrim')", timeout=120000)
    ok("offline: background removal still works (model served from the SW cache)", page.locator(".ce-done").count()==1 and page.locator(".scrim").count()==0, "%.1fs" % (time.time()-t0))
    ctx.set_offline(False); time.sleep(0.3); OFF["on"] = False
    page.click("[data-act=ceCancel]"); page.wait_for_selector(".scrim"); page.click("[data-act=confirmOk]"); settle(page, 0.6)
    ok("Cancel (after changes) asks, then discards: photo unchanged, back in viewer", page.locator("#viewer").count()==1 and photos(page)[1]["id"]==P0[1]["id"] and not photos(page)[1].get("origId"))

    # ---------- re-edit an already cleaned photo: original stays the same, the intermediate edit is deleted ----------
    page.click("#viewer [data-act=closeModal]"); settle(page)
    page.evaluate("__tjl.ceTestMask({delay:250})")   # fake mask from here on (the real model was verified above)
    first = photos(page)[0]
    open_viewer_clean(page, 0)
    page.click("[data-act=ceTab][data-v=tone]"); page.click("[data-act=ceAuto]"); settle(page, 0.3)
    page.click("#ceSaveBtn"); page.wait_for_selector("#ceEditor", state="detached"); settle(page, 0.5)
    again = photos(page)[0]
    ok("re-editing a cleaned photo keeps the SAME original and deletes the intermediate edit", again["origId"]==old["id"] and again["id"]!=first["id"] and page.evaluate("(id)=>__tjl.getPhoto(id).then(b=>!b)", first["id"]))
    P1[0] = again
    page.click("#viewer [data-act=closeModal]"); settle(page)
    page.locator("#photosCard .ph").nth(1).click(); page.wait_for_selector("#viewer"); settle(page)

    # ---------- entry (c) viewer: no-change cancel closes at once; transparent -> PNG ----------
    page.click("#viewer [data-act=ceFromViewer]"); page.wait_for_selector("#ceCanvas"); settle(page, 0.4)
    page.click("[data-act=ceCancel]"); settle(page, 0.4)
    ok("viewer: ✨ Clean up opens editor; Cancel without changes closes immediately back to viewer", page.locator("#ceEditor").count()==0 and page.locator("#viewer").count()==1 and page.locator(".scrim").count()==0)
    page.click("#viewer [data-act=ceFromViewer]"); page.wait_for_selector("#ceCanvas"); settle(page, 0.3)
    page.click(".ce-sw [data-bg='transparent']"); page.wait_for_selector(".ce-done", timeout=10000); settle(page, 0.3)
    ok("choosing a background first runs removal automatically", page.evaluate("__tjl.ce().doc.s.bg")=="transparent")
    page.click("#ceSaveBtn"); page.wait_for_selector("#ceEditor", state="detached"); settle(page, 0.5)
    q = photos(page)[1]
    ok("transparent background is saved as PNG (alpha kept), label/position kept", q.get("alpha") and page.evaluate("(id)=>__tjl.getPhoto(id).then(b=>b.type)", q["id"])=="image/png" and q["label"]==labels0[1], q["bytes"])
    ok("viewer returns on the cleaned photo with '↺ Revert to original'", page.locator("#viewer [data-act=photoRevert]").count()==1)
    page.click("#viewer [data-act=photoRevert]"); page.wait_for_selector(".scrim"); page.click("[data-act=confirmOk]"); settle(page, 0.5)
    q2 = photos(page)[1]
    ok("viewer: Revert to original restores the original picture (id, no origId), label/position kept", q2["id"]==P0[1]["id"] and not q2.get("origId") and q2["label"]==labels0[1])
    ok("reverted: edited PNG deleted from IndexedDB", page.evaluate("(id)=>__tjl.getPhoto(id).then(b=>!b)", q["id"]))
    page.click("#viewer [data-act=closeModal]"); settle(page)

    # ---------- cancel during processing ----------
    page.evaluate("__tjl.ceTestMask({delay:4000})")
    open_viewer_clean(page, 2)
    page.click("#ceRemoveBtn"); page.wait_for_selector("[data-act=ceRemoveCancel]"); settle(page, 0.3)
    page.click("[data-act=ceRemoveCancel]"); settle(page, 0.3)
    ok("Cancel during background removal stops it (overlay gone, no mask)", page.locator("#ceBusyText").count()==0 and page.evaluate("__tjl.ce().doc.mask")==None)
    time.sleep(4.2); ok("…and a late result is ignored", page.evaluate("__tjl.ce().doc.mask")==None)
    page.evaluate("__tjl.ceTestMask({delay:200})")
    page.click("[data-act=ceCancel]"); settle(page)
    page.click("#viewer [data-act=closeModal]"); settle(page)

    # ---------- entry (b) Arrange sheet + undo + revert ----------
    page.click("#photosCard [data-act=arrangeOpen]"); page.wait_for_selector("#arrGrid .arr-cell[data-id]"); settle(page, 0.5)
    page.locator("#arrGrid .arr-cell[data-slot='2']").click(); page.wait_for_selector("[data-act=arrClean]")
    clear_toast(page); page.screenshot(path=SHOTS+"12l-arrange-sheet.png")
    page.click("[data-act=arrClean]"); page.wait_for_selector("#ceCanvas"); settle(page, 0.4)
    page.click("#ceRemoveBtn"); page.wait_for_selector(".ce-done"); page.click(".ce-sw [data-bg='navy']"); settle(page, 0.3)
    before_ids = [q["id"] for q in photos(page)]
    page.click("#ceSaveBtn"); page.wait_for_selector("#ceEditor", state="detached"); settle(page, 0.5)
    P2 = photos(page)
    ok("Arrange: ✨ Clean up saves in place (#3 keeps label + position) with UNDO toast", P2[2]["id"]!=before_ids[2] and P2[2]["label"]==labels0[2] and "UNDO" in page.inner_text("#toastRoot") and page.evaluate("location.hash").endswith("/arrange"))
    page.click(".arrbar [data-act=arrUndo]"); settle(page, 0.4)
    ok("Arrange Undo reverts the clean-up", [q["id"] for q in photos(page)]==before_ids)
    page.locator("#arrGrid .arr-cell[data-slot='0']").click(); page.wait_for_selector("[data-act=arrRevert]")
    ok("Arrange sheet offers '↺ Revert to original' for a cleaned photo", page.locator("[data-act=arrRevert]").count()==1)
    page.click("[data-act=arrRevert]"); page.click("[data-act=confirmOk]"); settle(page, 0.4)
    P3 = photos(page)
    ok("Arrange: Revert to original (photo #1)", P3[0]["id"]==old["id"] and not P3[0].get("origId") and P3[0]["label"]==labels0[0])
    page.click(".arrbar [data-act=arrUndo]"); settle(page, 0.3)
    ok("…and Undo brings the cleaned version back", photos(page)[0]["id"]==P1[0]["id"])

    # ---------- entry (d) batch: remove background from all ----------
    page.click("[data-act=ceBatchOpen]"); page.wait_for_selector("[data-act=ceBatchGo]")
    page.click("[data-act=ceBatchBg][data-v=studio]"); clear_toast(page); page.screenshot(path=SHOTS+"12m-batch.png")
    page.click("[data-act=ceBatchGo]"); page.wait_for_function("!document.querySelector('#busyRoot .busy')", timeout=30000); settle(page, 0.5)
    PB = photos(page)
    ok("Batch: all 4 photos cleaned, labels/order kept, originals kept", all(q.get("origId") for q in PB) and [q["label"] for q in PB]==[q["label"] for q in P1[:3]]+[PB[3]["label"]] and PB[0]["origId"]==old["id"], [bool(q.get("origId")) for q in PB])
    page.click(".arrbar [data-act=arrUndo]"); settle(page, 0.4)
    ok("Batch is one Undo step", [q["id"] for q in photos(page)][:3]==[P1[0]["id"], P0[1]["id"], P0[2]["id"]])
    page.click(".arrbar [data-act=arrDone]"); page.wait_for_selector("#photosCard"); settle(page)

    # ---------- backup / duplicate include originals ----------
    page.goto(BASE+"#/settings"); page.wait_for_selector("#bgStatus"); time.sleep(0.8)
    ok("Settings: background remover saved for offline + kept originals listed", "saved for offline" in page.inner_text("#bgStatus") and "Kept originals" in page.inner_text("#app"), page.inner_text("#bgStatus"))
    with page.expect_download() as dl: page.click("[data-act=backupDownload]")
    bk = json.load(open(dl.value.path()))
    print("   backup jobs:", [(j["toolNumber"], j.get("partName"), len(j["photos"])) for j in bk["jobs"]])
    j7s = [j for j in bk["jobs"] if j["id"]==jid]
    if not j7s: print("   DEBUG mem jobs:", page.evaluate("__tjl.state.jobs.map(j=>[j.id,j.toolNumber,j.photos.length])"), "jid", jid, "LS:", page.evaluate("JSON.parse(localStorage.getItem('tjl2.jobs')).map(j=>[j.id,j.toolNumber])"))
    j7 = j7s[0]
    ok("backup includes the kept original pictures (Revert survives restore)", all(q["id"] in bk["photos"] and (not q.get("origId") or q["origId"] in bk["photos"]) for q in j7["photos"]) and any(q.get("origId") for q in j7["photos"]))

    # ---------- Settings toggle off: no offer ----------
    page.click("label.prefrow"); settle(page)
    ok("toggle off persists", page.evaluate("JSON.parse(localStorage.getItem('tjl2.meta')).offerCleanup")==False)
    page.goto(BASE+"#/job/"+jid); page.wait_for_selector("#photosCard")
    with page.expect_file_chooser() as fc: page.click("[data-act=photoLib]")
    fc.value.set_files(PHOTOS[5]); page.wait_for_selector("[data-act=photoPreset]"); page.locator("[data-act=photoPreset]").nth(6).click(); time.sleep(1.0)
    ok("with the toggle off, no clean-up offer after adding", page.locator(".toast.offer").count()==0)
    page.goto(BASE+"#/settings"); page.wait_for_selector("label.prefrow"); page.click("label.prefrow"); settle(page)
    ok("toggle back on", page.evaluate("JSON.parse(localStorage.getItem('tjl2.meta')).offerCleanup")==True)

    # ---------- skip all ----------
    page.goto(BASE+"#/job/"+jid); page.wait_for_selector("#photosCard")
    with page.expect_file_chooser() as fc: page.click("[data-act=photoLib]")
    fc.value.set_files(PHOTOS[6:8]); page.wait_for_selector("[data-act=photoPreset]")
    page.click("[data-act=photoLabelSkip]"); page.wait_for_selector("[data-act=photoPreset]"); page.click("[data-act=photoLabelSkip]")
    page.wait_for_selector(".toast.offer"); page.click("[data-act=toastAct2]"); settle(page)
    ok("SKIP ALL dismisses without opening the editor", page.locator("#ceEditor").count()==0 and page.locator(".toast").count()==0)

    # ---------- dark mode ----------
    page.evaluate("localStorage.setItem('tjl2.theme','\"dark\"')"); page.reload(); page.wait_for_selector("#photosCard"); settle(page, 0.8)
    open_viewer_clean(page, 0)
    page.click("#ceRemoveBtn"); page.wait_for_selector(".ce-done"); settle(page, 0.4)
    bgcol = page.evaluate("getComputedStyle(document.querySelector('.ce-panel')).backgroundColor")
    ok("dark mode: editor uses dark surfaces", bgcol in ("rgb(22, 29, 36)",), bgcol)
    clear_toast(page); page.screenshot(path=SHOTS+"12n-editor-dark.png")
    page.click("[data-act=ceTab][data-v=brush]"); settle(page, 0.4); clear_toast(page); page.screenshot(path=SHOTS+"12o-brush-dark.png")
    page.keyboard.press("Escape"); page.wait_for_selector(".scrim"); page.click("[data-act=confirmOk]"); settle(page)
    page.evaluate("localStorage.setItem('tjl2.theme','\"\"')")

    # ---------- migration: bad origId values are dropped, good ones kept ----------
    page.evaluate("""(()=>{const J=JSON.parse(localStorage.getItem('tjl2.jobs'));const j=J.find(x=>x.toolNumber==='T-7700');
      j.photos.push({id:'legacy1',label:'Legacy',origId:12345},{id:'legacy2',label:'Legacy2',origId:'legacy2'});localStorage.setItem('tjl2.jobs',JSON.stringify(J));})()""")
    page.reload(); page.wait_for_selector("#photosCard"); settle(page)
    lg = [q for q in photos(page) if q["id"].startswith("legacy")]
    ok("migration: invalid origId values removed safely, valid ones kept", all("origId" not in q for q in lg) and photos(page)[0].get("origId")==old["id"], lg)

    # ---------- v2.6.0 one tap: Make it professional (fake mask — real model already verified above) ----------
    page.evaluate("__tjl.ceTestMask({delay:200})")
    page.evaluate("localStorage.setItem('tjl2.theme','\"\"')"); page.reload(); page.wait_for_selector("#photosCard"); settle(page, 0.6)
    # reload cleared the test hook
    page.evaluate("__tjl.ceTestMask({delay:180})")
    labels_now = [q["label"] for q in photos(page)]
    ids_now = [q["id"] for q in photos(page)]
    open_viewer_clean(page, 2)
    ok("cleanup screen has a primary ✨ Make it professional button", page.locator("#ceProBtn").count()==1 and "Make it professional" in page.inner_text("#ceProBtn"))
    clear_toast(page); page.screenshot(path=SHOTS+"15a-before.png")
    page.click("#ceProBtn"); page.wait_for_selector(".ce-prochips", timeout=10000); settle(page, 0.7)
    ok("one tap shows the result with Save, Cancel and Before/After (no sliders first)", page.locator("#ceSaveBtn").count()==1 and page.locator("[data-act=ceCancel]").count()==1 and page.locator("#ceCmp").count()==1 and page.locator("#ceTabs[hidden]").count()==1 and page.locator("[data-ce=sharp]").count()==0)
    corner = px(page, 0.02, 0.02)
    ok("one tap: clean white background", corner[:3]==[255,255,255] and page.evaluate("__tjl.ce().doc.s.bg")=="white", corner)
    cen = page.evaluate("""()=>{const c=document.getElementById('ceCanvas'),g=c.getContext('2d'),w=c.width,h=c.height,d=g.getImageData(0,0,w,h).data;
      let x0=w,x1=0,y0=h,y1=0,n=0,sx=0,sy=0;
      for(let y=0;y<h;y+=2) for(let x=0;x<w;x+=2){const i=(y*w+x)*4; if(d[i]<248||d[i+1]<248||d[i+2]<248){if(x<x0)x0=x;if(x>x1)x1=x;if(y<y0)y0=y;if(y>y1)y1=y;sx+=x;sy+=y;n++;}}
      return {cx:n?((x0+x1)/2)/w:0, cy:n?((y0+y1)/2)/h:0, n};}""")
    ok("one tap: subject is centered", abs(cen["cx"]-0.5)<0.08 and abs(cen["cy"]-0.5)<0.1 and cen["n"]>50, cen)
    energy = page.evaluate("""()=>{const d=__tjl.ce().doc,S=d.cache.s; if(!S) return null;
      function energy(canvas, alphaFrom){const w=canvas.width,h=canvas.height,im=canvas.getContext('2d').getImageData(0,0,w,h).data;
        const aw=alphaFrom.width,ah=alphaFrom.height,al=alphaFrom.getContext('2d').getImageData(0,0,aw,ah).data;
        let e=0,n=0; for(let y=3;y<h-3;y+=3) for(let x=3;x<w-3;x+=3){
          const ax=Math.min(aw-1,Math.round(x*aw/w)), ay=Math.min(ah-1,Math.round(y*ah/h));
          const A=(ay*aw+ax)*4+3; if(al[A]<230||al[A-4]<200||al[A+4]<200) continue;
          const lum=(xx,yy)=>{const i=(yy*w+xx)*4; return im[i]*0.299+im[i+1]*0.587+im[i+2]*0.114;};
          const Y=lum(x,y), L=4*Y-lum(x-1,y)-lum(x+1,y)-lum(x,y-1)-lum(x,y+1); e+=L*L; n++;}
        return n?e/n:0;}
      const c=document.createElement('canvas'); c.width=S.width; c.height=S.height; const g=c.getContext('2d'); g.imageSmoothingQuality='high'; g.drawImage(d.src,0,0,c.width,c.height);
      return {src:energy(c,S), out:energy(S,S), n:S.width};}""")
    ok("one tap: subject is sharper than the input (edge energy)", energy and energy["out"]>energy["src"]*1.08, energy)
    ok("one tap turned on catalog tone (auto, sharpen, shadow, fit)", page.evaluate("__tjl.ce().doc.s.pro && __tjl.ce().doc.s.auto && __tjl.ce().doc.s.sharp>=80 && __tjl.ce().doc.s.shadow && __tjl.ce().doc.s.fit"))
    clear_toast(page); page.screenshot(path=SHOTS+"15b-pro-white.png")
    page.click(".ce-prochips [data-v=studio]"); settle(page, 0.45)
    st_c, st_m = px(page, 0.01, 0.02), px(page, 0.5, 0.04)
    ok("Studio chip is one tap (soft gradient, no sliders)", page.evaluate("__tjl.ce().doc.s.bg")=="studio" and st_m[0]>st_c[0]+8, (st_c, st_m))
    clear_toast(page); page.screenshot(path=SHOTS+"15c-pro-studio.png")
    page.click(".ce-prochips [data-v=white]"); settle(page, 0.3)
    # before/after hold shows the original (not white)
    page.dispatch_event("#ceCmp", "pointerdown"); settle(page, 0.45)
    ok("hold Before shows the original photo", page.locator("#ceBadge").is_visible() and px(page, 0.02, 0.02)[:3]!=[255,255,255])
    page.dispatch_event("#ceCmp", "pointerup"); settle(page, 0.3)
    page.click("#ceAdjustBtn"); settle(page, 0.4)
    ok("Adjust opens the brush on this result (not from scratch)", page.locator("[data-act=ceBrushMode][data-v=erase]").count()==1 and page.locator("[data-ce=brush]").count()==1 and page.evaluate("__tjl.ce().doc.mask!==null && __tjl.ce().doc.s.pro===true"))
    page.click("#ceSaveBtn"); page.wait_for_selector("#ceEditor", state="detached"); settle(page, 0.5)
    saved = photos(page)[2]
    ok("Save keeps label and position", saved["label"]==labels_now[2] and saved["id"]!=ids_now[2] and [q["label"] for q in photos(page)]==labels_now and saved.get("origId")==ids_now[2], saved.get("label"))
    page.click("#viewer [data-act=closeModal]"); settle(page)

    # cancel during removal still brightens + sharpens and says the background was left as-is
    page.evaluate("__tjl.ceTestMask({delay:4000})")
    open_viewer_clean(page, 3)
    sig_before = canvas_sig(page)
    page.click("#ceProBtn"); page.wait_for_selector("[data-act=ceRemoveCancel]"); settle(page, 0.2)
    page.click("[data-act=ceRemoveCancel]"); page.wait_for_selector("#ceAdjustBtn", timeout=8000); settle(page, 0.5)
    note = page.inner_text("#cePanel")
    ok("cancel: background left as-is, still brightened and sharpened", "left as-is" in note.lower() and page.evaluate("__tjl.ce().doc.mask")==None and page.evaluate("__tjl.ce().doc.s.bg")=='none' and page.evaluate("__tjl.ce().doc.s.sharp")>=80 and canvas_sig(page)["sig"]!=sig_before["sig"], note.replace("\\n"," ")[:140])
    page.click("[data-act=ceCancel]"); page.wait_for_selector(".scrim"); page.click("[data-act=confirmOk]"); settle(page, 0.4)
    page.click("#viewer [data-act=closeModal]"); settle(page)

    # removal failure: same fallback, no upload
    page.evaluate("__tjl.ceTestMask({delay:150, fail:true})")
    open_viewer_clean(page, 3)
    n_before = len(requests)
    page.click("#ceProBtn"); page.wait_for_selector("#ceAdjustBtn", timeout=8000); settle(page, 0.45)
    ok("failure: background left as-is with the touch-up", "left as-is" in page.inner_text("#cePanel").lower() and page.evaluate("__tjl.ce().doc.s.pro && __tjl.ce().doc.s.bg==='none'"))
    posted = [r for r in requests[n_before:] if r[1]!="GET" or r[3]>0]
    ok("professional edit never uploads the photo", not posted, posted[:3])
    page.click("[data-act=ceCancel]"); page.wait_for_selector(".scrim"); page.click("[data-act=confirmOk]"); settle(page, 0.3)
    ok("viewer has ✨ Make it professional", page.locator("#viewer #ceProViewer").count()==1)
    page.click("#viewer [data-act=closeModal]"); settle(page)
    page.click("#photosCard [data-act=arrangeOpen]"); page.wait_for_selector("#arrGrid"); settle(page, 0.3)
    page.locator("#arrGrid .arr-cell[data-slot='0']").click(); page.wait_for_selector("[data-act=arrPro]")
    ok("photo action sheet has Make it professional", "Make it professional" in page.inner_text("[data-act=arrPro]"))
    page.click("[data-act=closeModal]"); page.click(".arrbar [data-act=arrDone]"); page.wait_for_selector("#photosCard")
    page.evaluate("__tjl.ceTestMask(null)")

    ctx.close()

    # ---------- first use while OFFLINE: clear error ----------
    c2 = mk_ctx(b); p2 = c2.new_page(); watch(p2, "offline")
    p2.goto(BASE); p2.wait_for_selector(".jobcard"); p2.wait_for_function("navigator.serviceWorker.controller!==null", timeout=15000)
    p2.click(".jobcard:has-text('146-6000-00')"); p2.wait_for_selector("#photosCard")
    c2.set_offline(True)
    p2.locator("#photosCard .ph").nth(0).click(); p2.wait_for_selector("#viewer"); p2.click("[data-act=ceFromViewer]"); p2.wait_for_selector("#ceRemoveBtn")
    p2.click("#ceRemoveBtn"); p2.wait_for_selector(".scrim", timeout=10000); settle(p2)
    msg = p2.inner_text(".sheet")
    ok("offline on first use: clear message (needs internet once, ~57 MB, then offline)", "offline" in msg.lower() and "57 MB" in msg and "works offline" in msg, msg.replace("\n"," ")[:160])
    p2.screenshot(path=SHOTS+"12p-offline-first-use.png")
    c2.close()
    b.close()

print("\n=== console/page errors ===")
for e in errors: print(e)
print("none" if not errors else "")
fails = [r for r in results if not r[1]]
print(f"\nFirst download: {FIRST_MB:.1f} MB" if 'FIRST_MB' in dir() else "")
print(f"\n{len(results)-len(fails)}/{len(results)} passed")
