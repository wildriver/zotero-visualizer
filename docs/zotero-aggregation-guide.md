# Zotero を業績データベースにする — 生成AIと一緒に進める手引き

**対象**: Zotero が空の状態から、自分の全業績を集約したい研究者
**必要なもの**: Zotero アカウント、API キー、生成AIのコーディング環境（Claude Code / Codex など）
**前提**: 専用ツールは配りません。AIとの対話で進めます

---

## 0. なぜ「専用スクリプト」ではなく「AIとの対話」なのか

業績集約は、一見すると自動化しやすそうで、実際にはそうではありません。

判断が必要な場面が次々に出てきます。「この研究会発表は論文として数えるか」「同姓の別研究者をどう除くか」「和文シンポジウム（DICOMO など）は国内会議か国際会議か」「同じ内容が予稿集と論文誌の両方にある場合どちらを残すか」。これらは分野・所属・本人の方針で答えが変わり、コードに固定できません。

さらに、ソースの持ち方が人によって全く違います。researchmap を丁寧に更新している人、Google Scholar だけの人、手元に LaTeX の業績リストがある人、研究室HPで管理している人。共通の入力形式を仮定できません。

だから **「汎用ツール」より「手順とTipsを渡して、AIに自分用のスクリプトを書かせる」** ほうが現実的です。この文書はそのための知識をまとめたものです。

### 現実的な期待値

参考として、著者の1人（983件）の実績では次のような経過でした。

- 集計・分析スクリプトを **5世代** 書き直した
- 書誌情報の補完パッチを **4回** 当てた
- 著者名の修正スクリプトを **3世代** 書いた
- 「要確認リスト」を目視レビューした（17KB + 14KB の報告書）

**一発では終わりません。** 8割を自動で入れて、残りを人が確認できる形にするのが目標です。「何が入っていないか」を出力する仕組みのほうが、完璧な自動化より価値があります。

---

## 1. 全体像

データは一方向に流れます。Zotero は**出力先（データベース）**であり、集約の入力ではありません。

```
[各種ソース]  researchmap / ORCID / OpenAlex / DBLP / Crossref / BibTeX / 自分のCV
     │
     ├─ 取得（多くは APIキー不要）
     ↓
[中間形式]  {title, authors, year, venue, doi, kind, source} の配列
     │
     ├─ 名寄せ・重複排除・カテゴリ分類   ← ここが人手の入る山場
     ↓
[Zotero]  API で書き込み（★書き込みキーが必須）
     │
     ↓
[可視化・活用]  Zotero API で読み出し
```

---

## 2. 準備

### API キーを取る

1. https://www.zotero.org/settings/keys にアクセス
2. "Create new private key"
3. **"Allow library write access" にチェック**（登録するので書き込み必須）
4. 表示されたキーを保存（再表示されません）

同じページに **数値のユーザーID** が表示されます。これも記録してください。

### キーの扱い

```bash
export ZOTERO_API_KEY=xxxxxxxxxxxxx
export ZOTERO_USER_ID=1234567
```

**コードに直書きしないでください。** AIに書かせるとサンプルとして埋め込まれがちなので、「キーは環境変数から読むように」と最初に指示しておくとよいです。公開リポジトリに置く場合はもちろん、ローカルでもAIとの会話ログに残るため、作業後にキーを再発行するのが安全です。

### 疎通確認

```bash
curl -s -H "Zotero-API-Key: $ZOTERO_API_KEY" \
     -H "Zotero-API-Version: 3" \
     "https://api.zotero.org/keys/current"
```

権限（`library: {write: true}`）が返ればOKです。

---

## 3. ソースからの取得

以下の件数は、すべて**著者1人の実例**（情報系・日本、最終983件）です。

> ⚠️ **この数字を一般論として読まないでください。**
> どのソースにどれだけ入っているかは、その人がどのサービスを更新してきたかで決まります。
> この例は researchmap を長年更新し、手元にCVもあったという特殊な条件です。
> **まず自分の各ソースで件数を数え、実際の業績数と比べる**ところから始めてください。
> その比較結果こそが、あなたにとってどれを主軸にすべきかの答えになります。

### researchmap — 日本語の業績が入っているなら最初に試す

**公開APIで、APIキー不要**です。permalink（researchmap のURLに出る文字列。例 `yutaka.arakawa`）だけで叩けます。

```bash
RM=yutaka.arakawa   # 自分のpermalinkに置き換える
for ep in published_papers presentations books_etc misc industrial_property_rights awards; do
  curl -s "https://api.researchmap.jp/$RM/$ep?limit=1000&format=json" -o "rm_$ep.json"
done
```

