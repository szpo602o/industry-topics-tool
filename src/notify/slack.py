"""
Slack Webhook でレポート完了を通知する。

環境変数:
  SLACK_WEBHOOK_URL        必須: Incoming Webhook の URL
  PUBLIC_URL               任意: 公開サイトのベースURL（末尾スラッシュなし推奨）
                             当日ページは {PUBLIC_URL}/{YYYY-MM-DD}/ を組み立てる
  SLACK_NOTIFY_TEXT_FIELD  任意: 各行の表示に使うフィールド（title または summary、既定: title）
"""

import os
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent.parent
OUTPUT_DIR = ROOT / "output"

# Slack 1行あたりの目安（全角含め文字数）
_DEFAULT_MAX_LINE_CHARS = 56


def _truncate_line(text: str, max_chars: int = _DEFAULT_MAX_LINE_CHARS) -> str:
    """長いタイトル・要約を1行向けに短縮する。"""
    t = text.strip()
    if len(t) <= max_chars:
        return t
    return t[: max_chars - 1] + "…"


def _notify_text_field() -> str:
    """title または summary。不正値は title にフォールバック。"""
    raw = os.environ.get("SLACK_NOTIFY_TEXT_FIELD", "title").strip().lower()
    return raw if raw in ("title", "summary") else "title"


def slack_line_for_article(article: dict, field: str | None = None) -> str:
    """
    1記事分の通知用1行テキストを返す。
    field が summary のとき空なら title にフォールバックする。
    """
    f = field or _notify_text_field()
    if f == "summary":
        s = (article.get("summary") or "").strip()
        if not s:
            s = (article.get("title") or "").strip()
    else:
        s = (article.get("title") or "").strip()
    return _truncate_line(s)


def build_daily_public_url(date_label: str) -> str:
    """
    当日固定版の公開URL（末尾スラッシュ付き）を返す。
    PUBLIC_URL 未設定時はローカルの日付フォルダ index.html のパス（POSIX表記）。
    """
    base = os.environ.get("PUBLIC_URL", "").strip().rstrip("/")
    if base:
        return f"{base}/{date_label}/"
    local = OUTPUT_DIR / date_label / "index.html"
    return local.as_posix()


def build_slack_message(structured: dict, date_label: str) -> str:
    """
    Slack 本文（プレーンテキスト）を組み立てる。

    1行目: 本日の医療福祉業界トピックス（YYYY-MM-DD）
    2〜4行目: 各記事（最大3件）の短い1行
    最終行: 当日のURL
    """
    field = _notify_text_field()
    articles = structured.get("articles", [])[:3]

    lines: list[str] = [f"本日の医療福祉業界トピックス（{date_label}）"]
    for a in articles:
        lines.append(slack_line_for_article(a, field))
    lines.append(build_daily_public_url(date_label))
    return "\n".join(lines)


def notify(structured: dict, date_label: str) -> None:
    """
    Slack に通知を送る。本文は build_slack_message と同じ形式。

    Args:
        structured: structured JSON 相当の dict（articles を含む）
        date_label: 日付（YYYY-MM-DD）。当日固定版URLのパスに使う。

    Raises:
        RuntimeError: SLACK_WEBHOOK_URL 未設定 or Slack API エラー時
    """
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL")
    if not webhook_url:
        raise RuntimeError(
            "SLACK_WEBHOOK_URL が設定されていません。"
            " .env に SLACK_WEBHOOK_URL=https://hooks.slack.com/... を追加してください。"
        )

    message = build_slack_message(structured, date_label)

    print("[slack] Slack に通知中...")

    try:
        resp = requests.post(
            webhook_url,
            json={"text": message},
            timeout=10,
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        raise RuntimeError(f"[slack] Slack への通知に失敗しました: {e}") from e

    print("[slack] ✓ 通知完了")
