"""Private, source-bound podcast selection decisions; never a duration quota."""
import hashlib
import json
from datetime import datetime


CONVERSATION_START = '2026-10-24'


def broad_conversation(date):
    """Date-version writing policy, leaving already sealed editions intact."""
    if not isinstance(date, str):
        raise ValueError('Podcast policy requires a valid publication date')
    for pattern in ('%d.%m.%Y', '%Y-%m-%d'):
        try:
            return datetime.strptime(date, pattern).date().isoformat() >= CONVERSATION_START
        except ValueError:
            continue
    # Compatibility for callers holding the validated Turkish display date.
    from pulse.publication import MONTHS
    parts = date.split()
    if len(parts) == 3 and parts[1] in MONTHS:
        try:
            parsed = datetime(int(parts[2]), MONTHS.index(parts[1]) + 1, int(parts[0]))
            return parsed.date().isoformat() >= CONVERSATION_START
        except ValueError:
            pass
    raise ValueError('Podcast policy requires a valid publication date')


BROAD_CONVERSATION = '''
Bu yayın için kapsamlı sohbet politikası önceki dar konu seçimi önerilerinin yerini alır.
Zaten editoryal olarak seçilmiş haberlerin ÇOĞUNU konuş: seçilen benzersiz haber
kimliği sayısı toplamın yarısından fazla olmalı. Bu asgari oran hedef değildir;
kaynak ve süre elverdiğince gündemin daha geniş kısmını kapsa. Her habere eşit süre
verme, 4–6 konu gibi sabit bir kota koyma. Ana konuları önem, dinleyiciye etki ve
kaynakların sunduğu gerçek değerlendirme alanına göre derinleştir; diğer haberleri
kısa olgusal bağlam ve anlamlı değerlendirmeyle işle. Sadece adını geçirmek kapsam
sayılmaz. İlişkili gelişmeleri birleştir; aynı şirket adı tek başına ilişki değildir.
Önemli konularda Yaşar'ın somut sorusu, Necdet'in gerekçeli karşılığı ve bu karşılığa
gerçek takip gelişsin. Her konuya aynı soru-cevap şablonunu dayatma; genel onay,
başlığı farklı kelimelerle tekrar etmek ve sırayla bilgi tamamlamak yorum değildir.
Yorumlar kaynaklarla desteklenen sonuçlar veya açıkça koşullu değerlendirmeler
olsun; sahte deneyim, yeni olgu, şirket niyeti veya yapay karşıtlık ekleme.
Yayın için 20 dakikalık üst süre bütçesi kullan; yazımı yaklaşık 17–19 dakikaya,
doğal konuşma hızında yaklaşık 2200–2500 kelimeye göre planla. Bu kelime aralığı
bir kota veya kesin süre ölçümü değildir. Anlamlı gündem daha kısaysa uzatma.
Bütçe aşılır görünüyorsa önce tekrarları, uzun giriş/kapanışı ve gereksiz
geçişleri azalt; sonra düşük öncelikli ayrıntıları kısalt. Önemli yorumları
silerek bir dakikaya çok konu sıkıştırma. Her haberi almak için 20 dakikayı aşma.
Dışarıda kalan her habere kaynak derinliği, öncelik ve kalan kapsamla ilişkili
somut gerekçe ver; sırf kısa podcast yapmak veya yorum alanı yok demek yeterli
değil. Plan ve gerekçeler konuşmada okunmaz.
'''

BROAD_REVIEW = '''
Kapsamlı sohbet denetimi: haberlerin ÇOĞUNU (yarıdan fazlasını) gerçekten konuşmuş
olmalı; bu asgari oran hedef değil, kaynaklar elverdiğince geniş kapsam beklenir.
Seçilenler gerçekten konuşulmuş mu, yoksa planda
seçilip diyalogda yalnız başlık mı okunmuş? Yüksek öncelikli konularda gerekçeli
yorum ve önceki cevaba gerçek karşılık var mı? Kısa haberler bütün ana konuların
yerini almışsa veya yalnız genel tepkiler varsa discussion_substantive false olsun.
Kapsam sayısı tek başına kalite kanıtı değildir. Düşük öncelikli konular kısa
işlenebilir; her haber için zorunlu dönüş sayısı veya aynı şablonu arama.
20 dakikalık bütçeyi ve verilen yerel kelime sayımını birlikte değerlendir;
kelime sayısından kesin ses süresi çıkarma, alt kelime/süre sınırı yüzünden reddetme.
Gereksiz tekrarları ve kaynak dışı yorumları reddet. Var olan inceleme JSON'unu
kullan; ayrı bir araştırma, planlama veya denetim çağrısı isteme.
'''


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
Plan, haber kimlikleri ve seçme/eleme gerekçeleri sunucuların okuyacağı metin değildir;
konuşmaya üretim planı açıklaması ekleme.
Düzenleme ve düzeltmelerde plan ile diyalog birlikte tutarlı kalmalı; planı da döndür.
'''

REVIEW = '''
Yayın planını da bağımsız denetle. Seçilen ve dışarıda bırakılan haberlerin
gerekçelerini bütün kaynak notları ve önem değerlendirmeleriyle karşılaştır.
Önemli gelişme gerekçesiz atlanmışsa, ilişkisiz haberler zorla birleştirilmişse,
seçim gerekçesine kaynaksız olgu eklenmişse veya kapsam tek olay etrafında
gereksiz daraltılmışsa onaylama. Diyalogdaki gerçek sohbeti planın sorularıyla
karşılaştır: plan güzel yazılmış olsa bile konuşma sadece haber aktarıyorsa,
sorular kaynakların izin verdiği ölçüde ele alınmıyorsa, yorumlar genel veya
geçiştirilmişse ya da sunucular aynı
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