| エンドポイント | 内容 | 実測 |
|---|---|---|
| `published_papers` | 論文・予稿 | 519 |
| `presentations` | 学会発表 | 223 |
| `misc` | 解説記事など | 136 |
| `industrial_property_rights` | 特許 | 45 |
| `books_etc` | 著書 | 2 |
| `awards` | 受賞 | 27 |
| **計** | | **925** |

この例では最終983件のうち、9割にあたる分がこれだけで揃いました。

**ただしこれは researchmap を長年きちんと更新してきた場合の数字です。**
登録が数年止まっていれば当然その分は取れません。まず `total_items` を見て、
自分の実際の業績数と比べてみてください。乖離が大きければ、researchmap を主軸にはできません。

注意: permalink は**ドット区切り**のことがあります（`yutaka.arakawa`）。アンダースコアで試すと404になります。自分の researchmap ページのURLで確認してください。

### 国際的な索引 — 単独では足りない

同じ研究者で比較すると次のとおりでした。

| ソース | 実測件数 | キー | 備考 |
|---|---|---|---|
| OpenAlex | 407 | 不要 | 会議211・論文176。カバレッジ最良 |
| DBLP | 269 | 不要 | 情報系のみ |
| ORCID | 182（161件にDOI） | 不要 | 本人が登録した分だけ |
| Crossref | — | 不要 | DOIからの書誌補完に有用 |

この例では国際APIだけで全体の約40%にとどまりました。国内会議・研究会（540件）がどこにも載っていないためです。

**この比率は分野と業績構成で大きく変わります。** 国際会議・論文誌が中心の方なら国際APIでほぼ足りますし、
逆に国内発表が多い方はもっと下がります。自分がどちらに近いかは、取得件数を実際の業績数と比べれば分かります。

```bash
# ORCID（DOI付きの確実な情報源）
curl -s -H "Accept: application/json" \
  "https://pub.orcid.org/v3.0/0000-0002-XXXX-XXXX/works" -o orcid.json

# OpenAlex（ORCIDから全件）
curl -s "https://api.openalex.org/works?filter=author.orcid:0000-0002-XXXX-XXXX&per-page=200" -o openalex.json

# DBLP（情報系）
curl -s "https://dblp.org/search/publ/api?q=Yutaka+Arakawa&format=json&h=1000" -o dblp.json
```

### 自分のORCIDが分からない / 同姓の別人がいる場合

OpenAlex の著者検索が便利です。所属つきで候補が出るので、同姓同名を区別できます。

```bash
curl -s "https://api.openalex.org/authors?search=Yutaka%20Arakawa&per_page=5" \
 | python3 -c "
import json,sys
for a in json.load(sys.stdin)['results']:
    inst=(a.get('last_known_institutions') or [{}])[0].get('display_name')
    print(f\"{a['display_name']:<20} works={a['works_count']:<5} {a.get('orcid')}  {inst}\")"
```

実行例（3人が別人として並びます）:

```
Yutaka Arakawa   works=406  0000-0002-7156-9160  Kyushu University    ← 本人
Yutaka ARAKAWA   works=3    None                 Nagaoka Univ. of Tech.
Yutaka Arakawa   works=2    None                 None
```

**同姓の除外を後工程で手作業でやるより、入口で正しい著者IDを選ぶほうが確実です。**

### Google Scholar — 自動化を諦める

公式APIがありません。スクレイピングは利用規約違反で、CAPTCHAにより必ず壊れます。**他人に配る手順の土台にしてはいけません。**

正攻法は2つです。

1. **自分のプロフィールから BibTeX 書き出し** — 自分のデータなので正当。`.bib` を中間形式に変換するアダプタを1つ書けば、Scholar だけでなく手元のCVや共同研究者からもらった `.bib` も同じ経路で扱えます
2. **Zotero Connector**（ブラウザ拡張）— 利用者自身のブラウザが動くのでブロックされません。公式サポート経路です

### その他の自前ソース

手元の LaTeX 業績リスト、研究室HP、Word のCVなど。ここは各自バラバラなので、**AIに「このファイルを読んで中間形式のJSONにして」と頼むのが最速**です。正規表現を自分で書く必要はありません。

---

## 4. Zotero への書き込み — Tips集

ここが本題です。**ハマりどころが多いので、順に読んでください。**

### 4.1 基本形

