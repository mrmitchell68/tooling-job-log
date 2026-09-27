# Tooling Job Log v2

An offline-first PWA for building mold/job reference sheets on the injection molding floor. It's built for one-handed use on an Android phone in Chrome. There's no login and no server. Everything is stored on the phone (localStorage for jobs, IndexedDB for photos).

```
index.html             the whole app (HTML + CSS + JS, no build step)
manifest.webmanifest   PWA manifest (name, short_name "Job Log", start_url ./, standalone, navy theme)
sw.js                  service worker: caches the app shell + CDN libs (OCR, pdf.js, fonts) for offline use
icons/                 icon-192.png, icon-512.png, icon-maskable-512.png, apple-touch-icon.png, favicon-64.png
shots/                 412×915 phone screenshots
tests/                 Playwright end-to-end test (tests/test.py) + fixture generator
```

All URLs are relative, so it runs from any path: `https://<user>.github.io/<repo>/`, a subfolder, or localhost.

## What's new in 2.1.0 — Mold / Job Reference Sheet

- **Print → Reference sheet** (new default): one Letter page laid out like the shop's Mold / Job Reference Sheet: branded header, a photo grid with a blue label bar on every photo, then Part info / Supplies / Carton & packaging / Packaging description / Operator work instructions / Quality checks / Notes, and a footer band.
  - **All photos print.** 1–4 photos go in one row, 5–8 in rows of 4, 9–12 in rows of 4 with a short last row centered. Photos 13+ continue on page 2 (up to 20 per extra page). If the text columns run long, the photo band shrinks so page 1 still fits.
  - Temps and pressures show as a compact **Process** strip, but only when they have values.
- **Print → Process sheet**: the older layout (specs, temps, pressures, setup steps, recent runs) is still one tap away.
- New job sections: Mold / part information (part #, description, color, part weight, machine cycle time, parts/hr, machine, work order, date, revision), Required for the job (supplies) table, Carton / packaging, Packaging description, Operator work instructions, Quality checks, Notes / comments. Older jobs get the missing sections added automatically. Nothing is deleted or overwritten.
- Photo labels now match the template views (mold front / rear / side / top / bottom, insert detail, side profile, finished part views). To change the order photos print in, use **⇄ Reorder** in Photos, or ◀ / ▶ in the photo viewer.
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
`tests/test.py` runs 49 checks with headless Chrome at 412×915 and writes the screenshots:
```bash
python3 -m venv .venv && . .venv/bin/activate && pip install playwright pillow
python tests/make_fixtures.py        # generates sheet.png + scan2p.pdf in the current dir
python tests/test.py                 # expects the server on :8766; fixture paths are at the top of the script
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
- OCR runs in the browser (Tesseract). It works well on clean printed sheets. Handwriting, glare, curled paper and complex tables are much less reliable. **Paste text from Google Lens** is the most accurate route on Android. Tabular "label / value in the next column" layouts are handled only when both sit on the same line or the value is on the next line.
- Ordinal barrel names (front/center/rear/feed) are ambiguous from shop to shop. They're mapped to Zones 1–4 at low confidence and start unchecked.
- The OCR engine and English data (~7 MB) have to download once before scanning works offline. Everything else works offline after the first load.
- Share PDF goes through the print dialog ("Save as PDF"). There's no one-tap PDF file share. There's no QR code, only a printed Job ID label.
- Data lives only on this phone. Chrome's "Clear site data", or uninstalling the app, deletes it. Back up regularly (the app reminds you after 14 days). There's no automatic sync between devices.
- The backup JSON embeds photos as base64, so files get large with hundreds of photos.
- Fonts (Barlow) load from Google Fonts and are cached by the service worker. On a first load with no connection they fall back to system fonts.
