import json, re, unicodedata
from collections import defaultdict, Counter

raw = json.load(open("viz_data.json"))
items = raw["items"]
memberships = raw["memberships"]
COLLECTIONS = raw["collections"]

COL_ORDER = ["I.著書","II.学術論文","III.国際会議","IV.国内会議・研究会","V.解説記事・その他","VI.特許"]

def norm(n): return unicodedata.normalize("NFKC", n or "").strip()
def normkey(n): return re.sub(r"[\s　\-\.\・]", "", norm(n)).lower()

def en_first_last(n):
    """画面表示用。欧文名だけ「名 姓」にする（Arakawa Yutaka → Yutaka Arakawa）。
    引用スタイル用の ae は splitName が先頭を姓として読むので、そちらには使わない。"""
    if not n or has_cjk(n): return n
    t = n.split()
    return n if len(t) < 2 else " ".join(t[1:]) + " " + t[0]

def has_cjk(s): return bool(re.search(r"[　-鿿豈-﫿]", s))

def strip_num(t):
    """Strip session number prefix like B-15-13, M-049, BCS-1-4"""
    return re.sub(r"^[A-Z]+-\d+(?:-\d+)*\s+", "", t)

def strip_session_all(t):
    """Strip trailing parenthetical session info: (xxx) and -- (xxx)"""
    t = re.sub(r"\s*--\s*\([^)]*\)\s*$", "", t).strip()
    while re.search(r"\s*\([^)]*\)\s*$", t):
        t = re.sub(r"\s*\([^)]*\)\s*$", "", t).strip()
    return t

def clean_title(t):
    """Apply both prefix and suffix cleaning to a raw title."""
    t = norm(t)
    t = strip_num(t)
    t = strip_session_all(t)
    return t

def ntitle(t):
    """Normalized key for deduplication."""
    t = clean_title(t)
    return re.sub(r"[\s　]", "", t).lower()

def extract_year(item):
    d = item.get("data", {})
    for f in ["date", "filingDate"]:
        v = (d.get(f) or "").strip()
        m = re.search(r"(19|20)\d{2}", v)
        if m: return int(m.group())
    return None

def is_ja_title(title):
    return bool(re.search(r"[ぁ-んァ-ヿ一-鿿]", title))

def is_arakawa(name):
    n = norm(name)
    nk = normkey(n)
    if ("荒川" in n and "豊" in n) or ("arakawa" in nk and "yutaka" in nk):
        return True
    # 苗字のみ "Arakawa" は教授本人とみなす（学生なら必ずフルネーム）
    if nk == "arakawa" or n == "荒川":
        return True
    return False

def get_collection(key):
    for ck in memberships.get(key, []):
        if ck in COLLECTIONS: return COLLECTIONS[ck]
    return "その他"

