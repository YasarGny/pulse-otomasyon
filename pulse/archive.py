"""Portable offline publication: HTML, local pictures, four MP3s, integrity inventory."""
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
from pulse.source_media import fetch_public
from pulse.archive_media import portable_image


def package(site, destination, *, fetch=fetch_public):
    site, destination = Path(site), Path(destination)
    manifest = read_json(site / 'data/publication.json')
    release = site / 'releases' / manifest['release_id']
    verify_manifest(release, manifest)
    assert_public_tree(site)
    editions = {s: read_json(release / f'{s}.json') for s in SECTIONS}
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        # Exactly this day's public tree, never other archives or private generation state.
        for name in ('index.html', 'assets', 'teknoloji', 'oyun'):
            origin = site / name
            if origin.is_dir():
                shutil.copytree(origin, root / name)
            else:
                shutil.copyfile(origin, root / name)
        shutil.copytree(release, root / 'releases' / manifest['release_id'])
        for section, data in editions.items():
            for story in data['stories']:
                url = story.get('image_url')
                if not url:
                    continue
                body, kind = fetch(url)
                body, suffix = portable_image(body, kind)
                name = hashlib.sha256(body).hexdigest() + suffix
                path = root / 'media' / name
                path.parent.mkdir(exist_ok=True)
                path.write_bytes(body)
                story['archive_image'] = '../../media/' + name
                # Article pages are already static and open directly with file://.
                detail = root / section / 'haber' / story['id'] / 'index.html'
                if detail.exists():
                    import html
                    content = detail.read_text().replace(html.escape(url, quote=True), '../../../media/' + name)
                    detail.write_text(content)
        for path in root.rglob('*.html'):
            content = path.read_text()
            content = content.replace('class="pulse-loading"', '')
            content = re.sub(r'<script src="[^"]*printing.js" defer></script>', '', content)
            # Local files need explicit filenames; browsers do not resolve directory indexes.
            content = re.sub(r'(href=")((?!https?:|#)[^"]*/)(")', r'\1\2index.html\3', content)
            content = content.replace('<main id="main"', '<div class="archive-label">Arşiv · ' + display_date(manifest['publish_date']) + '</div><main id="main"', 1)
            if path == root / 'index.html':
                pass
            elif path.parent.name in SECTIONS:
                embedded = json.dumps({'manifest': manifest, 'editions': editions}, ensure_ascii=False).replace('<', '\\u003c')
                script = f'<script>window.PULSE_ARCHIVE=true;window.PULSE_RELEASE={embedded};window.PULSE_RELEASE.url=new URL("../releases/{manifest["release_id"]}/",location.href);</script>'
                content = content.replace('<script src="../assets/site.js', script + '<script src="../assets/site.js')
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
