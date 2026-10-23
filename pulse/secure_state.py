"""Authenticated encryption for temporary workflow checkpoints."""
import argparse
import base64
import io
import os
from pathlib import Path
import stat
import zipfile

MAGIC = b'PULSE-STATE-1\x00'
MAX_BYTES = 500_000_000


def require_key():
    try:
        key = base64.b64decode(os.environ.get('PULSE_STATE_KEY', ''), validate=True)
    except (ValueError, TypeError):
        raise ValueError('A valid checkpoint encryption key is required') from None
    if len(key) != 32:
        raise ValueError('A 32-byte checkpoint encryption key is required')
    return key


def encrypt(raw):
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    nonce = os.urandom(12)
    return MAGIC + nonce + AESGCM(require_key()).encrypt(nonce, raw, MAGIC)


def decrypt(raw):
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    if not raw.startswith(MAGIC) or len(raw) < len(MAGIC) + 28:
        raise ValueError('Invalid encrypted checkpoint')
    offset = len(MAGIC)
    try:
        return AESGCM(require_key()).decrypt(raw[offset:offset+12], raw[offset+12:], MAGIC)
    except ValueError:
        raise
    except Exception:
        raise ValueError('Checkpoint authentication failed') from None


def artifact_payload(raw):
    """The Actions download is a ZIP containing exactly one encrypted file."""
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        members = archive.infolist()
        if len(members) == 1 and members[0].filename == 'state.enc':
            if members[0].file_size > MAX_BYTES:
                raise ValueError('Oversized encrypted checkpoint')
            return decrypt(archive.read(members[0]))
    if os.environ.get('PULSE_REQUIRE_ENCRYPTED_STATE') == 'true':
        raise ValueError('Unencrypted workflow checkpoints are not accepted')
    return raw  # Legacy private checkpoints only; never enabled in the public workflow.


def pack(source, output):
    require_key()
    source, output = Path(source), Path(output)
    if not source.is_dir():
        return False
    files = sorted(source.rglob('*'))
    if any(p.is_symlink() for p in files):
        raise ValueError('Checkpoint symlinks are not accepted')
    files = [p for p in files if p.is_file()]
    if not files:
        return False
    if len(files) > 1000 or sum(p.stat().st_size for p in files) > MAX_BYTES:
        raise ValueError('Oversized checkpoint')
    raw = io.BytesIO()
    with zipfile.ZipFile(raw, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, path.relative_to(source).as_posix())
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(encrypt(raw.getvalue()))
    return True


def extract(source, target):
    """Safe extraction for the manual transcript review workflow."""
    target = Path(target).resolve()
    raw = decrypt(Path(source).read_bytes())
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        members = archive.infolist()
        if len(members) > 1000 or sum(m.file_size for m in members) > MAX_BYTES:
            raise ValueError('Oversized checkpoint')
        for member in members:
            path = Path(member.filename)
            if (path.is_absolute() or '..' in path.parts or '\\' in member.filename
                    or not path.parts or stat.S_ISLNK(member.external_attr >> 16)
                    or not (target / path).resolve().is_relative_to(target)):
                raise ValueError('Unsafe encrypted checkpoint path')
        archive.extractall(target)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('check', 'pack', 'extract'))
    parser.add_argument('--source')
    parser.add_argument('--output')
    args = parser.parse_args()
    if args.operation == 'check':
        require_key()
    elif args.operation == 'pack':
        if not args.source or not args.output:
            parser.error('pack requires source and output')
        pack(args.source, args.output)
    else:
        if not args.source or not args.output:
            parser.error('extract requires source and output')
        extract(args.source, args.output)


if __name__ == '__main__':
    main()