```bash
# コレクション作成
curl -s -X POST "https://api.zotero.org/users/$ZOTERO_USER_ID/collections" \
  -H "Zotero-API-Key: $ZOTERO_API_KEY" -H "Zotero-API-Version: 3" \
  -H "Content-Type: application/json" \
  -d '[{"name":"II. 学術論文"}]'

# アイテム投入（1リクエストにつき最大50件）
curl -s -X POST "https://api.zotero.org/users/$ZOTERO_USER_ID/items" \
  -H "Zotero-API-Key: $ZOTERO_API_KEY" -H "Zotero-API-Version: 3" \
  -H "Content-Type: application/json" \
  -d '[{ ...item1... }, { ...item2... }]'
```

レスポンスは `{"successful":{...}, "unchanged":{...}, "failed":{...}}` の形で、**インデックスごとに成否が返ります**。`failed` を必ず確認してください。全体が200でも個別に失敗します。

### 4.2 ★ itemType の選び方 — 最大の罠

**和文の研究会発表・国内会議に `presentation` 型を使わないでください。**

一見自然な選択ですが、後で必ず困ります。

| | `presentation` | `conferencePaper` |
|---|---|---|
| 会議名のフィールド | `meetingName` | `conferenceName` / `proceedingsTitle` |
| 著者の creatorType | `presenter` | `author` |
| ページ・DOI・巻号 | **持てない** | 持てる |
| 引用スタイル出力 | 貧弱 | 正常 |

著者の1人は 479件を `presentation` で登録してしまい、後から `conferencePaper` へ一括変換する必要が生じました。そのとき次の事故が起きかけています。

- **`meetingName` は `conferencePaper` に存在しないフィールド**です。素直に itemType を変えると **479件すべての会議名が消えます**
- **`presenter` は `conferencePaper` に存在しない creatorType** です。2,168名分の著者情報が壊れます

変換するなら、同一リクエスト内で移し替えます。

```python
nd["itemType"] = "conferencePaper"
mn = nd.pop("meetingName", "")
if mn:
    nd["proceedingsTitle"] = mn          # ← これを忘れると会議名が消える
nd["creators"] = [
    {**c, "creatorType": "author"} if c.get("creatorType") == "presenter" else c
    for c in nd.get("creators", [])
]
```

**最初から `conferencePaper` + `proceedingsTitle` にしておけば、この苦労はありません。**

補足: 引用スタイル出力では `proceedingsTitle`（基底フィールドが `publicationTitle`）が使われます。`conferenceName` は「イベント名」であり、多くのスタイルで無視されます。**会議名は `proceedingsTitle` に入れてください。**

### 4.3 itemType ごとに使えるフィールドが違う

Zotero はサーバー側で厳格に検証します。不正なフィールドを送るとそのアイテムだけ `failed` になります。**推測せず、スキーマを見てください。**

```bash
curl -s "https://api.zotero.org/schema" -o schema.json
python3 -c "
import json
s=json.load(open('schema.json'))
for t in s['itemTypes']:
    if t['itemType']=='conferencePaper':
        print('fields:',[f['field'] for f in t['fields']])
        print('creatorTypes:',[c['creatorType'] for c in t['creatorTypes']])
        print('baseField:',{f['field']:f.get('baseField') for f in t['fields'] if f.get('baseField')})"
```

AIに「このitemTypeで使えるフィールドをスキーマAPIで確認してから書いて」と指示すると事故が減ります。

### 4.4 更新時の version と 412

既存アイテムを更新するには、そのアイテムの**現在の `version`** を含めて送ります。古い version を送ると `412 Precondition Failed` で拒否されます（同時編集を防ぐ仕組み）。

つまり **「バックアップJSONをそのまま書き戻す」ことはできません。** バックアップ内の version は古いためです。復元スクリプトは必ず「現在の version を取得し直してから差し替える」構造にします。

```python
vers = {k: v for k, v in current_versions().items()}   # 最新versionを取得
for item in backup:
    item["version"] = vers[item["key"]]                 # 差し替えてから送る
```

### 4.5 レート制限

レスポンスに `Backoff` または `Retry-After` ヘッダが来たら、その秒数だけ待ちます。実用上は **バッチ間に 0.2 秒程度の待ちを入れれば十分**でした（1,000件で約11リクエスト）。

### 4.6 ★ inPublications と「公開」の意味

`inPublications: true` を付けると、そのアイテムは Zotero の **My Publications** に入り、**APIキー無しで誰でも読める**ようになります。

著者の1人は、一括登録時に全アイテムにこれが付いていたことに後から気づきました。業績リストは公開前提の情報なので実害は薄く、むしろCVとして公開するのは自然ですが、**意図せずそうなっている可能性**は知っておくべきです。

