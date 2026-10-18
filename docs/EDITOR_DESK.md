# Editör Masası

PULSE uses the approved Editor Desk redesign. The owner authorized this rollout
after the installation and quality checks. Future live design changes still need
the applicable owner approval and passing release checks.

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
  publication navigation keeps audio alive. Persistent header/footer and app-icon/
  manifest links retain their initial absolute targets across history changes;
  their URLs cannot drift into a nested article directory. Ordinary links and static full text
  remain usable without the enhancement. The mini player has seeking and an
  expandable panel with the same full controls (not a second audio element).
  Cards and listening pages contain only stable play/pause actions; starting audio
  never inserts a full transport into editorial content. The single transport
  lives outside main, in the floating panel. Its 60px launcher has a controls icon,
  because clicking it opens controls rather than toggling playback. It remains in
  the same corner, independent of card visibility and scroll position. Card SVGs
  retain strokes so pause bars cannot disappear.
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
  independently of any other audio that is already playing. Public identities use
  the publication date. Internal issue/episode integers stay unchanged for archive
  integrity; they are not repeated in headers, articles or audio controls.
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

## Categories and spoken text

The menu explicitly links Günün seçkisi, Teknoloji, Oyun and Podcast’ler. The home
keeps its mixed editorial selection; category pages show only their own stories,
podcast and daily summary. The podcast library has two large uncropped program
covers; small summaries remain secondary. Direct listening routes never select
or start a track until the user presses play.

`pulse/pronunciations.json` is a reviewed, finite speech lexicon. PULSE is spoken
as **Pals**, per the owner's clarified English pronunciation preference. The
speech layer makes a separate synthesis copy for both Edge TTS and Gemini; the
published news, approved canonical turns and speaker identities remain unchanged.
URLs, email addresses and inline code are protected, phrases match longest-first
at word boundaries, and unknown names are left intact rather than guessed.
`summary-spoken.txt` and `podcast-spoken.json` retain private audit copies; the latter
binds the lexicon and original dialogue hashes. These files do not ship publicly.

Spoken openings use the date and program name, without zero-padded issue numbers.
A defensive legacy-number rule pronounces labelled 003 as üç without changing
product/model numbers. Speech spelling improves synthesis input; it is not a claim
that every future proper noun or provider output is phonetically perfect.
Keep the successful Edge narrator, Gemini API and custom host voice IDs. Bump
`AUDIO_REVISION` when changing speech policy or the lexicon: the input fingerprint
includes its hash, and Gemini segment caches use the transformed turns. Revision 5
uses this shared layer. The workflow derives audio-vN from that constant, rather
than duplicating a hard-coded revision path.

## App installation and desktop media

`manifest.webmanifest` supplies a stable root identity and start URL, standalone
window, theme and 192/512px maskable icons derived from the preserved P. favicon.
Apple touch icons use the same mark. `scripts/render_app_icons.cjs` rasterizes the
original SVG; it is a development tool, not a runtime dependency.

`install.js` provides one quiet "Uygulamayı yükle" footer action on every live
page. There is no automatic installation banner, dialog or repeated reminder.
A click uses the current native `beforeinstallprompt` event when available;
otherwise it opens concise Android, iOS, macOS Safari or desktop instructions.
Cancellation leaves the footer action available. Native prompt failure falls back
to instructions. Acceptance alone does not confirm installation.

Standalone display mode, a current-page `appinstalled` event or a positive
`getInstalledRelatedApps` result hides the action. Old persistent installed and
30-day dismissal records are removed; history never permanently blocks reinstall.
A fresh eligibility event supersedes previous signals, including in-flight related
app checks. Related-app status is refreshed on return/focus when supported. Storage
denial and unknown installation status do not suppress the footer action.
An installed app in another browser/profile and iOS home-screen installations
cannot always be detected; unknown status keeps manual access available without
an automatic reminder. Native dialogs and OS uninstall behavior require physical
browser/device validation. No notification permission or push access is requested.
Offline/no-JavaScript pages leave the inactive footer button hidden.

`sw.js` handles only network navigation. It never puts HTML, daily JSON, stories
or audio into Cache Storage. Network failure shows a self-contained offline
message, not a cached issue. Existing 06:00/07:30 publication validation remains
authoritative. Offline ZIPs omit installation scripts and manifest links.

Media Session is shared by desktop and mobile, with metadata, cover, current
position/rate and supported play/pause/stop/seek actions. Actual notification,
lock-screen and desktop media widgets, and background process survival, depend
on browser/OS policy. Browser API checks are not a physical-device UI test.

## Routes and offline backup

Playback position and rate are kept locally for the four current audio assets,
keyed by publication date, section, audio kind and MP3 hash. No audio is selected
or loaded on a fresh visit. Pressing play explicitly resumes a valid unfinished
record; "Baştan dinle" resets it. Completed/near-complete records are discarded.
Writes are throttled, with final saves on pause, seek, track change and page hide.
Storage denial/corruption falls back safely; no listening data is sent to PULSE.
This does not synchronize listening across devices.

News search combines all query words across visible headline, brief, category and
source text, within the selected section/topic. Turkish casing and diacritics are
normalized. Query, filters, pagination and reading position survive article
return. Empty-result reset clears the query while retaining a section page's
section. There is no search service or network request for the query.

Section lists never link to the mixed list under a misleading "Tüm haberler"
label. "Daha fazla haber" expands the current section only; resetting the topic
filter retains that section and returns keyboard focus to an available control.
Opening an article records its originating selection/list, topic filter, revealed
count, scroll position and focused story in the browser history. "Haberlere dön"
uses that history entry rather than pushing a fresh category page; browser back
and forward retain the same behavior. The context survives an article reload and
is scoped to the verified release. A directly opened article without that context
falls back to its own category. Hash anchors do not override restored back-scroll.

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
image/audio errors, camera/mask alignment, stale HTML, 07:30/06:00 gates, offline extraction,
footer installation/reinstallation/standalone states, desktop Media Session and the real
network-only service worker. Installability is checked in a fresh normal Chromium
profile because incognito profiles deliberately disable installation.
Managed Chromium may block `file://`; in that case the suite reports the policy
and serves extracted files from an in-memory origin with external networking
still offline. This is not a physical iPhone/Safari test or field performance data.
