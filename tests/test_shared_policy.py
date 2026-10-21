"""Tomorrow's policy, legacy contracts and category-neutral headlines; no API calls."""
import copy
import hashlib
import json
import unittest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch

from fixtures import edition
from pulse.editorial import checked_selection
from pulse.news_priority import rank_key, validate_priority
from pulse.pages import selection, listing
from pulse.profile import (DAILY_PROFILE, DAILY_TARGET, POLICY_START, profile_for,
                           podcast_minimum, podcast_maximum, summary_minimum)
from pulse.publication import validate_content
import pulse_podcast_writer as writer


def priority(score):
    return dict(impact=score, development=score, timeliness=score, evidence=score,
                reason='Verilen kaynakta somut yeni gelişme ve etkisi açıklanıyor.')


def daily(section='teknoloji', count=3):
    data=edition(section, date=POLICY_START)
    data['publication_profile']=DAILY_PROFILE
    data['stories']=data['stories'][:count]
    for i,story in enumerate(data['stories']):
        story['editorial_priority']=priority(4-i)
        story['event_key']='different-event-'+str(i)
        story['body']=['Verilen kaynaktan alınan doğrulanmış ayrıntılar burada özgün biçimde açıklanır.',
                       'İkinci paragraf yalnız aynı kaynakta yer alan gelişmenin ayrıntılarını aktarır.']
        story['body_reviewed']=True
        story['body_sha256']=hashlib.sha256(json.dumps(story['body'],ensure_ascii=False).encode()).hexdigest()
    return data


