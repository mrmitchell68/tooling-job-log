"""v2.3.6: save scan images to the phone (DCT Document folder via File System Access, or Download folder).
No share sheet without a tap. Screenshots -> shots/17-*.png"""
import base64, json, os, time
from playwright.sync_api import sync_playwright
import importlib.util
BASE = "http://localhost:8766/"
SHOTS = "/workspace/tooling-job-log-v2/shots/"
PDF = "/workspace/tjl2-test/drive-scan.pdf"
os.makedirs(SHOTS, exist_ok=True)
pdf_bytes = open(PDF, "rb").read()
errors = []; results = []
def ok(name, cond, extra=""):
    results.append((name, bool(cond), extra))
    print(("PASS " if cond else "FAIL ") + name + ((" — " + str(extra)[:300]) if extra else ""), flush=True)
def watch(pg, tag):
    pg.on("pageerror", lambda e: errors.append(tag+" pageerror: "+str(e)))
    pg.on("console", lambda m: errors.append(tag+" console."+m.type+": "+m.text) if m.type=="error" and "favicon" not in m.text else None)
def mk_ctx(b):
    return b.new_context(viewport={"width":412,"height":915}, device_scale_factor=2, is_mobile=True, has_touch=True, accept_downloads=True,
        user_agent="Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Mobile Safari/537.36")
def new_job(page):
    page.goto(BASE+"#/"); page.wait_for_selector(".fab")
    page.click(".fab"); page.click("[data-act=newBlank]"); page.wait_for_selector("#h_tool")
    page.fill("#h_tool", "T-PHONE"); page.locator("#h_tool").blur(); time.sleep(0.2)
def scan_file(page):
    page.click(".bottombar [data-act=scanMenu]")
    with page.expect_file_chooser() as fc:
        page.click("[data-act=scanHere][data-kind=files]")
    fc.value.set_files(PDF)
    page.wait_for_selector("#phoneBox", timeout=90000)
    time.sleep(0.4)

FAKE_FS = """
(() => {
  window.__fs = {files:{}, picks:0, perm:'granted', reqs:0};
  const mkDir = () => ({
    kind:'directory', name:'DCT Document',
    queryPermission: async () => window.__fs.perm,
    requestPermission: async () => { window.__fs.reqs++; window.__fs.perm='granted'; return 'granted'; },
    getFileHandle: async (name, opt) => {
      if (!(opt && opt.create) && !(name in window.__fs.files)) { const e = new Error('nf'); e.name='NotFoundError'; throw e; }
      return { name, createWritable: async () => { const parts=[]; return { write: async (b) => parts.push(b), close: async () => {
        const blob = new Blob(parts); const buf = new Uint8Array(await blob.arrayBuffer()); let bin=''; for (let i=0;i<buf.length;i++) bin+=String.fromCharCode(buf[i]);
        window.__fs.files[name] = btoa(bin); } }; } };
    }
  });
  window.showDirectoryPicker = async (opts) => { window.__fs.picks++; window.__fs.opts = opts; return mkDir(); };
})();
"""

