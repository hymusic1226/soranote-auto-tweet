"""
台本工房ソラノテ - X自動投稿スクリプト

使用方法:
  python post_tweet.py morning                   # 朝の投稿（AI生成）
  python post_tweet.py evening                   # 夜の投稿（AI生成）
  python post_tweet.py morning --dry-run         # 投稿せず生成内容のみ表示
  python post_tweet.py custom --text "..."       # 指定テキストをそのまま投稿
  python post_tweet.py custom --file path.txt    # ファイルから読み込んで投稿
  python post_tweet.py custom --text "..." --dry-run  # 確認だけ

投稿スケジュール:
  水曜朝・土曜夜 → announce_*.txt ローテ（BOOTH商品訴求）
  その他         → AI生成Tips（VTuber/ASMR/宅録向け）
"""
import os
import sys
import random
import tweepy
from google import genai as google_genai
from dotenv import load_dotenv
from datetime import datetime

load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

X_API_KEY             = os.environ.get("X_API_KEY", "")
X_API_SECRET          = os.environ.get("X_API_SECRET", "")
X_ACCESS_TOKEN        = os.environ.get("X_ACCESS_TOKEN", "")
X_ACCESS_TOKEN_SECRET = os.environ.get("X_ACCESS_TOKEN_SECRET", "")
GEMINI_API_KEY        = os.environ.get("GEMINI_API_KEY", "")

ACCOUNT_URL = "https://note.com/soranote_works"
BOOTH_URL   = "https://progress-sheet.booth.pm/"

WEEKDAYS_JP = ["月", "火", "水", "木", "金", "土", "日"]
today   = datetime.now()
weekday = WEEKDAYS_JP[today.weekday()]
date_str = today.strftime(f"%-m月%-d日（{weekday}）")

# ── announce ファイルローテ（4日サイクル）──
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ANNOUNCE_FILES = [
    os.path.join(SCRIPT_DIR, "announce_pin.txt"),
    os.path.join(SCRIPT_DIR, "announce_1_serif.txt"),
    os.path.join(SCRIPT_DIR, "announce_2_mistakes.txt"),
    os.path.join(SCRIPT_DIR, "announce_3_fieldstory.txt"),
]

def load_announce() -> str:
    """day_of_year % 4 で announce ファイルをローテ選択"""
    idx = today.timetuple().tm_yday % len(ANNOUNCE_FILES)
    path = ANNOUNCE_FILES[idx]
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return f.read().strip()
    return ""

# ── 曜日別テーマ ──
MORNING_THEMES = [
    "ASMR台本の書き出し・冒頭セリフ設計",       # 月
    "キャラのセリフ設計・感情表現",               # 火
    "BOOTH導線（水曜・announce）",                # 水（※使用されない）
    "配信ネタ切れ対策・ASMR企画の作り方",         # 木
    "宅録・マイク収録のASMR向けTips",             # 金
    "週末活動の振り返り・来週の台本準備",          # 土
    "個人活動のモチベ維持・継続のコツ",            # 日
]

EVENING_THEMES = [
    "ASMR収録後の疲れ・次に活かすワンポイント",   # 月
    "台本準備の時短術・テンプレ活用",              # 火
    "配信企画ブラッシュアップ・差別化",            # 水
    "ストーリー構成・起承転結のASMR応用",          # 木
    "活動整理・やりたいことリスト",                # 金
    "BOOTH導線（土曜夜・announce）",               # 土（※使用されない）
    "月曜に向けた小さな目標設定",                  # 日
]

