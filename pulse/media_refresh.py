"""Fill missing publisher images without regenerating news, issues or approved audio."""
import argparse
import shutil
import requests
from pathlib import Path

from pulse.publication import SECTIONS, expected_date, now, read_json, seal_release, verify_manifest, write_json
from pulse.source_media import article_image


def refresh(published, output, *, lookup=article_image):
    published, output = Path(published), Path(output)
    manifest = read_json(published / 'data/publication.json')
    if manifest.get('status') != 'ready' or manifest.get('publish_date') != expected_date(now()):
        raise ValueError('Only the current completed publication can be refreshed')
    source = published / 'releases' / manifest['release_id']
    verify_manifest(source, manifest)
    if output.exists():
        raise ValueError('Media refresh output exists; preserve it and choose a new directory')
    if output.resolve().is_relative_to(source.resolve()) or source.resolve().is_relative_to(output.resolve()):
        raise ValueError('Media output overlaps the published release')
    shutil.copytree(source, output)
    for section in SECTIONS:
        data = read_json(output / f'{section}.json')
        for story in data['stories']:
            if not story.get('image_url'):
                try:
                    story['image_url'] = lookup(story['source_url'])
                except (requests.RequestException, ValueError, OSError):
                    pass  # A blocked publisher cannot invalidate the approved audio/news.
        write_json(output / f'{section}.json', data)
    return seal_release(output, manifest['publish_date'], manifest['game_start'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--published', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--checkpoint')
    args = parser.parse_args()
    result = refresh(args.published, args.output)
    if args.checkpoint:
        checkpoint = Path(args.checkpoint)
        for relative in ['release.json', 'teknoloji.json', 'oyun.json', 'teknoloji/summary.mp3', 'teknoloji/podcast.mp3', 'oyun/summary.mp3', 'oyun/podcast.mp3']:
            target = checkpoint / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(Path(args.output) / relative, target)
    print('Image metadata revised; audio unchanged:', result['release_id'])
