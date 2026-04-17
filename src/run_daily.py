"""
GemMed 業界トピックス 日次実行スクリプト。

実行フロー:
  1. GemMedから最新3件を取得 → data/raw_articles_YYYYMMDD.json
  2. AIで構造化         → data/structured_YYYYMMDD.json
  3. HTMLを生成         → output/index.html と output/YYYY-MM-DD/index.html
  4. Slack に通知

使い方:
  python src/run_daily.py                  # 今日の日付で実行
  python src/run_daily.py --date 20260411  # 日付指定
  python src/run_daily.py --skip-fetch     # 取得済みのrawを使う
  python src/run_daily.py --skip-analyze   # 構造化済みのJSONを使う
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

# プロジェクトルートを sys.path に追加
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

load_dotenv(ROOT / ".env")

from src.fetch.list_pages import fetch_latest_urls
from src.fetch.article_pages import fetch_article
from src.ai.analyzer import run as run_analyze
from src.render.render_html import build_html, write_html_to_path
from src.notify.slack import notify

DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "output"


def date_label_from_yyyymmdd(date_str: str) -> str:
    """YYYYMMDD → YYYY-MM-DD"""
    return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"


def step_fetch(date_str: str) -> Path:
    """記事を取得して raw JSON を保存する。"""
    print("\n[run_daily] === Step 1: 記事取得 ===")

    urls = fetch_latest_urls(limit=3)

    articles = [fetch_article(url) for url in urls]

    raw_path = DATA_DIR / f"raw_articles_{date_str}.json"
    DATA_DIR.mkdir(exist_ok=True)
    raw_path.write_text(
        json.dumps(
            {"fetched_at": date_str[:4] + "-" + date_str[4:6] + "-" + date_str[6:],
             "source": "https://gemmed.ghc-j.com/",
             "articles": articles},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"[run_daily] ✓ raw JSON を保存しました: {raw_path}")
    return raw_path


def step_analyze(date_str: str) -> Path:
    """structured JSON を生成する。"""
    print("\n[run_daily] === Step 2: AI構造化 ===")
    structured_path = run_analyze(date_str)
    return structured_path


def step_render(structured_data: dict, date_str: str) -> tuple[Path, Path]:
    """
    HTML を生成する（テンプレートは1回だけ適用し、同一バイト列を2か所に書く）。
    - output/index.html … 常に最新版
    - output/YYYY-MM-DD/index.html … 当日固定版（Slack はこちらのURLを通知）
    """
    print("\n[run_daily] === Step 3: HTML生成 ===")

    html = build_html(structured_data)

    latest_path = OUTPUT_DIR / "index.html"
    date_label = date_label_from_yyyymmdd(date_str)
    dated_path = OUTPUT_DIR / date_label / "index.html"

    write_html_to_path(html, latest_path)
    write_html_to_path(html, dated_path)
    print(f"[run_daily] ✓ 最新版: {latest_path}")
    print(f"[run_daily] ✓ 当日版: {dated_path}")
    return latest_path, dated_path


def step_notify(structured: dict, date_str: str) -> None:
    """Slack に通知する（当日固定版のURLを本文最終行に含める）。"""
    print("\n[run_daily] === Step 4: Slack通知 ===")
    # SLACK_WEBHOOK_URL 未設定の場合はスキップ（エラーにしない）
    import os
    if not os.environ.get("SLACK_WEBHOOK_URL"):
        print("[run_daily] SLACK_WEBHOOK_URL 未設定のため通知をスキップします")
        return
    date_label = date_label_from_yyyymmdd(date_str)
    notify(structured, date_label)


def main():
    parser = argparse.ArgumentParser(description="GemMed 業界トピックス 日次実行")
    parser.add_argument(
        "--date",
        type=str,
        default=date.today().strftime("%Y%m%d"),
        help="処理対象の日付（YYYYMMDD形式、デフォルト: 今日）",
    )
    parser.add_argument(
        "--skip-fetch",
        action="store_true",
        help="記事取得をスキップし、既存の raw JSON を使う",
    )
    parser.add_argument(
        "--skip-analyze",
        action="store_true",
        help="AI構造化をスキップし、既存の structured JSON を使う",
    )
    args = parser.parse_args()
    date_str = args.date

    print(f"[run_daily] 実行日付: {date_str}")

    try:
        # Step 1: 取得
        if args.skip_fetch:
            raw_path = DATA_DIR / f"raw_articles_{date_str}.json"
            if not raw_path.exists():
                print(f"ERROR: --skip-fetch 指定しましたが raw JSON が見つかりません: {raw_path}")
                sys.exit(1)
            print(f"[run_daily] Step 1: スキップ（既存ファイル使用: {raw_path}）")
        else:
            step_fetch(date_str)

        # Step 2: AI構造化
        if args.skip_analyze:
            structured_path = DATA_DIR / f"structured_{date_str}.json"
            if not structured_path.exists():
                print(f"ERROR: --skip-analyze 指定しましたが structured JSON が見つかりません: {structured_path}")
                sys.exit(1)
            print(f"[run_daily] Step 2: スキップ（既存ファイル使用: {structured_path}）")
        else:
            structured_path = step_analyze(date_str)

        # Step 3: HTML生成
        structured_data = json.loads(structured_path.read_text(encoding="utf-8"))
        latest_path, dated_path = step_render(structured_data, date_str)

        # Step 4: Slack通知
        step_notify(structured_data, date_str)

    except (RuntimeError, FileNotFoundError) as e:
        print(f"\nERROR: {e}")
        sys.exit(1)

    print(f"\n[run_daily] ✓ 完了: 最新 {latest_path} / 当日 {dated_path}")


if __name__ == "__main__":
    main()