# ── 投稿パターン ──
PATTERNS = {
    "counter_intuitive": """【型：反常識型】
1行目：多くの人がやってる行動を指摘し「〜してる人、実は損してます」で止める
空行1つ
2〜3行：なぜダメか、代わりに何をすべきかを具体的に
締め：制作進行経験に基づく一言（ASMR・台本・宅録に絡める）

例：
個人VTuberのASMR配信、
冒頭でBGMを流し始める人、実は損してます。

最初の5秒は無音の方が「え、始まった？」と視聴者が止まる。
BGMは15秒後から-20dBでフェードイン。""",

    "field_story": """【型：現場話型】
1行目：「制作進行でASMR/声優/配信現場を見てきたけど、」のような一次情報の導入
2〜3行：具体的に見てきた事実・パターン（ASMR台本・宅録に関すること）
締め：個人VTuber・宅録声優への応用ヒント

固有名詞（番組タイプ・役割・機材名）を混ぜて現場感を出す。""",

    "specific_line": """【型：セリフ例示型】
必ずASMR・配信・台本に関するセリフを「」付きで2つ以上入れる（NGとOKの対比）。
説明は最小限、セリフそのもので語らせる。

例：
「今日もよろしくお願いします」
より
「今日は耳かき、10分くらいで眠らせます」
の方が視聴者は止まる。

冒頭の一言で視聴継続率が変わる。""",

    "number_fact": """【型：数字ファクト型】
数字を最低2つ入れる（秒数・dB・文字数・割合など。ASMR・宅録に関する数字だと説得力が増す）。
数字→理由→アクションの順で構成。

例：ASMR配信の冒頭30秒で離脱する人は、8割が声量が大きすぎる配信者から逃げてる。""",

    "mistake_list": """【型：失敗列挙型】
「〜でNGな3つ」形式。ASMR・台本・宅録に特化した内容にする。
各項目1行、改行で区切り、理由は書かない（読者に考えさせる）。

例：
ASMR台本で詰む3大ミス

・冒頭の声量指定がない
・BGMのdB数を書いていない
・息継ぎのタイミングが「てきとうに」

全部直すと収録時間が半分になる。""",

    "asmr_hook": """【型：ASMR特化フック型】
ASMR配信・宅録声優が「わかる！」となる超具体的な場面を1つ切り取る。
台本のセリフサンプル or 収録中に起きる具体的な問題を1つ入れる。
締めは「こういう台本/コツ、需要ある？」「明日試せる」などの引きで終わる。

例：
寝かしつけASMRの台本、
「10……9……」の数え方で視聴者の眠気が変わる。

「10……9……ゆっくり、息を吐いて……8……」
これだけで平均視聴時間が伸びる。""",
}

# ── ハッシュタグプール ──
HASHTAG_POOLS = {
    "default":          ["#個人Vtuber", "#宅録声優"],
    "asmr_hook":        ["#ASMR", "#個人Vtuber"],
    "booth":            ["#個人Vtuber", "#宅録声優"],
    "broad":            ["#VTuber", "#個人Vtuber"],
    "asmr_broad":       ["#ASMR配信", "#個人Vtuber"],
}


def build_tips_prompt(theme: str, time_of_day: str) -> tuple[str, str]:
    """Tips投稿プロンプトを生成（パターンランダム選択）"""
    pattern_key = random.choice(list(PATTERNS.keys()))
    pattern_guide = PATTERNS[pattern_key]

    tod_rules = ""
    if time_of_day == "evening":
        tod_rules = "- 夜の投稿なので、振り返りや「明日試せる具体ネタ」寄りのトーンに"

    return (pattern_key, f"""あなたは制作進行の経験を持つ「台本工房ソラノテ」の中の人。
個人VTuber・宅録声優・ASMR配信者向けにX投稿を作ります。

テーマ：「{theme}」
日付：{date_str}

{pattern_guide}

【セリフを入れるときの質・絶対守る】
- ✅ 裏切り・自虐・メタ・数字入り具体・ASMR特有の表現
  例:「BGMは-20dBから始めます」「息継ぎをマイクに入れるタイミング、台本に書いてない」
- ❌ ポエム・クリシェ・情熱系で締める感動セリフ
  例:「一緒に素敵な時間を」「心に火をつけたい」「〜したいんです！」

【絶対ルール】
- 「おはようございます」「おつかれさまでした」等の挨拶は禁止（bot扱いされる）
- 「〜しましょう」「〜意識しよう」「〜大切です」等の抽象励まし禁止
- 絵文字は最大1つ、0でも可
- ハッシュタグは絶対に書かない（コード側で自動付与する）
- 全角130文字以内（URLは別カウント）。130文字を超えたら必ず削る。
- **や__などのMarkdown記法は絶対に使わない
- 〇〇・△△・XXなどのプレースホルダーを使わず、必ず具体的な内容で書く
- 必ず指示された型に従う
- 具体例・数字・実セリフのいずれかを最低1つ含む
{tod_rules}

【出力】
ツイート本文のみ。前置き・説明・URL・補足解説は一切不要。""")