# ─── Person registry ───
PERSONS = [
    # 教員
    {"ja":"笹瀬 巌",     "en":"Sasase Iwao",         "keys":["笹瀬巌","笹瀬厳","sasaseiwao","sasase"],            "faculty":True},
    {"ja":"山中 直明",   "en":"Yamanaka Naoaki",     "keys":["山中直明","yamanakanaoki","yamanaka","naoakiyamanaka"],"faculty":True},
    {"ja":"安本 慶一",   "en":"Yasumoto Keiichi",    "keys":["安本慶一","yasumotokeiichi","yasumoto","keiichiyasumoto"],"faculty":True},
    {"ja":"福田 晃",     "en":"Fukuda Akira",        "keys":["福田晃","fukudaakira","fukuda"],                    "faculty":True},
    {"ja":"田頭 茂明",   "en":"Tagashira Shigeaki",  "keys":["田頭茂明","tagashirashingeaki","tagashira"],        "faculty":True},
    {"ja":"諏訪 博彦",   "en":"Suwa Hirohiko",       "keys":["諏訪博彦","suwahirohiko"],                          "faculty":True},
    {"ja":"石田 繁巳",   "en":"Ishida Shigemi",      "keys":["石田繁巳","ishidashigemi"],                         "faculty":True},
    {"ja":"中村 優吾",   "en":"Nakamura Yugo",       "keys":["中村優吾","nakamuraugo"],                           "faculty":True,"faculty_from":2020},
    {"ja":"松田 裕貴",   "en":"Matsuda Yuki",        "keys":["松田裕貴","matsudayuki","matsudayuki0001","matsuda"],"faculty":True,"faculty_from":2019},
    {"ja":"岡本 聡",     "en":"Okamoto Satoru",      "keys":["岡本聡","okamotosatoru","okamoto"],                 "faculty":True},
    {"ja":"玉井 森彦",   "en":"Tamai Morihiko",      "keys":["玉井森彦","tamaimorihiko"],                         "faculty":True},
    {"ja":"藤本 まなと", "en":"Fujimoto Manato",     "keys":["藤本まなと","fujimotomanato"],                      "faculty":True},
    {"ja":"水本 旭洋",   "en":"Mizumoto Teruhiro",   "keys":["水本旭洋","mizumototeruhiro","mizumotoakihiro"],     "faculty":True},
    {"ja":"中西 恒夫",   "en":"Nakanishi Tsuneo",    "keys":["中西恒夫","nakanishitsuneo"],                       "faculty":True},
    {"ja":"崔 赫秦",     "en":"Choi Hyuckjin",       "keys":["崔赫秦","choihyuckjin","choihyuck-jin"],            "faculty":True},
    {"ja":"福嶋 政期",   "en":"Fukushima Shogo",     "keys":["福嶋政期","fukushimashogo","fukushimashōgo"],       "faculty":True},
    {"ja":"峯 恒憲",     "en":"Mine Tsunenori",      "keys":["峯恒憲","minetsunenori"],                           "faculty":True},
    # 既卒・研究者
    {"ja":"清水 翔",     "en":"Shimizu Sho",         "keys":["清水翔","shimizusho","shimizu","shoshimizu"],        "faculty":False},
    {"ja":"柏本 幸俊",   "en":"Kashimoto Yukitoshi", "keys":["柏本幸俊","kashimotoyukitoshi"],                    "faculty":False},
    {"ja":"林谷 昌洋",   "en":"Hayashitani Masahiro","keys":["林谷昌洋","hayashitanimasahiro","hayashitani"],      "faculty":False},
    {"ja":"笠原 照夫",   "en":"Kasahara Teruo",      "keys":["笠原照夫","笠原照雄","kasaharateruo","kasahara"],   "faculty":False},
    {"ja":"河中 祥吾",   "en":"Kawanaka Shogo",      "keys":["河中祥吾","kawanakashogo"],                         "faculty":False},
    {"ja":"甲斐 貴一朗", "en":"Kai Kiichiro",        "keys":["甲斐貴一朗","kaikiichiro"],                         "faculty":False},
    {"ja":"平岡 滉司",   "en":"Hiraoka Koushi",      "keys":["平岡滉司","hiraokakoushi"],                         "faculty":False},
    {"ja":"正井 克俊",   "en":"Masai Katsutoshi",    "keys":["正井克俊","masaikatsutoshi"],                       "faculty":True},
    {"ja":"林田 宗樹",   "en":"Hayashida Toshiki",   "keys":["林田宗樹","hayashidatoshiki"],                      "faculty":False},
    {"ja":"森田 達弥",   "en":"Morita Tatsuya",      "keys":["森田達弥","moritatatsuya","moritatsuya","morita"],  "faculty":False},
    {"ja":"藤原 聖司",   "en":"Fujiwara Masashi",    "keys":["藤原聖司","fujiwaramasashi","fujiwaraseiji"],       "faculty":False},
    {"ja":"北須賀 輝明", "en":"Kitasuka Teruaki",    "keys":["北須賀輝明","kitasukateruaki","kitasuka"],          "faculty":True},
    {"ja":"宮城 洋之",   "en":"Miyagi Hiroyuki",     "keys":["宮城洋之","miyagihiroyuki","miyagi"],               "faculty":False},
    {"ja":"梨本 恵一",   "en":"Nashimoto Keiichi",   "keys":["梨本恵一","nashimotokeiichi","nashimoto"],          "faculty":False},
    {"ja":"石井 大介",   "en":"Ishii Daisuke",       "keys":["石井大介","ishiidaisuke","ishii"],                  "faculty":False},
    {"ja":"竹沢 永訓",   "en":"Takezawa Naganori",   "keys":["竹沢永訓","takezawanaganori","takezawa"],           "faculty":False},
    {"ja":"新井 イスマイル","en":"Arai Ismail",       "keys":["新井イスマイル","araiismail"],                      "faculty":False},
    # 対応表より追加
    {"ja":"赤池 勇磨",   "en":"Akaike Yuma",         "keys":["赤池勇磨","akaikeyuma"],                            "faculty":False},
    {"ja":"芦沢 國正",   "en":"Ashizawa Kunitaka",   "keys":["芦沢國正","ashizawakunitaka","ashizawakunimasa"],   "faculty":False},
    {"ja":"阿部 竜弥",   "en":"Abe Tatsuya",         "keys":["阿部竜弥","abetatsuya","abe"],                      "faculty":False},
    {"ja":"雨森 千周",   "en":"Amenomori Chishu",    "keys":["雨森千周","amenomorichishu","amenomori"],           "faculty":False},
    {"ja":"荒賀 崇",     "en":"Araga Takashi",       "keys":["荒賀崇","aragatakashi"],                            "faculty":False},
    {"ja":"荒川 周造",   "en":"Arakawa Shuzo",       "keys":["荒川周造","arakawashuzo"],                          "faculty":False},
    {"ja":"石川 浩行",   "en":"Ishikawa Hiroyuki",   "keys":["石川浩行","ishikawahiroyuki"],                      "faculty":False},
    {"ja":"石川 雄一",   "en":"Ishikawa Yuichi",     "keys":["石川雄一","ishikawayuichi"],                        "faculty":False},
    {"ja":"石田 千枝",   "en":"Ishida Chie",         "keys":["石田千枝","ishidachie"],                            "faculty":False},
    {"ja":"石丸 翔也",   "en":"Ishimaru Shoya",      "keys":["石丸翔也","ishimarushoya"],                         "faculty":True},
    {"ja":"井上 創造",   "en":"Inoue Sozo",          "keys":["井上創造","inouesozo"],                             "faculty":True},
    {"ja":"岩本 智裕",   "en":"Iwamoto Tomohiro",    "keys":["岩本智裕","iwamototomohiro"],                       "faculty":False},
    {"ja":"植田 敏浩",   "en":"Ueda Toshihiro",      "keys":["植田敏浩","uedatoshihiro"],                         "faculty":False},
    {"ja":"碓井 亮太",   "en":"Usui Ryota",          "keys":["碓井亮太","usuiryota","usui"],                      "faculty":False},
    {"ja":"臼杵 乃理子", "en":"Usuki Noriko",        "keys":["臼杵乃理子","usukinoriko"],                         "faculty":False},
    {"ja":"梅木 寿人",   "en":"Umeki Kazuhito",      "keys":["梅木寿人","umekikazuhito"],                         "faculty":False},
    {"ja":"大坪 敦",     "en":"Otsubo Atsushi",      "keys":["大坪敦","otsuboatsushi"],                           "faculty":False},
    {"ja":"大坪 治喜",   "en":"Otsubo Haruki",       "keys":["大坪治喜","otsuboharuki"],                          "faculty":False},
    {"ja":"太田 敏澄",   "en":"Ohta Toshizumi",      "keys":["太田敏澄","ohtatoshizumi"],                         "faculty":False},
    {"ja":"岡崎 裕介",   "en":"Okazaki Yusuke",      "keys":["岡崎裕介","okazakiyusuke","okazaki"],               "faculty":False},
    {"ja":"小川 祐樹",   "en":"Ogawa Yuki",          "keys":["小川祐樹","ogawayuki"],                             "faculty":False},
    {"ja":"音田 恭宏",   "en":"Otoda Yasuhiro",      "keys":["音田恭宏","otodayasuhiro"],                         "faculty":False},
    {"ja":"片山 隆一郎", "en":"Katayama Ryuichiro",  "keys":["片山隆一郎","katayamaryuichiro"],                   "faculty":False},
    {"ja":"金谷 勇輝",   "en":"Kanaya Yuki",         "keys":["金谷勇輝","kanayayuki"],                            "faculty":False},
    {"ja":"金平 卓也",   "en":"Kanehira Takuya",     "keys":["金平卓也","kanehiratakuya","kanehira"],             "faculty":False},
    {"ja":"河村 一輝",   "en":"Kawamura Kazuki",     "keys":["河村一輝","kawamurakazuki"],                        "faculty":False},
    {"ja":"北田 夕子",   "en":"Kitada Yuko",         "keys":["北田夕子","kitadayuko"],                            "faculty":False},
    {"ja":"久保田 僚介", "en":"Kubota Ryosuke",      "keys":["久保田僚介","kubotaryosuke"],                       "faculty":False},
    {"ja":"小池 大地",   "en":"Koike Daichi",        "keys":["小池大地","koikedaichi"],                           "faculty":False},
    {"ja":"佐久田 誠",   "en":"Sakuta Makoto",       "keys":["佐久田誠","sakutamakoto"],                          "faculty":False},
    {"ja":"斯波 康祐",   "en":"Shiba Kosuke",        "keys":["斯波康祐","斯波康裕","shibakosuke","kosukeshiba","shiba"],"faculty":True},
    {"ja":"島津 明人",   "en":"Shimazu Akihito",     "keys":["島津明人","shimazuakihito"],                        "faculty":False},
    {"ja":"末松 慎司",   "en":"Suematsu Shinji",     "keys":["末松慎司","suematsushinji"],                        "faculty":False},
    {"ja":"曽根田 悠介", "en":"Soneda Yusuke",       "keys":["曽根田悠介","sonedayusuke"],                        "faculty":False},
    {"ja":"高石 智",     "en":"Takaishi Satoshi",    "keys":["高石智","takaishisatoshi"],                         "faculty":False},
    {"ja":"高野 茂",     "en":"Takano Shigeru",      "keys":["高野茂","takanoshigeru"],                           "faculty":True},
    {"ja":"高橋 雄太",   "en":"Takahashi Yuta",      "keys":["高橋雄太","takahashiyuta","takahashi"],             "faculty":False},
    {"ja":"滝 健太",     "en":"Taki Kenta",          "keys":["滝健太","takikenta","taki"],                        "faculty":False},
    {"ja":"竹森 敬祐",   "en":"Takemori Keisuke",    "keys":["竹森敬祐","takemorikeisuke"],                       "faculty":True},
    {"ja":"辰野 健太郎", "en":"Tatsuno Kentaro",     "keys":["辰野健太郎","tatsunokentaro"],                      "faculty":False},
    {"ja":"鳥越 庸平",   "en":"Torigoe Yohei",       "keys":["鳥越庸平","torigoeyohei"],                          "faculty":False},
    {"ja":"徳橋 和将",   "en":"Tokuhashi Kazumasa",  "keys":["徳橋和将","tokuhashikazumasa"],                     "faculty":False},
    {"ja":"中川 愛梨",   "en":"Nakagawa Eri",        "keys":["中川愛梨","nakagawaeri","nakagawaairi"],            "faculty":False},
    {"ja":"中島 千尋",   "en":"Nakajima Chihiro",    "keys":["中島千尋","nakajimachihiro"],                       "faculty":False},
    {"ja":"服部 祐一",   "en":"Hattori Yuichi",      "keys":["服部祐一","hattoriyuichi"],                         "faculty":False},
    {"ja":"原嶋 春輝",   "en":"Harashima Haruki",    "keys":["原嶋春輝","harashimaharuki"],                       "faculty":False},
    {"ja":"原田 直弥",   "en":"Harada Naoya",        "keys":["原田直弥","haradanaoya"],                           "faculty":False},
    {"ja":"日高 真人",   "en":"Hidaka Masato",       "keys":["日高真人","hidakamasato"],                          "faculty":False},
    {"ja":"平部 裕子",   "en":"Hirabe Yuko",         "keys":["平部裕子","hirabeyuko","hirabe"],                   "faculty":False},
    {"ja":"藤井 敬人",   "en":"Fujii Takahito",      "keys":["藤井敬人","fujiitakahito"],                         "faculty":False},
    {"ja":"藤澤 和輝",   "en":"Fujisawa Kazuki",     "keys":["藤澤和輝","fujisawakazuki","fujisawa"],             "faculty":False},
    {"ja":"藤原 晶",     "en":"Fujiwara Akira",      "keys":["藤原晶","fujiwaraakira"],                           "faculty":False},
    {"ja":"前中 省吾",   "en":"Maenaka Shogo",       "keys":["前中省吾","maenakashogo"],                          "faculty":False},
    {"ja":"松井 智一",   "en":"Matsui Tomokazu",     "keys":["松井智一","matsuitomokazu"],                        "faculty":False},
    {"ja":"松尾 周汰",   "en":"Matsuo Shuta",        "keys":["松尾周汰","matsuoshuta"],                           "faculty":False},
    {"ja":"松本 誠義",   "en":"Matsumoto Seigi",     "keys":["松本誠義","matsumotoseigi"],                        "faculty":False},
    {"ja":"三崎 慎也",   "en":"Misaki Shinya",       "keys":["三崎慎也","misakishinya"],                          "faculty":False},
    {"ja":"守谷 一希",   "en":"Moriya Kazuki",       "keys":["守谷一希","moriyakazuki"],                          "faculty":False},
    {"ja":"吉江 智秀",   "en":"Yoshie Tomohide",     "keys":["吉江智秀","yoshietomohide"],                        "faculty":False},
    {"ja":"米田 純",     "en":"Komeda Jun",          "keys":["米田純","komedajun"],                               "faculty":False},
    {"ja":"渡邉 洸",     "en":"Watanabe Ko",         "keys":["渡邉洸","watanabeko"],                              "faculty":False},
    {"ja":"渡邊 晃",     "en":"Watanabe Akifumi",    "keys":["渡邊晃","渡邉晃","watanabeakifumi","watanabeakira"], "faculty":True},
    # 2026-07-24 追加分③（ja=14 最終）
    {"ja":"瀧澤 亮佑",   "en":"Takizawa Ryosuke",    "keys":["瀧澤亮佑","takizawaryosuke"],                        "faculty":False},
    {"ja":"大木 英司",   "en":"Oki Eiji",            "keys":["大木英司","okieiji"],                                "faculty":False},
    {"ja":"中尾 一心",   "en":"Nakao Isshin",        "keys":["中尾一心","nakaoisshin"],                            "faculty":False},
    {"ja":"瀧口 諒久",   "en":"Takiguchi Akihisa",   "keys":["瀧口諒久","takiguchiakihisa"],                       "faculty":False},
    {"ja":"長谷川 高志", "en":"Hasegawa Takashi",    "keys":["長谷川高志","hasegawatakashi"],                      "faculty":False},
    {"ja":"堀 磨伊也",   "en":"Hori Maiya",          "keys":["堀磨伊也","horimaiya"],                              "faculty":False},
    {"ja":"谷中 健介",   "en":"Taninaka Kensuke",    "keys":["谷中健介","taninakakensuke"],                        "faculty":False},
    {"ja":"野田 厚志",   "en":"Noda Atsushi",        "keys":["野田厚志","nodaatsushi"],                            "faculty":False},
    {"ja":"北口 貴史",   "en":"Kitaguchi Takashi",   "keys":["北口貴史","kitaguchitakashi"],                       "faculty":False},
    {"ja":"羽田野 武蔵", "en":"Hadano Musashi",      "keys":["羽田野武蔵","hadanomusashi"],                        "faculty":False},
    {"ja":"石岡 匠也",   "en":"Ishioka Takuya",      "keys":["石岡匠也","ishiokatakuya"],                          "faculty":False},
    {"ja":"岩波 慶一朗", "en":"Iwanami Keiichiro",   "keys":["岩波慶一朗","iwanamikeiichiro"],                     "faculty":False},
    {"ja":"斉藤 直矢",   "en":"Saito Naoya",         "keys":["斉藤直矢","saitonaoya"],                             "faculty":False},
    {"ja":"佐野 あかね", "en":"Sano Akane",          "keys":["佐野あかね","sanoakane"],                            "faculty":False},
    # 2026-07-24 追加分②
    {"ja":"安藤 崇央",   "en":"Ando Takahiro",       "keys":["安藤崇央","andotakahiro"],                           "faculty":False},
    {"ja":"谷 優里",     "en":"Tani Yuri",           "keys":["谷優里","taniyuri"],                                 "faculty":False},
    {"ja":"有田 充",     "en":"Arita Mitsuru",       "keys":["有田充","aritamitsuru"],                             "faculty":False},
    {"ja":"田中 裕大",   "en":"Tanaka Yuta",         "keys":["田中裕大","tanakayuta"],                             "faculty":False},
    {"ja":"津村 直樹",   "en":"Tsumura Naoki",       "keys":["津村直樹","tsumuranaoki"],                           "faculty":False},
    {"ja":"小花 光広",   "en":"Kohana Mitsuhiro",    "keys":["小花光広","kohanamitsuhiro"],                        "faculty":False},
    {"ja":"上西 基弘",   "en":"Uenishi Motohiro",    "keys":["上西基弘","uenishimotohiro"],                        "faculty":False},
    {"ja":"田中 宏和",   "en":"Tanaka Hirokazu",     "keys":["田中宏和","tanakahirokazu"],                         "faculty":False},
    {"ja":"林 健太",     "en":"Hayashi Kenta",       "keys":["林健太","hayashikenta"],                             "faculty":False},
    {"ja":"園田 侑輝",   "en":"Sonoda Yuki",         "keys":["園田侑輝","sonodayuki"],                             "faculty":False},
    {"ja":"駒井 清顕",   "en":"Komai Kiyoaki",       "keys":["駒井清顕","komaikiyoaki"],                           "faculty":False},
    {"ja":"秦 恭史",     "en":"Hata Kyoji",          "keys":["秦恭史","hatakyoji"],                                "faculty":False},
    {"ja":"繁住 健哉",   "en":"Shigezumi Takeya",    "keys":["繁住健哉","shigezumitakeya"],                        "faculty":False},
    {"ja":"小宮 邦裕",   "en":"Komiya Kunihiro",     "keys":["小宮邦裕","komiyakunihiro"],                         "faculty":False},
    {"ja":"小西 健太",   "en":"Konishi Kenta",       "keys":["小西健太","konishikenta"],                           "faculty":False},
    {"ja":"上山 芳隆",   "en":"Ueyama Yoshitaka",    "keys":["上山芳隆","ueyamayoshitaka"],                        "faculty":False},
    {"ja":"中野 達彦",   "en":"Nakano Tatsuhiko",    "keys":["中野達彦","nakanotatsuhiko"],                        "faculty":False},
    {"ja":"久米 由花",   "en":"Kume Yuka",           "keys":["久米由花","kumeyuka","yukakume"],                    "faculty":False},
    {"ja":"寺澤 緑",     "en":"Terasawa Midori",     "keys":["寺澤緑","terasawamidori"],                           "faculty":False},
    {"ja":"菊田 洸",     "en":"Kikuta Kou",          "keys":["菊田洸","kikutakou"],                                "faculty":False},
    {"ja":"菅田 唯仁",   "en":"Sugata Yuito",        "keys":["菅田唯仁","sugatayuito"],                            "faculty":False},
    {"ja":"光来出 優大", "en":"Mitsukude Yudai",     "keys":["光来出優大","mitsukudeyudai"],                       "faculty":False},
    {"ja":"本間 潤一郎", "en":"Honma Junichiro",     "keys":["本間潤一郎","honmajunichiro"],                       "faculty":False},
    {"ja":"西村 勇亮",   "en":"Nishimura Yusuke",    "keys":["西村勇亮","nishimurayusuke"],                        "faculty":False},
    {"ja":"磯村 昇太",   "en":"Isomura Shota",       "keys":["磯村昇太","isomurashota"],                           "faculty":False},
    {"ja":"有吉 正行",   "en":"Ariyoshi Masayuki",   "keys":["有吉正行","ariyoshimasayuki","masayukiariyoshi"],    "faculty":True},
    {"ja":"矢野 一人",   "en":"Yano Kazuto",         "keys":["矢野一人","yanokazuto"],                             "faculty":True},
    {"ja":"塚本 悟司",   "en":"Tsukamoto Satoshi",   "keys":["塚本悟司","tsukamotosatoshi"],                       "faculty":True},
    {"ja":"畑山 満則",   "en":"Hatayama Michinori",  "keys":["畑山満則","hatayamamichinori"],                      "faculty":False},
    {"ja":"大平 祐大",   "en":"Ohira Yuta",          "keys":["大平祐大","ohirayuta"],                              "faculty":False},
    # 2026-07-24 追加分
    {"ja":"山口 弘純",   "en":"Yamaguchi Hirozumi",  "keys":["山口弘純","yamaguchihirozumi"],                      "faculty":False},
    {"ja":"本松 大夢",   "en":"Motomatsu Hiromu",    "keys":["本松大夢","motomatsuhiromu"],                        "faculty":False},
    {"ja":"西田 昌弘",   "en":"Nishida Masahiro",    "keys":["西田昌弘","nishidamasahiro"],                        "faculty":False},
    {"ja":"堀 祐貴",     "en":"Hori Yuki",           "keys":["堀祐貴","horiyuki"],                                 "faculty":False},
    {"ja":"内野 雅人",   "en":"Uchino Masato",       "keys":["内野雅人","uchinomasato"],                           "faculty":False},
    {"ja":"木原 拓",     "en":"Kihara Taku",         "keys":["木原拓","kiharataku"],                               "faculty":False},
    {"ja":"大園 咲奈",   "en":"Ozono Sana",          "keys":["大園咲奈","ozonosana"],                              "faculty":False},
    {"ja":"久住 憲嗣",   "en":"Hisazumi Kenji",      "keys":["久住憲嗣","hisazumikenji"],                          "faculty":False},
    {"ja":"福田 修之",   "en":"Fukuda Shuichi",      "keys":["福田修之","fukudashuichi"],                          "faculty":False},
    {"ja":"谷口 倫一郎", "en":"Taniguchi Rinichiro", "keys":["谷口倫一郎","taniguchirinichiro"],                   "faculty":False},
    {"ja":"藤本 隆晟",   "en":"Fujimoto Ryusei",     "keys":["藤本隆晟","fujimotoryusei"],                         "faculty":False},
    {"ja":"梅津 吉雅",   "en":"Umetsu Yoshimasa",    "keys":["梅津吉雅","梅津雅吉","umetsuyoshimasa","umetsuyoshinori"],"faculty":False},
    {"ja":"和田 遥香",   "en":"Wada Haruka",         "keys":["和田遥香","wadaharuka"],                             "faculty":False},
    {"ja":"佐々木 渉",   "en":"Sasaki Wataru",       "keys":["佐々木渉","sasakiwataru"],                           "faculty":False},
    {"ja":"高田 将志",   "en":"Takata Masashi",      "keys":["高田将志","takatamasashi"],                          "faculty":False},
    {"ja":"辻 智博",     "en":"Tsuji Tomohiro",      "keys":["辻智博","tsujitomohiro"],                            "faculty":False},
    {"ja":"落合 桂一",   "en":"Ochiai Keiichi",      "keys":["落合桂一","ochiaikeiichi"],                          "faculty":False},
    {"ja":"大滝 亨",     "en":"Otaki Toru",          "keys":["大滝亨","otakitoru"],                                "faculty":False},
    {"ja":"山田 曉",     "en":"Yamada Akira",        "keys":["山田曉","山田暁","yamadaakira"],                     "faculty":False},
    {"ja":"白井 拓也",   "en":"Shirai Takuya",       "keys":["白井拓也","shiraitakuya"],                           "faculty":True},
    {"ja":"金子 邦彦",   "en":"Kaneko Kunihiko",     "keys":["金子邦彦","kanekokunihiko"],                         "faculty":False},
    # 外国人研究者 — 表記揺れ統合
    {"ja":"Trono Edgar Marko","en":"Trono Edgar Marko","keys":["tronoedgarmarko","tronomarko","markotronoedgar"],"faculty":False},
    {"ja":"Akpa Akpro Elder Hippocrate","en":"Akpa Akpro Elder Hippocrate",
     "keys":["akpaelder","hippocrateakpaakproelder","akpaakproelderhippocrate","ahelderakpa"],"faculty":False},
    # 2026-07-24 追加分③
    {"ja":"Huang Jianyu",    "en":"Huang Jianyu",     "keys":["huangjianyu"],                                   "faculty":True,"faculty_from":2024},
    {"ja":"Dawton Billy",    "en":"Billy Dawton",     "keys":["billydawton","dawtonbilly"],                     "faculty":True,"faculty_from":2023},
    # 2001年初期メンバー（英語表記＋日本語表記の統合）
    {"ja":"秋山 裕司",       "en":"Akiyama Yuji",     "keys":["秋山裕司","akiyamayuji","akiyamayuuji"],         "faculty":False},
    {"ja":"坂本 憲司",       "en":"Sakamoto Kenji",   "keys":["坂本憲司","sakamotokenji"],                      "faculty":False},
    {"ja":"西野 嘉之",       "en":"Nishino Yoshiyuki","keys":["西野嘉之","nishinoyoshiyuki"],                    "faculty":False},
    {"ja":"磯原 隆将",       "en":"Isohara Takamasa", "keys":["磯原隆将","isoharatakamasa"],                    "faculty":False},
    {"ja":"鳥海 不二夫",     "en":"Torikai Fujio",    "keys":["鳥海不二夫"],                                    "faculty":True},
    {"ja":"野林 大起",       "en":"Nobayashi Daiki",  "keys":["野林大起","nobayashidaiki"],                     "faculty":True},
    {"ja":"塚本 和也",       "en":"Tsukamoto Kazuya", "keys":["塚本和也","tsukamotokazuya"],                    "faculty":True},
    {"ja":"船越 将一",       "en":"Funakoshi Shoichi","keys":["船越将一","funakoshishoichi"],                    "faculty":True},
    {"ja":"池永 全志",       "en":"Ikenaga Masashi",  "keys":["池永全志","ikenagamasashi"],                     "faculty":True},
    {"ja":"荒川 美保",       "en":"Arakawa Miho",     "keys":["荒川美保","arakawamisho","arakawamilpo"],         "faculty":True},
]

