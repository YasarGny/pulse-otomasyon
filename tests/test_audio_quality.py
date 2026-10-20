import copy
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from pulse.audio_quality import assert_no_long_silence, silence_gaps
from pulse.audio_repair import remap


class AudioQualityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.root=Path(cls.tmp.name)
        cls.tone=cls.root/'tone.wav';cls.silent=cls.root/'silence.wav'
        for path,source in [(cls.tone,'sine=frequency=440:sample_rate=44100'),(cls.silent,'anullsrc=r=44100:cl=mono')]:
            subprocess.run(['ffmpeg','-nostdin','-v','error','-y','-f','lavfi','-i',source,'-t','7',str(path)],check=True)

    @classmethod
    def tearDownClass(cls): cls.tmp.cleanup()

    def test_long_silence_is_rejected_but_real_signal_passes(self):
        assert_no_long_silence(self.tone)
        self.assertGreater(silence_gaps(self.silent)[0][1],6)
        with self.assertRaisesRegex(ValueError,'silence at'):
            assert_no_long_silence(self.silent)

    def test_bad_tts_part_is_retried_once_and_only_good_part_is_cached(self):
        import pulse_podcast_audio as audio
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);sources=iter([self.silent,self.tone])
            def synth(turns,path,*args,**kwargs): shutil.copyfile(next(sources),path)
            turns=[{'speaker':'Yaşar','text':'Sentetik kontrol.'}]
            with patch.object(audio,'synthesize',side_effect=synth) as provider:
                audio.render(turns,root/'first.mp3',checkpoint_dir=root/'cache')
                audio.render(turns,root/'second.mp3',checkpoint_dir=root/'cache')
                self.assertEqual(provider.call_count,2)
            assert_no_long_silence(root/'first.mp3')

    def test_repeated_bad_tts_does_not_publish_or_cache_the_part(self):
        import pulse_podcast_audio as audio
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            with patch.object(audio,'synthesize',side_effect=lambda turns,path,*a,**k:shutil.copyfile(self.silent,path)) as provider:
                with self.assertRaisesRegex(ValueError,'silence'):
                    audio.render([{'speaker':'Yaşar','text':'Kontrol.'}],root/'bad.mp3',checkpoint_dir=root/'cache')
                self.assertEqual(provider.call_count,2)
            self.assertFalse((root/'bad.mp3').exists())
            self.assertFalse(list((root/'cache').rglob('part_000.wav')))

    def test_chapter_and_story_times_follow_silence_edit(self):
        from pulse.clips import story_fingerprint
        stories=[{'id':'story','title':'Story','summary':'Evidence'}]
        old={'schema_version':1,'reviewed':True,'audio_sha256':'a'*64,
             'chapters':[{'start':0,'title':'Opening'},{'start':30,'title':'Story'}],
             'clips_reviewed':True,'stories_sha256':story_fingerprint(stories),
             'story_ranges':[{'story_id':'story','start':5,'end':40}]}
        result=remap(old,{'sha256':'b'*64,'duration':45},stories,10,15)
        self.assertEqual(result['chapters'][1]['start'],15)
        self.assertEqual(result['story_ranges'][0],{'story_id':'story','start':5,'end':25})
        self.assertEqual(old['audio_sha256'],'a'*64)

    def test_production_gate_requires_both_reviewed_chapter_sets(self):
        from fixtures import ready_release,tone
        from pulse.publication import read_json,write_json
        from pulse.clips import story_fingerprint
        from pulse.release_checks import check
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);release=root/'release'
            ready_release(release,tone(root/'tone.mp3'))
            with self.assertRaisesRegex(ValueError,'chapters are required'):check(release)
            for section in ('teknoloji','oyun'):
                edition=read_json(release/(section+'.json'));asset=edition['podcast']
                write_json(release/'chapters'/(asset['sha256']+'.json'),{'schema_version':1,
                    'reviewed':True,'audio_sha256':asset['sha256'],
                    'chapters':[{'start':0,'title':'Opening'},{'start':12,'title':'News'}],
                    'clips_reviewed':True,'stories_sha256':story_fingerprint(edition['stories']),
                    'story_ranges':[]})
                # Synthetic editions share the tone hash; use distinct hashes by
                # validating each section against its own metadata in the gate.
            # A shared hash with different catalogues must fail instead of
            # borrowing another show's chapter/range attestation.
            with self.assertRaisesRegex(ValueError,'catalogue identity'):check(release)
