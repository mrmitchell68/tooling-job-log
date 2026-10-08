# Tooling Job Log v2

An offline-first PWA for building mold/job reference sheets on the injection molding floor. It's built for one-handed use on an Android phone in Chrome. There's no login and no server. Everything is stored on the phone (localStorage for jobs, IndexedDB for photos).

```
index.html             the whole app (HTML + CSS + JS, no build step)
manifest.webmanifest   PWA manifest (name, short_name "Job Log", start_url ./, standalone, navy theme)
sw.js                  service worker: caches the app shell + CDN libs (OCR, pdf.js, fonts) for offline use,
                       plus the background-removal model in its own runtime cache (not precached)
bgworker.js            Web Worker that loads @imgly/background-removal on first use and returns the cutout mask
vendor/                jsPDF 4.2.1 UMD (MIT, see jspdf.LICENSE.txt): builds scan PDFs on the phone, precached for offline
icons/                 icon-192.png, icon-512.png, icon-maskable-512.png, apple-touch-icon.png, favicon-64.png
shots/                 412×915 phone screenshots
tests/                 Playwright end-to-end tests (test.py, test_refsheet.py, test_arrange.py, test_cleanup.py, test_scanfields.py, test_realforms.py, test_drive.py) + fixture generators
```

All URLs are relative, so it runs from any path: `https://<user>.github.io/<repo>/`, a subfolder, or localhost.

## What's new in 2.3.11 — Job photos go to Drive (DCT / Photos); Open Drive PDF for missing pictures

**Why job photos never reached Drive:** before 2.3.11 there was no photo upload at all. Job photos lived only in the phone's
IndexedDB. The **📁 Drive / Files** button in Photos only *picks* pictures from Drive, and the only Drive upload code (Google
sign-in) needs `GOOGLE_CLIENT_ID`, which is empty on the live app. Only scan PDFs had a working path (the Apps Script, 2.3.7+).

- **Photos → DCT / Photos.** Each job photo is posted to the same Apps Script as the scan PDFs (`action: "saveDocPhoto"`,
  no-cors, one at a time, time limit + 2 retries, progress “Uploading photo 2 of 6” with **Stop**). The script saves it in
  **DCT / Photos** (folder fixed on the server). It accepts only JPEG / PNG / WebP (checked by content) and skips a name it already has.
- **Automatic** right after you take or pick a photo (⚙️ → *Upload every job photo to Drive automatically*, on by default).
  If the job has no Part name, part number or tool # yet, the photo waits and goes as soon as you fill one in.
- **Name:** `<Part name> <YYYY-MM-DD> photo N.jpg`, e.g. `Closet Flange 2026-10-08 photo 1.jpg`. Part name, else part number,
  else tool / mold # (same as the PDFs); the date the photo was added; N = next free number. The name is saved on the photo,
  so retries never make copies.
