"""One-time conservative PULSE page cleanup; keeps news, callouts and archive label."""
import os
import requests

API = "https://api.notion.com/v1"
PAGE = "3f922115ab848156bb1fc0649973c0b5"
HEAD = {"Authorization": "Bearer " + os.environ["NOTION_TOKEN"], "Notion-Version": "2022-06-28"}


def call(method, path, **kwargs):
    r = requests.request(method, API + path, headers=HEAD, timeout=60, **kwargs)
    r.raise_for_status()
    return r.json() if r.content else {}


def blocks():
    out, cursor = [], None
    while True:
        p = {"page_size": 100}
        if cursor:
            p["start_cursor"] = cursor
        data = call("GET", f"/blocks/{PAGE}/children", params=p)
        out += data["results"]
        if not data.get("has_more"):
            return out
        cursor = data["next_cursor"]


def label(b):
    return "".join(x.get("plain_text", "") for x in b.get(b["type"], {}).get("rich_text", []))


items = blocks()
start = next(i for i, b in enumerate(items) if b["type"] == "heading_2" and "Günün Sesli Özeti" in label(b))
end = next(i for i, b in enumerate(items) if b["type"] == "heading_2" and "60 saniyede gündem" in label(b))
archive = next(i for i, b in enumerate(items) if b["type"] == "heading_2" and "Arşiv" in label(b))
if not (start < end < archive):
    raise RuntimeError("Unexpected page structure, refusing cleanup")
# Preserve archive heading and issue marker; remove old audio and experiments only.
to_delete = items[start:end]
for b in items[archive + 1:]:
    if b["type"] == "paragraph" and "15 Ekim 2026" in label(b) and "Sayı 001" in label(b):
        continue
    to_delete.append(b)
for b in to_delete:
    call("DELETE", "/blocks/" + b["id"])
print("Removed", len(to_delete), "obsolete audio and test blocks")
url = "https://yasargny.github.io/pulse-otomasyon/web-player/"
children = [
    {"object": "block", "type": "heading_2", "heading_2": {"rich_text": [{"type": "text", "text": {"content": "🎧 Günün Sesli Özeti"}}]}},
    {"object": "block", "type": "embed", "embed": {"url": url}},
]
call("PATCH", f"/blocks/{PAGE}/children", json={"children": children, "after": items[0]["id"]})
print("Inserted production player")
