"""Source/turn-bound discussion review inside the existing editorial call."""
from pulse.podcast_plan import publication_date

START = '2026-10-25'
TARGET_MINUTES = (15, 20)
# Conservative planning range, never a measured or mandatory audio duration.
WORDS_PER_MINUTE = (120, 160)


class ReviewFormatError(RuntimeError):
    """A malformed assessment is not proof that the dialogue needs rewriting."""


def enabled(date):
    return publication_date(date) >= START


WRITING = '''
Derin sohbet politikası: gündemin çoğunu kapsarken podcasti kısa haber özetine
dönüştürme. Hedef 15–20 dakikalık doyurucu sohbet; normal bir gündemde yaklaşık
2200–2500 konuşma kelimesi yazım rehberidir, doldurulacak kota değildir.
En önemli ve kaynakları tartışmaya elverişli konulara daha fazla alan ayır.
Önce kısa doğrulanmış bağlam; sonra Yaşar'ın somut merakı, Necdet'in gerekçeli
değerlendirmesi ve bu değerlendirmeyi ilerleten gerçek bir karşılık gelişsin.
Bir olgunun tekrarını, 'önemli bir gelişme', 'bekleyip göreceğiz', 'aynen' gibi
genel tepkileri yorum sayma. Yorum, kaynakta açıklanan ayrıntının dinleyiciye
etkisini, bir tercihin gerekçesini veya kesin bilmediğimiz sınırı açıklasın.
Koşullu çıkarımı açıkça koşullu söyle; dış bilgiyle olgu veya şirket niyeti ekleme.
Her haber aynı kalıba veya eşit süreye sokulmaz. İkincil gelişmeler kısa kalabilir;
ana konuların hepsini kısa geçerek gündem turu yapma. Sadece planda seçmek yetmez,
haber konuşmada da anlaşılır biçimde yer alsın. Kaynak elveriyorsa kapsamı ve
yorumları geliştir; her haberi almak için 20 dakikalık bütçeyi aşma.
Gerçek ilişkisi olmayan konular arasında Yaşar doğrudan geçebilir.
Editör doğru ve anlamlı değerlendirmeleri sırf daha kısa yazmak için özetlemesin.
Tekrar ve boş giriş/çıkışları çıkarsın; yorumun gerekçesini ve gerçek karşılığı
korusun. Taslak yetersizse önce önemli konuların kaynakta karşılığı olan sorularını
geliştirsin. Anlamlı gündem gerçekten kısa ise kaynaksız bilgi veya laf eklemesin.
Süre hedefi, üretim politikası, kelime sayısı ve denetim gerekçeleri seslendirilmez.
'''


REVIEW = '''
Somut sohbet denetimi: yalnız plan_review boolean onayları yeterli değildir.
Kaynakları, önem sırasını, plan sorularını ve GERÇEK replikleri birlikte incele.
Ana konularda görüşün gerekçesi ve önceki görüşü ilerleten karşılık bulunmalı.
İki kişinin sırayla olgu aktarması veya genel tepki vermesi derin sohbet değildir.
Önemli ve kaynakta tartışma alanı olan konular kısa geçilmişse onaylama; hangi
sorunun veya gerekçenin geliştirilmesi gerektiğini concerns içinde somutlaştır.
Haberlerin çoğu gerçekten konuşulmalı; yalnız seçili kimlik sayısını kabul etme.
Her plan konusu için asıl sohbetin geçtiği gerçek replikleri ve gerçekten konuşulan
haber kimliklerini göster. Sohbet eski konuya dönebilir; replikler kesintisiz bir
aralık olmak zorunda değildir. Aynı repliği bağımsız iki konuya kanıt gösterme;
gerçekten ilişkili haberler zaten tek plan konusu olarak birleştirilebilir.
Kısa bir geri gönderme yeni ana konu veya kapsam kanıtı sayılmaz.
Replik indeksleri turns dizisinde 0'dan
başlar; bu indeksler ses zamanı değildir ve kullanıcıya yayınlanmaz.
discussion türünde exchange üç farklı, artan replik indeksidir: gerekçeli
değerlendirme/soru, diğer sunucunun gerçek karşılığı, ilk sunucunun bu karşılığı
ilerletmesi. Bu üç referans bütün sohbeti sınırlamaz; arada başka replikler olabilir.
Bir haber başına sabit dönüş veya dakika arama. Diğer konular brief olabilir;
fakat bütün bölümün brief olması podcast işlevini karşılamaz.
15–20 dakika planlama hedefidir. Yerel kelime sayımı ve geniş hız tahmini yalnız
inceleme işaretidir, gerçek ses süresi değildir. Kısalık tek başına ret nedeni
olmaz. Buna rağmen kaynaklar daha kapsamlı anlamlı sohbet sunarken 'gündem kısa'
diyerek yüzeysel diyaloğu onaylama. Kısa bölüm için kaynakta hangi somut sınırların
bulunduğunu short_reason ve ilgili haber kimlikleriyle açıkla. Yalnız 'süre
doldurmamak' veya 'yeterli' demek gerekçe değildir. Kaynağın ayrıntılarını ve
önemli soruları ele almış kısa sohbet kabul edilebilir. Üst bütçede önce tekrarı
ve gereksiz ayrıntıyı azalt; ses hızlandırma veya sonradan kesme önerme.
Mevcut review JSON'una şu alanı ekle; ayrı bir çağrı isteme:
"discussion_review":{"schema_version":1,"topics":[{"topic_index":0,
"covered_story_ids":["gerçek id"],"turn_ids":[1,2,3,5,8],
"treatment":"discussion","exchange":[2,3,5],
"finding":"Bu repliklerin kaynağa dayanan hangi fikri nasıl geliştirdiği"}],
"budget":{"appropriate":true,"reason":"Kapsam ve derinliğin kaynaklara göre değerlendirmesi",
"short_reason":null,"limited_story_ids":[]}}.
Her plan konusu topics içinde tam bir kez bulunmalı. brief için exchange null.
finding konuya ve repliklere özgü olmalı; doğru konuşulmamış habere kimlik verme.
Yerel ölçüm short_review_required true ise short_reason somut kaynak gerekçesi,
limited_story_ids ilgili gerçek kimlikler olmalı. Diğer durumlarda null ve [] olur.
Kalite yetersizse appropriate false, approved false ve somut concerns döndür;
kanıt veya replik referansı uydurup onay verme.
'''