- **Small posts:** photos are sent as JPEG, long side at most 2000 px (most are already 1280 px and go as they are; cleaned-up PNGs go on white).
- **Never deletes:** the photo always stays on the phone.
- **Waiting / retry:** no signal or Google unreachable → kept in a queue and sent when the app opens or the phone is back online.
- ⚙️ → **Upload all saved photos to Drive (DCT / Photos)** checks Drive first (re-sends any photo that didn't arrive) and sends
  every photo not sent yet. Job ⋮ → **Upload photos to Drive** sends that job's photos.
- **Safe before the script update:** photos are only sent once the script answers `docInfo` with `photos:true` (Code.gs 2.3.11).
  With the older script they wait on the phone (no false “sent”), and go by themselves once the new version is live.
- **Open Drive PDF.** A job with Missing photos/scans shows a banner with **📄 Open Drive PDF**; the photo viewer of a Missing photo
  and job ⋮ also have it. The script (`action=findDocs`, JSONP) searches DCT / Building Material for the Part name, part number
  and tool # (case-insensitive, punctuation ignored, whole words first, newest first, at most 20) and the app lists the matches;
  tap one to open it. No match → **Open Building Material folder**. Older script / no signal → the folder plus a Google Drive search link.
- Example-job placeholder pictures are never uploaded.

**Code.gs 2.3.11** (deploy as a new version of the same web app): `DOC_PHOTO_FOLDER_ID`; doPost `saveDocPhoto` → `saveDocPhoto_`
(`imageType_`, `photoName_`); doGet `docInfo` → `docInfo_`, `findDocs` → `findDocs_` (`findNorm_`, `jsonpOut_`);
`docExists_` takes `kind=photo` to check DCT / Photos.

## What's new in 2.3.10 — Keep scan originals after Drive copy; show missing photos

- **Bug fix:** “Save a copy to Drive” (direct Google upload when a client id is set) was **deleting the local scan files** after a successful upload. That looked like “copy” but acted like “move,” so older jobs lost their stored scans / local previews after a Drive save — and PDF upload / Re-send / Save to phone could no longer find the originals. Instant share-sheet and PDF upload already kept them; direct upload now does too. Toast: “Saved a copy to Drive. Original still on this phone.”
- **Skip Drive copy** still removes the stored scans from the phone (by design — the button says so).
- Job / list photos whose IndexedDB blob is gone (phone cleared storage, low space, etc.) show a clear **Missing** placeholder instead of a blank tile.
- Scan keep asks the browser for persistent storage so the phone is less likely to wipe photos when space is low.
- PDF “Sent to Drive” never removed local scans (unchanged). If images already disappeared on the phone, the **Drive PDFs in DCT / Building Material** are the backup.

## What's new in 2.3.9 — Drive PDFs are named by Part name

- Each PDF is named **`<Part name> <YYYY-MM-DD>.pdf`**, using the **Part name** on the job sheet (the job's `partName` field, shown under the tool # on the job sheet and job card). If the part name is empty, the part number is used, then the tool / mold #. Slashes, quotes and `: * ? < > |` are replaced with spaces.
- A short time is added only when it's needed to keep names unique (another scan of the same part on the same day): `Closet Flange 2026-10-06 0611.pdf`, then `…061114.pdf`, then `(2)`. Split PDFs keep `… part 1 of 2.pdf`.
- The name is saved with the scan the first time it's worked out, so retries always use the same name and the script skips duplicates. Changing the part name later doesn't rename scans already named.
- Scans already sent under a number (2.3.7 / 2.3.8) keep that name. **Upload all** and **Re-send all** don't make renamed copies. Settings → **Send copies named by part name** (with a confirm) is the only thing that sends them again under the part name. The old number-named files stay in Drive.

## What's new in 2.3.8 — "Upload all saved scans" fixed: small uploads, one at a time, with progress and Stop

- **Why 2.3.7 got stuck:** older scans (saved before 2.3.7) were merged into one big PDF per job, and an original PDF was sent at full size, so a single upload could be many MB. Each upload had no time limit, so one slow or dropped mobile upload left the button greyed out with no progress, and failures were only marked "waiting to retry". Nothing reached Drive.
- Every post now stays small. Pages are downscaled to 1800 px (JPEG 0.72) and shrunk again if a page is still over about 650 KB. A scan that would make a PDF over about 2.2 MB is split into **`… part 1 of 3.pdf`**, **`… part 2 of 3.pdf`**, and so on. An original PDF over 2.2 MB is redrawn page by page with pdf.js and rebuilt small. If pdf.js can't load, a PDF up to 12 MB is sent as is.
- Uploads run **one at a time** with a time limit per request (45 s plus 1 s per 40 KB, at most 5 min) and 2 quick retries (3 s, then 8 s). If 2 PDFs in a row can't reach Google, the app stops instead of grinding through the rest. Everything stays on the phone and is listed as "not sent yet".
- A progress panel shows **"Making PDF 2 of 6…" / "Uploading 2 of 6 · 628 KB…"** with **Stop**. The busy state always clears, including after errors, timeouts, and Stop. The screen stays on while it runs (wake lock).
- **Upload all** sends PDFs that are waiting to retry plus scans not sent yet, each once. **Re-send all saved scans** sends everything again, and the script skips names already in the folder. A retry that starts when the app opens can be taken over by tapping Upload all.
- Optional Drive check: with **Code.gs 2.3.8** deployed (`doGet ?action=docExists`, JSONP), Upload all asks the script which PDFs are really in DCT / Building Material and re-sends any that are missing. If the script hasn't been updated, the app works without the check.
- The app shows no "wait N minutes" message.

## What's new in 2.3.7 — Scans upload to Google Drive as PDF (DCT / Building Material)

- Each scan is made into a **PDF on the phone** and sent to Drive → **DCT / Building Material** through the owner's Google Apps Script web app (`saveDocPdf`). The Drive folder is fixed on the server; the app never picks a folder.
- Photos are downscaled (long side 2000 px, JPEG 0.8). All pages scanned together become **one PDF**. A scanned PDF is sent as is. File name: `<part no. or job> <yyyy-mm-dd> <hhmmss>.pdf`. That name stays the same on every retry, and the script skips a name that's already in the folder.
- Review scanned values → **Scan image on this phone** → **Upload PDF to Drive (DCT / Building Material)**. Job ⋮ menu → **Upload scans to Drive as PDF**.
- Settings → **Upload scans to Drive as PDF**: **Upload every scan to Drive automatically** (on by default; sends after Apply selected / Create job), and **Upload all saved scans to Drive** (one PDF per scan, skips scans this phone already sent).
- The post uses `fetch` `no-cors` (text/plain JSON), so the phone can't read Google's reply. "Sent to Drive" means the PDF was handed to Google. With no signal it says "Saved on this phone. Upload will retry." The queue keeps only names and scan ids, never PDF bytes. It retries when the app opens, when the phone comes back online, and before the next upload.
- The 2.3.6 save-to-phone buttons are still there. No share sheet opens without a tap.

## What's new in 2.3.6 — Save scan images to the phone (DCT Document)

- Review scanned values now has **Scan image on this phone**: **Save to DCT Document** (Android Chrome 132+: pick Pictures → DCT Document once; later scans are written there automatically while the phone keeps the permission) and **Save to phone (Download folder)**.
- A web app cannot add pictures to a Gallery album by name; writing into the DCT Document folder is the closest thing. Otherwise the file goes to Download and can be moved in Gallery.
- No more automatic share sheet after a scan (Android blocks it without a tap, which caused "Couldn't open the share sheet"). Share to Google Drive is a tap; if the phone still refuses, the message offers SAVE TO PHONE.
- Settings → Save scans to the phone: choose/change/forget the folder, auto-save toggle. Job menu: Save scans to DCT Document / Save scans to phone.

## What's new in 2.3.5 — Scans save on the phone and offer a Drive copy

When you scan or photograph a document (camera, gallery, PDF, or Google Drive / Files), the **original file is saved with that job** on the phone as soon as the review screen opens.

- **Send a Drive copy after each scan** is on by default (Settings).
- **Until a Google client id is set** (the app today): the Android share sheet opens once, so you can pick **Google Drive → DCT → Building Material**. If you dismiss it, the file stays on the phone and the job's ⋮ menu still has **Share to Google Drive**. Opening the job again does not pop the sheet again.
- **Once a Google client id is set:** the file uploads straight into **DCT / Building Material**. The first time, Google asks you to sign in. If the app can't write that folder yet, you choose **Building Material** once and the phone remembers it.
- Settings says **Scanned documents: saved on this phone. Drive copy: share sheet**, or **Drive copy: DCT / Building Material** after that folder is remembered (or when direct upload is on).
- Paste-text scans have no file. A direct upload (and a share-sheet copy) keep the stored originals on the phone so PDF upload / re-send still works. **Skip Drive copy** is what removes them.

## What's new in 2.3.4 — ✨ Make it professional

One tap does the edit Allen would ask for, instead of driving every slider.

- **✨ Make it professional** is the primary button on the Clean up screen, under the photo in the viewer, and on the Arrange photo sheet.
- That tap removes the background (same on-device model, same download / progress / Cancel), puts the part on a **clean white** background with a little padding and a **soft shadow**, centers it, and applies a stronger catalog brighten, contrast, and a real **unsharp mask** (only inside the part, so the cut edge doesn't pick up a halo from the old background).
- The result shows immediately. **Hold ◐** to see the original. **Save** and **Cancel** are at the top. **White** is the default; **Studio** (soft light gradient) is one tap. **Adjust** opens the brush, crop, and sliders **starting from this result**.
- If background removal is cancelled or fails, the photo is still brightened and sharpened and the screen says the **background was left as-is**.
- The photo is never uploaded. The manual Clean up tools are still there.

## What's new in 2.3.3 — Save a copy of the scan to Google Drive

After you photograph or pick a job document (camera, gallery, or Drive/Files), the **original file** is kept on the phone until you save it or skip.

- **Review screen:** **Save a copy to Drive** (DCT / Building Material), or **Skip Drive copy**.
- **Job menu (⋮):** the same actions stay available for any scan files still stored with that job. Paste-text scans have no file, so they don't show the button.
- **What is uploaded:** only the original photo/PDF bytes you scanned — not the rest of the job. The Drive file name is the part number (or job name), the document type (Photo or PDF), the date, and a short time, with the original extension.
- **How it signs in:** Google Identity Services on the phone, as the Google account you pick. Scope is `drive.file` (files this app creates). The first time, if that account can't write to the Building Material folder yet, you choose **Building Material** once (Google Picker) or grant Drive access so the known folder can be used. The folder id is remembered on this phone.
- **Until a Google client id is set in the app:** the button is **Share to Google Drive** and opens the Android share sheet so you can drop the files in Drive today. Settings explains: "Drive save needs a one-time Google setup."

## What's new in 2.3.2 — Real job forms fill in from a scan

**Why scans of real forms came out empty before:** phone photos of the paper forms
have heavy table grid lines, uneven light and a little skew. Tesseract dropped whole
tables (the Work Instructions header came back empty), and the parser only understood
simple "Label value" lines. It could not read tables, packaging blocks, BOM item lists,
NetSuite printouts (ALL-CAPS labels with the value on the next line), or several documents at once.

- **Better OCR for phone photos:** the page is auto-cropped, deskewed (±4°), scaled up to about 2400 px,
  put through an adaptive threshold, and the table grid lines are removed before OCR. Tesseract then runs in block mode (PSM 6).
  This takes about 0.5 s of preprocessing plus a few seconds of OCR per page.
- **Understands the real layouts:**
  - **Operator Work Instructions:** 4-column header table (two label/value pairs per row, "Part Wt. 0.288" in one cell),
    REQUIREMENT / METHOD rows (split into Quality checks and Operator work instructions, each with its method),
    PACKAGING INFORMATION with several components (e.g. *FP 124 Small Box Back* and *FP 124 Front Plate*, each with its own carton rows),
    packaging description and pallet, and Tool # / Machine # from the notes.
  - **Bill of Materials:** WO#, date, customer, assembly, qty required, machine + tonnage, material, and supply lines with quantities
    (these go into *Required for the job*).
  - **NetSuite item printout:** column labels with values on the next line (item number, display name, customer, machine,
    tool number, cavities, tool cycle time).
- **Several documents → one job:** each photo/file is parsed on its own and then merged. A good value is never replaced by a blank.
  When the documents disagree (for example Tool # 134-4004-02 vs 134-4003-00), the review screen shows an amber
  **"⚠ The documents disagree — tap the right value"** row with one button per value. The value most documents agree on is pre-selected.
- Handwriting is usually not readable. It shows up as an unmatched line you can assign or skip, instead of turning into garbage values.
- **Version is easy to find:** Settings now opens with an **App version 2.3.2** card and a **🔄 Check for update** button.
  The button checks GitHub Pages, installs the new version and reloads. The app also checks for updates when it comes back
  to the foreground and every hour, and `sw.js` is never served from a cache.

## What's new in 2.3.1 — Scanned values now print on the Reference Sheet

**Bug fixed:** part weight, shot weight, material, color and other molding values that came from a scan or paste were saved on the job but were missing from the printed **Mold / Job Reference Sheet**. The causes:
- The reference sheet printed a fixed list of fields, looked up by internal key only. Custom fields, fields with no key, Specs (grade, tonnage, temps, pressures), unknown labels and custom sections printed only on the old Process sheet.
- Jobs made in v2.0.x saved "Color" into *Material grade/color* and "part weight" as *Shot weight*. The v2.1 migration then added empty Color / Part weight fields, and the sheet printed those blanks.
- There were also parser gaps. "Material Type: X" was saved as "Type". "Mold temp" matched Tool #. Header-row tables weren't read. OCR's "Ibs" wasn't treated as lb, so weights printed as grams. Labels inside sentences were matched. On multi-column sheets, values ran on into the next column.

**Where values print now (Reference Sheet):**
- **Mold / Part Information:** Customer, Part name/number, Description, Material, Color, Cavities, Part weight, Shot weight, cycle times, Machine/Press, Tool #, and so on. Values saved under a custom label with the same meaning are picked up too.
- **Material & Process** strip (only fields that have values): Material grade, Colorant/masterbatch, Let-down ratio, Regrind %, Dryer temp/time, Clamp tonnage, Shot size, Barrel temps, Nozzle/zones, Mold temp, Injection/hold pressures, Hold/Cooling times.
- **Other specs:** every other field that has a value, plus custom sections (notes, tables, steps). When they don't fit, the sheet continues on page 2.

**Scan labels recognized** (with or without a colon, value on the same line or the next line, in header-row tables or two-column layouts, tolerant of OCR letter swaps like `weiqht` and `Materia1`):
- **Part weight:** Part Weight, Part Wt, Part Wt. (g), Piece weight, Piece wt
- **Shot weight:** Shot Weight, Shot Wt, Shot size (a weight unit makes it the shot weight)
- **Material:** Material, Resin, Material Type, Resin type, Plastic. *Grade* / Material grade go to Material grade.
- **Color:** Color, Colour, Material Color. Colorant / Masterbatch / MB and Let-down ratio / LDR have their own fields.
- **Units:** g, grams, kg, oz, lb, lbs, OCR "Ibs"/"1bs", cc, in³, °F/°C, psi/bar, s/sec, %, ton. A unit written in the label is used too, e.g. "Part Wt. (g)" or "Regrind %".
- **Other molding fields:** cycle time, cavities / cavitation, press / machine, clamp tonnage, mold / tool number, part number, customer, regrind %, dryer temp/time, barrel temps, nozzle, zones, mold temp, injection / hold pressure, hold time, cooling time.

**Review screen:**
- Unknown "Label: value" lines are offered as **Other spec**.
- Lines that matched nothing are listed under **Not matched to a field** with a dropdown so you can assign each one to any field or keep it as an Other spec.
- A banner warns when some values are unchecked.

**Existing jobs:** a safe migration (schema 4) runs on load, and no data is deleted:
- Custom or unkeyed fields whose label means Part weight, Shot weight, Material, Color and so on are linked to the proper field.
- A v2.0 *Material grade/color* that holds only a color is copied into Color.
- If two fields hold different values, both are kept, and the extra one prints under Other specs.

**⋮ → 🔁 Re-check notes / saved scan** re-reads text saved in Notes into the review screen. Use it if a scan's text ended up in Notes.

**OCR:** runs at a higher resolution and in sparse-text mode, and rebuilds lines from word positions so that labels and values in table columns stay together.

## What's new in 2.3.0 — ✨ Clean up (photo editor)

A full-screen **✨ Clean up** editor for one photo: remove the background, put the part on a clean backdrop, and touch it up. It works in light and dark mode. It has four tabs:
- **Background.** **Remove background** runs *on the phone*. Photos are never uploaded anywhere. Backdrops: None (transparent), White, Light gray, Studio (soft light gradient), Company navy, a Custom color picker, and **Photo…** (pick any picture, with optional Blur). Other options: **Soft shadow** under the part, and **Center & fit**, which centers the part with padding when a new background is used.
- **Touch up.** **Auto enhance** (levels, white balance, gamma), plus Brightness, Contrast, Sharpness and a **Straighten** slider (±15°). There are also ⟲ / ⟳ 90° buttons.
- **Crop.** Free, 1:1 or 4:3. Drag the corners, or drag inside the box to move it.
- **Brush.** Fixes the cutout by hand. **Erase** removes leftover background, **Restore** paints the part back, and there's a brush-size slider, stroke Undo and **Auto cutout** (reset to the model's mask). Zoom with two fingers or the + / − buttons, and pan with two fingers.
- **Before / after:** hold the ◐ button to see the original, or tap it quickly to toggle.
- **Save** replaces the job's photo in the same position with the same label. **Cancel** throws the edits away.

Where to find it:
- **After adding photos:** a toast asks "✨ Clean up this photo?" (Clean up / Skip). For several photos it asks "Clean up N new photos?" (One by one / Skip all). The one-by-one editor shows "Photo 2 of 5" and a Skip rest button. To turn this off, go to ⚙️ → **Offer cleanup after adding photos**.
- **Arrange photos → tap a photo → ✨ Clean up** (and **↺ Revert to original**). Both can be undone.
- **Photo viewer:** the ✨ Clean up / ↺ Revert to original buttons are under the picture.
- **Batch:** **✂️ Remove background from all N photos…** at the bottom of the Arrange screen. Pick one backdrop (white / gray / studio / navy / transparent) with Auto enhance, Shadow and Center & fit options. It shows progress and can be cancelled, and the whole run is one Undo step.

How it works:
- **Model:** [@imgly/background-removal](https://github.com/imgly/background-removal-js) 1.7.0 (ISNet, quantized `isnet_quint8`, ONNX Runtime Web / WASM) runs in a Web Worker. It downloads the **first time you tap Remove background, about 54 MB** (44 MB model + 12 MB WASM runtime + ~0.5 MB JS). The download shows progress and can be cancelled. The service worker keeps it in a separate cache (`tjl-bgmodel-v1`), so after that it **works offline** and survives app updates. It is not part of the app-shell precache. If the phone is offline on first use, you get a clear message. ⚙️ shows whether the remover is downloaded and lets you delete it. The model works on objects, not just people. The library is AGPL-3.0 licensed, which fits this open, public repo.
- The model looks at a 1024 px version of the photo. Its mask is scaled back up to the working size (up to 1280 px), cleaned up (firmer edges, stray specks dropped) and applied. The worker is shut down right after each cutout to give memory back.
- **Output:** with a backdrop, the photo is flattened and saved as JPEG q0.82 (≤1280 px), like other photos, so it prints well. With **None (transparent)**, it's saved as PNG so the transparency is kept. The print sheet shows it on white.
- **Original kept:** the first time a photo is cleaned up, its original picture stays in IndexedDB. The photo record keeps `origId` (plus `origBytes/origW/origH/cleanedAt`). **↺ Revert to original** (viewer or Arrange) brings it back. Re-editing a cleaned photo starts from the saved result (or tap **↩ Start over from the original photo**) and keeps the same original. Backups, job export and Duplicate job include the originals, so **a cleaned photo takes about twice the space in a backup**. To free that space, use ⚙️ → **Forget kept originals** (this removes the revert option). Older data needs no migration, and bad `origId` values are dropped safely.

## What's new in 2.2.0 — Arrange photos

A full-screen **Arrange photos** screen for putting photos in the exact order they print on the reference sheet. Open it from **↕ Arrange** in the job's Photos section, or **↕ Arrange photos** on the Print screen.
- The grid matches the sheet: 4 across, the same rows (a short last row is centered), big position numbers and labels, and a dashed **✂ Page 2** divider after photo 12 (then every 20).
- **Drag and drop:** on a phone, press and hold a photo for about ¼ s, then drag it. A dashed "Drop here" slot shows where it will land. The page scrolls on its own near the top and bottom edges, and a quick swipe still scrolls normally. With a mouse, just drag.
- **Tap a photo** for big buttons: Move first / last / earlier / later, **Move to position…** (tap a number 1–N), **Change label** (template views or your own text), **Replace picture** (camera, gallery or Google Drive / Files; the label and position stay), **Rotate 90°** (saves a rotated, compressed JPEG), View full size, and **Delete**.
- **⇅ Preset order** sorts photos into the template view order: mold front (A), rear (B), side left, side right, top, bottom, insert detail, side profile, then finished part top, bottom and front edge. Other photos keep their order after those.
- Every change saves immediately. **↶ Undo** (bottom bar, top bar, or UNDO on the toast) steps back through the changes made on this screen. **✓ Done** returns to where you came from. The job's Photos grid and the printed sheet follow the new order.
- The old ⇄ Reorder mode has been replaced by this screen. ◀ / ▶ in the photo viewer still work.

## What's new in 2.1.0 — Mold / Job Reference Sheet

- **Print → Reference sheet** (new default): one Letter page laid out like the shop's Mold / Job Reference Sheet: branded header, a photo grid with a blue label bar on every photo, then Part info / Supplies / Carton & packaging / Packaging description / Operator work instructions / Quality checks / Notes, and a footer band.
  - **All photos print.** 1–4 photos go in one row, 5–8 in rows of 4, 9–12 in rows of 4 with a short last row centered. Photos 13+ continue on page 2 (up to 20 per extra page). If the text columns run long, the photo band shrinks so page 1 still fits.
  - Temps and pressures show as a compact **Process** strip, but only when they have values.
- **Print → Process sheet**: the older layout (specs, temps, pressures, setup steps, recent runs) is still one tap away.
- New job sections: Mold / part information (part #, description, color, part weight, machine cycle time, parts/hr, machine, work order, date, revision), Required for the job (supplies) table, Carton / packaging, Packaging description, Operator work instructions, Quality checks, Notes / comments. Older jobs get the missing sections added automatically. Nothing is deleted or overwritten.
- Photo labels now match the template views (mold front / rear / side / top / bottom, insert detail, side profile, finished part views). To change the order photos print in, use **↕ Arrange** in Photos (2.2.0), or ◀ / ▶ in the photo viewer.
- Settings → **Company branding**: company name, tagline, slogans, footer text and an optional logo (compressed and stored on the phone).
- Scan-to-fill also reads Part Number, Description, Color, Part/Shot Weight (lbs), Avg./Machine Cycle Time, Parts Per Hour, Machine, Work Order, Date, Revision, Carton Size, Qty per Carton, Pallet Size and Cartons per Layer.

## Run locally
```bash
cd /workspace/tooling-job-log-v2
python3 -m http.server 8766
# open http://localhost:8766/
```
The service worker needs http(s) or localhost. If you open the file with `file://`, the app works but the service worker doesn't, so nothing is cached for offline use.

## Put it on GitHub Pages and install it on Android
1. Create a repo and commit the contents of this folder. `shots/` and `tests/` are optional.
2. Go to Settings → Pages and choose Deploy from branch → `main` / root.
3. Open `https://<user>.github.io/<repo>/` on the phone in Chrome.
4. Tap ⋮ → **Install app** (or **Add to Home screen**). It opens full-screen as "Job Log".
5. Open ⚙️ → **Download scanning engine for offline** once while on Wi-Fi. After that, scanning works with no signal too. The app also tries this by itself on Wi-Fi about 8 seconds after first launch.

**Shipping an update:** edit `index.html`, then bump `VERSION` in `sw.js`. The next time the phone opens the app, it shows "A new version is ready → Update".

## Features
- **Job list:** Search covers every field: tool #, customer, part, material, press, and also notes, steps and run-log text. Multi-word searches try the exact phrase first (so "press 3" doesn't also match "3.5 s"), then fall back to all-words. Status chips (All / Active / Setup / On hold / Done) show counts. Press chips are built from your jobs. Sort by recently updated, tool #, or customer. Pinned (★) jobs stay on top. Cards show a thumbnail, material, setup progress and "updated 2h ago".
- **Structured process sheet:** New jobs start with default sections:
  - **Specs:** Material, Grade/color, Dryer temp/time, Cavities, Shot weight g, Cycle time s, Runner type, Gate type, Shrinkage %
  - **Temperatures:** Nozzle, Zones 1–4, Mold A side, Mold B side (°F or °C)
  - **Pressures & speeds:** Injection pressure, Hold pressure, Hold time, Back pressure, Screw RPM, Cooling time
  - **Setup steps** (8 sensible defaults) and **Notes**

  Values are always editable. Tap **Edit** on a section to rename it, reorder or delete fields, change units (there's a list of suggestions), or move and delete the section. Deletes can be undone. You can add custom sections (fields, checklist or notes). Fields with numeric units bring up the number keyboard, and Enter jumps to the next field. There's a preference for °F/psi or °C/bar on new jobs.
- **Templates / duplicate:** ⋮ → *Save as mold template* (with values, or as a blank layout). **+ New job → From a mold template** creates a new job in Setup status with the press cleared. *Duplicate job* copies the sheet and photos but clears the checklist and run log.
- **Setup checklist mode:** Steps have big check boxes on the sheet, with a progress bar and ↺ Reset. **Setup mode** is a full-screen view:
  - large text, and a sticky "5 / 8 steps" progress bar
  - the next step is highlighted, and tapping anywhere on a row toggles it
  - a key-settings grid (temps and pressures) for reference while setting up
  - the screen stays on (Wake Lock)
  - a short vibration on each check, and "All steps done → Log run" at the end

  Reset can be undone.
- **Run history / change log:** Each entry has a date, operator (remembered and suggested), what changed, cycle time, and issues. Quick chips cover common changes. If you edit an existing value on the sheet (for example hold pressure 850 → 900), it's saved as an **unlogged change**. These show as a banner and get pre-filled into the next entry. Saving an entry can also update Cycle time on the sheet. The log shows the cycle-time range. You can edit or delete entries (with undo).
- **Scan to fill:**
  - Input can be a camera photo, one or more gallery images, a PDF (all pages, up to 15), or **Paste text** (from Google Lens).
  - For a PDF, the text layer is used when it has one (exact and instant). Scanned pages go through OCR with Tesseract.js, after grayscale and contrast cleanup.
  - A synonym dictionary maps shop wording to fields, for example "Inj Press", "1st stage pressure", "Hold/Pack", "Barrel zone 1", "Z1", "A-side/cavity side", "B-side/core side", "BP", "Screw speed", "Dry temp"/"Dry time". Numbers are split from their units and the units are normalized (°F, psi, s, hr, rpm, g, in…). Common OCR digit mistakes are fixed (O→0, l→1).
  - The unit is checked against the field type: "Hold 5 sec" goes to Hold time, not Hold pressure.
  - Labels you added yourself are matched too. Other "Label: value" lines are offered as new fields, unchecked.
  - **You always review before anything is applied.** Each value shows a confidence %, its current value, and the source line. You can edit the value and unit. Low-confidence items start unchecked. You can optionally save the raw scanned text into Notes.
  - Scanning from **+ New job** creates the job only when you tap *Create job*.
- **Photos:** Take a photo or upload several at once. Each is compressed to 1280 px JPEG q0.72 (about 50–250 KB). You get quick label presets (Part, Mold A/B side, Gate, Water lines, Setup sheet, Defect…) or can type your own. Tap a photo for a fullscreen viewer with swipe/prev/next, relabel and delete (with undo).
- **Print / share:** A clean one-page Letter sheet. It has a navy header with tool #, part, and a **Job ID label** (e.g. `J-0PQK1`), plus customer, press, status and date. Below that are up to 4 labeled photos, a 2-column spec layout, a checklist with empty ☐ boxes, notes, and the last 3 runs. **Print / Save PDF** uses Chrome's print dialog; you can share the PDF from there. **Share text** uses the Web Share API to send a plain-text summary to SMS, WhatsApp or email; if sharing isn't available it copies to the clipboard. There's also *Copy summary* and *Export job file*.
- **Backup:** ⚙️ → **Share backup file** (Web Share with the file, e.g. to Google Drive or Gmail) or **Download backup file**. Either way you get one `.json` with all jobs, templates and photos (as data URLs). **Import / merge** matches jobs by ID and keeps whichever copy is newer, adds new ones, restores photos, and shows a summary. Importing onto a fresh phone removes the untouched sample jobs. You can export a single job from the job menu. A **14-day backup reminder** banner can be snoozed for 3 days. The settings page shows last backup, storage used, and whether storage is protected; the app requests `navigator.storage.persist()`.
- **General:** Light/dark/system theme (◐ button in Setup mode and Settings). The Android back button works because views use hash routes (`#/job/<id>/setup`). Destructive actions have undo. Tap targets are 44–64 px, and main actions sit at the bottom of the screen (bottom bar, FAB, setup bar) so you can reach them with your thumb.
- **Examples:** Two sample jobs are marked **EXAMPLE**: T-1042 "Cap, 28mm" (PP, Press 7, setup 5/8, 3 run entries, photos) and T-2210 "Battery door, housing" (ABS, Press 3). There's also one example template. Remove them with ⚙️ → *Remove example jobs & template*, or delete each one.
- **v1 data:** On first run, jobs saved by v1 on the same origin (`toolingJobLog.v1`) are imported automatically. Photos carry over because v2 uses the same IndexedDB store.

## Tests
`tests/test.py` runs 52 checks with headless Chrome at 412×915 and writes the screenshots:
```bash
python3 -m venv .venv && . .venv/bin/activate && pip install playwright pillow
python tests/make_fixtures.py        # generates sheet.png + scan2p.pdf in the current dir
python tests/test.py                 # expects the server on :8766; fixture paths are at the top of the script
python tests/test_refsheet.py        # reference sheet, branding, migration
python tests/test_arrange.py         # Arrange photos: touch long-press drag, mouse drag, auto-scroll, action sheet, undo, print order
python tests/make_cleanup_sample.py  # synthetic "part on a busy workbench" photo + ground-truth mask (tests/fixtures/)
python tests/make_scan_fixtures.py   # sample mold sheet PDF (text layer) + PNG (for OCR) in tests/fixtures/
python tests/test_realforms.py       # 2.3.2 the 3 real phone-photo forms (tests/fixtures), merge/conflicts, apply, detail, sheet, update flow
python tests/test_phone.py           # 2.3.6 save scans to DCT Document folder / Download folder
python tests/test_docpdf.py          # 2.3.7 scan → PDF → Apps Script post (script.google.com is intercepted, never reached), offline queue
python tests/test_naming239.py       # 2.3.9 '<Part name> <date>.pdf' names, fallbacks, uniqueness, stability, copies only on request
python tests/test_upload238.py       # 2.3.8 Upload all with 19 big scans: small posts, progress/Stop, timeout+retry, waiting+unsent, Re-send all, docExists check
python tests/test_drive.py           # 2.3.5 auto-save scan on the job + Drive copy (share sheet or mocked upload)
python tests/test_scanfields.py      # 2.3.1 scan labels/units, review + assign, apply, detail, both print layouts, page 2, migration
python tests/test_cleanup.py         # ✨ Clean up: every entry point, REAL background removal (downloads the model), backgrounds,
                                     # sliders, crop, rotate, brush, save/revert/cancel, print sheet, batch, offline, dark mode, setting
```
It covers:
- service worker registration, control and caching; manifest; icon sizes
- search, filters and pinning
- pending-change capture, checklist, reset and undo, run log
- paste parsing (10 field checks) and applying the review
- one-page print (PDF page count)
- blank job, template, job from template, duplicate
- custom field and undo
- photo compression, labeling and viewer
- OCR on a real image (8/8 key fields) and on a 2-page image PDF (values from both pages)
- full and per-job export, import into a fresh profile, re-import without duplicates
- backup reminder, delete + undo, offline reload

Chrome's `Page.getInstallabilityErrors` reports no errors, so the app is installable.

## Known gaps
- **Clean up / background removal:**
  - Accuracy is good on a solid part against a background that's clearly different. It is weaker on **clear, translucent or shiny parts** (reflections of the bench get kept or holes get cut), on parts the same color as the background, and on **clutter touching the part** (it's often kept as part of the "object"). Use the Brush to fix these. On the synthetic test photo the cutout overlapped the true part by IoU 0.67, because touching clutter was kept. A real stapler photo came out clean.
  - **Speed:** the model runs single-threaded WASM on the CPU, because GitHub Pages can't send the COOP/COEP headers that multi-threading needs, and WebGPU isn't used. It takes about 8–9 s per photo on a desktop CPU, and likely **15–40 s on a mid-range phone** (not measured). Batch on many photos takes a while.
  - **Memory:** about 0.8 GB peak while the model runs (its input is fixed at 1024×1024). On phones with little RAM, Chrome might kill the tab. The worker is shut down after each photo to limit this.
  - Tested in desktop headless Chrome with Android emulation (412×915, touch). **Not yet tried on a physical Android phone.**
  - Rotate 90° in Arrange rotates the cleaned photo only. The kept original isn't rotated, so Revert brings back the original orientation.
- OCR runs in the browser (Tesseract). It works well on clean printed sheets. Handwriting, glare, curled paper and complex tables are much less reliable. **Paste text from Google Lens** is the most accurate route on Android. Label/value tables, header-row tables and two-column sheets are handled. Dense 3-column sheets still misread a word now and then (e.g. a work-order line), so always check the review screen. The migration can't tell a v2.0 "part weight" that was saved as Shot weight from a real shot weight, so check those old jobs by eye.
- Ordinal barrel names (front/center/rear/feed) are ambiguous from shop to shop. They're mapped to Zones 1–4 at low confidence and start unchecked.
- The OCR engine and English data (~7 MB) have to download once before scanning works offline. Everything else works offline after the first load.
- Share PDF goes through the print dialog ("Save as PDF"). There's no one-tap PDF file share. There's no QR code, only a printed Job ID label.
- Data lives only on this phone. Chrome's "Clear site data", or uninstalling the app, deletes it. Back up regularly (the app reminds you after 14 days). There's no automatic sync between devices.
- The backup JSON embeds photos as base64, so files get large with hundreds of photos.
- Arrange photos: Undo history covers the current visit to the screen only. It's cleared when you tap Done, and pictures that were replaced, rotated or deleted are removed from storage then. If you close the app while on the Arrange screen, those old pictures stay in phone storage unused. They take up space but are never shown or backed up.
- Drag and drop has been tested in desktop Chrome with emulated Android touch (CDP touch events), not yet on a physical phone. If a long-press ever doesn't pick a photo up, tap it and use Move to position.
- Fonts (Barlow) load from Google Fonts and are cached by the service worker. On a first load with no connection they fall back to system fonts.
