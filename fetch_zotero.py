"""
Zotero API から全アイテムを再取得して viz_data.json を更新するスクリプト。

読み取りのみなので、ライブラリが公開されていれば API キーは不要。
非公開ライブラリを読む場合だけ環境変数 ZOTERO_API_KEY を設定する。

    export ZOTERO_USER_ID=15268781     # 省略時は下の既定値
    export ZOTERO_API_KEY=xxxxx        # 公開ライブラリなら不要
    python3 fetch_zotero.py
"""
import json, os, urllib.request, time, sys

USER_ID = os.environ.get("ZOTERO_USER_ID", "15268781")
KEY_API = os.environ.get("ZOTERO_API_KEY", "")
BASE    = f"https://api.zotero.org/users/{USER_ID}"
HEADERS = {"Zotero-API-Version": "3"}
if KEY_API:
    HEADERS["Zotero-API-Key"] = KEY_API

def get(path, params=None):
    url = f"{BASE}{path}"
    if params:
        url += "?" + "&".join(f"{k}={v}" for k, v in params.items())
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        total = r.headers.get("Total-Results")
        return json.loads(r.read()), int(total) if total else None

def fetch_all(path, extra=None):
    """100件ずつページングして全件取得。"""
    params = {"limit": "100", "start": "0"}
    if extra:
        params.update(extra)
    result, total = get(path, params)
    print(f"  {path}: total={total}, fetched={len(result)}", end="", flush=True)
    start = len(result)
    while total and start < total:
        params["start"] = str(start)
        chunk, _ = get(path, params)
        result.extend(chunk)
        start += len(chunk)
        print(f" {start}", end="", flush=True)
        time.sleep(0.1)
    print()
    return result

# ── コレクション取得 ───────────────────────────────────────
print("コレクション取得中...")
cols_raw, _ = get("/collections", {"limit": "100"})
import re as _re
def _norm_col(n): return _re.sub(r'^([IVX]+)\.\s+', r'\1.', n)
collections = {c["key"]: _norm_col(c["data"]["name"]) for c in cols_raw}
print(f"  コレクション数: {len(collections)}")
for k, v in collections.items():
    print(f"    {k}: {v}")

# ── 全アイテム取得 ─────────────────────────────────────────
print("\nアイテム取得中...")
items = fetch_all("/items")
print(f"  取得完了: {len(items)} 件")

# ── membership 構築 ────────────────────────────────────────
memberships = {}
for item in items:
    cols = item.get("data", {}).get("collections", [])
    if cols:
        memberships[item["key"]] = cols

print(f"  コレクション所属アイテム: {len(memberships)} 件")

# ── 保存 ──────────────────────────────────────────────────
out = {
    "items":       items,
    "memberships": memberships,
    "collections": collections,
}
with open("viz_data.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=None, separators=(",", ":"))

size_mb = len(json.dumps(out, ensure_ascii=False)) / 1024 / 1024
print(f"\nviz_data.json 書き込み完了 ({size_mb:.1f} MB)")
print(f"  items: {len(items)}, memberships: {len(memberships)}, collections: {len(collections)}")
