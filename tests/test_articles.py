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

    def test_reader_ignores_script_and_navigation(self):
        parser=ArticleText();parser.feed('<nav><p>'+('Navigation '*20)+'</p></nav><article><p>'+('Actual article text '*10)+'</p><script>secret()</script></article>')
        text=' '.join(t for _,t in parser.paragraphs)
        self.assertIn('Actual article',text)
        self.assertNotIn('Navigation',text)
        self.assertNotIn('secret()',text)
