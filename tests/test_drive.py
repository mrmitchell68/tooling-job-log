"""v2.3.3: original scan files can be saved to DCT / Building Material.
Mocks the Google token and intercepts Drive upload (no real API). Also checks the
share-sheet fallback when GOOGLE_CLIENT_ID is empty. Screenshots -> shots/15-*.png"""
import base64, json, os, time
from playwright.sync_api import sync_playwright

BASE = "http://localhost:8766/"
SHOTS = "/workspace/tooling-job-log-v2/shots/"
PDF = "/workspace/tjl2-test/drive-scan.pdf"
FOLDER = "17H6NaqOz34DgtE3jnYIZsS341ZiahRVe"
os.makedirs("/workspace/tjl2-test", exist_ok=True)
os.makedirs(SHOTS, exist_ok=True)

def simple_pdf(text):
    stream = ("BT /F1 16 Tf 36 100 Td (%s) Tj ET\n" % text).encode("latin1")
    objs = [
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        b"2 0 obj\n<< /Type /Pages /Count 1 /Kids [3 0 R] >>\nendobj\n",
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 420 200] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n",
        b"4 0 obj\n<< /Length %d >>\nstream\n%sendstream\nendobj\n" % (len(stream), stream),
        b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
    ]
    header = b"%PDF-1.4\n"
    body = b""
    offsets = []
    pos = len(header)
    for o in objs:
        offsets.append(pos)
        body += o
        pos += len(o)
    xref = ("xref\n0 6\n0000000000 65535 f \n" + "".join("%010d 00000 n \n" % off for off in offsets)).encode()
    trailer = ("trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % pos).encode()
    return header + body + xref + trailer

PDF_TEXT = "Material: Polypropylene Part No: 88-1042-A Tool T-100"
pdf_bytes = simple_pdf(PDF_TEXT)
open(PDF, "wb").write(pdf_bytes)

errors = []; results = []
def ok(name, cond, extra=""):
    results.append((name, bool(cond), extra))
    print(("PASS " if cond else "FAIL ") + name + ((" — " + str(extra)[:300]) if extra else ""), flush=True)


def shot(locator, path):
    last=None
    for _ in range(6):
        try:
            locator.screenshot(path=path)
            return
        except Exception as e:
            last=e
            time.sleep(0.35)
    raise last

def watch(pg, tag):
    pg.on("pageerror", lambda e: errors.append(tag+" pageerror: "+str(e)))
    pg.on("console", lambda m: errors.append(tag+" console."+m.type+": "+m.text) if m.type=="error" and "favicon" not in m.text else None)

def mk_ctx(b, client_id=""):
    ctx = b.new_context(viewport={"width":412,"height":915}, device_scale_factor=2, is_mobile=True, has_touch=True,
        user_agent="Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Mobile Safari/537.36")
    if client_id:
        ctx.add_init_script("window.__TJL_GOOGLE_CLIENT_ID=%s;" % json.dumps(client_id))
    return ctx

def new_job(page):
    page.goto(BASE+"#/"); page.wait_for_selector(".fab")
    page.click(".fab"); page.click("[data-act=newBlank]"); page.wait_for_selector("#h_tool")
    page.fill("#h_tool", "T-DRIVE"); page.locator("#h_tool").blur(); time.sleep(0.2)

def scan_file(page):
    page.click(".bottombar [data-act=scanMenu]")
    with page.expect_file_chooser() as fc:
        page.click("[data-act=scanHere][data-kind=files]")
    fc.value.set_files(PDF)
    page.wait_for_selector("#driveSaveBtn", timeout=90000)
    time.sleep(0.3)

SHARE_JS = """
() => {
  window.__shared = null;
  window.__shareCalls = 0;
  const share = async (data) => {
    window.__shareCalls++;
    const files = [];
    for (const f of data.files) {
      const buf = new Uint8Array(await f.arrayBuffer());
      let bin = "";
      for (let i = 0; i < buf.length; i++) bin += String.fromCharCode(buf[i]);
      files.push({name: f.name, type: f.type, size: f.size, b64: btoa(bin)});
    }
    window.__shared = {title: data.title, text: data.text, files};
  };
  const can = () => true;
  try { Object.defineProperty(navigator, "share", {configurable:true, writable:true, value: share}); } catch (e) { navigator.share = share; }
  try { Object.defineProperty(navigator, "canShare", {configurable:true, writable:true, value: can}); } catch (e) { navigator.canShare = can; }
}
"""

with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])

    # ---------- no client id: share sheet ----------
    ctx = mk_ctx(b); page = ctx.new_page(); watch(page, "share")
    hits = {"n": 0}
    def count_google(route):
        hits["n"] += 1
        route.abort()
    page.route("https://www.googleapis.com/**", count_google)
    page.goto(BASE+"#/settings"); page.wait_for_selector("#driveSetupNote")
    note = page.inner_text("#driveSetupNote")
    ok("settings: Drive save needs a one-time Google setup", "Drive save needs a one-time Google setup" in note, note)
    ok("settings: share sheet mentioned", "Share to Google Drive" in note)
    line = page.inner_text("#driveCopyLine").strip()
    ok("settings: scanned documents saved on this phone", line=="Scanned documents: saved on this phone. Drive copy: share sheet", line)
    ok("settings: Send a Drive copy after each scan default on", page.is_checked("#prefDriveCopy"))
    shot(page.locator("#driveCard"), SHOTS+"15-settings-drive-note.png")
    ok("client id empty in the app", page.evaluate("__tjl.googleClientId")=="")
    new_job(page); scan_file(page)
    label = page.inner_text("#driveSaveBtn")
    ok("review: Share to Google Drive button (not a broken Save)", "Share to Google Drive" in label and "Save a copy to Drive" not in label, label)
    ok("review: folder named on the button", "DCT / Building Material" in label)
    ok("review: original scan kept in IndexedDB", page.evaluate("""() => {
      const id = __tjl.state.modal.scanFiles[0].id;
      return __tjl.getPhoto(id).then(b => !!(b && b.size));
    }"""))
    page.locator("#driveBox").scroll_into_view_if_needed()
    shot(page, SHOTS+"15-review-share.png")
    page.evaluate(SHARE_JS)
    page.click("#driveSaveBtn")
    page.wait_for_function("window.__shared && window.__shared.files.length===1", timeout=15000)
    shared = page.evaluate("window.__shared")
    raw = base64.b64decode(shared["files"][0]["b64"])
    ok("share: original PDF bytes (not a re-photo)", raw==pdf_bytes, "got %d expected %d" % (len(raw), len(pdf_bytes)))
    ok("share: title and folder hint", shared["title"]=="Save to Google Drive" and "Building Material" in (shared["text"] or ""))
    ok("share: file name keeps .pdf and says PDF", shared["files"][0]["name"].endswith(".pdf") and "PDF" in shared["files"][0]["name"], shared["files"][0]["name"])
    ok("share: did not call the Drive API", hits["n"]==0, hits["n"])
    page.wait_for_selector(".toast")
    ok("share: success toast", "Shared" in page.inner_text(".toast") and "err" not in (page.get_attribute(".toast","class") or ""))
    shot(page, SHOTS+"15-share-toast.png")
    # share unavailable
    page.evaluate("""() => {
      const can = () => false;
      try { Object.defineProperty(navigator, "canShare", {configurable:true, writable:true, value: can}); } catch (e) { navigator.canShare = can; }
      try { Object.defineProperty(navigator, "share", {configurable:true, writable:true, value: undefined}); } catch (e) {}
    }""")
    page.click("#driveSaveBtn")
    page.wait_for_function("document.querySelector('.toast.err') && /isn't available/i.test(document.querySelector('.toast').textContent)", timeout=10000)
    ok("share unavailable toast", "isn't available" in page.inner_text(".toast"))
    ok("share unavailable: scan files still stored", page.evaluate("(__tjl.state.modal.scanFiles||[]).length===1"))
    # paste has no file, so no button
    page.click("[data-act=closeModal]")
    page.click(".bottombar [data-act=scanMenu]")
    page.click("[data-act=scanHere][data-kind=paste]")
    page.fill("#pasteBox", "Material: PP")
    page.click("[data-act=pasteGo]")
    page.wait_for_selector(".sheet h3:has-text('Review')")
    ok("paste review has no Drive button", page.locator("#driveSaveBtn").count()==0)
    page.click("[data-act=closeModal]")
    ctx.close()

    # ---------- client id: mocked token + upload ----------
    ctx = mk_ctx(b, "test-client.apps.googleusercontent.com")
    ctx.add_init_script("""
      try {
        var m = JSON.parse(localStorage.getItem('tjl2.meta')||'{}');
        m.driveCopy = false;
        localStorage.setItem('tjl2.meta', JSON.stringify(m));
      } catch (e) {}
    """)
    page = ctx.new_page(); watch(page, "up")
    state = {"mode": "ok", "posts": [], "gets": []}
    def handle(route):
        req = route.request
        if req.method == "GET" and "/drive/v3/files/" in req.url:
            state["gets"].append({"url": req.url, "auth": req.headers.get("authorization")})
            route.fulfill(status=200, content_type="application/json",
                body=json.dumps({"id": FOLDER, "name": "Building Material", "mimeType": "application/vnd.google-apps.folder", "capabilities": {"canAddChildren": True}}))
            return
        if req.method == "POST" and "/upload/drive/" in req.url:
            raw = req.post_data_buffer or b""
            state["posts"].append({"url": req.url, "auth": req.headers.get("authorization"), "body": raw})
            if state["mode"] == "fail":
                route.fulfill(status=403, content_type="application/json", body=json.dumps({"error": {"message": "The user does not have sufficient permissions"}}))
            else:
                route.fulfill(status=200, content_type="application/json",
                    body=json.dumps({"id": "file123", "name": "saved", "webViewLink": "https://drive.google.com/file/d/file123/view"}))
            return
        route.fulfill(status=599, body="unexpected "+req.url)
    page.route("https://www.googleapis.com/**", handle)
    page.goto(BASE); page.wait_for_selector(".fab")
    ok("client id applied for upload build", page.evaluate("__tjl.googleClientId")=="test-client.apps.googleusercontent.com")
    page.goto(BASE+"#/settings"); page.wait_for_selector("#driveSetupNote")
    note = page.inner_text("#driveSetupNote")
    ok("settings with client id does not hide behind the setup note", "one-time Google setup" not in note and "Building Material" in note, note)
    new_job(page); scan_file(page)
    label = page.inner_text("#driveSaveBtn")
    ok("review: Save a copy to Drive button", "Save a copy to Drive" in label and "DCT / Building Material" in label, label)
    sid = page.evaluate("__tjl.state.modal.scanFiles[0].id")
    page.locator("#driveBox").scroll_into_view_if_needed()
    shot(page, SHOTS+"15-review-save.png")
    page.evaluate("""() => { window.__tjlDriveToken = () => "test-token"; window.__driveLog = []; }""")
    page.click("#driveSaveBtn")
    page.wait_for_selector(".toast a.tlink", timeout=20000)
    ok("progress shown", any(t.startswith("Saving ") and "to Drive" in t for t in page.evaluate("window.__driveLog||[]")), page.evaluate("window.__driveLog"))
    ok("one upload posted", len(state["posts"])==1, len(state["posts"]))
    post = state["posts"][0]
    ok("upload uses the signed-in token", post["auth"]=="Bearer test-token", post["auth"])
    body = post["body"]
    i = body.find(b"{"); j = body.find(b"}", i)
    meta = json.loads(body[i:j+1])
    ok("upload metadata is only name + parent folder", set(meta.keys())=={"name","parents"} and meta["parents"]==[FOLDER], meta)
    ok("upload body contains the original PDF bytes", pdf_bytes in body, "body %d pdf %d" % (len(body), len(pdf_bytes)))
    today = page.evaluate("""() => { var d=new Date(); function z(n){return (n<10?'0':'')+n;} return d.getFullYear()+'-'+z(d.getMonth()+1)+'-'+z(d.getDate()); }""")
    ok("upload file name has part or job, PDF, date, extension",
       meta["name"].endswith(".pdf") and "PDF" in meta["name"] and today in meta["name"] and ("88-1042-A" in meta["name"] or "T-DRIVE" in meta["name"]),
       meta["name"]+" expected "+today)
    ok("folder probe used the same token", state["gets"] and all(g["auth"]=="Bearer test-token" for g in state["gets"]))
    toast = page.inner_text(".toast")
    href = page.get_attribute(".toast a.tlink", "href")
    ok("success toast with Drive link", "Saved a copy to Drive" in toast and href=="https://drive.google.com/file/d/file123/view", (toast, href))
    ok("success is not an error toast", "err" not in (page.get_attribute(".toast","class") or ""))
    ok("blobs removed after a successful save", page.evaluate("""id => __tjl.getPhoto(id).then(b => !b)""", sid))
    ok("review no longer offers the button", page.locator("#driveSaveBtn").count()==0)
    shot(page, SHOTS+"15-save-success.png")
    page.click("[data-act=closeModal]")

    # failure keeps the file; job menu still offers save; cancel + offline + skip
    state["mode"] = "fail"
    state["posts"].clear()
    scan_file(page)
    page.evaluate("""() => { window.__tjlDriveToken = () => "test-token"; window.__driveLog = []; }""")
    page.click("#driveSaveBtn")
    page.wait_for_function("document.querySelector('.toast.err') && /permissions|Drive/i.test(document.querySelector('.toast').textContent)", timeout=20000)
    err = page.inner_text(".toast")
    ok("failure toast", "err" in (page.get_attribute(".toast","class") or "") and "permission" in err.lower(), err)
    ok("failure did not delete the scan", page.evaluate("(__tjl.state.modal.scanFiles||[]).length===1"))
    kept = page.evaluate("__tjl.state.modal.scanFiles[0].id")
    ok("failure bytes still in IndexedDB", page.evaluate("""id => __tjl.getPhoto(id).then(b => b && b.size)""", kept)==len(pdf_bytes))
    page.click("[data-act=rvApply]"); page.wait_for_selector("#h_tool"); time.sleep(0.3)
    ok("apply keeps scan files on the job", page.evaluate("(__tjl.state.jobs.find(j=>j.id===__tjl.state.route.id).scanFiles||[]).length===1"))
    page.click("[aria-label='More actions']")
    page.wait_for_selector(".sheet #driveSaveBtn")
    menu = page.inner_text("#driveSaveBtn")
    ok("job menu: Save a copy to Drive for stored scans", "Save a copy to Drive" in menu and "DCT / Building Material" in menu, menu)
    shot(page, SHOTS+"15-job-menu.png")
    page.evaluate("""() => { window.__tjlDriveToken = () => ""; }""")
    page.evaluate("document.getElementById('toastRoot').innerHTML=''")
    page.click("#driveSaveBtn", force=True)
    page.wait_for_function("document.querySelector('.toast.err') && /Sign-in cancelled/i.test(document.querySelector('.toast').textContent)", timeout=10000)
    ok("sign-in cancel toast", "Sign-in cancelled" in page.inner_text(".toast") and "Nothing was uploaded" in page.inner_text(".toast"))
    ok("cancel leaves the scan stored", page.evaluate("(__tjl.state.jobs.find(j=>j.id===__tjl.state.route.id).scanFiles||[]).length===1"))
    ctx.set_offline(True)
    page.click("#driveSaveBtn")
    page.wait_for_function("document.querySelector('.toast.err') && /offline/i.test(document.querySelector('.toast').textContent)", timeout=10000)
    ok("offline toast", "offline" in page.inner_text(".toast").lower())
    ctx.set_offline(False)
    page.click("#driveSkipBtn")
    page.wait_for_function("!(__tjl.state.jobs.find(j=>j.id===__tjl.state.route.id).scanFiles||[]).length")
    ok("skip removes the job menu button", page.locator("#driveSaveBtn").count()==0)
    ok("skip deletes the IndexedDB blob", page.evaluate("""id => __tjl.getPhoto(id).then(b => !b)""", kept))
    ctx.close()

    # ---------- v2.3.4 auto: share once, keep file, no second share, toggle off ----------
    AUTO_SHARE_JS = """
(() => {
  const share = async (data) => {
    const n = +(localStorage.getItem('tjl.testShareN')||'0') + 1;
    localStorage.setItem('tjl.testShareN', String(n));
    window.__shareCalls = n;
    const files = [];
    for (const f of data.files) {
      const buf = new Uint8Array(await f.arrayBuffer());
      let bin = '';
      for (let i = 0; i < buf.length; i++) bin += String.fromCharCode(buf[i]);
      files.push({name: f.name, type: f.type, size: f.size, b64: btoa(bin)});
    }
    window.__shared = {title: data.title, text: data.text, files};
  };
  const can = () => true;
  try { Object.defineProperty(navigator, 'share', {configurable:true, writable:true, value: share}); } catch (e) { navigator.share = share; }
  try { Object.defineProperty(navigator, 'canShare', {configurable:true, writable:true, value: can}); } catch (e) { navigator.canShare = can; }
})();
"""
    ctx = mk_ctx(b)
    ctx.add_init_script(AUTO_SHARE_JS)
    page = ctx.new_page(); watch(page, "auto")
    new_job(page)
    page.click(".bottombar [data-act=scanMenu]")
    with page.expect_file_chooser() as fc:
        page.click("[data-act=scanHere][data-kind=files]")
    fc.value.set_files(PDF)
    page.wait_for_selector("#driveSaveBtn", timeout=90000)
    page.wait_for_function("+(localStorage.getItem('tjl.testShareN')||'0')===1", timeout=15000)
    ok("auto share invoked once after scan", page.evaluate("+(localStorage.getItem('tjl.testShareN')||'0')")==1)
    shared = page.evaluate("window.__shared")
    ok("auto share title points at Drive folder", shared["title"]=="Save to Google Drive" and "Google Drive" in (shared["text"] or "") and "Building Material" in (shared["text"] or ""), shared)
    raw = base64.b64decode(shared["files"][0]["b64"])
    ok("auto share sends the original PDF", raw==pdf_bytes)
    jid = page.evaluate("__tjl.state.route.id")
    ok("file stored with the job", page.evaluate("""id => { const j=__tjl.state.jobs.find(x=>x.id===id); return !!(j && (j.scanFiles||[]).length===1); }""", jid))
    sid = page.evaluate("""id => __tjl.state.jobs.find(x=>x.id===id).scanFiles[0].id""", jid)
    ok("stored scan blob kept in IndexedDB", page.evaluate("""id => __tjl.getPhoto(id).then(b => b && b.size)""", sid)==len(pdf_bytes))
    shot(page, SHOTS+"16-review-autoshare.png")
    page.click("[data-act=closeModal]")
    time.sleep(0.2)
    page.reload()
    page.wait_for_selector("[aria-label='More actions']", timeout=20000)
    page.click("[aria-label='More actions']")
    page.wait_for_selector(".sheet #driveSaveBtn")
    time.sleep(0.7)
    ok("reopen does not share again", page.evaluate("+(localStorage.getItem('tjl.testShareN')||'0')")==1)
    ok("job menu still offers Share to Google Drive", "Share to Google Drive" in page.inner_text("#driveSaveBtn"))
    shot(page, SHOTS+"16-reopen-menu.png")
    page.click("[data-act=closeModal]")
    page.goto(BASE+"#/settings"); page.wait_for_selector("#prefDriveCopy")
    page.uncheck("#prefDriveCopy")
    page.wait_for_function("__tjl.state.meta.driveCopy===false")
    ok("toggle off stays off", page.is_checked("#prefDriveCopy")==False)
    shot(page.locator("#driveCard"), SHOTS+"16-settings-share-sheet.png")
    page.goto(BASE+"#/job/"+jid)
    page.wait_for_selector(".bottombar [data-act=scanMenu]")
    page.click(".bottombar [data-act=scanMenu]")
    with page.expect_file_chooser() as fc:
        page.click("[data-act=scanHere][data-kind=files]")
    fc.value.set_files(PDF)
    page.wait_for_selector("#driveSaveBtn", timeout=90000)
    time.sleep(0.8)
    ok("toggle off skips the share sheet", page.evaluate("+(localStorage.getItem('tjl.testShareN')||'0')")==1)
    ok("toggle off still saves the file on the job", page.evaluate("""id => (__tjl.state.jobs.find(x=>x.id===id).scanFiles||[]).length===2""", jid))
    ctx.close()

    # ---------- auto upload posts the Building Material folder id ----------
    ctx = mk_ctx(b, "test-client.apps.googleusercontent.com")
    ctx.add_init_script("window.__tjlDriveToken = function(){ return 'test-token'; };")
    page = ctx.new_page(); watch(page, "autoup")
    up = {"posts": []}
    def handle_auto(route):
        req = route.request
        if req.method == "GET" and "/drive/v3/files/" in req.url:
            route.fulfill(status=200, content_type="application/json",
                body=json.dumps({"id": FOLDER, "name": "Building Material", "mimeType": "application/vnd.google-apps.folder", "capabilities": {"canAddChildren": True}}))
            return
        if req.method == "POST" and "/upload/drive/" in req.url:
            up["posts"].append(req.post_data_buffer or b"")
            route.fulfill(status=200, content_type="application/json",
                body=json.dumps({"id": "file999", "name": "saved", "webViewLink": "https://drive.google.com/file/d/file999/view"}))
            return
        route.fulfill(status=599, body="unexpected "+req.url)
    page.route("https://www.googleapis.com/**", handle_auto)
    new_job(page)
    page.click(".bottombar [data-act=scanMenu]")
    with page.expect_file_chooser() as fc:
        page.click("[data-act=scanHere][data-kind=files]")
    fc.value.set_files(PDF)
    page.wait_for_selector(".toast a.tlink", timeout=90000)
    ok("auto upload posted once without tapping the button", len(up["posts"])==1, len(up["posts"]))
    body = up["posts"][0]
    i = body.find(b"{"); j = body.find(b"}", i)
    meta = json.loads(body[i:j+1])
    ok("auto upload parent is DCT / Building Material", meta.get("parents")==[FOLDER], meta)
    ok("auto upload body is the original PDF", pdf_bytes in body)
    page.goto(BASE+"#/settings"); page.wait_for_selector("#driveCopyLine")
    line = page.inner_text("#driveCopyLine")
    ok("settings: Drive copy DCT / Building Material once direct save is on", "Scanned documents: saved on this phone. Drive copy: DCT / Building Material" in line, line)
    shot(page.locator("#driveCard"), SHOTS+"16-settings-direct.png")
    ctx.close()
    b.close()

bad = [e for e in errors if "Failed to load resource" not in e and "net::ERR" not in e]
ok("no page errors", not bad, bad[:4])
fails = [r for r in results if not r[1]]
print("\n%d checks, %d failed" % (len(results), len(fails)))
for f in fails:
    print("FAILED:", f[0], "—", f[2])
raise SystemExit(1 if fails else 0)
