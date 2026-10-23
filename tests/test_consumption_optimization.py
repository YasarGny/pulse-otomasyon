import copy
import json
import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import Mock,patch

from pulse.usage import record,reused,scope,summarize
from pulse.source_package import encode,podcast_sources
import pulse_podcast_writer as writer
from test_audio_editorial import TURNS,APPROVED
from test_articles import ARTICLE,APPROVED as ARTICLE_APPROVED
from pulse.articles import full_articles


class ConsumptionOptimizationTests(unittest.TestCase):
    def test_usage_reports_unknown_counters_and_does_not_double_count_aliases_or_restores(self):
        with tempfile.TemporaryDirectory() as tmp:
            log=Path(tmp)/'api-usage.jsonl'
            with patch.dict(os.environ,{'PULSE_USAGE_LOG':str(log)}),scope('podcast.review','oyun'):
                record('podcast-script','fixture',{'usageMetadata':{'promptTokenCount':100,'candidatesTokenCount':20,'totalTokenCount':125,'thoughtsTokenCount':5},'usage':{'total_input_tokens':100,'total_output_tokens':20,'total_tokens':125}},1000)
                record('podcast-script','fixture',{},100)
                reused()
            copied=Path(tmp)/'copy.jsonl';copied.write_bytes(log.read_bytes())
            result=summarize([log,copied]);paid=next(g for g in result['groups'] if g['model']=='fixture')
            self.assertEqual(paid['calls'],2)
            self.assertEqual(paid['tokens']['total'],125)
            self.assertEqual(paid['tokens']['input'],100)
            self.assertEqual(paid['missing']['total'],1)
            self.assertEqual(sum(g['reuses'] for g in result['groups']),1)
            self.assertNotIn('prompt',result['groups'][0])

    def test_thread_labels_are_isolated_and_rows_are_complete(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'PULSE_USAGE_LOG':str(Path(tmp)/'api-usage.jsonl')}):
            def worker(i):
                with scope('article.review',str(i)):
                    record('editorial','fixture',{'usageMetadata':{'totalTokenCount':i}},10)
            with ThreadPoolExecutor(max_workers=4) as pool: list(pool.map(worker,range(20)))
            groups=summarize([Path(tmp)/'api-usage.jsonl'])['groups']
            self.assertEqual(len(groups),20)
            self.assertEqual(sum(g['tokens']['total'] for g in groups),sum(range(20)))

    def test_source_references_restore_every_character_and_keep_distinct_claims(self):
        text='Açıklamanın tamamı; sayı 1.25 ve tarih 23.10.2026.\n'*150
        data=[{'id':'a','url':'https://a.test','evidence':text},{'id':'b','url':'https://b.test','evidence':text},
              {'id':'c','evidence':text+'Farklı olgu.'}]
        original=copy.deepcopy(data);packed=encode(data)
        self.assertLess(len(packed),len(json.dumps(data,ensure_ascii=False)))
        payload=json.loads(packed.split('\n',1)[1])
        restored=copy.deepcopy(payload['records'])
        for row in restored:
            if isinstance(row['evidence'],dict): row['evidence']=payload['shared_text'][row['evidence']['shared_text_ref']]
        self.assertEqual(restored,original);self.assertEqual(data,original)
        self.assertEqual(encode([{'evidence':'unique text'}]),'[{"evidence":"unique text"}]')

    def test_duplicate_headings_are_referenced_only_when_unambiguous(self):
        sources=[{'id':'a','headline':'A unique title','verified_summary':'Original summary'}]
        evidence=[{'headline':'A unique title','source_url':'https://a.test','excerpt':'Original evidence'}]
        payload=json.loads(podcast_sources(sources,evidence))
        self.assertEqual(payload['evidence'][0],{'story_id':'a','source_url':'https://a.test','excerpt':'Original evidence'})
        self.assertEqual(evidence[0]['headline'],'A unique title')
        duplicate=sources+[{'id':'b','headline':'A unique title'}]
        self.assertIn('headline',json.loads(podcast_sources(duplicate,evidence))['evidence'][0])

    def test_approved_review_reuse_requires_exact_model_evidence_policy_and_valid_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            audit=Path(tmp)/'review.json'
            def run(notes='Source facts'):
                return writer.generate([('Headline',notes)],audit_path=audit)
            def fresh():
                return copy.deepcopy([{'turns':TURNS},{'turns':TURNS},APPROVED])
            with patch.object(writer,'_request',side_effect=fresh()): run()
            with patch.object(writer,'_request',side_effect=AssertionError('No paid call')): run()
            with patch.object(writer,'REVIEWER',writer.REVIEWER+' New review policy.'),patch.object(writer,'_request',return_value=copy.deepcopy(APPROVED)) as call:
                run();self.assertEqual(call.call_count,1)
            with patch.object(writer,'MODEL','different-model'),patch.object(writer,'_request',side_effect=fresh()) as call:
                run();self.assertEqual(call.call_count,3)
            with patch.object(writer,'_request',side_effect=fresh()) as call:
                run('Different source facts');self.assertEqual(call.call_count,3)
            record_json=json.loads(audit.read_text());record_json['review']['extra']='Corrupted approval record'
            audit.write_text(json.dumps(record_json))
            with patch.object(writer,'_request',return_value=copy.deepcopy(APPROVED)) as call:
                run('Different source facts');self.assertEqual(call.call_count,1)

    def test_article_cache_does_not_reuse_an_old_models_approval(self):
        sources={'source1':{'original_title':'Source','source_url':'https://example.com','source_excerpt':'Verified source. '*100}}
        with tempfile.TemporaryDirectory() as tmp:
            generate=Mock(side_effect=copy.deepcopy([{'articles':[ARTICLE]},ARTICLE_APPROVED]))
            full_articles([{'id':'source1'}],sources,generate,cache_dir=tmp)
            no_calls=Mock(side_effect=AssertionError('Reused approved article'))
            full_articles([{'id':'source1'}],sources,no_calls,cache_dir=tmp)
            no_calls.assert_not_called()
            with patch('pulse.editorial.MODEL','new-model'):
                generate=Mock(side_effect=copy.deepcopy([{'articles':[ARTICLE]},ARTICLE_APPROVED]))
                full_articles([{'id':'source1'}],sources,generate,cache_dir=tmp)
                self.assertEqual(generate.call_count,2)