KEY_TO_IDX = {}
for i, p in enumerate(PERSONS):
    for k in p["keys"]:
        KEY_TO_IDX[k] = i
    KEY_TO_IDX[normkey(p["ja"])] = i
    KEY_TO_IDX[normkey(p["en"])] = i

def person_idx(name):
    return KEY_TO_IDX.get(normkey(name), None)

def is_faculty_for_year(pid, year):
    p = PERSONS[pid]
    if not p.get("faculty", False): return False
    ffy = p.get("faculty_from")
    if ffy and year < ffy: return False
    return True

# ─── Deduplication ───
# Collect presentation + conferencePaper per year, then mark duplicates
by_year_types = defaultdict(lambda: {"presentation": [], "conferencePaper": []})
for item in items:
    d = item.get("data", {})
    it = d.get("itemType","")
    if it not in ("presentation","conferencePaper"): continue
    if d.get("itemType") == "attachment": continue
    year = extract_year(item)
    if not year: continue
    nt = ntitle(d.get("title",""))
    by_year_types[year][it].append((item["key"], d.get("title",""), nt))

dup_keys = set()
for year, typs in by_year_types.items():
    conf_nt_set = {nt for _, _, nt in typs["conferencePaper"]}
    for pkey, pt, pnt in typs["presentation"]:
        matched = pnt in conf_nt_set
        if not matched and len(pnt) >= 15:
            for _, _, cnt in typs["conferencePaper"]:
                ml = min(len(pnt), len(cnt))
                if ml >= 15 and pnt[:ml] == cnt[:ml]:
                    matched = True; break
        if matched:
            dup_keys.add(pkey)

