"""Exact compact URL hashes; legacy Bloom hits are advisory, never exclusion.

No article bodies. The irreversible old filter is retained for diagnostics;
confirmed identities accumulate separately without probabilistic false positives.
"""
import base64
import hashlib
import re
import zlib
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

SIZE = 512 * 1024
BITS = SIZE * 8
HASHES = 7
TRACKING = {'fbclid', 'gclid', 'dclid', 'msclkid', 'mc_cid', 'mc_eid'}


def canonical_url(url):
    parts = urlsplit(url)
    if parts.scheme.lower() not in ('http', 'https') or not parts.hostname or parts.username or parts.password:
        raise ValueError('Invalid source URL')
    host = parts.hostname.lower().removeprefix('www.')
    port = parts.port
    if port and port not in (80, 443):
        host += ':' + str(port)
    query = sorted((k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
                   if not k.lower().startswith('utm_') and k.lower() not in TRACKING)
    # Preserve content-bearing parameters, path case, and distinct article IDs.
    return urlunsplit(('https', host, parts.path.rstrip('/') or '/', urlencode(query), ''))


def fingerprint(url):
    return hashlib.sha256(canonical_url(url).encode()).hexdigest()


class SourceHistory:
    def __init__(self, record=None):
        self.data = bytearray(SIZE)
        self.exact = set()
        self.legacy = False
        if record is None:
            return
        if record.get('schema_version') == 3:
            if record.get('algorithm') != 'sha256-exact-v1':
                raise ValueError('Unknown exact history format')
            values = record.get('hashes')
            if not isinstance(values, list) or len(values) > 500000:
                raise ValueError('Invalid exact history size')
            for value in values:
                self.positions(value)
            if values != sorted(set(values)):
                raise ValueError('Noncanonical exact history')
            self.exact = set(values)
            if record.get('legacy') is not None:
                if record['legacy'].get('schema_version') != 2:
                    raise ValueError('Invalid legacy history format')
                legacy = SourceHistory(record['legacy'])
                self.data[:] = legacy.data
                self.legacy = True
            return
        if record.get('schema_version') == 2:
            self.legacy = True
            if record.get('algorithm') != 'sha256-bloom-4194304-7':
                raise ValueError('Unknown source history format')
            compressed = base64.b64decode(record['bits'], validate=True)
            if len(compressed) > SIZE + 1024:
                raise ValueError('Oversized source history')
            decoder = zlib.decompressobj()
            raw = decoder.decompress(compressed, SIZE + 1)
            if len(raw) != SIZE or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
                raise ValueError('Invalid source history payload')
            if hashlib.sha256(raw).hexdigest() != record.get('sha256'):
                raise ValueError('Source history checksum mismatch')
            self.data[:] = raw
        elif set(record) == {'teknoloji', 'oyun'}:
            self.legacy = True
            for hashes in record.values():
                if not isinstance(hashes, list):
                    raise ValueError('Invalid legacy history')
                for value in hashes:
                    self.positions(value)
                    self.exact.add(value)
        else:
            raise ValueError('Invalid source history')

    def positions(self, value):
        if not isinstance(value, str) or not re.fullmatch('[a-f0-9]{64}', value):
            raise ValueError('Invalid source fingerprint')
        raw = bytes.fromhex(value)
        first, step = int.from_bytes(raw[:8], 'big'), int.from_bytes(raw[8:16], 'big') | 1
        return [(first + i * step) % BITS for i in range(HASHES)]

    def add_hash(self, value):
        for bit in self.positions(value):
            self.data[bit // 8] |= 1 << (bit % 8)

    def add(self, url):
        self.exact.add(fingerprint(url))
        # The legacy probabilistic filter is frozen, not extended.

    def contains(self, url):
        # A probabilistic legacy hit is evidence for review, never a veto.
        return any(value in self.exact for value in
                   (fingerprint(url), hashlib.sha256(url.encode()).hexdigest()))

    def uncertain(self, url):
        return self.legacy and not self.contains(url) and any(
            all(self.data[p // 8] & (1 << (p % 8)) for p in self.positions(value))
            for value in (fingerprint(url), hashlib.sha256(url.encode()).hexdigest()))

    def bloom_record(self):
        if sum(byte.bit_count() for byte in self.data) > BITS * 0.30:
            raise ValueError('Source history capacity reached; preserve it and migrate before publishing')
        raw = bytes(self.data)
        return {'schema_version': 2, 'algorithm': 'sha256-bloom-4194304-7',
                'sha256': hashlib.sha256(raw).hexdigest(),
                'bits': base64.b64encode(zlib.compress(raw, 9)).decode('ascii')}

    def record(self):
        # 500k SHA-256 values fit ~500k new articles: decades at today's cadence.
        # Stop explicitly at capacity, never forget old exact identities.
        if len(self.exact) > 500000:
            raise ValueError('Exact source history capacity reached; migrate before publishing')
        result = {'schema_version': 3, 'algorithm': 'sha256-exact-v1',
                  'hashes': sorted(self.exact)}
        # Validate occupancy even on fresh histories for corruption detection.
        legacy = self.bloom_record()
        if self.legacy:
            result['legacy'] = legacy
        return result
