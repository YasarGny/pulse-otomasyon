import copy
import tempfile
import unittest
from pathlib import Path
from pulse.clips import build_clips, story_fingerprint, validate_ranges
from pulse.publication import digest, read_json, write_json
from fixtures import ready_release, tone
from pulse.build import build
from pulse.publication import not_before
from fixtures import DATE


class ClipTests(unittest.TestCase):
    def setUp(self):
        self.stories = [{'id': 'story0', 'title': 'Title', 'summary': 'Summary'}]
        self.asset = {'duration': 42, 'sha256': 'a' * 64}
        self.data = {'reviewed': True, 'audio_sha256': 'a' * 64, 'clips_reviewed': True, 'stories_sha256': story_fingerprint(self.stories),
                     'story_ranges': [{'story_id': 'story0', 'start': 3, 'end': 8}]}

    def test_exact_catalogue_and_finite_disjoint_boundaries_required(self):
        self.assertEqual(len(validate_ranges(self.data, self.asset, self.stories)), 1)
        invalid = [None, True, -1, float('nan'), float('inf'), 45, 8]
        for value in invalid:
            data = copy.deepcopy(self.data); data['story_ranges'][0]['start'] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_ranges(data, self.asset, self.stories)
        for change in ({'clips_reviewed': False}, {'stories_sha256': 'wrong'}, {'story_ranges': [None]},
                       {'story_ranges': [{'story_id': 'unknown', 'start': 1, 'end': 5}]},
                       {'story_ranges': [{'story_id':'story0','start':1,'end':6}, {'story_id':'story0','start':5,'end':8}]}):
            with self.assertRaises(ValueError):
                validate_ranges({**self.data, **change}, self.asset, self.stories)
        with self.assertRaises(ValueError):
            validate_ranges(self.data, self.asset, [dict(self.stories[0], title='Changed')])

    def test_real_files_stop_at_native_eof_and_rebuild_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); release = root / 'release'
            manifest = ready_release(release, tone(root / 'tone.mp3'))
            edition = read_json(release / 'teknoloji.json'); asset = edition['podcast']
            sidecar = {'schema_version': 1, 'reviewed': True, 'audio_sha256': asset['sha256'],
                       'chapters': [{'start':0,'title':'Opening'}, {'start':12,'title':'Topic'}],
                       'section':'teknoloji', 'clips_reviewed':True, 'stories_sha256':story_fingerprint(edition['stories']),
                       'story_ranges':[{'story_id':edition['stories'][0]['id'],'start':12,'end':14}]}
            write_json(release / 'chapters' / (asset['sha256'] + '.json'), sidecar)
            output = root / 'dist'; build('site', output, release=release, at=not_before(DATE))
            index = read_json(output / 'assets/clips/index.json')
            entry = index['stories']['teknoloji:teknoloji0'][0]
            self.assertLess(abs(entry['duration'] - 2), .2)
            self.assertEqual(digest(output / entry['file']), entry['sha256'])
            self.assertEqual(digest(release / asset['file']), asset['sha256'])
            self.assertTrue((output / 'akis/index.html').is_file())
            content = (output / 'akis/index.html').read_text()
            self.assertEqual(content.count('class="flow-story"'), 6)
            rebuilt = root / 'again'; build('site', rebuilt, release=release, previous=output, at=not_before(DATE))
            self.assertEqual(read_json(rebuilt / 'assets/clips/index.json'), index)
            # Absent mappings remove old clips instead of leaking yesterday's content.
            (release / 'chapters' / (asset['sha256'] + '.json')).unlink()
            build('site', root / 'empty', release=release, at=not_before(DATE))
            self.assertEqual(read_json(root / 'empty/assets/clips/index.json')['stories'], {})

    def test_range_proposal_requires_an_independent_review_and_real_transcript_boundaries(self):
        from scripts.prepare_chapters import propose
        from unittest.mock import Mock
        transcript = {'audio_sha256':'a'*64, 'section':'teknoloji',
                      'canonical_stories':self.stories,
                      'segments':[{'start':0,'end':2,'text':'Açılış'},
                                  {'start':5,'end':9,'text':'Title hakkında açıklama'},
                                  {'start':10,'end':13,'text':'Konuşmanın son cümlesi'}]}
        proposal = {'chapters':[{'segment_id':0,'title':'Açılış'},{'segment_id':1,'title':'Title'}],
                    'story_ranges':[{'story_id':'story0','start_segment_id':1,'end_segment_id':2}]}
        generate = Mock(side_effect=[proposal, {'approved':True}])
        result = propose(transcript, self.asset, generate)
        self.assertEqual(result['story_ranges'], [{'story_id':'story0','start':5,'end':13}])
        self.assertEqual(generate.call_count, 2)
        generate = Mock(side_effect=[proposal, {'approved':False,'reason':'Wrong event'}])
        with self.assertRaises(ValueError):
            propose(transcript,self.asset,generate,retry=False)
        self.assertEqual(generate.call_count, 2)
