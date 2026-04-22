"""
structured JSON を読み込み Slack に投稿する（Surge デプロイ成功後用）。

使い方:
  python src/notify/post_slack.py
  python src/notify/post_slack.py --date 20260422

環境変数:
  SLACK_WEBHOOK_URL, PUBLIC_URL（CI では必須）
"""

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

load_dotenv(ROOT / ".env")

from src.notify.slack import notify  # noqa: E402


def date_label_from_yyyymmdd(date_str: str) -> str:
    return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"


def main() -> None:
    parser = argparse.ArgumentParser(description="structured JSON から Slack 通知のみ行う")
    parser.add_argument(
        "--date",
        type=str,
        default=date.today().strftime("%Y%m%d"),
        help="YYYYMMDD（デフォルト: 今日・ランナーのローカル日付）",
    )
    args = parser.parse_args()
    date_str = args.date

    if os.environ.get("GITHUB_ACTIONS") == "true" and not os.environ.get("PUBLIC_URL", "").strip():
        print("ERROR: GitHub Actions 上では PUBLIC_URL が必須です。", file=sys.stderr)
        sys.exit(1)

    path = ROOT / "data" / f"structured_{date_str}.json"
    if not path.exists():
        print(f"ERROR: structured JSON が見つかりません: {path}", file=sys.stderr)
        sys.exit(1)

    structured = json.loads(path.read_text(encoding="utf-8"))
    date_label = date_label_from_yyyymmdd(date_str)

    if not os.environ.get("SLACK_WEBHOOK_URL"):
        print("ERROR: SLACK_WEBHOOK_URL が未設定です。", file=sys.stderr)
        sys.exit(1)

    try:
        notify(structured, date_label)
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