with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
    # ---------- folder picker available ----------
    ctx = mk_ctx(b); ctx.add_init_script(FAKE_FS)
    page = ctx.new_page(); watch(page, "fs")
    page.goto(BASE+"#/settings"); page.wait_for_selector("#albumCard")
    note = page.inner_text("#albumCard")
    ok("settings: says app can't add to a Gallery album by name", "does not let a web app add pictures to a Gallery album" in note, note)
    ok("settings: choose DCT Document folder button", page.locator("#pickAlbumBtn").count()==1 and "DCT Document" in page.inner_text("#pickAlbumBtn"))
    page.locator("#albumCard").screenshot(path=SHOTS+"17-settings-album.png")
    new_job(page); scan_file(page)
    ok("no auto write before a folder is chosen", page.evaluate("Object.keys(window.__fs.files).length")==0)
    status = page.inner_text("#phoneStatus")
    ok("review: explains camera photo is not in Gallery", "not in your Gallery" in status, status)
    page.locator("#phoneBox").scroll_into_view_if_needed(); page.screenshot(path=SHOTS+"17-review-phonebox.png")
    page.click("#phoneAlbumBtn")
    page.wait_for_function("Object.keys(window.__fs.files).length===1", timeout=10000)
    ok("picker asked for readwrite, starts in Pictures", page.evaluate("window.__fs.opts.mode==='readwrite' && window.__fs.opts.startIn==='pictures'"))
    name, b64 = list(page.evaluate("window.__fs.files").items())[0]
    ok("folder file is the original bytes", base64.b64decode(b64)==pdf_bytes)
    ok("folder file name has part/job + date + ext", name.endswith(".pdf") and ("88-1042-A" in name or "T-PHONE" in name), name)
    page.wait_for_function("/Saved to DCT Document/.test(document.querySelector('.toast')?.textContent||'')", timeout=5000)
    ok("toast: Saved to DCT Document", True)
    page.wait_for_function("/✓ Saved to DCT Document/.test(document.getElementById('phoneStatus').textContent)", timeout=5000)
    ok("review status shows saved", True)
    page.screenshot(path=SHOTS+"17-review-saved.png")
    page.click("[data-act=rvApply]"); page.wait_for_selector("#h_tool"); time.sleep(0.3)
    # second scan: auto write without a tap
    scan_file(page)
    page.wait_for_function("Object.keys(window.__fs.files).length===2", timeout=10000)
    ok("second scan saved to DCT Document automatically", page.evaluate("window.__fs.picks")==1)
    page.click("[data-act=closeModal]"); time.sleep(0.2)
    # permission needs a tap again
    page.evaluate("window.__fs.perm='prompt'")
    scan_file(page); time.sleep(0.6)
    ok("no silent write when the phone wants permission", page.evaluate("Object.keys(window.__fs.files).length")==2)
    st = page.inner_text("#phoneStatus")
    ok("status asks to allow again", "allow it again" in st, st)
    page.click("#phoneAlbumBtn")
    page.wait_for_function("Object.keys(window.__fs.files).length===3", timeout=10000)
    ok("tap requested permission and saved", page.evaluate("window.__fs.reqs")==1)
    # job menu offers the folder + download
    page.click("[data-act=rvApply]"); page.wait_for_selector("#h_tool"); time.sleep(0.3)
    page.click("[aria-label='More actions']"); page.wait_for_selector(".sheet #phoneDlBtn")
    ok("job menu: Save scans to DCT Document", "Save scans to DCT Document" in page.inner_text(".sheet #phoneAlbumBtn"))
    page.locator(".sheet").screenshot(path=SHOTS+"17-job-menu.png")
    page.click("[data-act=closeModal]")
    page.goto(BASE+"#/settings"); page.wait_for_selector("#albumLine")
    ok("settings: folder chosen line", "DCT Document folder" in page.inner_text("#albumLine"), page.inner_text("#albumLine"))
    ctx.close()

    # ---------- no folder picker: Download folder + share failure fallback ----------
    ctx = mk_ctx(b)
    ctx.add_init_script("try{ delete window.showDirectoryPicker; }catch(e){} try{ Object.defineProperty(window,'showDirectoryPicker',{value:undefined,configurable:true}); }catch(e){}")
    ctx.add_init_script("""(() => {
      const share = async () => { const e = new Error('Must be handling a user gesture'); e.name='NotAllowedError'; throw e; };
      Object.defineProperty(navigator, 'share', {configurable:true, writable:true, value: share});
      Object.defineProperty(navigator, 'canShare', {configurable:true, writable:true, value: () => true});
    })();""")
    page = ctx.new_page(); watch(page, "dl")
    new_job(page); scan_file(page)
    ok("no folder button without the picker", page.locator("#phoneAlbumBtn").count()==0)
    with page.expect_download() as dl:
        page.click("#phoneDlBtn")
    d = dl.value
    path = d.path()
    ok("download is the original bytes", open(path,"rb").read()==pdf_bytes)
    ok("download file name", d.suggested_filename.endswith(".pdf") and "PDF" in d.suggested_filename, d.suggested_filename)
    page.wait_for_function("/Download folder/.test(document.querySelector('.toast')?.textContent||'')", timeout=5000)
    t = page.inner_text(".toast")
    ok("toast tells how to move it into DCT Document", "DCT Document" in t, t)
    page.wait_for_function("/Saved to this phone/.test(document.getElementById('phoneStatus').textContent)", timeout=5000)
    page.screenshot(path=SHOTS+"17-review-downloaded.png")
    page.evaluate("document.getElementById('toastRoot').innerHTML=''")
    page.click("#driveSaveBtn")
    page.wait_for_function("/share menu/.test(document.querySelector('.toast')?.textContent||'')", timeout=8000)
    t = page.inner_text(".toast")
    ok("share failure explains and offers SAVE TO PHONE", "SAVE TO PHONE" in t.upper() and "still saved" in t, t)
    page.screenshot(path=SHOTS+"17-share-fail.png")
    with page.expect_download() as dl2:
        page.click(".toast [data-act=toastAct]")
    ok("SAVE TO PHONE downloads", open(dl2.value.path(),"rb").read()==pdf_bytes)
    ctx.close()
    b.close()

bad = [e for e in errors if "Failed to load resource" not in e and "net::ERR" not in e]
ok("no page errors", not bad, bad[:4])
fails = [r for r in results if not r[1]]
print("\n%d checks, %d failed" % (len(results), len(fails)))
raise SystemExit(1 if fails else 0)
