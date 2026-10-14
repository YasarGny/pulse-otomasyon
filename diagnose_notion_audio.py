import json, os, subprocess, tempfile, requests, traceback
from datetime import datetime, timezone
API="https://api.notion.com/v1"
HEAD={"Authorization":"Bearer "+os.environ["NOTION_TOKEN"],"Notion-Version":"2022-06-28"}
PAGE="3f922115ab848156bb1fc0649973c0b5"
report={"checked_at":datetime.now(timezone.utc).isoformat(),"checks":[],"status":"started"}
def api(path):
 r=requests.get(API+path,headers=HEAD,timeout=40)
 r.raise_for_status()
 return r.json()
try:
 blocks=api("/blocks/"+PAGE+"/children?page_size=100")["results"]
 audio=[b for b in blocks if b["type"]=="audio"]
 report["audio_block_count"]=len(audio)
 if not audio: raise RuntimeError("No Notion audio blocks found")
 for block in audio[:8]:
  entry={"block_id":block["id"]}
  report["checks"].append(entry)
  data=api("/blocks/"+block["id"])
  item=data["audio"]
  kind=item["type"]
  entry["type"]=kind
  url=item.get(kind,{}).get("url")
  entry["has_url"]=bool(url)
  if not url:
   entry["result"]="missing_url"
   continue
  response=requests.get(url,timeout=90)
  entry["http_status"]=response.status_code
  entry["content_type"]=response.headers.get("Content-Type")
  entry["bytes"]=len(response.content)
  response.raise_for_status()
  with tempfile.NamedTemporaryFile(suffix=".bin") as tmp:
   tmp.write(response.content);tmp.flush()
   check=subprocess.run(["ffprobe","-v","error","-show_entries","format=format_name,duration","-show_entries","stream=codec_name","-of","default=noprint_wrappers=1",tmp.name],capture_output=True,text=True)
   entry["ffprobe_exit"]=check.returncode
   entry["media_info"]=check.stdout[:500]
   entry["result"]="valid" if check.returncode==0 else "invalid_media"
  if check.returncode: raise RuntimeError("Downloaded media failed ffprobe")
 report["status"]="ok" if all(x.get("result")=="valid" for x in report["checks"]) else "partial"
except Exception as exc:
 report["status"]="error"
 report["error_type"]=type(exc).__name__
 report["error_message"]="Audio diagnostic failed; inspect status fields" 
finally:
 with open("audio-diagnostics.json","w",encoding="utf-8") as f:
  json.dump(report,f,ensure_ascii=False,indent=2)
 print(json.dumps(report,ensure_ascii=False,indent=2))
if report["status"]=="error": raise SystemExit(1)
