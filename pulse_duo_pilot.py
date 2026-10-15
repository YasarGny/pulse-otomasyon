"""Generate an independent PULSE two-male-host podcast pilot from today's Notion news."""
import asyncio, datetime as dt, hashlib, json, os, re, subprocess, tempfile
from pathlib import Path
import edge_tts, requests

PAGE="3f922115ab848156bb1fc0649973c0b5"
HEAD={"Authorization":"Bearer "+os.environ["NOTION_TOKEN"],"Notion-Version":"2022-06-28"}
OUT=Path("web-player")
def rich(b): return "".join(x.get("plain_text","") for x in b.get(b.get("type"),{}).get("rich_text",[]))
def blocks():
    all_blocks=[]; cursor=None
    while True:
        p={"page_size":100}
        if cursor:p["start_cursor"]=cursor
        r=requests.get(f"https://api.notion.com/v1/blocks/{PAGE}/children",headers=HEAD,params=p,timeout=40);r.raise_for_status()
        data=r.json();all_blocks+=data["results"];cursor=data.get("next_cursor")
        if not cursor:return all_blocks
def stories_from_notion():
    b=blocks();today=dt.datetime.now(dt.timezone(dt.timedelta(hours=3)))
    date=f"{today.day} "+("Ocak Şubat Mart Nisan Mayıs Haziran Temmuz Ağustos Eylül Ekim Kasım Aralık".split()[today.month-1])+f" {today.year}"
    # Pilot intentionally reads the currently published issue, even if the workflow
    # runs on a later calendar day. The production daily audio retains its date guard.
    intro=" ".join(rich(x) for x in b[:5])
    match=re.search(r"(\d{1,2})\s+(Ocak|Şubat|Mart|Nisan|Mayıs|Haziran|Temmuz|Ağustos|Eylül|Ekim|Kasım|Aralık)\s+(20\d{2})",intro,re.I)
    if not match:raise RuntimeError("Published issue date not found in Notion")
    date=match.group(0)
    active=False; stories=[]
    for i,x in enumerate(b):
        if x["type"]=="heading_1":
            if "Bugünün haberleri" in rich(x):active=True
            elif active:break
        if active and x["type"]=="heading_3":
            title=rich(x)
            summary=next((rich(y) for y in b[i+1:i+4] if y["type"]=="paragraph" and rich(y)),"")
            if summary:stories.append((title,summary))
    if len(stories)<3:raise RuntimeError("Not enough current stories")
    return date,stories[:5]
def clean(s):
    s=re.sub(r"\bAI\b","yapay zekâ",s,flags=re.I)
    return re.sub(r"\s+"," ",s).strip()
def conversation(date,stories):
    d=[("Yaşar",f"Merhaba, Yeni Sekme'ye hoş geldiniz. Ben Yaşar. Bugün {date}. Necdet'le günün ilginç teknoloji haberlerini konuşacağız."),
       ("Necdet","Selam Yaşar. Ben de birkaç gelişme seçtim. Haberleri sadece okumayalım, ne anlama geldiklerini de tartışalım.")]
    questions=["Peki bu gelişmenin günlük hayattaki karşılığı ne olabilir?","Burada sence en önemli ayrıntı ne?","Güzel ama bunun önünde ne gibi engeller var?","Bu haberin teknoloji dünyası açısından anlamı ne?","Bu gelişmeye biraz temkinli yaklaşmak gerekir mi?"]
    for i,(title,summary) in enumerate(stories):
        lead="Yaşar" if i%2==0 else "Necdet"
        other="Necdet" if lead=="Yaşar" else "Yaşar"
        d.append((lead,("Benim getirdiğim habere bakalım. " if i else "İlk haberimiz şu. ")+clean(title)+". "+clean(summary)))
        d.append((other,questions[i%len(questions)]))
        d.append((lead,[
            "Bence burada asıl mesele, açıklanan teknolojinin gerçek koşullarda ne kadar iyi çalışacağı. İlk duyuruyla sahadaki sonuçları birbirinden ayırmak gerekiyor.",
            "Bu haber, yapay zekânın yalnızca yazılımdan ibaret olmadığını hatırlatıyor. Altyapı ve maliyet tarafı da belirleyici.",
            "Erişim artması umut verici ama duyurunun somut sonuçlarını görmek gerek. Araştırmacıların ne üretebildiği daha önemli.",
            "Yetki, denetim ve güvenlik sınırları çok önemli. Bir sistemin yapabiliyor olması, her şeyi kontrolsüz yapması gerektiği anlamına gelmiyor.",
            "Teknolojiye talep yüksek olsa bile finansman şartları yatırım kararlarını etkileyebilir. Borsa hareketini tek başına talep göstergesi saymamak lazım."
        ][i%5]))
        d.append((other,"Yani heyecan verici tarafı var ama sonucu görmek için biraz beklemek gerekiyor. Bir sonraki gelişmeye geçelim." if i<len(stories)-1 else "Bugünkü haberlerin ortak noktası da bu: teknolojinin gerçek dünyadaki etkisi."))
    d.extend([("Yaşar","Bugünlük bu kadar. Ayrıntılı haberleri ve kaynakları PULSE bülteninde bulabilirsiniz."),
              ("Necdet","Yeni Sekme'de görüşmek üzere!")])
    return d
async def main():
    date,stories=stories_from_notion()
    turns=conversation(date,stories)
    OUT.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        folder=Path(tmp);parts=[]
        for i,(speaker,line) in enumerate(turns):
            part=folder/f"{i:03d}.mp3"
            # Turkish neural voice: two male roles differentiated by pitch and pace.
            await edge_tts.Communicate(line,"tr-TR-AhmetNeural",rate="-7%" if speaker=="Yaşar" else "+3%",pitch="-18Hz" if speaker=="Yaşar" else "+18Hz").save(str(part))
            parts.append(part)
        listing=folder/"list.txt"
        listing.write_text("".join("file '"+str(p.resolve())+"'\n" for p in parts),encoding="utf-8")
        target=OUT/"pilot-duo.mp3"
        subprocess.run(["ffmpeg","-v","error","-y","-f","concat","-safe","0","-i",str(listing),"-ac","1","-ar","44100","-c:a","libmp3lame","-b:a","96k",str(target)],check=True)
        duration=float(subprocess.check_output(["ffprobe","-v","error","-show_entries","format=duration","-of","default=noprint_wrappers=1:nokey=1",str(target)],text=True))
        if duration<90 or target.stat().st_size<30000:raise RuntimeError("Pilot validation failed")
        (OUT/"pilot-duo.json").write_text(json.dumps({"date":date,"audio":"pilot-duo.mp3","version":hashlib.sha256(target.read_bytes()).hexdigest()[:16],"duration":round(duration),"speakers":["Yaşar","Necdet"]},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print("Pilot complete:",date,round(duration),"seconds")
if __name__=="__main__":asyncio.run(main())
