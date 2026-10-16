import copy
import datetime as dt
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from fixtures import DATE, edition
from pulse.daily_archive import canonical_name, protect_order, retire_older, select_daily
from pulse.publication import validate_content, write_json
import pulse_podcast_writer as writer


class DailyArchiveTests(unittest.TestCase):
    def manifest(self, id='new', stamp='2026-10-16T10:00:00+03:00'):
        return {'publish_date':DATE,'release_id':id,'validated_at':stamp}

    def test_simple_date_name(self):
        self.assertEqual(canonical_name(DATE), 'PULSE-16.10.2026.zip')

    def test_late_old_job_cannot_replace_newer_drive_backup(self):
        with self.assertRaises(ValueError):
            protect_order([{'appProperties':{'release_id':'new','release_order':'2026-10-16T12:00:00+03:00'}}], self.manifest('old'))

    def test_failed_verification_never_promotes_or_trashes(self):
        drive=Mock()
        with self.assertRaises(ValueError):
            retire_older(drive,'parent',self.manifest(), {'verified':False})
        drive.request.assert_not_called()

    def test_verified_promotion_precedes_retiring_old_versions(self):
        drive=Mock();drive.api='https://www.googleapis.com/drive/v3/files'
        drive.daily_files.return_value=[{'id':'keep','name':'pending.zip','appProperties':{'release_id':'new'}},{'id':'old','name':'legacy.zip','appProperties':{'release_id':'old'}}]
        retire_older(drive,'parent',self.manifest(),{'verified':True,'release_id':'new','file_id':'keep'})
        self.assertEqual(drive.request.call_args_list[0].kwargs['json']['name'],'PULSE-16.10.2026.zip')
        self.assertEqual(drive.request.call_args_list[1].kwargs['json'],{'trashed':True})

    def test_select_latest_by_order_not_hash_or_directory_sort(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for id, stamp in [('z-old','2026-10-16T07:00:00+03:00'),('a-new','2026-10-16T08:00:00+03:00')]:
                write_json(root/'releases'/id/'release.json',self.manifest(id,stamp))
            write_json(root/'data/publication.json',dict(self.manifest('a-new','2026-10-16T08:00:00+03:00'),status='ready'))
            with patch('pulse.daily_archive.verify_manifest'):
                chosen, all=select_daily(root,root)
            self.assertEqual(chosen[DATE][1]['release_id'],'a-new')
            self.assertEqual(len(all[DATE]),2)


class ExpandedEditorialTests(unittest.TestCase):
    def full(self):
        data=edition('teknoloji');data['publication_profile']='expanded-v1'
        data['stories']=[dict(copy.deepcopy(data['stories'][i%3]), id=f'id{i}', source_url=f'https://example.com/{i}', event_key=f'event-{i}') for i in range(15)]
        return data

    def test_expanded_allows_fifteen_distinct_stories(self):
        data=self.full();validate_content(data,'teknoloji',DATE,DATE)

    def test_three_story_short_issue_cannot_be_new_profile(self):
        data=self.full();data['stories']=data['stories'][:3]
        with self.assertRaises(ValueError):validate_content(data,'teknoloji',DATE,DATE)

    def test_same_event_twice_blocks_even_with_different_urls(self):
        data=self.full();data['stories'][1]['event_key']=data['stories'][0]['event_key']
        with self.assertRaisesRegex(ValueError,'event identity'):validate_content(data,'teknoloji',DATE,DATE)

    def test_approved_two_minute_script_still_fails_long_profile(self):
        turns=[{'speaker':'Yaşar' if i%2==0 else 'Necdet','text':'Kısa bir kaynak notu hakkında konuşuyoruz.'} for i in range(12)]
        approved={'approved':True,'unsupported_claims':[],'misleading_opinions':[],'concerns':[]}
        with patch.object(writer,'_request',side_effect=[{'turns':turns},{'turns':turns},approved,{'turns':turns},approved]):
            with self.assertRaisesRegex(RuntimeError,'independent evidence'):
                writer.generate([('Haber','Doğrulanmış kaynak')],long_form=True)


class TTSCheckpointTests(unittest.TestCase):
    def test_second_render_reuses_verified_parts_and_changed_dialogue_does_not(self):
        import subprocess
        import shutil
        import pulse_podcast_audio as audio
        from fixtures import tone
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            mp3=tone(root/'tone.mp3')
            wav=root/'tone.wav'
            subprocess.run(['ffmpeg','-v','error','-y','-i',str(mp3),str(wav)],check=True)
            turns=[{'speaker':'Yaşar','text':'Kaynağa göre açıklanan gelişmeyi birlikte konuşalım.'}, {'speaker':'Necdet','text':'Belirsiz kalan noktaları da ayrı değerlendirelim.'}]
            def synth(group,destination,number,**kwargs):shutil.copyfile(wav,destination)
            relative_cache=Path(__import__('os').path.relpath(root/'cache',Path.cwd()))
            with patch.object(audio,'synthesize',side_effect=synth) as call:
                audio.render(turns,root/'first.mp3',strict_audio=True,checkpoint_dir=relative_cache)
                audio.render(turns,root/'second.mp3',strict_audio=True,checkpoint_dir=relative_cache)
                self.assertEqual(call.call_count,1)
                changed=copy.deepcopy(turns);changed[1]['text']+=' Bir sorumuz daha var.'
                audio.render(changed,root/'third.mp3',strict_audio=True,checkpoint_dir=relative_cache)
                self.assertEqual(call.call_count,2)
            self.assertFalse(list((root/'cache').rglob('merged.wav')))
