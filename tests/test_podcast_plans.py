"""Accountable selection and real discussion review without paid generation."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pulse_podcast_writer as writer
from pulse.podcast_plan import catalogue, validate, verify_audit, digest
from pulse.profile import DAILY_PROFILE, planned_podcast
from pulse.publication import read_json

STORIES=[('Önemli stüdyo gelişmesi','Kaynakta açıklanan stüdyo kararı.'),
         ('Kararın ilgili oyuna etkisi','Aynı duyuruda açıklanan oyun değişikliği.'),
         ('Küçük güncelleme','Kaynakta doğrulanmış küçük bir güncelleme.')]
META=[{'id':key,'title':title,'event_key':'studio-change' if i<2 else 'minor-update',
       'category':'OYUN','editorial_priority':{'impact':4-i,'development':2,'timeliness':3,'evidence':3,
          'reason':'Kaynak somut yeni bir gelişmeyi açıkça duyuruyor.'}}
      for i,(key,(title,_)) in enumerate(zip(('a','b','c'),STORIES))]
PLAN={'schema_version':1,'topics':[{'story_ids':['a','b'],'title':'Stüdyo kararı ve ilgili oyun',
      'reason':'Aynı açıklamanın doğrudan ilgili iki gelişmesi.',
      'questions':['Açıklanan karar oyuncuların tercihini nasıl etkileyebilir?']}],
      'omitted':[{'story_id':'c','reason':'Açıklama sınırlı; yeni bir değerlendirme alanı sunmuyor.'}]}
TURNS=[{'speaker':'Yaşar','text':'Kaynakta açıklanan bu karar oyuncu açısından nasıl değerlendirilebilir?'},
       {'speaker':'Necdet','text':'Bence tercih yaparken duyurulan kapsamı dikkate almak gerekir.'},
       {'speaker':'Yaşar','text':'Beklemeyi tercih eden biri açısından belirsiz kalan ne var?'},
       {'speaker':'Necdet','text':'Kaynakta açıklanmayan ayrıntı için kesin bir sonuç söyleyemeyiz.'}]
RESULT={'plan':PLAN,'turns':TURNS}
APPROVED={'approved':True,'unsupported_claims':[],'misleading_opinions':[],'concerns':[],
          'plan_review':{'selection_justified':True,'dialogue_follows_plan':True,'discussion_substantive':True}}


def generate(**kwargs):
    kwargs.setdefault('date', '23.10.2026')
    return writer.generate(STORIES,section='oyun',publication_profile=DAILY_PROFILE,
                           require_plan=True,story_catalogue=kwargs.pop('story_catalogue',META),**kwargs)


class PodcastPlanTests(unittest.TestCase):
    def test_broad_policy_starts_tomorrow_with_both_date_formats(self):
        from pulse.podcast_plan import broad_conversation
        for date, expected in [('23.10.2026',False),('2026-10-23',False),
                               ('24.10.2026',True),('2026-10-24',True),('01.11.2026',True)]:
            self.assertEqual(broad_conversation(date),expected)
        with self.assertRaises(ValueError):
            broad_conversation('24.99.2026')

    def test_broad_depth_and_budget_use_three_existing_calls_for_both_programs(self):
        for section in ('oyun','teknoloji'):
            with self.subTest(section=section),patch.object(writer,'_request',side_effect=copy.deepcopy([RESULT,RESULT,APPROVED])) as request:
                writer.generate(STORIES, section=section, date='24.10.2026', long_form=True,
                    publication_profile=DAILY_PROFILE, require_plan=True, story_catalogue=META)
            self.assertEqual(request.call_count,3)
            for call in request.call_args_list:
                prompt=call.args[0]['system_instruction']['parts'][0]['text']
                self.assertIn('20 dakikalık',prompt)
                self.assertIn('ÇOĞUNU',prompt)
                self.assertNotIn('15–25 dakika',prompt)
                self.assertNotIn('Bir konuyu konuşmak yeterliyse',prompt)
            review=request.call_args_list[-1].args[0]
            self.assertIn('toplam 3 haber; planda seçilen 2',review['contents'][0]['parts'][0]['text'])
            self.assertIn('önceki cevaba gerçek karşılık',review['system_instruction']['parts'][0]['text'])

    def test_minority_cannot_bypass_coverage_even_with_model_approval(self):
        minority=copy.deepcopy(RESULT)
        minority['plan']['topics'][0]['story_ids']=['a']
        minority['plan']['omitted'].append({'story_id':'b','reason':'Kaynağın açıkladığı ayrıntı sınırlı.'})
        with patch.object(writer,'_request',side_effect=copy.deepcopy([minority,minority,APPROVED,minority,APPROVED])) as request:
            with self.assertRaisesRegex(RuntimeError,'meaningfully cover most'):
                generate(date='24.10.2026',long_form=True)
        self.assertEqual(request.call_count,5)

    def test_new_policy_reuses_approval_but_changed_policy_cannot_reuse_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            audit=Path(tmp)/'review.json'
            for date in ('23.10.2026','24.10.2026'):
                with patch.object(writer,'_request',side_effect=copy.deepcopy([RESULT,RESULT,APPROVED])) as request:
                    generate(date=date,audit_path=audit,long_form=True)
                self.assertEqual(request.call_count,3)
            with patch.object(writer,'_request') as request:
                generate(date='24.10.2026',audit_path=audit,long_form=True)
            request.assert_not_called()

    def test_group_related_news_and_explain_omission_without_duration_or_topic_quota(self):
        self.assertEqual(validate(PLAN,['a','b','c']),PLAN)
        for field in ('impact','development','timeliness','evidence'):
            self.assertIn(field,catalogue(STORIES,META)[0]['editorial_priority'])

    def test_missing_unknown_duplicate_and_unexplained_decisions_are_rejected(self):
        cases=[]
        p=copy.deepcopy(PLAN);p['omitted']=[];cases.append(p)
        p=copy.deepcopy(PLAN);p['omitted'][0]['story_id']='unknown';cases.append(p)
        p=copy.deepcopy(PLAN);p['omitted'][0]['story_id']='a';cases.append(p)
        p=copy.deepcopy(PLAN);p['omitted'][0]['reason']=' ';cases.append(p)
        p=copy.deepcopy(PLAN);p['topics'][0]['questions']=[];cases.append(p)
        p=copy.deepcopy(PLAN);p['topics']=[];cases.append(p)
        for plan in cases:
            with self.subTest(plan=plan),self.assertRaises(RuntimeError):
                validate(plan,['a','b','c'])

    def test_plan_and_independent_review_use_the_existing_three_calls(self):
        with tempfile.TemporaryDirectory() as tmp:
            audit=Path(tmp)/'podcast-review.json'
            with patch.object(writer,'_request',side_effect=copy.deepcopy([RESULT,RESULT,APPROVED])) as request:
                generate(audit_path=audit)
            self.assertEqual(request.call_count,3)
            record=read_json(audit)
            verify_audit(record,catalogue(STORIES,META))
            self.assertEqual(record['plan'],PLAN)
            self.assertEqual(record['turns_sha256'],writer.dialogue_digest(TURNS))
            for call in request.call_args_list:
                self.assertIn('editorial_priority',call.args[0]['contents'][0]['parts'][0]['text'])
            review=request.call_args_list[-1].args[0]
            self.assertIn('Plan diyaloğun yerine geçmez',review['system_instruction']['parts'][0]['text'])
            self.assertIn('discussion_substantive',review['system_instruction']['parts'][0]['text'])

    def test_invalid_plan_is_repaired_once_before_editor_and_independent_review(self):
        bad=copy.deepcopy(RESULT);bad['plan']['omitted']=[]
        with patch.object(writer,'_request',side_effect=copy.deepcopy([bad,RESULT,RESULT,APPROVED])) as request:
            generate()
        self.assertEqual(request.call_count,4)
        self.assertIn('every available story',request.call_args_list[1].args[0]['contents'][0]['parts'][0]['text'])

    def test_even_general_approval_cannot_bypass_missing_or_failed_depth_review(self):
        for flag in (None,False,'true'):
            review=copy.deepcopy(APPROVED)
            if flag is None: review.pop('plan_review')
            else: review['plan_review']['discussion_substantive']=flag
            with self.subTest(flag=flag),patch.object(writer,'_request',side_effect=copy.deepcopy([RESULT,RESULT,review,RESULT,review])) as request:
                with self.assertRaisesRegex(RuntimeError,'complete independent approval'):
                    generate()
                self.assertEqual(request.call_count,5)

    def test_reviewer_can_require_a_different_selection_without_extra_planning_stage(self):
        rejected=copy.deepcopy(APPROVED)
        rejected.update(approved=False,concerns=['Önemli c haberi gerekçesiz atlanmış.'])
        rejected['plan_review']['selection_justified']=False
        fixed=copy.deepcopy(RESULT)
        fixed['plan']['topics'].append({'story_ids':['c'],'title':'Güncellemenin etkisi',
           'reason':'Kaynağın açıkladığı ayrıntı değerlendirme gerektiriyor.', 'questions':['Değişiklik tercihi etkiler mi?']})
        fixed['plan']['omitted']=[]
        with tempfile.TemporaryDirectory() as tmp:
            audit=Path(tmp)/'review.json'
            with patch.object(writer,'_request',side_effect=copy.deepcopy([RESULT,RESULT,rejected,fixed,APPROVED])):
                generate(audit_path=audit)
            self.assertEqual(read_json(audit)['plan'],fixed['plan'])
            verify_audit(read_json(audit),catalogue(STORIES,META))

    def test_checkpoint_reuses_approved_plan_only_for_exact_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            audit=Path(tmp)/'review.json'
            with patch.object(writer,'_request',side_effect=copy.deepcopy([RESULT,RESULT,APPROVED])):
                generate(audit_path=audit)
            with patch.object(writer,'_request',return_value=copy.deepcopy(APPROVED)) as request:
                generate(audit_path=audit)
            self.assertEqual(request.call_count,0)
            changed=copy.deepcopy(META);changed[0]['editorial_priority']['reason']='Kaynakta yeni ve daha geniş etki açıkça belirtiliyor.'
            with patch.object(writer,'_request',side_effect=copy.deepcopy([RESULT,RESULT,APPROVED])) as request:
                generate(audit_path=audit,story_catalogue=changed)
            self.assertEqual(request.call_count,3)

    def test_audit_detects_plan_and_catalogue_changes(self):
        source=catalogue(STORIES,META)
        audit={'plan':copy.deepcopy(PLAN),'plan_sha256':digest(PLAN),'catalogue_sha256':digest(source),'review':APPROVED}
        verify_audit(audit,source)
        audit['plan']['topics'][0]['reason']='Değiştirilmiş gerekçe.'
        with self.assertRaisesRegex(RuntimeError,'differs'):
            verify_audit(audit,source)
        audit['plan']=PLAN
        altered=copy.deepcopy(source);altered[0]['verified_summary']='Farklı kanıt.'
        with self.assertRaisesRegex(RuntimeError,'differs'):
            verify_audit(audit,altered)

    def test_catalogue_order_and_missing_priority_cannot_be_silently_accepted(self):
        for metadata in (META[:2],list(reversed(META)),[{k:v for k,v in row.items() if k!='editorial_priority'} for row in META]):
            with self.subTest(metadata=metadata),self.assertRaises((RuntimeError,ValueError)):
                catalogue(STORIES,metadata)

    def test_new_requirement_preserves_today_and_legacy_profiles(self):
        for profile,date,expected in [(DAILY_PROFILE,'2026-10-22',False),(DAILY_PROFILE,'2026-10-23',True),('expanded-v1','2026-10-23',False)]:
            self.assertEqual(planned_podcast({'publication_profile':profile,'publish_date':date}),expected)

    def test_audio_pipeline_blocks_a_cached_general_approval_without_plan_before_paid_voice(self):
        from pulse.pipeline import generate_audio
        from pulse.publication import write_json
        data={'section':'oyun','publication_profile':DAILY_PROFILE,'publish_date':'2026-10-23',
              'issue':8,'date':'23.10.2026','stories':[
                  {**row,'summary':summary,'brief':'Kaynağın açıkladığı bu somut gelişme bugün doğrulandı.'}
                  for row,(_,summary) in zip(META,STORIES)]}
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);folder=root/'oyun';folder.mkdir()
            write_json(folder/'turns.json',{'turns':TURNS})
            write_json(folder/'podcast-review.json',{'review':APPROVED,'turns_sha256':writer.dialogue_digest(TURNS)})
            with patch('pulse.pipeline.valid_audio',return_value=True), \
                 patch('pulse.pipeline.audio_info',return_value={'duration':60,'bytes':40000,'sha256':'f'*64}), \
                 patch('edge_tts.Communicate') as summary, \
                 patch('pulse_podcast_audio.render') as voice, \
                 patch.object(writer,'generate') as rewrite:
                with self.assertRaisesRegex(RuntimeError,'selection plan'):
                    generate_audio(root,data)
                voice.assert_not_called();summary.assert_not_called();rewrite.assert_not_called()
