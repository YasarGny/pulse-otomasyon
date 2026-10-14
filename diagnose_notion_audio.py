import os, subprocess, tempfile, requests
API="https://api.notion.com/v1"
HEAD={"Authorization":"Bearer "+os.environ["NOTION_TOKEN"],"Notion-Version":"2022-06-28"}
PAGE="3f922115ab848156bb1fc0649973c0b5"
def api(path):
 r=requests.get(API+path,headers=HEAD,timeout=40)
 r.raise_for_status()
 return r.json()
blocks=api("/blocks/"+PAGE+"/children?page_size=100")["results"]
audio=[b for b in blocks if b["type"]=="audio"]
print("Audio blocks found:",len(audio))
for block in audio[:5]:
 data=api("/blocks/"+block["id"])
 item=data["audio"]
 kind=item["type"]
 url=item.get(kind,{}).get("url")
 print("Audio block:",block["id"],"type:",kind,"url_present:",bool(url))
 if not url: continue
 response=requests.get(url,timeout=90)
 print("Media HTTP:",response.status_code,"Content-Type:",response.headers.get("Content-Type"),"bytes:",len(response.content))
 response.raise_for_status()
 with tempfile.NamedTemporaryFile(suffix=".bin") as tmp:
  tmp.write(response.content);tmp.flush()
  check=subprocess.run(["ffprobe","-v","error","-show_entries","format=format_name,duration","-show_entries","stream=codec_name","-of","default=noprint_wrappers=1",tmp.name],capture_output=True,text=True)
  print("FFprobe exit:",check.returncode,"details:",(check.stdout+check.stderr)[:500])
  if check.returncode: raise RuntimeError("Notion-hosted audio cannot be decoded")
print("Diagnostics complete")
