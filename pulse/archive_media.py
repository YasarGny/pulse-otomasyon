"""Decode publisher bitmaps and retain only self-contained, passive SVGs."""
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path


def portable_image(body, kind):
    if not kind.lower().startswith('image/') and kind.lower().split(';')[0].strip() not in {'application/octet-stream','binary/octet-stream'}:
        raise ValueError('Archive media response is not an image')
    if body.startswith(b'\xff\xd8\xff'):
        suffix = '.jpg'
    elif body.startswith(b'\x89PNG'):
        suffix = '.png'
    elif body.startswith(b'RIFF') and body[8:12] == b'WEBP':
        suffix = '.webp'
    elif body.startswith(b'GIF8'):
        suffix = '.gif'
    elif body[4:8] == b'ftyp' and any(brand in body[8:40] for brand in (b'avif', b'avis')):
        suffix = '.avif'
    elif 'svg' in kind.lower() or body.lstrip().startswith((b'<svg', b'<?xml')):
        upper = body.upper()
        if b'<!DOCTYPE' in upper or b'<!ENTITY' in upper:
            raise ValueError('Archive SVG must not declare entities')
        try:
            svg = ET.fromstring(body)
        except ET.ParseError:
            raise ValueError('Invalid publisher SVG') from None
        if svg.tag.rsplit('}',1)[-1] != 'svg':
            raise ValueError('Archive image is not an SVG document')
        for index, element in enumerate(svg.iter()):
            tag = element.tag.rsplit('}',1)[-1]
            if index > 10000 or tag in {'script','foreignObject','animate','animateMotion','animateTransform','set'}:
                raise ValueError('Archive SVG contains active or excessive content')
            for name, value in element.attrib.items():
                name = name.rsplit('}',1)[-1].lower()
                if name.startswith('on') or name in {'href','src'} and not value.startswith('#'):
                    raise ValueError('Archive SVG contains external or active references')
                if 'javascript:' in value.lower():
                    raise ValueError('Archive SVG contains active references')
            styles = [value for name,value in element.attrib.items() if name == 'style']
            if tag == 'style':
                styles.append(element.text or '')
            # SVG paints may reference internal gradients, never network/filesystem URLs.
            styles.extend(element.attrib.values())
            for style in styles:
                if '\\' in style or '@import' in style.lower() or any(not target.strip(" \t\r\n\"'").startswith('#') for target in re.findall(r'url\s*\(([^)]*)\)',style,re.I)):
                    raise ValueError('Archive SVG has nonlocal styling references')
        return body, '.svg'
    else:
        safe_kind = re.sub(r'[^a-zA-Z0-9/+.-]','',kind)[:60]
        raise ValueError(f'Archive image format unsupported: {safe_kind}; signature {body[:12].hex()}')
    with tempfile.TemporaryDirectory() as tmp:
        source = Path(tmp) / ('source' + suffix)
        source.write_bytes(body)
        # Full decoding of the displayed frame catches corrupt files beyond magic bytes.
        command = ['ffmpeg','-v','error','-nostdin','-y','-protocol_whitelist','file,pipe','-max_pixels','40000000','-i',str(source),'-frames:v','1']
        if suffix == '.avif':
            target = Path(tmp) / 'image.webp'
            subprocess.run(command + ['-c:v','libwebp','-quality','95',str(target)],check=True,capture_output=True,timeout=30)
            return target.read_bytes(), '.webp'
        subprocess.run(command + ['-f','null','-'],check=True,capture_output=True,timeout=30)
    return body, suffix