確認方法:

```bash
# キーを付けずに叩く。件数が返るなら公開されている
curl -s -I "https://api.zotero.org/users/1234567/items" | grep -i total-results
```

副作用として、公開すれば**可視化ツールをキーなしで動かせます**。デモを人に見せたいときには便利です。

---

## 5. 名寄せと重複排除 — 自動化しきれない部分

複数ソースを混ぜると必ず重複します。

**DOI があるもの**: 小文字化して比較すれば確実です。

**DOI が無いもの**（国内会議はほぼこれ）: タイトルの正規化で突き合わせます。

```python
import re, unicodedata
def normkey(s):
    s = unicodedata.normalize("NFKC", s or "").lower()
    s = re.sub(r"\[[^\]]*\]", "", s)                    # [招待講演] などを除去
    return re.sub(r"[^0-9a-z぀-ヿ一-鿿]+", "", s)        # 記号・空白を全部落とす
```

**ただしこれだけでは足りません。** 実データ1,052件に対し、この正規化だけで見つかる重複は **2件** でした。学会の予稿は、同じ論文にセッション番号や開催情報が付いて表記が揺れるためです。

```
B-15-13 屋内位置推定手法の検討          ← セッション番号が前置
屋内位置推定手法の検討 (一般セッション)    ← 開催情報が後置
```

前後の付随情報を落としてから比較すると、検出数は **2件 → 68件** に増えました（同じ1,052件に対する実測）。

```python
def clean_title(t):
    t = re.sub(r"^[A-Z]+-\d+(?:-\d+)*\s+", "", t)        # B-15-13, M-049, BCS-1-4 など
    t = re.sub(r"\s*--\s*\([^)]*\)\s*$", "", t).strip()  # -- (特集 ○○)
    while re.search(r"\s*\([^)]*\)\s*$", t):             # 末尾の (…) を繰り返し除去
        t = re.sub(r"\s*\([^)]*\)\s*$", "", t).strip()
    return t
# 比較は normkey(clean_title(title)) で行う
```

**この手の除去パターンは分野ごとに違います。** 自分のデータで「重複と判定されなかったが実は同じもの」を数件見つけて、AIに「この2つが同一と判定されるように正規化を直して」と頼むのが早いです。

**著者名の統合が最も厄介です。** 「荒川 豊 / 荒川豊 / Arakawa Yutaka / Yutaka ARAKAWA / Arakawa」が同一人物であることを機械的に判定するのは困難です。著者の1人は結果的に **175人分の名前辞書を手作業で作りました**（別名リスト付き、184行）。

現実的な進め方:

1. 正規化キー（空白・中黒・ハイフンを除去して小文字化）で自動クラスタリング
2. **「統合されなかった名前の一覧」を出力させる** ← ここが重要
3. その一覧をAIに見せて「同一人物と思われるものをグループ化して」と頼む
4. 結果を目視で確認して辞書化

**完璧を目指さないでください。** 共著者Top5などの集計は、上位数人が正しければ実用に足ります。

---

## 6. AIとの対話例

実際の指示の出し方です。そのまま使えます。

### 集約の開始

```
Zotero を業績データベースとして使いたい。今は空。
私の researchmap permalink は yutaka.arakawa、ORCID は 0000-0002-XXXX-XXXX。

まず researchmap の公開API（キー不要）から
published_papers / presentations / books_etc / misc / industrial_property_rights
の5つを取得して、件数を報告して。まだ Zotero には書き込まないで。
```

### 分類方針の相談

```
取得したデータを Zotero のコレクションに分けたい。
私の分野の慣習では 著書 / 学術論文 / 国際会議 / 国内会議・研究会 / 解説記事 / 特許 の6分類。

和文か欧文か、researchmap の type、査読の有無から分類ルールを提案して。
判断が微妙なものは「要確認リスト」として別に出して。

重要: 国内会議・研究会も itemType は conferencePaper にして、
会議名は proceedingsTitle に入れて。presentation 型は使わないで。
```

### 書き込み前の確認

```
Zotero に投入する直前のJSONを、コレクションごとに3件ずつ見せて。
itemType ごとに使えるフィールドは Zotero のスキーマAPIで検証してから。
問題なければ、まず5件だけ投入して結果を確認したい。
```

### 投入と検証

```
残りを50件ずつ投入して。failed が出たら中断して内容を見せて。

投入後、コレクション × itemType のクロス集計と、
・会議名が空のもの
・著者が空のもの
・同一タイトルの重複
を一覧にして。
```

