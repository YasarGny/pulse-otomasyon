import os, asyncio, datetime, requests, edge_tts, re, unicodedata, subprocess
API="https://api.notion.com/v1"
HEAD={"Authorization":"Bearer "+os.environ["NOTION_TOKEN"],"Notion-Version":"2022-06-28"}
PAGE="3f922115ab848156bb1fc0649973c0b5"
def req(method,path,**kw):
 r=requests.request(method,API+path,headers=HEAD,timeout=90,**kw);r.raise_for_status();return r.json()
def txt(b):
 return "".join(x.get("plain_text","") for x in b.get(b.get("type"),{}).get("rich_text",[]))
def nested_text(block):
 parts=[txt(block)]
 if block.get("has_children"):
  for child in req("GET",f"/blocks/{block['id']}/children",params={"page_size":100})["results"]:
   parts.append(txt(child))
 return " ".join(parts)
async def main():
 blocks=req("GET",f"/blocks/{PAGE}/children",params={"page_size":100})["results"]
 today=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=3)))
 months="Ocak Şubat Mart Nisan Mayıs Haziran Temmuz Ağustos Eylül Ekim Kasım Aralık".split()
 date=f"{today.day} {months[today.month-1]} {today.year}"
 page_intro=" ".join(nested_text(b) for b in blocks[:8])
 def normalize(s):
  return "".join(ch for ch in unicodedata.normalize("NFKD",s.casefold()) if not unicodedata.combining(ch))
 print("Beklenen tarih:",date,"Sayfa başlangıcı:",repr(page_intro[:450]))
 if normalize(date) not in normalize(page_intro) and today.strftime("%d.%m.%Y") not in page_intro:
  raise RuntimeError("Bugünün bülteni henüz sayfada değil")
 marker="PULSE-AUDIO-"+today.strftime("%Y%m%d")
 if any(marker in txt(b) for b in blocks) and os.environ.get("REPAIR_AUDIO") != "1": return
 stories=[]
 for i,b in enumerate(blocks):
  if b["type"]=="heading_3":
   summary=next((txt(x) for x in blocks[i+1:i+4] if x["type"]=="paragraph" and txt(x)),"")
   if summary: stories.append(txt(b)+". "+summary)
 if not stories: raise RuntimeError("Haber bulunamadı")
 def for_voice(s):
  substitutions={"PULSE":"Pals","AI":"yapay zeka","DeepMind":"Diip Maynd","AlphaFold":"Alfa Fold","Google":"Gugıl","Cloud":"Klaud"}
  for original,pronunciation in substitutions.items():
   s=re.sub(r"\\b"+re.escape(original)+r"\\b",pronunciation,s,flags=re.I)
  return s
 speech="Merhaba. Pals günlük teknoloji bültenine hoş geldiniz. Bugün "+date+". "
 speech+=" ".join("Sıradaki haber. "+for_voice(story) for story in stories[:5])
 speech+=" Bugünün öne çıkan haberleri bunlardı. Ayrıntılar Pals sayfasında. Yarın görüşmek üzere."
 await edge_tts.Communicate(speech,"tr-TR-EmelNeural",rate="-5%").save("original.mp3")
 formats=[
  ("pulse.mp3","audio/mpeg",["-c:a","libmp3lame","-b:a","128k"],"MP3"),
  ("pulse.m4a","audio/mp4",["-c:a","aac","-b:a","128k"],"M4A")
 ]
 uploads=[]
 for filename,mime,codec,label in formats:
  subprocess.run(["ffmpeg","-v","error","-y","-i","original.mp3","-vn","-ac","2","-ar","44100",*codec,filename],check=True)
  info=subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","default=noprint_wrappers=1:nokey=1",filename],capture_output=True,text=True,check=True)
  duration=float(info.stdout.strip())
  subprocess.run(["ffmpeg","-v","error","-i",filename,"-f","null","-"],check=True)
  print(label,"duration:",duration,"bytes:",os.path.getsize(filename))
  if duration<15 or os.path.getsize(filename)<20000: raise RuntimeError(label+" audio validation failed")
  upload=req("POST","/file_uploads",json={"mode":"single_part","filename":filename,"content_type":mime})
  with open(filename,"rb") as stream:
   response=requests.post(API+"/file_uploads/"+upload["id"]+"/send",headers=HEAD,files={"file":(filename,stream,mime)},timeout=120)
  response.raise_for_status()
  uploads.append((label,upload["id"]))
 def rt(s): return [{"type":"text","text":{"content":s}}]
 children=[{"object":"block","type":"heading_2","heading_2":{"rich_text":rt("🎧 Günün Sesli Özeti")}}]
 for label,uid in uploads:
  children.append({"object":"block","type":"paragraph","paragraph":{"rich_text":rt(label+" ses kaydı")}})
  children.append({"object":"block","type":"audio","audio":{"type":"file_upload","file_upload":{"id":uid}}})
 children.append({"object":"block","type":"paragraph","paragraph":{"rich_text":rt(marker)}})
 req("PATCH",f"/blocks/{PAGE}/children",json={"children":children,"after":blocks[0]["id"]})
 if os.environ.get("REPAIR_AUDIO") == "1":
  for i,b in enumerate(blocks):
   if marker in txt(b):
    for old in blocks[max(0,i-2):i+1]:
     if old["type"] in ("heading_2","audio","paragraph"):
      req("DELETE","/blocks/"+old["id"])

 print("Sesli özet yüklendi")
asyncio.run(main())
