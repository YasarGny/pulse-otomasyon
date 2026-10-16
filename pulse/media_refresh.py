"""Fill missing publisher images without regenerating news, issues or approved audio."""
import argparse
import shutil
import requests
from pathlib import Path

from pulse.publication import SECTIONS, expected_date, now, read_json, seal_release, verify_manifest, write_json
from pulse.source_media import article_image


def refresh(published, output, *, lookup=article_image, release=None, prefer_original=False):
    published, output = Path(published), Path(output)
    manifest = read_json(Path(release) / 'release.json' if release else published / 'data/publication.json')
    if manifest.get('status') != 'ready' or manifest.get('publish_date') != expected_date(now()):
        raise ValueError('Only the current completed publication can be refreshed')
    source = Path(release) if release else published / 'releases' / manifest['release_id']
    verify_manifest(source, manifest)
    if output.exists():
        raise ValueError('Media refresh output exists; preserve it and choose a new directory')
    if output.resolve().is_relative_to(source.resolve()) or source.resolve().is_relative_to(output.resolve()):
        raise ValueError('Media output overlaps the published release')
    shutil.copytree(source, output)
    changed = False
    for section in SECTIONS:
        data = read_json(output / f'{section}.json')
        for story in data['stories']:
            if prefer_original or not story.get('image_url'):
                try:
                    original = lookup(story['source_url'])
                    if original and original != story.get('image_url'):
                        story['image_url'] = original
                        changed = True
                except (requests.RequestException, ValueError, OSError):
                    pass  # A blocked publisher cannot invalidate the approved audio/news.
        write_json(output / f'{section}.json', data)
    return seal_release(output, manifest['publish_date'], manifest['game_start']) if changed else manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--published', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--checkpoint')
    parser.add_argument('--release', help='Verified complete local release to revise instead of the live legacy issue')
    parser.add_argument('--prefer-original', action='store_true', help='Prefer publisher Open Graph originals over RSS thumbnails')
    args = parser.parse_args()
    result = refresh(args.published, args.output, release=args.release, prefer_original=args.prefer_original)
    destinations = {Path(path).resolve() for path in (args.checkpoint, args.release) if path}
    for checkpoint in destinations:
        for relative in ['release.json', 'teknoloji.json', 'oyun.json', 'teknoloji/summary.mp3', 'teknoloji/podcast.mp3', 'oyun/summary.mp3', 'oyun/podcast.mp3']:
            target = checkpoint / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(Path(args.output) / relative, target)
    print('Image metadata revised; audio unchanged:', result['release_id'])
