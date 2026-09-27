# Tooling Job Log v2

An offline-first PWA for building mold/job reference sheets on the injection molding floor. It's built for one-handed use on an Android phone in Chrome. There's no login and no server. Everything is stored on the phone (localStorage for jobs, IndexedDB for photos).

```
index.html             the whole app (HTML + CSS + JS, no build step)
manifest.webmanifest   PWA manifest (name, short_name "Job Log", start_url ./, standalone, navy theme)
sw.js                  service worker: caches the app shell + CDN libs (OCR, pdf.js, fonts) for offline use,
                       plus the background-removal model in its own runtime cache (not precached)
bgworker.js            Web Worker that loads @imgly/background-removal on first use and returns the cutout mask
icons/                 icon-192.png, icon-512.png, icon-maskable-512.png, apple-touch-icon.png, favicon-64.png
shots/                 412×915 phone screenshots
tests/                 Playwright end-to-end tests (test.py, test_refsheet.py, test_arrange.py, test_cleanup.py) + fixture generators
```

All URLs are relative, so it runs from any path: `https://<user>.github.io/<repo>/`, a subfolder, or localhost.

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
- OCR runs in the browser (Tesseract). It works well on clean printed sheets. Handwriting, glare, curled paper and complex tables are much less reliable. **Paste text from Google Lens** is the most accurate route on Android. Tabular "label / value in the next column" layouts are handled only when both sit on the same line or the value is on the next line.
- Ordinal barrel names (front/center/rear/feed) are ambiguous from shop to shop. They're mapped to Zones 1–4 at low confidence and start unchecked.
- The OCR engine and English data (~7 MB) have to download once before scanning works offline. Everything else works offline after the first load.
- Share PDF goes through the print dialog ("Save as PDF"). There's no one-tap PDF file share. There's no QR code, only a printed Job ID label.
- Data lives only on this phone. Chrome's "Clear site data", or uninstalling the app, deletes it. Back up regularly (the app reminds you after 14 days). There's no automatic sync between devices.
- The backup JSON embeds photos as base64, so files get large with hundreds of photos.
- Arrange photos: Undo history covers the current visit to the screen only. It's cleared when you tap Done, and pictures that were replaced, rotated or deleted are removed from storage then. If you close the app while on the Arrange screen, those old pictures stay in phone storage unused. They take up space but are never shown or backed up.
- Drag and drop has been tested in desktop Chrome with emulated Android touch (CDP touch events), not yet on a physical phone. If a long-press ever doesn't pick a photo up, tap it and use Move to position.
- Fonts (Barlow) load from Google Fonts and are cached by the service worker. On a first load with no connection they fall back to system fonts.
