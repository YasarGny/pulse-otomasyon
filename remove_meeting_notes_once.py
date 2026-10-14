import os,requests
base="https://api.notion.com/v1"
h={"Authorization":"Bearer "+os.environ["NOTION_TOKEN"],"Notion-Version":"2022-06-28"}
page="3f922115ab848156bb1fc0649973c0b5"
def get(id):
 r=requests.get(f"{base}/blocks/{id}/children",headers=h,params={"page_size":100},timeout=30);r.raise_for_status();return r.json()["results"]
def txt(b):
 return "".join(x.get("plain_text","") for x in b.get(b["type"],{}).get("rich_text",[]))
removed=0
for b in get(page):
 if b["type"]=="callout" and ("GÜNÜN DEĞERLENDİRMESİ" in txt(b) or b.get("has_children")):
  for child in get(b["id"]):
   if child["type"] in ("meeting_notes","meeting_note"):
    r=requests.delete(f"{base}/blocks/{child['id']}",headers=h,timeout=30);r.raise_for_status();removed+=1
print("Removed meeting notes:",removed)
