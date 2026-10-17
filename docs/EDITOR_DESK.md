# Editör Masası

The approved PULSE redesign lives in the source repository only. Merging this
branch would make the next scheduled deployment use it; do not merge or deploy
until the owner has reviewed the working result and given final live approval.

## Source and build

- `pulse/pages.py`: one static renderer for the home, all news, section, article
  and listening routes. `pulse/details.py` renders the complete sourced article.
- `site/assets/style.css`: shared dark/light responsive components. Original
  PULSE wordmark, P. favicon and both original cover illustrations are preserved.
- `theme.js` runs before paint. First visit defaults to dark, the user's explicit
  choice is stored locally. Storage denial does not break the site. No external
  font request is required; the system sans stack includes Turkish fallbacks.
- The matching Yeni Sekme / Moradon FM covers use local 192px and 768px WebP
  files. Moradon artwork draws on a medieval merchant-town plaza; it is original
  artwork, not a game screenshot. The covers also appear in the full/mini player
  and supported browser media controls.
- `site.js`: progressive list filtering and one persistent audio element. Internal
  publication navigation keeps audio alive, ordinary links and static full text
  remain usable without the enhancement. The mini player has seeking and an
  expandable panel with the same full controls (not a second audio element).
  The compact player is a 60px floating launcher, not a second scroll frame.
  Its nonmodal controls close on outside press, focus leaving, Escape, explicit
  collapse or another launcher press. There is no inactivity timer while editing
  controls. Collapse retains playback; ending playback is a separate labelled
  action. The page keeps ordinary window scrolling and back-position restoration.
  Speed cycles through 0.75 / 1 / 1.1 / 1.2 / 1.25 / 1.5 / 2. iOS uses device
  volume controls, explicitly labelled instead of a nonfunctional range slider.
  Privacy/terms navigation from an active session also retains audio. Direct
  legal pages remain readable without the publication gate. If publication
  verification expires while a legal page is open, audio stops but legal text
  remains accessible; publication pages still require a verified matching release.
  Media Session supplies the selected episode metadata, cover, playback state,
  position and play/pause/stop/seek handlers where supported. OS/browser policy
  controls notification/lock-screen presentation and background playback; no
  physical-phone validation is implied. Summary routes update tab/OG identity
  independently of any other audio that is already playing. Section stamps use
  their own issue number; combined pages show only the date if numbers differ.
- The print room uses an actual isometric 3D press model. The pink ink roll,
  front ivory blanket roll and hidden impression roll share one scene; the
  newspaper passes through the blanket/impression nip. The rendered paper mask
  and SVG print projection come from that same camera, so ink cannot cross the
  rollers or body. The browser animates only the projected print, with no WebGL
  dependency or frame-by-frame video download. Reduced motion freezes the print;
  hidden tabs pause it. Normal and delayed states share the model, connection
  failure has its separate newspaper illustration. Only connection failure has
  a manual retry button; normal preparation/delay keep polling automatically.
- `scripts/render_press_scene.py` rebuilds the assets and the marked camera
  projection in `printing.js` together. Use Blender 4.3+ and ffmpeg from the repo
  root: `blender -b -t 5 --python scripts/render_press_scene.py`, then format
  `site/assets/printing.js` with Prettier. The native scene and intermediate PNGs
  stay in ignored `test-results/press-render`; only a small WebP and grayscale
  occlusion mask ship to readers. Blender is an optional artwork tool, not a
  production/CI Python dependency.
- The manifest gate waits for both verified editions, all four MP3s **and HTML
  from the matching release**. Cached HTML is refreshed before the site is shown.
  A missing or mismatched page fails closed. No client-clock opening shortcut.
- There are no API keys or model calls in the frontend. Audio production, voice
  identifiers, news sourcing and the daily schedule remain the existing pipeline.

The home uses the first technology story, first gaming story and next technology
story in the editions' existing editorial order. This is a representative selection,
not a newly invented importance score. Full section lists keep their own order.

Every available photograph uses `object-fit: contain`; article images use their
natural ratio. Publisher provenance is linked below the picture without pretending
that the publisher is the photographer. Optional explicit image credits are escaped.
An image transfer error retains the article and its source with a retry control;
it does not replace the picture with unrelated artwork.

## Routes and offline backup

`/`, `/haberler/`, `/podcastler/`, `/teknoloji/`, `/oyun/`, each section's
`/dinle/` and `/haber/<id>/` are built from the same validated daily data.
The offline ZIP includes those pages, local images and the original four MP3s.
It embeds that day's data without the live gate and labels the issue as archived.
No local server is required by the files. Enhanced audio continuity across pages
is for the live HTTP site; `file://` archive pages deliberately use normal links.

The current/older backup retention, canonical daily ZIP verification and public
repository history policy are unchanged. This branch does not rewrite Git history.

## Validation

Run from the repository root:

```sh
python -m unittest discover -s tests -p 'test_*.py'
npm test
npm run test:browser
```

Use `PULSE_PYTHON` to select a prepared Python environment and `PULSE_CHROMIUM` to
select a system Chromium. The browser fixture is explicitly synthetic; it makes
no Gemini, Edge TTS or Drive calls. Screenshots under `test-results/editor-*`
are produced by a real browser, not image generation. They are UI test evidence,
not a claim that the fixture headlines/photos are real reporting.

Browser checks cover both themes, mobile/tablet/desktop widths, keyboard, axe,
200% text enlargement, full-card/source separation, filter/back state, real MP3
playback, speed/10-second seek/volume/mute, audio across reading navigation,
image/audio errors, camera/mask alignment, stale HTML, 07:30/06:00 gates and offline extraction.
Managed Chromium may block `file://`; in that case the suite reports the policy
and serves extracted files from an in-memory origin with external networking
still offline. This is not a physical iPhone/Safari test or field performance data.
