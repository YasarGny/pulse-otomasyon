"""Lossless source packaging: no fuzzy matching, extraction or text truncation."""
import copy
import json
from collections import Counter

FIELDS={'excerpt','evidence','source_full_text','verified_summary'}


def encode(value):
    original=json.dumps(value,ensure_ascii=False,separators=(',',':'))
    texts=[]
    def visit(node):
        if isinstance(node,dict):
            for key,item in node.items():
                if key in FIELDS and isinstance(item,str) and len(item)>=160: texts.append(item)
                else: visit(item)
        elif isinstance(node,list):
            for item in node: visit(item)
    visit(value)
    repeats={text for text,n in Counter(texts).items() if n>1}
    if not repeats: return original
    shared={}; refs={}
    def pack(node):
        if isinstance(node,dict):
            result={}
            for key,item in node.items():
                if key in FIELDS and isinstance(item,str) and item in repeats:
                    if item not in refs:
                        name='source-text-'+str(len(refs)+1);refs[item]=name;shared[name]=item
                    result[key]={'shared_text_ref':refs[item]}
                else: result[key]=pack(item)
            return result
        if isinstance(node,list): return [pack(item) for item in node]
        return node
    packed=pack(value)
    candidate=json.dumps({'records':packed,'shared_text':shared},ensure_ascii=False,separators=(',',':'))
    candidate='shared_text_ref değerleri shared_text içindeki AYNI tam metne başvurur; kaynak rolleri records alanında korunur.\n'+candidate
    return candidate if len(candidate)<len(original) else original


def podcast_sources(source,evidence):
    # Stable source IDs replace only an unambiguously identical repeated heading.
    titles=Counter(row['headline'] for row in source)
    ids={row['headline']:row['id'] for row in source if titles[row['headline']]==1}
    records=copy.deepcopy(evidence or [])
    for row in records:
        if (isinstance(row,dict) and row.get('headline') in ids
                and ('story_id' not in row or row['story_id']==ids[row['headline']])):
            row['story_id']=ids[row.pop('headline')]
    return encode({'stories':source,'evidence':records})