def metrics(turns):
    words = sum(len(turn['text'].split()) for turn in turns)
    return {'words': words, 'target_minutes': list(TARGET_MINUTES),
            'estimated_minutes': [round(words / WORDS_PER_MINUTE[1], 1),
                                  round(words / WORDS_PER_MINUTE[0], 1)],
            'short_review_required': words < TARGET_MINUTES[0] * WORDS_PER_MINUTE[0],
            'duration_is_estimate': True}


def validate_review(review, plan, turns, source):
    """Require checkable evidence, not a word quota or self-assessed score."""
    def reject(message, *, substantive=False):
        error = RuntimeError if substantive else ReviewFormatError
        raise error('Podcast discussion review: ' + message)

    def text(value, minimum=20):
        return isinstance(value, str) and minimum <= len(value.strip()) <= 1200

    if not isinstance(turns, list) or not turns:
        reject('final dialogue is required')
    report = review.get('discussion_review') if isinstance(review, dict) else None
    if not isinstance(report, dict) or type(report.get('schema_version')) is not int or report['schema_version'] != 1:
        reject('missing source/turn-bound assessment')
    rows = report.get('topics')
    topics = plan['topics']
    if not isinstance(rows, list) or len(rows) != len(topics):
        reject('every planned topic needs its own assessment')
    seen, covered, referenced, discussions = set(), set(), set(), 0
    known = {row['id'] for row in source}
    for row in rows:
        if not isinstance(row, dict):
            reject('invalid topic assessment')
        index = row.get('topic_index')
        if type(index) is not int or not 0 <= index < len(topics) or index in seen:
            reject('unknown or duplicate topic assessment')
        seen.add(index)
        ids = row.get('covered_story_ids')
        if (not isinstance(ids, list) or not ids or any(not isinstance(i, str) for i in ids)
                or len(set(ids)) != len(ids) or not set(ids) <= set(topics[index]['story_ids'])):
            reject('coverage must identify real stories from the corresponding topic')
        covered.update(ids)
        references = row.get('turn_ids')
        if (not isinstance(references, list) or not references
                or any(type(i) is not int or not 0 <= i < len(turns) for i in references)
                or references != sorted(set(references))):
            reject('invalid final-dialogue turn references')
        if referenced.intersection(references):
            reject('independent topics cannot reuse the same dialogue as coverage evidence')
        referenced.update(references)
        if not text(row.get('finding')):
            reject('topic-specific reasoning is required')
        treatment = row.get('treatment')
        if treatment == 'discussion':
            exchange = row.get('exchange')
            if (not isinstance(exchange, list) or len(exchange) != 3
                    or any(type(i) is not int for i in exchange)
                    or not exchange[0] < exchange[1] < exchange[2]
                    or not set(exchange) <= set(references)):
                reject('discussion needs grounded reasoning, response and follow-up references')
            speakers = [turns[i].get('speaker') for i in exchange]
            if speakers[0] != speakers[2] or set(speakers) != {'Yaşar', 'Necdet'}:
                reject('referenced exchange must include a genuine two-host response')
            discussions += 1
        elif treatment != 'brief' or row.get('exchange') is not None:
            reject('unknown treatment or invalid brief references')
    if len(covered) * 2 <= len(known):
        reject('most news must be covered in the actual dialogue, not only the plan', substantive=True)
    if not discussions:
        reject('a headline/brief tour alone is not a developed conversation', substantive=True)
    budget = report.get('budget')
    if isinstance(budget, dict) and budget.get('appropriate') is False:
        reject('source-grounded scope/depth budget assessment is required', substantive=True)
    if not isinstance(budget, dict) or budget.get('appropriate') is not True or not text(budget.get('reason')):
        reject('source-grounded scope/depth budget assessment is required')
    if metrics(turns)['short_review_required']:
        limited = budget.get('limited_story_ids')
        if (not text(budget.get('short_reason'), 30) or not isinstance(limited, list)
                or not limited or any(not isinstance(i, str) or i not in known for i in limited)
                or len(set(limited)) != len(limited)):
            reject('short dialogue needs a specific source-bound editorial justification')
    return report