print(f"Duplicates removed: {len(dup_keys)}")

TOPIC_KEYWORDS = {
    "ネットワーク":        ["routing","802.11","通信プロトコル","obs","バースト生成","qos","tcp","パケット"],
    "モバイル/ユビキタス": ["モバイル","ユビキタス","mobile","ubiquitous","pervasive","ubicomp"],
    "センサ・IoT":        ["センサ","iot","sensor","wearable","ウェアラブル","ble","accelerometer","加速度"],
    "活動認識":            ["行動認識","活動認識","activity recognition","行動推定","行動検知","gesture"],
    "ヘルスケア":          ["健康","ヘルス","health","医療","sleep","睡眠","生体","physiolog","心拍","バイタル"],
    "省エネ・電力":        ["省エネ","節電","energy saving","電力消費","power saving","消費電力"],
    "スマートシティ":      ["スマートシティ","smart city","まちづくり","にぎわい","nigiwai","crowd"],
    "推薦・行動変容":      ["推薦","行動変容","recommendation","nudge","persuasion","レコメンド"],
    "労働・生産性":        ["労働","生産性","productivity","workplace","知的生産","職場環境"],
    "機械学習・AI":        ["機械学習","deep learning","neural","lstm","transformer","学習モデル","識別器"],
    "防災・緊急":          ["防災","disaster","emergency","避難","緊急"],
    "位置情報":            ["位置推定","gps","localization","indoor","屋内測位","geofence"],
    "コミュニケーション":  ["コミュニケーション","slack","孤立","チャット","online communication","テレワーク"],
    "環境センシング":      ["環境","音響","照度","温度","co2","騒音","ambient"],
}

