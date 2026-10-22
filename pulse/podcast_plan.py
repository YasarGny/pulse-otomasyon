"""Private, source-bound podcast selection decisions; never a duration quota."""
import hashlib
import json


CONTRACT = '''
Önce podcast yayın planını, sonra bu plana dayanan diyaloğu yaz. Çıktı sözleşmesi:
{"plan":{"schema_version":1,"topics":[{"story_ids":["gerçek haber id"],
"title":"Sohbet konusu","reason":"Bu gelişmeler neden seçildi/birleştirildi?",
"questions":["Kaynaklardan çıkan gerçek bir değerlendirme sorusu"]}],
"omitted":[{"story_id":"gerçek haber id","reason":"Bu haber neden ana sohbet konusu seçilmedi?"}]},
"turns":[{"speaker":"Yaşar","text":"..."},{"speaker":"Necdet","text":"..."}]}.
Her haber kimliği planın topics veya omitted alanında tam bir kez bulunmalı.
Başlık numarası uydurma; verilen id değerlerini aynen kullan. Konu sayısı kotası yok.
Seçimde editorial_priority, kullanıcı/oyuncuya etkisi, kaynak derinliği ve gerçek
bir değerlendirme sorusu sunması birlikte önemli. Puanlar olgu değil editoryal
değerlendirmedir. En önemli haberleri atlamak somut, habere özgü gerekçe gerektirir;
"süre yok" veya "diğerlerini seçtik" tek başına gerekçe değildir.
Aynı olayın ilişkili gelişmelerini bir sohbet kümesinde ele al; salt aynı şirket
veya oyun adını taşımak bağlantı değildir. Yapay ilişki kurma. Bir kümede ilgili
ayrıntıları tekrar tekrar baştan anlatma; konu çeşitliliğini gerekçesiz daraltma.
Günün Özeti bütün gündemi özetler. Podcast bu işlevi tekrarlamaz: kısa olgusal
bağlamın ardından soruya cevap, önceki fikre yanıt ve gerekçeli farklı bakış açıları
gelişsin. Sunucu değişimi veya "bence" eklemek tek başına derinlik değildir.
Sorular uydurma olgu, şirket niyeti, sahte deneyim veya yapay karşıtlık içermesin.
Her haberi konuşmak veya süre/kelime/konu sayısı doldurmak zorunda değilsin.
Düzenleme ve düzeltmelerde plan ile diyalog birlikte tutarlı kalmalı; planı da döndür.
'''

REVIEW = '''
Yayın planını da bağımsız denetle. Seçilen ve dışarıda bırakılan haberlerin
gerekçelerini bütün kaynak notları ve önem değerlendirmeleriyle karşılaştır.
Önemli gelişme gerekçesiz atlanmışsa, ilişkisiz haberler zorla birleştirilmişse,
seçim gerekçesine kaynaksız olgu eklenmişse veya kapsam tek olay etrafında
gereksiz daraltılmışsa onaylama. Diyalogdaki gerçek sohbeti planın sorularıyla
karşılaştır: plan güzel yazılmış olsa bile konuşma sadece haber aktarıyorsa,
sorular yanıtsız kalıyorsa, yorumlar genel/geçiştirilmişse veya sunucular aynı
bilgiyi sırayla tamamlıyorsa concerns ile reddet. Plan diyaloğun yerine geçmez.
Kısa süre, her haberin konuşulmaması veya doğrudan konu değişimi tek başına kusur
değildir. Derinliği kaynakların sunduğu gerçek tartışma alanına göre değerlendir.
Mevcut JSON denetimine plan_review alanını da ekle:
{"selection_justified":true,"dialogue_follows_plan":true,"discussion_substantive":true}.
Bu üç alanda yalnız gerçek boolean kullan; bir sorun varsa ilgili alan false,
approved false ve concerns içinde somut düzeltme bulgusu olmalı.
'''


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def catalogue(stories, metadata):
    from pulse.news_priority import validate_priority
    if not isinstance(metadata, list) or len(metadata) != len(stories) or not stories:
        raise RuntimeError('Podcast planning requires the complete matching story catalogue')
    result, seen = [], set()
    for (title, summary), story in zip(stories, metadata):
        if not isinstance(story, dict):
            raise RuntimeError('Invalid podcast story catalogue row')
        identity = story.get('id')
        if not isinstance(identity, str) or not identity or identity in seen or story.get('title') != title:
            raise RuntimeError('Podcast planning catalogue identity/order mismatch')
        validate_priority(story)
        seen.add(identity)
        result.append({'id': identity, 'headline': title, 'verified_summary': summary,
                       'editorial_priority': story['editorial_priority'],
                       'event_key': story.get('event_key'), 'category': story.get('category')})
    return result


def validate(plan, identities):
    if not isinstance(plan, dict) or type(plan.get('schema_version')) is not int or plan['schema_version'] != 1:
        raise RuntimeError('Missing/invalid podcast selection plan')
    topics, omitted = plan.get('topics'), plan.get('omitted')
    if not isinstance(topics, list) or not topics or not isinstance(omitted, list):
        raise RuntimeError('Podcast plan requires selected topics and explicit omissions')
    known, seen = set(identities), set()
    def text(value):
        return isinstance(value, str) and bool(value.strip()) and len(value) <= 2000
    def account(identity):
        if not isinstance(identity, str) or identity not in known or identity in seen:
            raise RuntimeError('Podcast plan contains an unknown or duplicate story identity')
        seen.add(identity)
    for topic in topics:
        if (not isinstance(topic, dict) or not text(topic.get('title')) or not text(topic.get('reason'))
                or not isinstance(topic.get('story_ids'), list) or not topic['story_ids']
                or not isinstance(topic.get('questions'), list) or not topic['questions']
                or any(not text(question) for question in topic['questions'])):
            raise RuntimeError('Podcast topic requires a grounded reason and discussion questions')
        for identity in topic['story_ids']:
            account(identity)
    for row in omitted:
        if not isinstance(row, dict) or not text(row.get('reason')):
            raise RuntimeError('Podcast omission requires a specific reason')
        account(row.get('story_id'))
    if seen != known:
        raise RuntimeError('Podcast plan does not account for every available story')
    return plan


def approved(review):
    result = review.get('plan_review') if isinstance(review, dict) else None
    return isinstance(result, dict) and all(result.get(key) is True for key in (
        'selection_justified', 'dialogue_follows_plan', 'discussion_substantive'))


def verify_audit(audit, source):
    validate(audit.get('plan'), [row['id'] for row in source])
    if (audit.get('plan_sha256') != digest(audit['plan'])
            or audit.get('catalogue_sha256') != digest(source) or not approved(audit.get('review'))):
        raise RuntimeError('Podcast plan differs from its approved source/coverage review')
