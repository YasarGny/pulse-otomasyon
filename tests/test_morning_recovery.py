"""Real morning failures must repair boundedly without weakening publication gates."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from pulse.articles import full_articles
from pulse.editorial import checked_selection
import pulse_podcast_writer as writer

APPROVED={'approved':True,'unsupported_claims':[],'misleading_opinions':[],'concerns':[]}
REJECTED={**APPROVED,'approved':False,'unsupported_claims':['Unverified numerical claim']}


def turns(words):
    return [{'speaker':'Yaşar' if i%2==0 else 'Necdet',
             'text':' '.join(['olgu']*(words//40+(i<words%40)))} for i in range(40)]


class MorningRecoveryTests(unittest.TestCase):
    def test_missing_selection_fields_are_repairable_value_errors(self):
        source={'a':{'source_url':'https://example.com/a'}}
        valid={'id':'a','category':'BİLİM','event_key':'new-event','title':'Başlık','summary':'Kaynak özeti','why':'Önem açıklaması'}
        for field in ('id','title','summary','why'):
            bad=copy.deepcopy(valid);bad.pop(field)
            with self.subTest(field=field),self.assertRaises(ValueError):
                checked_selection({'stories':[bad]},source,'teknoloji')

    def test_short_script_is_length_repaired_before_independent_review(self):
        short,long=turns(2200),turns(2800)
        with patch.object(writer,'_request',side_effect=[{'turns':short},{'turns':short},{'turns':long},APPROVED]) as request:
            _,result=writer.generate([('Haber','Doğrulanmış not')],long_form=True)
        self.assertEqual(result,long);self.assertEqual(request.call_count,4)
        self.assertIn('2200',str(request.call_args_list[2]))
        self.assertIn('2800',str(request.call_args_list[2]))
        self.assertIn('titiz bir doğruluk',str(request.call_args_list[3]))

    def test_2446_word_script_does_not_need_filler_to_meet_an_arbitrary_boundary(self):
        with patch.object(writer,'_request',side_effect=[{'turns':turns(2446)},{'turns':turns(2446)},APPROVED]) as request:
            _,result=writer.generate([('Haber','Doğrulanmış not')],long_form=True)
        self.assertEqual(request.call_count,3);self.assertEqual(result,turns(2446))

    def test_small_word_deviation_does_not_bypass_evidence_review(self):
        with patch.object(writer,'_request',side_effect=[{'turns':turns(2446)},{'turns':turns(2446)},REJECTED,{'turns':turns(2446)},REJECTED]):
            with self.assertRaisesRegex(RuntimeError,'Unverified numerical claim'):
                writer.generate([('Haber','Doğrulanmış not')],long_form=True)

    def test_length_failure_is_bounded_and_draft_resumes_without_rewriting(self):
        with tempfile.TemporaryDirectory() as tmp:
            audit=Path(tmp)/'podcast-review.json'
            with patch.object(writer,'_request',return_value={'turns':turns(2200)}) as request:
                with self.assertRaisesRegex(RuntimeError,'bounded length repair'):
                    writer.generate([('Haber','Doğrulanmış not')],long_form=True,audit_path=audit)
            self.assertEqual(request.call_count,4)
            self.assertTrue((audit.parent/'podcast-draft.json').exists())
            self.assertFalse(audit.exists())
            with patch.object(writer,'_request',side_effect=[{'turns':turns(2800)},APPROVED]) as request:
                _,result=writer.generate([('Haber','Doğrulanmış not')],long_form=True,audit_path=audit)
            self.assertEqual(request.call_count,2);self.assertEqual(result,turns(2800))

    def test_changed_evidence_cannot_reuse_the_previous_draft(self):
        with tempfile.TemporaryDirectory() as tmp:
            audit=Path(tmp)/'podcast-review.json'
            with patch.object(writer,'_request',side_effect=[{'turns':turns(2800)},{'turns':turns(2800)},APPROVED]):
                writer.generate([('Haber','İlk kaynak notu')],long_form=True,audit_path=audit)
            with patch.object(writer,'_request',side_effect=[{'turns':turns(2700)},{'turns':turns(2700)},APPROVED]) as request:
                _,result=writer.generate([('Haber','Farklı kaynak notu')],long_form=True,audit_path=audit)
            self.assertEqual(request.call_count,3);self.assertEqual(result,turns(2700))

    def test_correct_length_never_overrides_an_evidence_rejection(self):
        with patch.object(writer,'_request',side_effect=[{'turns':turns(2200)},{'turns':turns(2200)},{'turns':turns(2800)},REJECTED,{'turns':turns(2800)},REJECTED]):
            with self.assertRaisesRegex(RuntimeError,'Unverified numerical claim'):
                writer.generate([('Haber','Doğrulanmış not')],long_form=True)

    def test_malformed_independent_review_is_not_approval(self):
        with patch.object(writer,'_request',side_effect=[{'turns':turns(2800)},{'turns':turns(2800)},[],{'turns':turns(2800)},APPROVED]) as request:
            writer.generate([('Haber','Doğrulanmış not')],long_form=True)
        self.assertEqual(request.call_count,5);self.assertFalse(writer._approved([]))

    def test_missing_article_field_is_repaired_then_independently_reviewed(self):
        article={'id':'a','title':'Doğrulanmış başlık','summary':'Kaynak özeti',
                 'brief':'Kaynak olgularına dayanan yorumsuz kısa haber özeti.', 'why':'Önem açıklaması',
                 'body':['Kaynağa dayanan ilk paragraf yalnız doğrulanmış olguları içerir.',
                         'İkinci paragraf yeni olgu eklemeden doğrulanmış ayrıntıyı açıklar.']}
        bad=copy.deepcopy(article);bad.pop('why')
        stories=[{'id':'a'}];sources={'a':{'original_title':'Source headline','source_url':'https://example.com/a','source_excerpt':'Evidence. '*160}}
        with patch('pulse.source_media.article_text',return_value=''),patch('pulse.articles.article_text',return_value=''),patch('pulse.editorial.gemini') as unused:
            from unittest.mock import Mock
            generate=Mock(side_effect=[{'articles':[bad]},{'articles':[article]},{'approved':True,'unsupported_claims':[],'concerns':[]}])
            result=full_articles(stories,sources,generate)
        self.assertEqual(generate.call_count,3);self.assertTrue(result[0]['body_reviewed']);unused.assert_not_called()

    def test_repeated_malformed_article_does_not_reach_paid_review(self):
        from unittest.mock import Mock
        generate=Mock(return_value={'articles':[{'id':'a'}]})
        sources={'a':{'original_title':'Source','source_url':'https://example.com/a','source_excerpt':'Evidence. '*160}}
        with self.assertRaisesRegex(ValueError,'Missing complete'):
            full_articles([{'id':'a'}],sources,generate)
        self.assertEqual(generate.call_count,2)