NTT_TITLES = ["utuplespace","ubi-tree","広域ユビキタス","名前解決"]
NTT_AUTH = {"南裕也","斎藤洋","井手一郎","中村隆幸"}
def is_ntt(item):
    d = item.get("data", {})
    title = norm(d.get("title","")).lower()
    for t in NTT_TITLES:
        if t in title: return True
    for c in d.get("creators",[]):
        if norm(c.get("lastName","")) in NTT_AUTH: return True
    return False

def score_title(title, kws):
    t = title.lower()
    return sum(1 for kw in kws if kw.lower() in t)

# ─── Accumulate ───
year_by_col   = defaultdict(lambda: defaultdict(int))
year_titles   = defaultdict(list)
year_person   = defaultdict(lambda: defaultdict(lambda: {"ja":0,"en":0,"canonical":None,"_dja":"","_den":""}))

total_kept = 0
papers_out = []
for item in items:
    d = item.get("data", {})
    if d.get("itemType") == "attachment": continue
    if item["key"] in dup_keys: continue
    if is_ntt(item): continue
    year = extract_year(item)
    if not year or year < 1998 or year > 2026: continue
    col = get_collection(item["key"])
    year_by_col[year][col] += 1
    total_kept += 1

    raw_title = d.get("title","")
    clean_t = clean_title(raw_title)
    year_titles[year].append(clean_t)
    lang = "ja" if is_ja_title(raw_title) else "en"

    for c in d.get("creators",[]):
        ln = norm(c.get("lastName",""))
        fn = norm(c.get("firstName",""))
        full = (ln + " " + fn).strip() if fn else ln
        if not full: full = norm(c.get("name",""))
        if not full or is_arakawa(full): continue
        # Skip bare initials like "Y.", "K.", single-char names
        if re.match(r'^[A-Za-z]\.?$', full) or len(full) <= 1: continue

        pid = person_idx(full)
        if pid is not None:
            key = pid
        else:
            key = normkey(full)

        bucket = year_person[year][key]
        bucket[lang] += 1
        bucket["canonical"] = pid
        if pid is not None:
            bucket["_dja"] = PERSONS[pid]["ja"]
            bucket["_den"] = PERSONS[pid]["en"]
        else:
            if not bucket["_dja"]: bucket["_dja"] = full
            if not bucket["_den"]: bucket["_den"] = full

    # ── 論文レベルデータ収集 ────────────────────────────────────
    paper_authors = []
    paper_authors_en = []   # 引用スタイル用のローマ字表記（「姓 名」順。無ければ空文字）
    first_surname = ""      # BibTeX の引用キー用（筆頭著者のローマ字姓）
    for c in d.get("creators", []):
        ln = norm(c.get("lastName",""))
        fn = norm(c.get("firstName",""))
        full = (ln + " " + fn).strip() if fn else ln
        if not full: full = norm(c.get("name",""))
        if not full: continue
        if re.match(r'^[A-Za-z]\.?$', full) or len(full) <= 1: continue
        is_first = not paper_authors
        # 著者名は Zotero の表記をそのまま出す。
        # 和文業績は日本人が漢字・外国人がローマ字、英文業績は全員ローマ字で
        # 登録されているので、変換すると業績の言語と表記がずれる。
        # PERSONS 辞書は ae（引用スタイル用のローマ字）と集計にのみ使う。
        if is_arakawa(full):
            paper_authors.append(en_first_last(full))
            paper_authors_en.append("Arakawa Yutaka")
            if is_first: first_surname = "Arakawa"
            continue
        pid2 = person_idx(full)
        if pid2 is not None:
            en = PERSONS[pid2]["en"]
        else:
            en = "" if has_cjk(full) else full
        if is_first and en:
            first_surname = en.split()[0]
        paper_authors.append(en_first_last(full))
        paper_authors_en.append(en)
        if len(paper_authors) >= 20: break
    # 全員が日本語表記のままなら ae は持たせない（データ量削減）
    if not any(paper_authors_en):
        paper_authors_en = []

    paper_topics = [t for t, kws in TOPIC_KEYWORDS.items() if score_title(clean_t, kws) > 0]

    # BibTeX/Markdown エクスポート用の書誌情報（存在するものだけ入れる）
    rec = {
        "k": item["key"],
        "t": clean_t,
        "a": paper_authors,
        "y": year,
        "c": col,
        "tp": paper_topics,
    }
    venue = (norm(d.get("publicationTitle","")) or norm(d.get("proceedingsTitle",""))
             or norm(d.get("bookTitle","")) or norm(d.get("conferenceName","")))
    extra = {
        "it": d.get("itemType",""),
        "v":  venue,
        "doi": norm(d.get("DOI","")),
        "u":  norm(d.get("url","")),
        "pg": norm(d.get("pages","")),
        "vl": norm(d.get("volume","")),
        "is": norm(d.get("issue","")),
        "pb": norm(d.get("publisher","")),
        "ra": first_surname,
    }
    if paper_authors_en:
        rec["ae"] = paper_authors_en
    for kk, vv in extra.items():
        if vv: rec[kk] = vv
    papers_out.append(rec)