### 事故ったとき

```
itemType を変換したら会議名が消えたかもしれない。
meetingName を持っているアイテムがまだあるか、
conferencePaper で proceedingsTitle が空のものが何件あるか調べて。
```

### コツ

- **「まだ書き込まないで」を最初に言う。** AIは親切に実行してしまいます
- **少数（5件）で試す→確認→一括** の順を守る
- **書き込み前にバックアップを取らせる。** 「変更対象の現在の状態をJSONに保存してから実行して」
- **キーは環境変数から読ませる。** 「コードにAPIキーを直書きしないで」

---

## 7. 投入後の健全性チェック

必ず実行してください。件数が合っているだけでは不十分です。

```python
import json, urllib.request, collections, os, time
KEY=os.environ["ZOTERO_API_KEY"]; UID=os.environ["ZOTERO_USER_ID"]
H={"Zotero-API-Key":KEY,"Zotero-API-Version":"3"}

items=[];start=0
while True:
    r=urllib.request.Request(f"https://api.zotero.org/users/{UID}/items?limit=100&start={start}",headers=H)
    with urllib.request.urlopen(r) as x:
        c=json.loads(x.read()); t=int(x.headers.get("Total-Results") or 0)
    if not c: break
    items+=c; start+=len(c)
    if start>=t: break
    time.sleep(0.05)

# コレクション × itemType のクロス集計（分類ミスが一目で分かる）
r=urllib.request.Request(f"https://api.zotero.org/users/{UID}/collections?limit=100",headers=H)
with urllib.request.urlopen(r) as x: cols=json.loads(x.read())
cmap={c["key"]:c["data"]["name"] for c in cols}
cross=collections.defaultdict(collections.Counter)
for i in items:
    for c in i["data"].get("collections",[]):
        cross[cmap.get(c,c)][i["data"].get("itemType")]+=1
for c in sorted(cross):
    print(f"\n{c} (計{sum(cross[c].values())})")
    for t,n in cross[c].most_common(): print(f"   {t:<18} {n}")

# 欠落チェック
conf=[i for i in items if i["data"].get("itemType")=="conferencePaper"]
print("\n会議名が空:", sum(1 for i in conf if not (i["data"].get("proceedingsTitle") or i["data"].get("conferenceName"))))
print("著者が空:", sum(1 for i in items if not [c for c in i["data"].get("creators",[]) if c.get("creatorType")=="author"]))
print("meetingName 残存:", sum(1 for i in items if i["data"].get("meetingName")))
```

**クロス集計は特に有効です。** 「IV. 国内会議・研究会 に presentation が479件」のような分類ミスが一目で分かります。逆に「V. 解説記事に複数著者の項目が62件」のような違和感も見つかります（解説記事は単著が多いはず、という自分の感覚と突き合わせる）。

---

## 8. 可視化へ

集約が終われば、Zotero API から読み出して自由に使えます。可視化ツールはこのリポジトリの `pub_timeline.html` を参考にしてください（**集約とは独立**しています）。

冒頭の `CFG` ブロックを自分用に書き換えるだけで動きます。

```javascript
const CFG={
  ownerName:'山田 太郎',
  subtitle:'研究業績の変遷',
  eyebrow:'Research Output Timeline',
  zoteroUsername:'yamada',   // Zotero のユーザー名（数値IDではリンクが404になる）
};
```

---

## 付録: 使ったAPIの一覧

| API | 認証 | CORS | 用途 |
|---|---|---|---|
| `api.zotero.org` | 読=公開時不要 / 書=必須 | ✅ `*` | 登録・読み出し |
| `api.researchmap.jp/{permalink}/...` | 不要 | ✅ `*` | 日本の業績（最重要） |
| `pub.orcid.org/v3.0/{orcid}/works` | 不要 | ✅ `*` | DOI付き業績 |
| `api.openalex.org` | 不要 | ✅ `*` | 著者特定・広いカバレッジ |
| `dblp.org/search/publ/api` | 不要 | ✅ | 情報系 |
| `api.crossref.org` | 不要 | ✅ `*` | DOIから書誌補完 |
| `api.semanticscholar.org` | 任意（無しは429になりやすい） | ✅ `*` | 抄録補完 |
| Google Scholar | — | — | **APIなし。BibTeX書き出しで代替** |

すべて CORS 対応なので、ブラウザだけで動くツールも作れます（サーバー不要）。

---

*この文書は、実際に983件を集約した際に遭遇した問題をもとに書かれています。数値はすべて実測値です。*
