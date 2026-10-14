import os, asyncio, datetime, requests, edge_tts
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
 if date.casefold() not in " ".join(nested_text(b) for b in blocks[:8]).casefold():
  raise RuntimeError("Bugünün bülteni henüz sayfada değil")
 marker="PULSE-AUDIO-"+today.strftime("%Y%m%d")
 if any(marker in txt(b) for b in blocks): return
 stories=[]
 for i,b in enumerate(blocks):
  if b["type"]=="heading_3":
   summary=next((txt(x) for x in blocks[i+1:i+4] if x["type"]=="paragraph" and txt(x)),"")
   if summary: stories.append(txt(b)+". "+summary)
 if not stories: raise RuntimeError("Haber bulunamadı")
 speech="Merhaba. PULSE günlük teknoloji bülteni. Bugün "+date+". "+" ".join(stories[:5])+" Ayrıntılar PULSE sayfasında. Yarın görüşmek üzere."
 filename="pulse.mp3"
 await edge_tts.Communicate(speech,"tr-TR-EmelNeural").save(filename)
 upload=req("POST","/file_uploads",json={"mode":"single_part","filename":filename,"content_type":"audio/mpeg"})
 with open(filename,"rb") as f:
  r=requests.post(API+"/file_uploads/"+upload["id"]+"/send",headers=HEAD,files={"file":(filename,f,"audio/mpeg")},timeout=120)
 r.raise_for_status()
 def rt(s): return [{"type":"text","text":{"content":s}}]
 children=[{"object":"block","type":"heading_2","heading_2":{"rich_text":rt("🎧 Günün Sesli Özeti")}},{"object":"block","type":"audio","audio":{"type":"file_upload","file_upload":{"id":upload["id"]}}},{"object":"block","type":"paragraph","paragraph":{"rich_text":rt(marker)}}]
 req("PATCH",f"/blocks/{PAGE}/children",json={"children":children,"after":blocks[0]["id"]})
 print("Sesli özet yüklendi")
asyncio.run(main())
