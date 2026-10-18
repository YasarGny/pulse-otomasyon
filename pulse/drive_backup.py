"""Private Drive backups, verified by full readback before issuing a cleanup receipt."""
import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path

import requests

from pulse.archive import package
from pulse.build import build
from pulse.details import display_date
from pulse.publication import digest, not_before, read_json, write_json

API = 'https://www.googleapis.com/drive/v3/files'


class Drive:
    api = API
    def __init__(self):
        response = requests.post('https://oauth2.googleapis.com/token', data={
            'client_id': os.environ['PULSE_DRIVE_CLIENT_ID'],
            'client_secret': os.environ['PULSE_DRIVE_CLIENT_SECRET'],
            'refresh_token': os.environ['PULSE_DRIVE_REFRESH_TOKEN'],
            'grant_type': 'refresh_token',
        }, timeout=30)
        if not response.ok:
            raise RuntimeError('Drive authentication failed: HTTP ' + str(response.status_code))
        self.session = requests.Session()
        self.session.headers['Authorization'] = 'Bearer ' + response.json()['access_token']

    def request(self, method, url=API, **kwargs):
        response = self.session.request(method, url, timeout=(15, 180), **kwargs)
        if not response.ok:
            raise RuntimeError('Drive operation failed: HTTP ' + str(response.status_code))
        return response

    def children(self, parent, name):
        # Values originate from our own date/release identities or the configured folder ID.
        if not all(c.isalnum() or c in '-_' for c in parent):
            raise ValueError('Invalid Drive folder ID')
        escaped = name.replace('\\', '\\\\').replace("'", "\\'")
        params = {'q': f"'{parent}' in parents and name = '{escaped}' and trashed = false", 'fields': 'files(id,name,size,mimeType,appProperties),nextPageToken', 'pageSize': 100}
        found = []
        while True:
            data = self.request('GET', params=params).json()
            found.extend(data.get('files', []))
            if not data.get('nextPageToken'):
                return found
            params['pageToken'] = data['nextPageToken']

    def daily_files(self, parent, date):
        from pulse.daily_archive import canonical_name
        name = canonical_name(date).removesuffix('.zip')
        params = {'q': f"'{parent}' in parents and trashed = false and mimeType != 'application/vnd.google-apps.folder' and name contains '{name}'", 'fields': 'files(id,name,size,mimeType,appProperties),nextPageToken', 'pageSize': 100}
        found = []
        while True:
            data = self.request('GET', params=params).json()
            found.extend(f for f in data.get('files', []) if f['name'].startswith(name) and f['name'].endswith('.zip'))
            if not data.get('nextPageToken'):
                return found
            params['pageToken'] = data['nextPageToken']

    def folder(self, parent, name):
        found = self.children(parent, name)
        if len(found) > 1:
            raise ValueError('Ambiguous duplicate Drive folder')
        if found:
            if found[0].get('mimeType') != 'application/vnd.google-apps.folder':
                raise ValueError('Drive folder name belongs to a non-folder file')
            return found[0]['id']
        return self.request('POST', json={'name': name, 'parents': [parent], 'mimeType': 'application/vnd.google-apps.folder'}, params={'fields': 'id'}).json()['id']

    def readback(self, file_id, expected):
        metadata = self.request('GET', API + '/' + file_id, params={'fields': 'id,size,appProperties'}).json()
        if int(metadata.get('size', -1)) != expected['bytes'] or metadata.get('appProperties', {}).get('sha256') != expected['sha256']:
            raise ValueError('Drive backup size/checksum metadata mismatch')
        response = self.request('GET', API + '/' + file_id, params={'alt': 'media'}, stream=True)
        h, size = hashlib.sha256(), 0
        with response:
            for chunk in response.iter_content(1024 * 1024):
                h.update(chunk)
                size += len(chunk)
                if size > expected['bytes']:
                    raise ValueError('Drive readback is too large')
        if size != expected['bytes'] or h.hexdigest() != expected['sha256']:
            raise ValueError('Drive full readback verification failed')
        return {'file_id': file_id, **expected, 'verified': True}

    def existing(self, name, parent, release, manifest, *, file_id=None):
        matches = self.children(parent, name)
        if file_id:
            matches = [file for file in matches if file["id"] == file_id]
        if not matches:
            return None
        if len(matches) != 1:
            raise ValueError('Ambiguous archived release')
        file = matches[0]
        expected = {'release_id': manifest['release_id'], 'publish_date': manifest['publish_date'], 'bytes': int(file['size']), 'sha256': file.get('appProperties', {}).get('sha256')}
        receipt = self.readback(file['id'], expected)
        # Check that this is our complete original release, not a same-named ZIP.
        from pulse.archive import verify_package
        import zipfile
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'existing.zip'
            response = self.request('GET', API + '/' + file['id'], params={'alt': 'media'}, stream=True)
            with response, path.open('wb') as target:
                for chunk in response.iter_content(1024 * 1024):
                    target.write(chunk)
                    if target.tell() > expected['bytes']:
                        raise ValueError('Oversize archived release')
            if digest(path) != expected['sha256']:
                raise ValueError('Archive changed during verification')
            inventory = verify_package(path)
            if inventory['release_id'] != manifest['release_id']:
                raise ValueError('Archived identity mismatch')
            with zipfile.ZipFile(path) as z:
                for section in ('teknoloji', 'oyun'):
                    for relative in (section + '.json', section + '/summary.mp3', section + '/podcast.mp3'):
                        if hashlib.sha256(z.read('releases/' + manifest['release_id'] + '/' + relative)).hexdigest() != digest(release / relative):
                            raise ValueError('Archived edition/audio mismatch')
        return receipt

    def upload(self, path, parent, expected):
        path = Path(path)
        matches = self.children(parent, path.name)
        if len(matches) > 1:
            raise ValueError('Duplicate archive names on Drive')
        if matches:
            return self.readback(matches[0]['id'], expected)
        # Resumable protocol avoids assembling MP3-sized multipart bodies in memory.
        session = self.request('POST', 'https://www.googleapis.com/upload/drive/v3/files', params={'uploadType': 'resumable', 'fields': 'id'}, headers={'X-Upload-Content-Type': 'application/zip', 'X-Upload-Content-Length': str(expected['bytes'])}, json={
            'name': path.name, 'parents': [parent], 'appProperties': {'sha256': expected['sha256'], 'release_id': expected['release_id'], **({'release_order': expected['release_order']} if expected.get('release_order') else {})},
        })
        location = session.headers['Location']
        from urllib.parse import urlparse
        if urlparse(location).scheme != 'https' or urlparse(location).hostname != 'www.googleapis.com':
            raise ValueError('Unexpected Drive upload endpoint')
        with path.open('rb') as body:
            result = self.request('PUT', location, data=body, headers={'Content-Type': 'application/zip', 'Content-Length': str(expected['bytes'])}).json()
        return self.readback(result['id'], expected)