class SharedPolicyTests(unittest.TestCase):
    def test_activation_keeps_today_on_legacy_contract(self):
        self.assertEqual(profile_for('2026-10-21'),'expanded-v1')
        self.assertEqual(profile_for(POLICY_START),DAILY_PROFILE)
        bad=daily();bad['publish_date']='2026-10-21'
        # Explicit profile cannot be used to retroactively relax today's checks.
        from pulse.publication import issue_number,turkish_date
        bad['issue']=issue_number(bad['publish_date'],'teknoloji','2026-10-16')
        bad['date']=turkish_date(bad['publish_date'])
        with self.assertRaisesRegex(ValueError,'not active'):
            validate_content(bad,'teknoloji',bad['publish_date'],'2026-10-16')

    def test_both_categories_accept_a_small_valid_edition_but_never_an_empty_one(self):
        for section in ('teknoloji','oyun'):
            data=daily(section,1)
            validate_content(data,section,POLICY_START,'2026-10-16')
            data['stories']=[]
            with self.assertRaises(ValueError):validate_content(data,section,POLICY_START,'2026-10-16')

    def test_rank_and_source_checks_are_still_required(self):
        data=daily();data['stories'].reverse()
        with self.assertRaisesRegex(ValueError,'editorial priority'):
            validate_content(data,'teknoloji',POLICY_START,'2026-10-16')
        data=daily();data['stories'][0]['source_url']='javascript:bad'
        with self.assertRaisesRegex(ValueError,'HTTPS'):
            validate_content(data,'teknoloji',POLICY_START,'2026-10-16')

    def test_invalid_scores_are_not_silently_replaced(self):
        for value in (True,4.5,5,-1):
            story={'editorial_priority':priority(2)};story['editorial_priority']['impact']=value
            with self.assertRaises(ValueError):validate_priority(story)
        for key in ('evidence','development'):
            story={'editorial_priority':priority(2)};story['editorial_priority'][key]=0
            with self.assertRaisesRegex(ValueError,'concrete new development'):
                validate_priority(story)

    def test_selection_uses_new_policy_without_lowering_old_floor(self):
        story=daily(count=1)['stories'][0];source={story['id']:story}
        self.assertEqual(len(checked_selection({'stories':[story]},source,'teknoloji',profile=DAILY_PROFILE)),1)
        with self.assertRaises(ValueError):checked_selection({'stories':[story]},source,'teknoloji')
        story.pop('editorial_priority')
        with self.assertRaisesRegex(ValueError,'editorial priority'):
            checked_selection({'stories':[story]},source,'teknoloji',profile=DAILY_PROFILE)

    def test_games_can_lead_and_both_categories_are_represented(self):
        editions={s:daily(s) for s in ('teknoloji','oyun')}
        for story in editions['teknoloji']['stories']:story['editorial_priority']=priority(1)
        lead=selection(editions)
        self.assertEqual(lead[0][0],'oyun')
        self.assertEqual({s for s,_ in lead},{'teknoloji','oyun'})
        self.assertEqual(lead,sorted(lead,key=lambda item:rank_key(item[1])))
        html=listing(editions,'./')
        self.assertLess(html.index(editions['oyun']['stories'][0]['title']),html.index(editions['teknoloji']['stories'][0]['title']))

    def test_tiny_day_has_no_duplicate_or_missing_headline(self):
        editions={s:daily(s,1) for s in ('teknoloji','oyun')}
        self.assertEqual(len(selection(editions)),2)

    def test_future_edition_keeps_rank_metadata_through_article_review(self):
        from pulse.editorial import create_edition
        story=daily(count=1)['stories'][0]
        source={**story,'original_title':'Source title','source_excerpt':'Verified source evidence. '*100}
        article={k:story[k] for k in ('id','title','summary','why','body')}
        article['brief']='Yalnız kaynakta bulunan doğrulanmış olguların yorumsuz kısa özeti.'
        approved={'approved':True,'unsupported_claims':[],'concerns':[]}
        with patch('pulse.editorial.enrich_selection_sources'),patch('pulse.source_media.trusted_hosts',return_value={'example.com'}),patch('pulse.source_media.verified_article_image',return_value=None),patch('pulse.editorial.gemini',side_effect=[{'stories':[story]},{'articles':[article]},approved]) as generate:
            data=create_edition({'publish_date':POLICY_START,'sections':{'teknoloji':[source]}},'teknoloji',POLICY_START,7,'2026-10-16')
        self.assertEqual(data['publication_profile'],DAILY_PROFILE)
        self.assertEqual(data['stories'][0]['editorial_priority'],story['editorial_priority'])
        self.assertEqual(generate.call_count,3)
        self.assertIn('15–20',generate.call_args_list[0].args[0])
        self.assertIn('editorial_priority.reason',generate.call_args_list[-1].args[0])

    def test_two_story_future_site_builds_with_the_new_browser_contract(self):
        from fixtures import tone
        from pulse.publication import audio_info,write_json,seal_release,not_before
        from pulse.build import build
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'release';root.mkdir();audio=tone(Path(tmp)/'tone.mp3')
            for section in ('teknoloji','oyun'):
                data=daily(section,1)
                for kind in ('summary','podcast'):
                    target=root/section/(kind+'.mp3');target.parent.mkdir(exist_ok=True)
                    if kind=='summary':
                        import subprocess
                        subprocess.run(['ffmpeg','-v','error','-y','-i',str(audio),'-t','15','-c:a','copy',str(target)],check=True,capture_output=True)
                        with self.assertRaisesRegex(ValueError,'short MP3'):
                            audio_info(target,20)
                    else:
                        shutil.copyfile(audio,target)
                    data[kind]={'file':section+'/'+kind+'.mp3', 'episode':data['issue'],
                                'title':('Yeni Sekme' if section=='teknoloji' else 'Moradon FM') if kind=='podcast' else 'Günün Özeti',
                                **({'hosts':['Yaşar','Necdet']} if kind=='podcast' else {}),
                                **audio_info(target,5 if kind=='summary' else 40)}
                data['ready']=True
                write_json(root/(section+'.json'),data)
            seal_release(root,POLICY_START,'2026-10-16')
            output=Path(tmp)/'site'
            build('site',output,release=root,at=not_before(POLICY_START))
            home=(output/'index.html').read_text()
            self.assertEqual(home.count('class="story lead-story"'),2)
            self.assertIn('publication.js?v=5',home)

    def test_old_homepage_selection_is_preserved(self):
        editions={s:edition(s) for s in ('teknoloji','oyun')}
        self.assertEqual([s for s,_ in selection(editions)],['teknoloji','oyun','teknoloji'])

    def test_duration_targets_do_not_rewrite_legacy_audio_contract(self):
        self.assertEqual(DAILY_TARGET,(15,20))
        for section in ('teknoloji','oyun'):
            self.assertEqual(podcast_minimum(daily(section)),40)
            self.assertIsNone(podcast_maximum(daily(section)))
        self.assertEqual(podcast_minimum({'section':'teknoloji','publication_profile':'expanded-v1'}),900)
        self.assertEqual(podcast_minimum({'section':'oyun','publication_profile':'expanded-v1'}),720)

    def test_summary_guard_scales_with_the_actual_script_without_weakening_old_issues(self):
        short=daily(count=1)
        short['stories'][0]['brief']=' '.join(['Doğrulanmış']*35)
        self.assertGreaterEqual(summary_minimum(short),5)
        self.assertLess(summary_minimum(short),15)
        long=daily()
        for story in long['stories']:story['brief']=' '.join(['Doğrulanmış']*40)
        self.assertEqual(summary_minimum(long),20)
        self.assertEqual(summary_minimum({'publication_profile':'expanded-v1'}),20)
        from pulse.publication import audio_info
        # The decoder still rejects a fragment shorter than the minimum text bound.
        from fixtures import tone
        import subprocess
        with tempfile.TemporaryDirectory() as tmp:
            original=tone(Path(tmp)/'tone.mp3');fragment=Path(tmp)/'fragment.mp3'
            subprocess.run(['ffmpeg','-v','error','-y','-i',str(original),'-t','5','-c:a','copy',str(fragment)],check=True,capture_output=True)
            with self.assertRaisesRegex(ValueError,'short MP3'):
                audio_info(fragment,summary_minimum(short))

    def test_natural_transition_and_flexible_length_still_require_review(self):
        turns=[{'speaker':'Yaşar' if i%2==0 else 'Necdet','text':'Kaynağa dayanan bir düşünceyi karşılıklı değerlendiriyoruz.'} for i in range(12)]
        approved={'approved':True,'unsupported_claims':[],'misleading_opinions':[],'concerns':[]}
        for section in ('teknoloji','oyun'):
            with patch.object(writer,'_request',side_effect=[{'turns':turns},{'turns':turns},approved]) as request:
                writer.generate([('Haber','Doğrulanmış not')],section=section,long_form=True,publication_profile=DAILY_PROFILE)
            self.assertEqual(request.call_count,3)
            prompts=[call.args[0]['system_instruction']['parts'][0]['text'] for call in request.call_args_list]
            self.assertIn('2500–3100',prompts[0]);self.assertIn('15–25',prompts[0])
            self.assertNotIn('konuşmaya değer konuşmaya değer',prompts[0])
            self.assertIn('kota değildir',prompts[0]);self.assertIn('doğrudan konu değişimini',prompts[1])
            self.assertIn('uydurulmuş ilişki',prompts[2])
        rejected={**approved,'approved':False,'unsupported_claims':['Kaynakta bulunmayan iddia']}
        with patch.object(writer,'_request',side_effect=[{'turns':turns},{'turns':turns},rejected,{'turns':turns},rejected]):
            with self.assertRaisesRegex(RuntimeError,'Kaynakta bulunmayan'):
                writer.generate([('Haber','Doğrulanmış not')],long_form=True,publication_profile=DAILY_PROFILE)
