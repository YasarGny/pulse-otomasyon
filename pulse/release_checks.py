"""Production completeness gate: existing verified audio, silence and chapters."""
import argparse
from pathlib import Path
from pulse.audio_quality import assert_no_long_silence
from pulse.chapters import load_chapters
from pulse.clips import validate_ranges
from pulse.publication import read_json, verify_manifest, write_json


def check(root, previous=None):
    root=Path(root)
    manifest=read_json(root/'release.json')
    verify_manifest(root,manifest)
    for section in ('teknoloji','oyun'):
        edition=read_json(root/(section+'.json'))
        for kind in ('summary','podcast'):
            assert_no_long_silence(root/edition[kind]['file'])
        asset=edition['podcast']
        data=load_chapters(root/'chapters',asset)
        if not data and previous:
            data=load_chapters(Path(previous)/'assets/chapters',asset)
        if not data or len(data['chapters'])<2:
            raise ValueError(section+': reviewed final-audio chapters are required')
        validate_ranges(data,asset,edition['stories'])
        print(section+': full audio, silence and reviewed chapter checks passed',flush=True)
    return manifest


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--release',required=True);p.add_argument('--previous')
    a=p.parse_args();check(a.release,a.previous)
