"""
raw_articles_YYYYMMDD.json を読み込み、各記事を1回のAI呼び出しで構造化し
structured_YYYYMMDD.json として保存する。

使い方:
  python src/ai/analyzer.py               # 今日付のrawファイルを処理
  python src/ai/analyzer.py --date 20260411  # 日付指定
"""

import argparse
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

import anthropic
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT / "data"

# .env から ANTHROPIC_API_KEY を読み込む
load_dotenv(ROOT / ".env")

# トークン節約のため軽量モデルを使用
MODEL = "claude-haiku-4-5"
MAX_TOKENS = 700  # 各記事1回あたりの上限（JSON出力に十分な量）

# AI に渡す本文の最大文字数（raw取得時に800字で切っているが念のため再確認）
BODY_MAX_CHARS = 700

SYSTEM_PROMPT = """\
あなたは医療政策の専門記者です。
与えられた記事のタイトルと本文をもとに、以下のJSONを生成してください。
他のテキストは一切出力せず、JSONのみ返してください。

出力スキーマ:
{
  "summary": "記事の要約（2〜3文、100字以内）",
  "points": ["要点1", "要点2", "要点3"],
  "tags": ["タグ1", "タグ2", "タグ3"],
  "business_impacts_our_company": ["当社への影響1", "当社への影響2", "当社への影響3"],
  "business_impacts_customer": ["顧客（医療・福祉機関）への影響1", "影響2", "影響3"]
}

タグのルール:
- 最大3個
- 専門用語・固有名詞・テーマ語のみ（例：診療報酬改定、認知症治療病棟、処遇改善加算）
- 一般語は禁止（記事・影響・対応・取り組み・強化・制度・医療 など）
- 3文字以上のみ
- 他の記事と重複しないよう記事固有のキーワードを選ぶ
"""


def analyze_article(client: anthropic.Anthropic, article: dict) -> dict:
    """
    1記事を1回のAI呼び出しで構造化する。

    Args:
        client: Anthropic クライアント
        article: raw JSON の1記事（title, url, body を持つ dict）

    Returns:
        structured dict（title と url を保持し、AI出力フィールドを追加）
    """
    title = article.get("title", "")
    body = article.get("body", "")[:BODY_MAX_CHARS]

    user_message = f"【タイトル】\n{title}\n\n【本文】\n{body}"

    print(f"[analyzer] AI呼び出し中: {title[:40]}...")

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
    except anthropic.APIError as e:
        print(f"[analyzer] ERROR: API呼び出し失敗: {e}")
        return _fallback_result(article)

    raw_text = response.content[0].text.strip()

    # JSONブロック（```json ... ```）が含まれる場合は中身だけ取り出す
    json_match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", raw_text)
    if json_match:
        raw_text = json_match.group(1)

    try:
        ai_data = json.loads(raw_text)
    except json.JSONDecodeError as e:
        print(f"[analyzer] ERROR: JSONパース失敗: {e}")
        print(f"[analyzer] 生レスポンス: {raw_text[:200]}")
        return _fallback_result(article)

    # 必要なキーが揃っているか確認し、不足はデフォルト値で補完
    result = {
        "title": title,
        "url": article.get("url", ""),
        "published_at": article.get("published_at", ""),
        "summary": ai_data.get("summary", ""),
        "points": ai_data.get("points", [])[:3],
        "tags": ai_data.get("tags", [])[:3],
        "business_impacts_our_company": ai_data.get("business_impacts_our_company", [])[:3],
        "business_impacts_customer": ai_data.get("business_impacts_customer", [])[:3],
    }

    print(f"[analyzer]   tags: {result['tags']}")
    return result


def _fallback_result(article: dict) -> dict:
    """AI呼び出し失敗時のフォールバック。空値で構造だけ揃える。"""
    return {
        "title": article.get("title", ""),
        "url": article.get("url", ""),
        "published_at": article.get("published_at", ""),
        "summary": "",
        "points": [],
        "tags": [],
        "business_impacts_our_company": [],
        "business_impacts_customer": [],
    }


def run(date_str: str) -> Path:
    """
    指定日付の raw JSON を読み込み、structured JSON を生成して返す。

    Args:
        date_str: "YYYYMMDD" 形式の文字列

    Returns:
        保存した structured JSON のパス
    """
    raw_path = DATA_DIR / f"raw_articles_{date_str}.json"
    if not raw_path.exists():
        raise FileNotFoundError(f"raw JSON が見つかりません: {raw_path}")

    raw_data = json.loads(raw_path.read_text(encoding="utf-8"))
    articles_raw = raw_data.get("articles", [])

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY が設定されていません。"
            " .env ファイルに ANTHROPIC_API_KEY=sk-ant-... を追加してください。"
        )

    client = anthropic.Anthropic(api_key=api_key)

    structured_articles = []
    for i, article in enumerate(articles_raw, 1):
        print(f"\n[analyzer] --- 記事 {i}/{len(articles_raw)} ---")
        result = analyze_article(client, article)
        structured_articles.append(result)

    output = {
        "date": raw_data.get("fetched_at", date_str),
        "articles": structured_articles,
    }

    out_path = DATA_DIR / f"structured_{date_str}.json"
    out_path.write_text(
        json.dumps(output, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print(f"\n[analyzer] ✓ structured JSON を保存しました: {out_path}")
    return out_path


def main():
    parser = argparse.ArgumentParser(description="記事をAIで構造化する")
    parser.add_argument(
        "--date",
        type=str,
        default=date.today().strftime("%Y%m%d"),
        help="処理対象の日付（YYYYMMDD形式、デフォルト: 今日）",
    )
    args = parser.parse_args()

    try:
        run(args.date)
    except (FileNotFoundError, RuntimeError) as e:
        print(f"ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
