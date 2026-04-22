"""
Slack Webhook でレポート完了を通知する。

環境変数:
  SLACK_WEBHOOK_URL  必須（通知する場合）: Incoming Webhook の URL
  PUBLIC_URL         本番・CIでは必須推奨: ベースURL（末尾スラッシュなし）
                       ローカルでは未設定時は通知をスキップ（警告のみ）
"""

from __future__ import annotations

import os
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent.parent
SITE_DIR = ROOT / "site"

# 記事あたり: slack_title + slack_note の合計文字数目安・上限（全角=1）
SLACK_CHAR_SOFT = 60
SLACK_CHAR_HARD = 80


def _truncate_run(text: str, max_chars: int) -> str:
    t = text.strip()
    if len(t) <= max_chars:
        return t
    if max_chars <= 1:
        return "…"
    return t[: max_chars - 1] + "…"


def _fit_slack_pair(title: str, note: str) -> tuple[str, str]:
    """
    原則60字以内、最大80字まで。タイトル優先で短くし、足りなければ注釈を削る。
    カウント: title + note（「→」は行に含めず、note 側のみ本文）。
    """
    t = title.strip()
    n = note.strip()
    # プレフィックス「1. 」「   → 」は build_slack_message 側。ここでは本文長のみ調整。
    for _ in range(20):
        combined = len(t) + len(n)
        if combined <= SLACK_CHAR_SOFT:
            return t, n
        if combined <= SLACK_CHAR_HARD:
            return t, n
        if len(n) > 0:
            n = _truncate_run(n, len(n) - 1)
        elif len(t) > 0:
            t = _truncate_run(t, len(t) - 1)
        else:
            break
    return _truncate_run(t, 40), _truncate_run(n, 35)


def build_daily_public_url(date_label: str) -> str:
    base = os.environ.get("PUBLIC_URL", "").strip().rstrip("/")
    if base:
        return f"{base}/{date_label}/"
    local = SITE_DIR / date_label / "index.html"
    return local.as_posix()


def _slack_lines_for_article(article: dict, index: int) -> tuple[str, str]:
    st = (article.get("slack_title") or "").strip()
    sn = (article.get("slack_note") or "").strip()
    if not st and not sn:
        st = (article.get("title") or "").strip()
        pts = article.get("points")
        if isinstance(pts, list) and pts:
            sn = str(pts[0]).strip()
        elif article.get("summary"):
            sn = str(article.get("summary", "")).strip()
    st, sn = _fit_slack_pair(st, sn)
    line1 = f"{index}. {st}" if st else f"{index}. （無題）"
    line2 = f"   → {sn}" if sn else ""
    return line1, line2


def build_slack_message(structured: dict, date_label: str) -> str:
    articles = structured.get("articles", [])[:3]

    lines: list[str] = [f"本日の医療福祉業界トピックス（{date_label}）"]
    for i, a in enumerate(articles, 1):
        l1, l2 = _slack_lines_for_article(a, i)
        lines.append(l1)
        if l2.strip():
            lines.append(l2)
    lines.append(build_daily_public_url(date_label))
    return "\n".join(lines)


def should_skip_slack_for_missing_public_url() -> bool:
    """ローカル等: PUBLIC_URL が無ければ通知しない。"""
    return not os.environ.get("PUBLIC_URL", "").strip()


def notify(structured: dict, date_label: str) -> None:
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL")
    if not webhook_url:
        raise RuntimeError(
            "SLACK_WEBHOOK_URL が設定されていません。"
            " .env に SLACK_WEBHOOK_URL=https://hooks.slack.com/... を追加してください。"
        )

    if should_skip_slack_for_missing_public_url():
        print(
            "[slack] PUBLIC_URL が未設定のため通知をスキップします（本番・CI では PUBLIC_URL を設定してください）"
        )
        return

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