def sanitize(text: str, pattern_key: str = "") -> str:
    """Markdown除去・ハッシュタグ剥がし・文字数トリム・タグ強制付与"""
    import re
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'__(.+?)__', r'\1', text)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    text = re.sub(r'#\S+', '', text)
    text = re.sub(r'[ \t]+\n', '\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text).strip()

    lines = text.split('\n')
    body_lines, url_lines = [], []
    for line in lines:
        if line.strip().startswith('http'):
            url_lines.append(line.strip())
        else:
            body_lines.append(line)
    body = '\n'.join(body_lines).strip()

    if len(body) > 130:
        body = body[:127] + '…'

    # ハッシュタグ選択
    if pattern_key == "asmr_hook":
        tags = HASHTAG_POOLS["asmr_hook"]
    elif pattern_key in HASHTAG_POOLS:
        tags = HASHTAG_POOLS[pattern_key]
    elif random.random() < 0.2:
        tags = HASHTAG_POOLS["asmr_broad"]  # 20%でASMR広めタグ
    elif random.random() < 0.3:
        tags = HASHTAG_POOLS["broad"]
    else:
        tags = HASHTAG_POOLS["default"]

    tag_line = " ".join(tags)
    parts = [body] + url_lines + [tag_line]
    return "\n\n".join(parts)


def generate_text(prompt: str, pattern_key: str = "") -> str:
    client = google_genai.Client(api_key=GEMINI_API_KEY)
    resp = client.models.generate_content(
        model="gemini-2.5-flash-lite",
        contents=prompt
    )
    return sanitize(resp.text.strip(), pattern_key)


def generate_morning_post() -> tuple[str, str, str]:
    # 水曜朝 → announce ローテ
    if today.weekday() == 2:
        text = load_announce()
        if text:
            return text, "", "announce"
        # fallback: AI生成
    theme = MORNING_THEMES[today.weekday()]
    pattern_key, prompt = build_tips_prompt(theme, "morning")
    text = generate_text(prompt, pattern_key)
    url = ACCOUNT_URL if random.random() < 0.5 else ""
    return text, url, pattern_key


def generate_evening_post() -> tuple[str, str, str]:
    # 土曜夜 → announce ローテ
    if today.weekday() == 5:
        text = load_announce()
        if text:
            return text, "", "announce"
        # fallback: AI生成
    theme = EVENING_THEMES[today.weekday()]
    pattern_key, prompt = build_tips_prompt(theme, "evening")
    text = generate_text(prompt, pattern_key)
    url = ACCOUNT_URL if random.random() < 0.5 else ""
    return text, url, pattern_key


def post_tweet(text: str) -> None:
    client = tweepy.Client(
        consumer_key=X_API_KEY,
        consumer_secret=X_API_SECRET,
        access_token=X_ACCESS_TOKEN,
        access_token_secret=X_ACCESS_TOKEN_SECRET
    )
    response = client.create_tweet(text=text)
    print(f"✅ 投稿成功: tweet_id={response.data['id']}")


def main():
    post_type = sys.argv[1] if len(sys.argv) > 1 else "morning"
    dry_run = "--dry-run" in sys.argv

    # custom モード
    if post_type == "custom":
        custom_text = ""
        if "--text" in sys.argv:
            idx = sys.argv.index("--text")
            if idx + 1 < len(sys.argv):
                custom_text = sys.argv[idx + 1]
        elif "--file" in sys.argv:
            idx = sys.argv.index("--file")
            if idx + 1 < len(sys.argv):
                with open(sys.argv[idx + 1], encoding="utf-8") as f:
                    custom_text = f.read().strip()
        if not custom_text:
            print("❌ --text \"内容\" または --file path を指定してください")
            sys.exit(1)
        if not dry_run and not all([X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET]):
            print("❌ X API 環境変数が不足しています")
            sys.exit(1)
        print(f"──────────────────────────────")
        print(f"📅 {date_str} / custom / 文字数: {len(custom_text)}")
        print(f"──────────────────────────────")
        print(custom_text)
        print(f"──────────────────────────────")
        if dry_run:
            print("🧪 dry-run モード：投稿はスキップしました")
            return
        post_tweet(custom_text)
        return

    required_keys = [GEMINI_API_KEY]
    if not dry_run:
        required_keys += [X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET]
    if not all(required_keys):
        print("❌ 環境変数が不足しています")
        sys.exit(1)

    if post_type == "morning":
        text, url, pattern = generate_morning_post()
    elif post_type == "evening":
        text, url, pattern = generate_evening_post()
    else:
        print(f"❌ 不明な投稿タイプ: {post_type} (morning / evening / custom を指定)")
        sys.exit(1)

    final_text = f"{text}\n{url}" if url else text

    print(f"──────────────────────────────")
    print(f"📅 {date_str} / {post_type} / 型: {pattern}")
    print(f"🔗 URL: {url if url else '(なし)'}")
    print(f"📝 文字数: {len(text)}（URL除く）")
    print(f"──────────────────────────────")
    print(final_text)
    print(f"──────────────────────────────")

    if dry_run:
        print("🧪 dry-run モード：投稿はスキップしました")
        return

    post_tweet(final_text)


if __name__ == "__main__":
    main()
