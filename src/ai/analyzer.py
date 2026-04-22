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

load_dotenv(ROOT / ".env")

MODEL = "claude-haiku-4-5"
MAX_TOKENS = 600

BODY_MAX_CHARS = 700

SYSTEM_PROMPT = """\
あなたは医療政策の専門記者です。
与えられた記事のタイトルと本文をもとに、次の1つのJSONオブジェクトだけを返してください。
他のテキスト・説明・マークダウンは一切出力しないでください。

【HTML表示用】
- points: 文字列の配列で、要点はちょうど2つ。各文は60文字以内。長文要約・背景説明は禁止。
- implication: 示唆を1文（「示唆：」のプレフィックスは付けない）。60文字以内。
- points と implication を合わせた文字数は150文字以内を目安にする。
- tags: キーワードをちょうど3つ。専門用語・固有名詞・テーマ語のみ（例：診療報酬改定、認知症治療病棟）。
  一般語は避ける（記事・影響・対応・取り組み・強化・制度 など）。各3文字以上。

【Slack通知用】（同じJSON内に含める）
- slack_title: 1行目用の短い見出し（「1.」は付けない）。30文字以内を目安。
- slack_note: 2行目用。先頭に「→」は付けない（アプリ側で付与）。30文字以内を目安。
- slack_title と slack_note を合わせて、原則60文字以内。どうしても必要なら合計80文字以内。

出力スキーマ（このキーだけ）:
{
  "points": ["要点1", "要点2"],
  "implication": "示唆の一文",
  "tags": ["キーワード1", "キーワード2", "キーワード3"],
  "slack_title": "Slack1行目用",
  "slack_note": "Slack2行目用"
}
"""


def analyze_article(client: anthropic.Anthropic, article: dict) -> dict:
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

    json_match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", raw_text)
    if json_match:
        raw_text = json_match.group(1)

    try:
        ai_data = json.loads(raw_text)
    except json.JSONDecodeError as e:
        print(f"[analyzer] ERROR: JSONパース失敗: {e}")
        print(f"[analyzer] 生レスポンス: {raw_text[:200]}")
        return _fallback_result(article)

    points = ai_data.get("points", [])
    if not isinstance(points, list):
        points = []
    points = [str(p).strip() for p in points if str(p).strip()][:2]

    tags = ai_data.get("tags", [])
    if not isinstance(tags, list):
        tags = []
    tags = [str(t).strip() for t in tags if str(t).strip()][:3]

    result = {
        "title": title,
        "url": article.get("url", ""),
        "published_at": article.get("published_at", ""),
        "points": points,
        "implication": str(ai_data.get("implication", "")).strip(),
        "tags": tags,
        "slack_title": str(ai_data.get("slack_title", "")).strip(),
        "slack_note": str(ai_data.get("slack_note", "")).strip(),
    }

    print(f"[analyzer]   tags: {result['tags']}")
    return result


def _fallback_result(article: dict) -> dict:
    title = article.get("title", "") or ""
    return {
        "title": title,
        "url": article.get("url", ""),
        "published_at": article.get("published_at", ""),
        "points": [],
        "implication": "",
        "tags": [],
        "slack_title": title[:40] if title else "",
        "slack_note": "",
    }


def run(date_str: str) -> Path:
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
        encoding="utf-8",
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