# タイトルベース重複排除（同一タイトルが複数カテゴリに登録されている場合）
seen_titles = set()
deduped_papers = []
for p in papers_out:
    tk = normkey(p["t"])
    if tk not in seen_titles:
        seen_titles.add(tk)
        deduped_papers.append(p)
papers_out = deduped_papers
print(f"Total items kept: {total_kept} (after title dedup: {len(papers_out)})")

def display_name(b):
    dja = b["_dja"]
    if has_cjk(dja): return dja
    return en_first_last(dja if b["ja"] >= b["en"] else b["_den"])

def total_count(b):
    return b["ja"] + b["en"]

FACULTY_IDS = set(i for i,p in enumerate(PERSONS) if p.get("faculty"))

year_top_coauthors = {}
year_top_students  = {}
year_top_keywords  = {}

for year in sorted(year_person.keys()):
    buckets = year_person[year]
    all_sorted = sorted(buckets.items(), key=lambda kv: -total_count(kv[1]))

    year_top_coauthors[year] = [
        (display_name(b), total_count(b))
        for _, b in all_sorted[:5]
    ]

    students = []
    for k, b in all_sorted:
        pid = b["canonical"]
        if pid is not None:
            if is_faculty_for_year(pid, year): continue
        else:
            # Unknown: check name against faculty patterns
            name = b["_dja"] or b["_den"]
            if any(re.search(fp.lower(), name.lower()) for fp in [
                "笹瀬","山中","安本","福田","田頭","諏訪","石田","岡本","玉井","藤本",
                "水本","中西","崔","福嶋","峯","nakamura.*yugo","matsuda.*yuki"
            ]): continue
        students.append((display_name(b), total_count(b)))
    year_top_students[year] = students[:5]

