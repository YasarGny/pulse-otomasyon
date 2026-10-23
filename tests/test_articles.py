import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from pulse.articles import full_articles
from pulse.source_media import ArticleText
from pulse.details import article_body

APPROVED={'approved':True,'unsupported_claims':[],'concerns':[]}
REJECTED={'approved':False,'unsupported_claims':['Desteksiz özellik'],'concerns':[]}
ARTICLE={'id':'source1','title':'Doğrulanan yeni sürüm açıklandı','summary':'Yeni sürüm hakkında kaynağa dayanan bir özet.','brief':'Yeni sürümün duyurusu resmî kaynakta yayımlandı.','why':'Duyurulan değişiklikler kullanıcılar açısından değerlendirilebilir.','body':['Kaynağın açıkladığı değişiklikleri aktaran özgün Türkçe ilk paragraf.', 'Aynı kaynakta yer alan ayrıntıları açıklayan ayrı bir ikinci paragraf.']}

class FullArticlesTests(unittest.TestCase):
    def sources(self):
        return {'source1':{'original_title':'Official release','source_url':'https://www.nasa.gov/official','source_excerpt':'Kaynağın doğrulanmış açıklaması. '*60}}

    def test_unapproved_article_never_returns(self):
        call=Mock(side_effect=[{'articles':[ARTICLE]},REJECTED,{'articles':[ARTICLE]},REJECTED])
        with self.assertRaisesRegex(ValueError,'review rejected'):
            full_articles([{'id':'source1'}],self.sources(),call)

    def test_reviewed_complete_text_is_cached_and_does_not_repeat_model_calls(self):
        with tempfile.TemporaryDirectory() as tmp:
            call=Mock(side_effect=[{'articles':[ARTICLE]},APPROVED])
            stories=full_articles([{'id':'source1'}],self.sources(),call,cache_dir=tmp)
            self.assertEqual(stories[0]['body'],ARTICLE['body'])
            self.assertTrue(stories[0]['body_reviewed'])
            again=full_articles([{'id':'source1'}],self.sources(),call,cache_dir=tmp)
            self.assertEqual(call.call_count,2)
            self.assertEqual(again[0]['body_sha256'],stories[0]['body_sha256'])

    def test_detail_contains_both_full_paragraphs_escaped_and_source(self):
        story={**copy.deepcopy(ARTICLE),'source_name':'NASA','source_url':'https://www.nasa.gov/official','category':'UZAY','image_url':''}
        story['body'][0]+=' <script>unsafe()</script>'
        html=article_body({'publish_date':'2026-10-16','issue':1},story)
        self.assertIn('article-text',html)
        self.assertIn('&lt;script&gt;',html)
        self.assertNotIn('<script>unsafe()',html)
        self.assertIn('https://www.nasa.gov/official',html)
        self.assertEqual(html.count('class="source-link"'),1)
        self.assertNotIn('class="article-source"',html)
        self.assertIn('<time class="detail-meta" datetime="2026-10-16">16.10.2026</time>',html)

    def test_reader_ignores_script_and_navigation(self):
        parser=ArticleText();parser.feed('<nav><p>'+('Navigation '*20)+'</p></nav><article><p>'+('Actual article text '*10)+'</p><script>secret()</script></article>')
        text=' '.join(t for _,t in parser.paragraphs)
        self.assertIn('Actual article',text)
        self.assertNotIn('Navigation',text)
        self.assertNotIn('secret()',text)

    def test_priority_claim_can_be_repaired_and_reviewed_as_draft_not_evidence(self):
        priority={'impact':2,'development':2,'timeliness':2,'evidence':2,
                  'reason':'Kaynağın söylemediği bir milyon kullanıcı iddiası.'}
        fixed={**priority,'reason':'Kaynak yeni sürümün duyurulduğunu açıklıyor.'}
        bad={**copy.deepcopy(ARTICLE),'editorial_priority':priority}
        good={**copy.deepcopy(ARTICLE),'editorial_priority':fixed}
        call=Mock(side_effect=[{'articles':[bad]},REJECTED,{'articles':[good]},APPROVED])
        result=full_articles([{'id':'source1','editorial_priority':priority}],self.sources(),call)
        self.assertEqual(result[0]['editorial_priority'],fixed)
        review_prompt=call.call_args_list[1].args[0]
        source_part=review_prompt.split('Kaynaklar: ')[1].split('\nHaberler: ')[0]
        self.assertNotIn('editorial_priority',source_part)
        self.assertIn('editorial_priority',review_prompt.split('\nHaberler: ')[1])

    def test_failure_is_private_and_next_attempt_receives_previous_feedback(self):
        with tempfile.TemporaryDirectory() as tmp:
            rejected=Mock(side_effect=[{'articles':[ARTICLE]},REJECTED,{'articles':[ARTICLE]},REJECTED])
            with self.assertRaisesRegex(ValueError,'source IDs: source1') as error:
                full_articles([{'id':'source1'}],self.sources(),rejected,cache_dir=tmp)
            self.assertNotIn('Desteksiz özellik',str(error.exception))
            reports=list(Path(tmp).glob('*.review.json'))
            self.assertEqual(len(reports),1)
            import json
            report=json.loads(reports[0].read_text())
            self.assertEqual(report['review'],REJECTED)
            self.assertEqual(report['sources'][0]['id'],'source1')
            recovered=Mock(side_effect=[{'articles':[ARTICLE]},APPROVED])
            full_articles([{'id':'source1'}],self.sources(),recovered,cache_dir=tmp)
            self.assertIn('Desteksiz özellik',recovered.call_args_list[0].args[0])
            self.assertEqual(recovered.call_count,2)

    def test_invalid_priority_is_not_accepted_even_if_model_approves(self):
        priority={'impact':2,'development':2,'timeliness':2,'evidence':2,
                  'reason':'Kaynağa dayanan yeterince uzun önem açıklaması.'}
        call=Mock(return_value={'articles':[ARTICLE]})
        with self.assertRaisesRegex(ValueError,'priority'):
            full_articles([{'id':'source1','editorial_priority':priority}],self.sources(),call)
        self.assertEqual(call.call_count,2)
