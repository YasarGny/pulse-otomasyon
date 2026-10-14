import os,base64,requests,json
API="https://api.notion.com/v1"
HEAD={"Authorization":"Bearer "+os.environ["NOTION_TOKEN"],"Notion-Version":"2022-06-28"}
PAGE="3f922115ab848156bb1fc0649973c0b5"
def call(method,path,**kwargs):
 r=requests.request(method,API+path,headers=HEAD,timeout=120,**kwargs);r.raise_for_status();return r.json()
blocks=call("GET",f"/blocks/{PAGE}/children",params={"page_size":100})["results"]
audio=next((b for b in blocks if b["type"]=="audio"),None)
if not audio:raise RuntimeError("No audio block")
item=call("GET","/blocks/"+audio["id"])["audio"]
url=item[item["type"]]["url"]
r=requests.get(url,timeout=120);r.raise_for_status()
raw=r.content
if len(raw)>4000000:raise RuntimeError("Audio too large for this embed test")
data=base64.b64encode(raw).decode("ascii")
html="""<!doctype html><html lang="tr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>body{background:#151c25;color:#fff;font:16px system-ui;margin:0;padding:20px}button{border:0;background:#009f8a;color:#fff;border-radius:12px;padding:14px;font-size:16px;font-weight:bold;margin-right:7px}#status{color:#b8c9d7;line-height:1.5;margin:20px 0}small{color:#9aabb9}</style></head><body><h2>🎧 PULSE · Gerçek MP3</h2><p>Dosya seçmeden, mevcut özel ses kaydı doğrudan bu HTML dosyasının içinden çözülür.</p><button id="play">▶ Dinle</button><button id="pause" style="background:#526173">■ Durdur</button><div id="status">Hazır · MP3 gömülü</div><small>Harici ses bağlantısı kullanılmıyor.</small><script>const b64='__BASE64__';let ctx,src;const status=document.getElementById('status');document.getElementById('play').onclick=async()=>{try{status.textContent='Ses çözümleniyor...';const AC=window.AudioContext||window.webkitAudioContext;if(!AC)throw Error('Web Audio desteklenmiyor');ctx=ctx||new AC();await ctx.resume();const binary=atob(b64),bytes=new Uint8Array(binary.length);for(let i=0;i<binary.length;i++)bytes[i]=binary.charCodeAt(i);const audio=await ctx.decodeAudioData(bytes.buffer);if(src){try{src.stop()}catch(e){}}src=ctx.createBufferSource();src.buffer=audio;src.connect(ctx.destination);src.start();status.textContent='Çalıyor · '+Math.round(audio.duration)+' saniye';src.onended=()=>status.textContent='Oynatma tamamlandı';}catch(e){status.textContent='Hata: '+e.name+' · '+e.message}};document.getElementById('pause').onclick=()=>{if(src){try{src.stop()}catch(e){}}status.textContent='Durduruldu'};</script></body></html>""".replace("__BASE64__",data)
with open("pulse-private-audio-test.html","w",encoding="utf-8") as f:f.write(html)
print("MP3 bytes",len(raw),"HTML bytes",len(html.encode()))
upload=call("POST","/file_uploads",json={"mode":"single_part","filename":"pulse-private-audio-test.html","content_type":"text/html"})
with open("pulse-private-audio-test.html","rb") as stream:
 response=requests.post(API+"/file_uploads/"+upload["id"]+"/send",headers=HEAD,files={"file":("pulse-private-audio-test.html",stream,"text/html")},timeout=180)
response.raise_for_status()
def rt(s):return [{"type":"text","text":{"content":s}}]
children=[{"object":"block","type":"heading_2","heading_2":{"rich_text":rt("🧪 PULSE gerçek ses · otomatik Web Audio testi")}},{"object":"block","type":"paragraph","paragraph":{"rich_text":rt("Dosya seçmeden, mevcut MP3 bu özel oynatıcıya gömülüdür.")}},{"object":"block","type":"embed","embed":{"url":"https://example.com"}}]
# Notion REST embed blocks cannot reference uploaded HTML files; use file block instead.
children[-1]={"object":"block","type":"file","file":{"type":"file_upload","file_upload":{"id":upload["id"]}}}
call("PATCH",f"/blocks/{PAGE}/children",json={"children":children})
print("Uploaded embedded-audio HTML as Notion file; open it to test.")