def backup_releases(source, published, output, *, drive=None, folder=None, refresh_current=False):
    Path(output).unlink(missing_ok=True)  # A failed retry must not leave a stale cleanup receipt.
    drive = drive or Drive()
    folder = folder or os.environ.get('PULSE_DRIVE_FOLDER_ID') or drive.folder('root', 'PULSE')
    from pulse.daily_archive import select_daily, canonical_name, protect_order, retire_older
    chosen, grouped = select_daily(source, published)
    if not chosen:
        # A retried preparation can follow a successful backup+prune: there is
        # genuinely nothing left to archive. Never mask a missing ready release.
        source_manifest = read_json(Path(source) / 'data/publication.json')
        published_path = Path(published) / 'data/publication.json'
        published_manifest = read_json(published_path) if published_path.exists() else {}
        if source_manifest.get('status') != 'preparing' or published_manifest.get('status') not in (None, 'preparing'):
            raise ValueError('No complete release to archive')
        write_json(output, {'schema_version': 2, 'releases': {}, 'superseded': {}})
        return {}

    active_file = Path(source) / "data/publication.json"
    active = read_json(active_file) if refresh_current and active_file.exists() else {}
    receipts, superseded = {}, {}
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        for date, (release, manifest) in sorted(chosen.items()):
            release_id = manifest['release_id']
            parent = folder
            for part in (date[:4], date[5:7], display_date(date)):
                parent = drive.folder(parent, part)
            files = drive.daily_files(parent, date)
            protect_order(files, manifest)
            # Reuse any already verified legacy/pending/current ZIP of exactly this release.
            matching = [f for f in files if f.get('appProperties', {}).get('release_id') == release_id and int(f.get('size', 0)) > 0]
            receipt = None
            if matching and not (refresh_current and release_id == active.get("release_id")):
                match = sorted(matching, key=lambda f: (f['name'] != canonical_name(date), f['name']))[0]
                try:
                    receipt = drive.existing(match['name'], parent, release, manifest, file_id=match['id'])
                except ValueError:
                    receipt = None  # Rebuild a corrupt/incomplete copy; keep every old ZIP until verification.
            if not receipt:
                snapshot = tmp / 'site'
                build(source, snapshot, release=release, at=not_before(date))
                import uuid
                archive = tmp / (canonical_name(date).removesuffix('.zip') + '.pending-' + uuid.uuid4().hex + '.zip')
                expected = package(snapshot, archive)
                expected['release_order'] = manifest['validated_at']
                receipt = drive.upload(archive, parent, expected)
                archive.unlink()
            receipts[release_id] = retire_older(drive, parent, manifest, receipt)
            superseded.update({old: release_id for old in grouped[date] if old != release_id})
    write_json(output, {'schema_version': 2, 'releases': receipts, 'superseded': superseded})
    return receipts


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', default='site')
    p.add_argument('--published', default='.published')
    p.add_argument('--receipts', default='.drive-receipts.json')
    p.add_argument('--refresh-current', action='store_true', help='Rebuild the active date archive with the current website before retiring its previous ZIP')
    args = p.parse_args()
    receipts = backup_releases(args.source, args.published, args.receipts, refresh_current=args.refresh_current)
    print(f'Drive: {len(receipts)} complete releases verified by full readback; no credentials logged.')


if __name__ == '__main__':
    main()
