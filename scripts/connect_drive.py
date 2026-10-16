"""One-time local OAuth consent. Secrets go directly to GitHub, never to chat/logs.
Usage: python scripts/connect_drive.py --client-file /path/client_secret.json
Requires local Python with requests and an authenticated GitHub CLI.
"""
import argparse
import http.server
import json
import secrets
import subprocess
import threading
import urllib.parse
import webbrowser
from pathlib import Path

import requests


def gh(*args, value=None):
    result = subprocess.run(['gh', *args], input=value, text=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if result.returncode:
        raise RuntimeError('GitHub setting failed. Check gh authentication and repository admin access.')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--client-file', required=True)
    p.add_argument('--repo', default='YasarGny/pulse-otomasyon')
    args = p.parse_args()
    client = json.loads(Path(args.client_file).read_text()).get('installed')
    if not client:
        raise ValueError('A Desktop app OAuth client JSON is required')
    state, received = secrets.token_urlsafe(32), {}
    complete = threading.Event()

    class Callback(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
            if q.get('state') != [state] or 'code' not in q:
                self.send_error(400)
                return
            received['code'] = q['code'][0]
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'PULSE: Google consent received. Return to your terminal.')
            complete.set()

        def log_message(self, *args):
            pass

    server = http.server.HTTPServer(('127.0.0.1', 0), Callback)
    redirect = f'http://127.0.0.1:{server.server_port}'
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = 'https://accounts.google.com/o/oauth2/v2/auth?' + urllib.parse.urlencode({
        'client_id': client['client_id'], 'redirect_uri': redirect, 'response_type': 'code',
        'scope': 'https://www.googleapis.com/auth/drive.file', 'state': state,
        'access_type': 'offline', 'prompt': 'consent',
    })
    print('Opening Google consent in your browser. Only files created by PULSE are requested.')
    if not webbrowser.open(url):
        print(url)  # Public consent link; contains no access/refresh token or client secret.
    if not complete.wait(300):
        raise RuntimeError('Google consent timed out; no settings changed')
    server.shutdown()
    response = requests.post('https://oauth2.googleapis.com/token', data={
        'client_id': client['client_id'], 'client_secret': client['client_secret'],
        'code': received['code'], 'redirect_uri': redirect, 'grant_type': 'authorization_code',
    }, timeout=30)
    if not response.ok:
        raise RuntimeError('Google token exchange failed: HTTP ' + str(response.status_code))
    token = response.json()
    if not token.get('refresh_token'):
        raise RuntimeError('No offline refresh token received; no settings changed')
    response = requests.post('https://www.googleapis.com/drive/v3/files', headers={'Authorization': 'Bearer ' + token['access_token']}, json={'name': 'PULSE', 'mimeType': 'application/vnd.google-apps.folder'}, timeout=30)
    if not response.ok:
        raise RuntimeError('Cannot create private PULSE folder: HTTP ' + str(response.status_code))
    folder = response.json()['id']
    # Pause backup while installing its settings. Never print secret values on failure.
    gh('variable', 'set', 'PULSE_DRIVE_ENABLED', '--repo', args.repo, '--body', 'false')
    for name, value in [('PULSE_DRIVE_CLIENT_ID', client['client_id']), ('PULSE_DRIVE_CLIENT_SECRET', client['client_secret']), ('PULSE_DRIVE_REFRESH_TOKEN', token['refresh_token'])]:
        gh('secret', 'set', name, '--repo', args.repo, value=value)
    gh('variable', 'set', 'PULSE_DRIVE_FOLDER_ID', '--repo', args.repo, '--body', folder)
    print('Drive folder created and GitHub Secrets saved. Backup is still disabled until a successful rehearsal.')
    print('Private folder: https://drive.google.com/drive/folders/' + folder)


if __name__ == '__main__':
    main()
