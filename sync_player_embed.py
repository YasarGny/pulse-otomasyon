"""Update the existing Notion player embed URL when player HTML changes."""
import os
import requests

API = "https://api.notion.com/v1"
PAGE = "3f922115ab848156bb1fc0649973c0b5"
BASE = "https://yasargny.github.io/pulse-otomasyon/web-player/"
HEAD = {"Authorization": "Bearer " + os.environ["NOTION_TOKEN"], "Notion-Version": "2022-06-28", "Content-Type": "application/json"}
version = os.environ["GITHUB_SHA"][:12]
url = BASE + "?v=" + version

def children(page):
    cursor = None
    while True:
        params = {"page_size": 100}
        if cursor:
            params["start_cursor"] = cursor
        response = requests.get(f"{API}/blocks/{page}/children", headers=HEAD, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        yield from data["results"]
        cursor = data.get("next_cursor")
        if not cursor:
            break

found = []
for block in children(PAGE):
    if block.get("type") == "embed":
        current = block.get("embed", {}).get("url", "")
        if current.startswith(BASE):
            found.append(block)
if len(found) != 1:
    raise RuntimeError(f"Expected exactly one PULSE embed, found {len(found)}; no changes made.")
block = found[0]
if block["embed"]["url"] == url:
    print("PULSE player already current.")
else:
    response = requests.patch(f"{API}/blocks/{block['id']}", headers=HEAD, json={"embed": {"url": url}}, timeout=30)
    response.raise_for_status()
    print("Updated existing PULSE player embed URL to", url)
