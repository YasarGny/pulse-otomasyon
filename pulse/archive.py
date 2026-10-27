"""Portable offline publication: HTML, local pictures, available MP3s, integrity inventory."""
import copy
import hashlib
import json
import re
import shutil
import tempfile
import zipfile
from pathlib import Path

from pulse.build import assert_public_tree
from pulse.details import display_date
from pulse.publication import SECTIONS, digest, read_json, verify_manifest, write_json
from pulse.source_media import fetch_public, SourceTooLarge
from pulse.archive_media import portable_image

# Original publisher PNGs may legitimately exceed the discovery fetcher's 8 MB.
# Keep original quality and a finite streaming budget; decoder pixel/time limits
# remain independently enforced by portable_image. Article/discovery limits stay
# unchanged. Never silently omit a picture from a supposedly complete backup.
ARCHIVE_IMAGE_MAX_BYTES = 64_000_000


def fetch_archive_image(url):
    return fetch_public(url, limit=ARCHIVE_IMAGE_MAX_BYTES)


def package(site, destination, *, fetch=fetch_archive_image):
    site, destination = Path(site), Path(destination)
    manifest = read_json(site / 'data/publication.json')
    release = site / 'releases' / manifest['release_id']
    verify_manifest(release, manifest)
    assert_public_tree(site)
    editions = {s: read_json(release / f'{s}.json') for s in SECTIONS}
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        # Exactly this day's public tree, never other archives or private generation state.
        for name in ('index.html', 'assets', 'teknoloji', 'oyun', 'haberler', 'akis', 'podcastler', 'gizlilik', 'kosullar'):
            origin = site / name
            # Older verified publications predate the optional Akış route.
            if name == 'akis' and not origin.exists():
                continue
            if origin.is_dir():
                shutil.copytree(origin, root / name)
            else:
                shutil.copyfile(origin, root / name)
        shutil.copytree(release, root / 'releases' / manifest['release_id'])
        downloaded = {}
        for section, data in editions.items():
            for story in data['stories']:
                url = story.get('image_url')
                if not url:
                    continue
                if url in downloaded:
                    name = downloaded[url]
                else:
                    try:
                        body, kind = fetch(url)
                    except SourceTooLarge as exc:
                        # Log a non-sensitive identifier, never a signed source URL.
                        image_id = hashlib.sha256(url.encode()).hexdigest()[:16]
                        raise ValueError(f'Archive image {section}/{image_id}: {exc}') from None
                    body, suffix = portable_image(body, kind)
                    name = hashlib.sha256(body).hexdigest() + suffix
                    path = root / 'media' / name
                    path.parent.mkdir(exist_ok=True)
                    path.write_bytes(body)
                    downloaded[url] = name
                story['archive_image'] = '../../media/' + name
        image_paths = {story['image_url']: story['archive_image'].split('/')[-1]
                       for data in editions.values() for story in data['stories'] if story.get('archive_image')}
        for path in root.rglob('*.html'):
            import html
            prefix = '../' * len(path.parent.relative_to(root).parts)
            content = path.read_text()
            for url, filename in image_paths.items():
                content = content.replace(html.escape(url, quote=True), prefix + 'media/' + filename)
            content = content.replace('class="pulse-loading"', '')
            content = re.sub(r'<script src="[^"]*install\.js(?:\?[^\"]*)?" defer></script>', '', content)
            content = re.sub(r'<link rel="manifest"[^>]*>', '', content)
            content = re.sub(r'<script src="[^"]*printing\.js(?:\?[^\"]*)?" defer></script>', '', content)
            content = re.sub(r'<script src="[^"]*controls\.js[^"]*" defer></script>', '', content)
            # Explicit filenames work with file:// and don't need a local HTTP server.
            content = re.sub(r'(href=")((?!https?:|#)[^"]*/)(")', r'\1\2index.html\3', content)
            content = content.replace('<main id="main"', '<div class="archive-label">Arşiv · ' + display_date(manifest['publish_date']) + '</div><main id="main"', 1)
            chapters = {}
            from pulse.chapters import load_chapters
            for data in editions.values():
                if not data.get('podcast'):
                    continue
                asset = data['podcast']
                chapter_data = load_chapters(site / 'assets/chapters', asset)
                if chapter_data:
                    chapters[asset['sha256']] = chapter_data
            embedded = json.dumps({'manifest': manifest, 'editions': editions, 'chapters': chapters, 'clips': read_json(site / 'assets/clips/index.json') if (site / 'assets/clips/index.json').is_file() else None}, ensure_ascii=False).replace('<', chr(92) + 'u003c')
            script = f'<script>window.PULSE_ARCHIVE=true;window.PULSE_RELEASE={embedded};window.PULSE_RELEASE.url=new URL("{prefix}releases/{manifest["release_id"]}/",location.href);</script>'
            content = re.sub(r'(?=<script src="[^\"]*site\.js)', lambda m: script, content, count=1)
            path.write_text(content)
        inventory = {str(p.relative_to(root)): {'sha256': digest(p), 'bytes': p.stat().st_size} for p in sorted(root.rglob('*')) if p.is_file()}
        write_json(root / 'archive.json', {'schema_version': 1, 'publish_date': manifest['publish_date'], 'display_date': display_date(manifest['publish_date']), 'release_id': manifest['release_id'], 'files': inventory})
        destination.parent.mkdir(parents=True, exist_ok=True)
        tempzip = destination.with_suffix('.partial')
        try:
            with zipfile.ZipFile(tempzip, 'w', compression=zipfile.ZIP_DEFLATED) as z:
                for p in sorted(root.rglob('*')):
                    if p.is_file():
                        info = zipfile.ZipInfo(p.relative_to(root).as_posix(), (2026, 1, 1, 0, 0, 0))
                        info.compress_type = zipfile.ZIP_DEFLATED
                        z.writestr(info, p.read_bytes())
            verify_package(tempzip)
            tempzip.replace(destination)
        finally:
            tempzip.unlink(missing_ok=True)
    return {'release_id': manifest['release_id'], 'publish_date': manifest['publish_date'], 'sha256': digest(destination), 'bytes': destination.stat().st_size}


def verify_package(path):
    with zipfile.ZipFile(path) as z:
        if z.testzip():
            raise ValueError('Corrupt archive')
        inventory = json.loads(z.read('archive.json'))
        if set(z.namelist()) != set(inventory['files']) | {'archive.json'}:
            raise ValueError('Archive inventory mismatch')
        for name, expected in inventory['files'].items():
            if name.startswith('/') or '..' in Path(name).parts:
                raise ValueError('Unsafe archive path')
            body = z.read(name)
            if len(body) != expected['bytes'] or hashlib.sha256(body).hexdigest() != expected['sha256']:
                raise ValueError('Archive integrity mismatch')
    return inventory
