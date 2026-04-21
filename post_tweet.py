"""
台本工房ソラノテ - X自動投稿スクリプト
朝・夜の台本/脚本関連コンテンツをGemini AIで生成してXに投稿する

使用方法:
  python post_tweet.py morning            # 朝の投稿
  python post_tweet.py evening            # 夜の投稿
  python post_tweet.py morning --dry-run  # 投稿せず生成内容のみ表示
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
BOOTH_URL   = "https://soranote.booth.pm/"

WEEKDAYS_JP = ["月", "火", "水", "木", "金", "土", "日"]
today   = datetime.now()
weekday = WEEKDAYS_JP[today.weekday()]
date_str = today.strftime(f"%-m月%-d日（{weekday}）")

MORNING_THEMES = [
    "台本の書き出し・導入",
    "キャラのセリフ設計・感情表現",
    "BOOTH導線（水曜）",
    "配信ネタ・企画の作り方",
    "宅録・収録Tips",
    "週末の振り返り・翌週準備",
    "個人活動のモチベ維持",
]

EVENING_THEMES = [
    "セリフ演技・発声",
    "台本準備の時短術",
    "配信企画のブラッシュアップ",
    "ストーリー構成・起承転結",
    "活動整理・やりたいことリスト",
    "週末の充電・次の一歩",
    "月曜に向けた小さな目標",
]

# ── 投稿パターン（AI臭を消すための型） ──
PATTERNS = {
    "counter_intuitive": """【型：反常識型】
1行目：多くの人がやってる行動を指摘し「〜してる人、実は損してます」で止める
空行1つ
2〜3行：なぜダメか、代わりに何をすべきかを具体的に
締め：制作進行経験に基づく一言

例：
個人VTuberの初配信、
「初めまして！」から入ってる人、損してます。

視聴者は自己紹介に興味がない。
「この配信で何が起きるか」に興味がある。

冒頭1文を"予告"に変えるだけで離脱率が変わる。""",

    "field_story": """【型：現場話型】
1行目：「制作進行で〇〇現場を見てきたけど、」のような一次情報の導入
2〜3行：具体的に見てきた事実・パターン
締め：個人活動者への応用ヒント

固有名詞（番組タイプ・役割）を混ぜて現場感を出す。""",

    "specific_line": """【型：セリフ例示型】
必ずセリフを「」付きで2つ以上入れる（NGとOKの対比）。
説明は最小限、セリフそのもので語らせる。

例：
「今日もよろしくお願いします」
より
「昨日の配信、実は1回撮り直してます」
の方が残る。

視聴者が手を止めるのは"情報"じゃなく"気配"。""",

    "number_fact": """【型：数字ファクト型】
数字を最低2つ入れる（年数・割合・秒数など）。
数字→理由→アクションの順で構成。

例：配信冒頭30秒で離脱される人は、9割が自己紹介から入ってる。""",

    "mistake_list": """【型：失敗列挙型】
「〜でNGな3つ」形式。
各項目1行、改行で区切り、理由は書かない（読者に考えさせる）。

例：
配信台本で詰む3大ミス

・結論が最後に来る
・「えー」を台本に書く
・尺の指定がない

全部直すと収録時間が半分になる。""",
}


def build_tips_prompt(theme: str, time_of_day: str) -> str:
    """AI臭のないTips投稿プロンプトを生成（パターンランダム選択）"""
    pattern_key = random.choice(list(PATTERNS.keys()))
    pattern_guide = PATTERNS[pattern_key]
    include_url = random.random() < 0.5

    tod_rules = ""
    if time_of_day == "evening":
        tod_rules = "- 夜の投稿なので、振り返りや「明日試せる具体ネタ」寄りのトーンに"

    url_note = "最後にURLを1行で入れる（記事導線のため）" if include_url else "URLは一切入れない（拡散狙い）"

    return (pattern_key, f"""あなたは制作進行の経験を持つ「台本工房ソラノテ」の中の人。
個人VTuber・宅録声優向けにX投稿を作ります。

テーマ：「{theme}」
日付：{date_str}

{pattern_guide}

【絶対ルール】
- 「おはようございます」「おつかれさまでした」等の挨拶は禁止（bot扱いされる）
- 「〜しましょう」「〜意識しよう」「〜大切です」等の抽象励まし禁止
- 絵文字は最大1つ、0でも可
- ハッシュタグは末尾に最大2個（#個人Vtuber #宅録声優 から選ぶ）
- 全角130文字以内（URLは別カウント）
- 必ず指示された型に従う
- 具体例・数字・実セリフのいずれかを最低1つ含む
{tod_rules}

【出力】
ツイート本文のみ。前置き・説明・URL・補足解説は一切不要。""")


def build_booth_prompt() -> str:
    """水曜BOOTH導線プロンプト（告知型ではなくコンテンツ型）"""
    return f"""あなたは「台本工房ソラノテ」の中の人。
水曜朝、BOOTHの商品へ誘導する投稿を書きます。

【重要】告知型にしないこと。
以下の型で書く：

1〜2行目：実際に使える具体的な台本のセリフや構成のサンプルを1つ提示
空行
3〜4行目：「こういうのが15個入ってる商品、BOOTHで500円です」のような控えめな紹介
締めなし

例：
個人VTuber初配信の第一声、
これだけで離脱率が変わる：

「この30分で、私のこと嫌いになってもらえたら勝ちです」

こういう"ひっかけ型"の冒頭台本を15本、
BOOTHで500円で置いてます。

【絶対ルール】
- 「おはようございます」等の挨拶禁止
- 絵文字は最大1つ
- ハッシュタグは末尾に #個人Vtuber #宅録声優 のみ
- 全角130文字以内
- サンプルのセリフまたは構成は必ず実在しそうな具体的なものにする

ツイート本文のみ出力。URL不要。"""


def generate_text(prompt: str) -> str:
    client = google_genai.Client(api_key=GEMINI_API_KEY)
    resp = client.models.generate_content(
        model="gemini-2.5-flash-lite",
        contents=prompt
    )
    return resp.text.strip()


def generate_morning_post() -> tuple[str, str]:
    if today.weekday() == 2:
        text = generate_text(build_booth_prompt())
        return text, BOOTH_URL, "booth"

    theme = MORNING_THEMES[today.weekday()]
    pattern_key, prompt = build_tips_prompt(theme, "morning")
    text = generate_text(prompt)
    url = ACCOUNT_URL if random.random() < 0.5 else ""
    return text, url, pattern_key


def generate_evening_post() -> tuple[str, str]:
    theme = EVENING_THEMES[today.weekday()]
    pattern_key, prompt = build_tips_prompt(theme, "evening")
    text = generate_text(prompt)
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
        print(f"❌ 不明な投稿タイプ: {post_type} (morning / evening を指定)")
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
