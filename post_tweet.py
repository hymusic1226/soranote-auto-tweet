"""
台本工房ソラノテ - X自動投稿スクリプト
朝・夜の台本/脚本関連コンテンツをGemini AIで生成してXに投稿する

使用方法:
  python post_tweet.py morning   # 朝の投稿
  python post_tweet.py evening   # 夜の投稿
"""
import os
import sys
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

WEEKDAYS_JP = ["月", "火", "水", "木", "金", "土", "日"]
today = datetime.now()
weekday = WEEKDAYS_JP[today.weekday()]
date_str = today.strftime(f"%-m月%-d日（{weekday}）")


def generate_morning_post() -> str:
    """朝のVTuber・宅録声優向けTipsツイートを生成する"""
    client = google_genai.Client(api_key=GEMINI_API_KEY)
    prompt = f"""あなたは「台本工房ソラノテ」のSNS担当です。
今日（{date_str}）の朝、個人VTuberや宅録声優に向けた実践的なTipsをXに投稿するツイートを作成してください。

必ず以下の形式・改行で出力してください（空行も含めて厳守）：

おはようございます！[朝の絵文字]
[今日のテーマを表すキャッチコピー1行][絵文字]

[VTuber・宅録声優が「わかる…！」と感じる台本・配信・収録に関するTipsや気づきを2〜3行に分けて、各行を短く]

[締めの一言（今日の配信・収録への意欲を高める言葉）]

#個人Vtuber #宅録声優 #ボイス台本

条件：
- 個人VTuber・宅録声優が日々感じる悩み（台本が書けない・セリフが浮かばない・配信ネタ切れ）に刺さる内容
- 「台本を自分で用意している人」の共感を引き出す視点
- 本文合計130文字以内
- 絵文字は朝らしいもの（☀️🎙️✨📝など）を2〜3個
- 宣伝色を出さず、まず共感・有益情報を優先する

ツイート本文のみ出力してください（URLは含めない、前置き・説明不要）。"""
    resp = client.models.generate_content(
        model="gemini-2.5-flash-lite",
        contents=prompt
    )
    text = resp.text.strip()
    return f"{text}\n{ACCOUNT_URL}"


def generate_evening_post() -> str:
    """夜のVTuber・宅録声優向け振り返りツイートを生成する"""
    client = google_genai.Client(api_key=GEMINI_API_KEY)
    prompt = f"""あなたは「台本工房ソラノテ」のSNS担当です。
今日（{date_str}）の夜、個人VTuberや宅録声優に向けた夜の振り返り・明日の活動への意欲を高めるツイートを作成してください。

必ず以下の形式・改行で出力してください（空行も含めて厳守）：

おつかれさまでした[夜の絵文字]
[今夜のテーマを表すキャッチコピー1行][絵文字]

[VTuber・宅録声優が「今日もがんばった」と感じられる振り返りや、明日の収録・配信に向けたワンポイントアドバイスを2〜3行に分けて、各行を短く]

[明日も活動を続けることへの励ましの言葉]

#個人Vtuber #宅録声優 #ボイス台本

条件：
- 収録後の疲れ・台本準備の大変さ・配信継続の難しさなど、個人活動者のリアルな苦労に寄り添う内容
- セリフ・演技・台本・配信演出などのワンポイントアドバイスを1つ入れる
- 本文合計130文字以内
- 絵文字は夜らしいもの（🌙🎙️🌟📖など）を2〜3個
- 宣伝色を出さず、まず共感・癒やしを優先する

ツイート本文のみ出力してください（URLは含めない、前置き・説明不要）。"""
    resp = client.models.generate_content(
        model="gemini-2.5-flash-lite",
        contents=prompt
    )
    text = resp.text.strip()
    return f"{text}\n{ACCOUNT_URL}"


def post_tweet(text: str) -> None:
    """X APIでツイートを投稿する"""
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

    if not all([X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET, GEMINI_API_KEY]):
        print("❌ 環境変数が不足しています")
        sys.exit(1)

    if post_type == "morning":
        print(f"🌅 朝の投稿 - {date_str}")
        text = generate_morning_post()
    elif post_type == "evening":
        print(f"🌙 夜の投稿 - {date_str}")
        text = generate_evening_post()
    else:
        print(f"❌ 不明な投稿タイプ: {post_type} (morning / evening を指定)")
        sys.exit(1)

    print(f"生成内容:\n{text}\n文字数: {len(text)}")
    post_tweet(text)


if __name__ == "__main__":
    main()
