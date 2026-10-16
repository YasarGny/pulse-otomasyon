"""Bounded, public-network-only retrieval of publisher supplied article images."""
import ipaddress
import socket
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import requests

from pulse.publication import https_url, read_json
from pathlib import Path


def trusted_hosts(section=None):
    configured = read_json(Path(__file__).with_name('feeds.json'))
    groups = [configured[section]] if section else configured.values()
    return {h for feeds in groups for feed in feeds for h in feed['hosts']}


def public_url(url):
    if not https_url(url):
        raise ValueError('HTTPS public URL required')
    host = urlparse(url).hostname
    if urlparse(url).port not in (None, 443):
        raise ValueError('Unexpected source port')
    addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
        raise ValueError('Non-public source address')


def fetch_public(url, *, limit=8_000_000, hosts=None):
    for _ in range(4):
        public_url(url)
        if hosts is not None and urlparse(url).hostname not in hosts:
            raise ValueError('Unapproved publisher redirect')
        with requests.get(url, timeout=(8, 20), stream=True, allow_redirects=False,
                          headers={'User-Agent': 'PULSE/1.0 (+https://yasargny.github.io/)'}) as response:
            if response.is_redirect:
                url = urljoin(url, response.headers['Location'])
                continue
            response.raise_for_status()
            body = bytearray()
            for chunk in response.iter_content(65536):
                body.extend(chunk)
                if len(body) > limit:
                    raise ValueError('Source response too large')
            return bytes(body), response.headers.get('Content-Type', '')
    raise ValueError('Too many source redirects')


class Images(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'meta' and (a.get('property') or a.get('name')) in ('og:image', 'og:image:secure_url', 'twitter:image'):
            self.urls.append(a.get('content', ''))


def article_image(url):
    body, kind = fetch_public(url, limit=2_000_000, hosts=trusted_hosts())
    if 'html' not in kind:
        return ''
    parser = Images()
    parser.feed(body.decode('utf-8', errors='replace'))
    return next((urljoin(url, image) for image in parser.urls if https_url(urljoin(url, image))), '')
