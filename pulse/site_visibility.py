"""Reversible display-only cover; original static pages remain recoverable."""
import re
from pathlib import Path

START = '<!-- PULSE_SITE_VISIBILITY_START -->'
END = '<!-- PULSE_SITE_VISIBILITY_END -->'
COVER = START + '''<style>
body[data-pulse-paused="true"]{min-height:100dvh;display:grid;place-items:center;padding:0}
body[data-pulse-paused="true"]>:not(#pulse-owner-visibility){display:none!important}
</style><main id="pulse-owner-visibility" class="owner-pause-card"><div class="brand">PULSE<span class="brand-dot">.</span></div><h1>Yayınlara kısa bir ara verdik.</h1><p>Yeniden buluşmak üzere.</p></main>''' + END


def visible_page(content):
    content = re.sub(re.escape(START) + r'.*?' + re.escape(END), '', content, flags=re.S)
    return re.sub(r'(<body\b[^>]*?)\sdata-pulse-paused="true"', r'\1', content, count=1, flags=re.I)


def display_page(content, enabled):
    content = visible_page(content)
    if enabled:
        return content
    return re.sub(r'(<body\b[^>]*)(>)', lambda m: m[1] + ' data-pulse-paused="true">' + COVER,
                  content, count=1, flags=re.I)


def apply_visibility(root, enabled):
    root = Path(root)
    changed = False
    for page in root.rglob('*.html'):
        if '.git' in page.relative_to(root).parts:
            continue
        if page.is_symlink() or not page.resolve().is_relative_to(root.resolve()):
            raise ValueError('Unsafe visibility page')
        original = page.read_text()
        updated = display_page(original, enabled)
        if updated != original:
            page.write_text(updated)
            changed = True
    return changed