for year, titles in sorted(year_titles.items()):
    topic_scores = Counter()
    for t in titles:
        for topic, kws in TOPIC_KEYWORDS.items():
            topic_scores[topic] += score_title(t, kws)
    top = [(t,c) for t,c in topic_scores.most_common(10) if c > 0][:5]
    year_top_keywords[year] = top

all_years = sorted(year_by_col.keys())
result = {
    "years":             all_years,
    "col_order":         COL_ORDER,
    "total":             total_kept,
    "year_by_col":       {str(y): {c: year_by_col[y].get(c,0) for c in COL_ORDER} for y in all_years},
    "year_top_coauthors":{str(y): v for y,v in year_top_coauthors.items()},
    "year_top_students": {str(y): v for y,v in year_top_students.items()},
    "year_top_keywords": {str(y): v for y,v in year_top_keywords.items()},
    "papers":            papers_out,
}
json.dump(result, open("viz_final5.json","w"), ensure_ascii=False, indent=2)
print("DONE → viz_final5.json")

# Spot-check
for y in [2016, 2017, 2018, 2020, 2024]:
    print(f"\n{y}:")
    print(f"  coauthors: {year_top_coauthors.get(y,[])}")
    print(f"  students:  {year_top_students.get(y,[])}")
    print(f"  keywords:  {year_top_keywords.get(y,[])}")
