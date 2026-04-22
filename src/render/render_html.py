"""
structured JSON（またはダミーデータ）を Jinja2 テンプレートに差し込み、
site/{YYYY-MM-DD}/index.html を生成する。

使い方:
  python src/render/render_html.py              # ダミーデータで確認
  python src/render/render_html.py --data <path>  # 指定JSONファイルを使用
"""

import argparse
import html
import json
import re
import sys
from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

ROOT = Path(__file__).resolve().parent.parent.parent
TEMPLATE_DIR = ROOT / "src" / "render"
SITE_DIR = ROOT / "site"
TEMPLATE_FILE = "template.html"

_DATE_DIR_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")

DUMMY_DATA = {
    "date": date.today().isoformat(),
    "articles": [
        {
            "title": "身体的拘束最小化に向けた加算新設と減算強化",
            "url": "https://gemmed.ghc-j.com/2026/02/18/example-1/",
            "published_at": "2026-02-18",
            "points": ["新加算は拘束削減に取り組む病院が対象", "未達時は減算のリスクが高まる"],
            "implication": "算定・届出支援の問い合わせ増が見込まれる",
            "tags": ["診療報酬改定", "身体的拘束", "医療安全"],
            "slack_title": "拘束最小化と加算・減算",
            "slack_note": "体制確認を早めに",
        },
        {
            "title": "ベースアップ評価料の拡充と医療従事者の賃上げ",
            "url": "https://gemmed.ghc-j.com/2026/04/07/example-2/",
            "published_at": "2026-04-07",
            "points": ["ベースアップ評価料が拡充され賃上げを後押し", "施設基準届出が算定の前提になりやすい"],
            "implication": "届出・算定スケジュールの確認需要が増える",
            "tags": ["ベースアップ評価料", "賃上げ", "施設基準"],
            "slack_title": "ベア評価料の拡充",
            "slack_note": "届出タイミングに注意",
        },
        {
            "title": "在宅支援診療所・病院に求められる往診体制の詳細",
            "url": "https://gemmed.ghc-j.com/2026/04/08/example-3/",
            "published_at": "2026-04-08",
            "points": ["往診体制の疑義解釈が具体化", "訪問看護・遠隔診療の算定要件が整理"],
            "implication": "在宅体制の見直し相談が増える可能性",
            "tags": ["在宅医療", "訪問看護", "遠隔診療"],
            "slack_title": "在支の往診体制",
            "slack_note": "連携フローを点検",
        },
    ],
}


def _article_display_fields(a: dict) -> dict:
    """テンプレ用: 要点2・示唆・タグ3・後方互換。"""
    out = dict(a)
    raw_points = a.get("points")
    if isinstance(raw_points, list) and raw_points:
        display_points = [str(p).strip() for p in raw_points if str(p).strip()][:2]
    else:
        display_points = []
    if len(display_points) < 2:
        legacy = a.get("summary", "")
        if isinstance(legacy, str) and legacy.strip():
            display_points.append(legacy.strip()[:80])
        while len(display_points) < 2:
            display_points.append("—")

    implication = (a.get("implication") or "").strip()
    if not implication and a.get("summary"):
        implication = str(a["summary"]).strip()[:120]

    tags = a.get("tags")
    if isinstance(tags, list):
        display_tags = [str(t).strip() for t in tags if str(t).strip()][:3]
    else:
        display_tags = []
    while len(display_tags) < 3:
        display_tags.append("—")

    out["display_points"] = display_points[:2]
    out["implication"] = implication
    out["display_tags"] = display_tags[:3]
    return out


def normalize(data: dict) -> dict:
    date_str = data.get("date", data.get("generated_at", ""))
    articles_in = data.get("articles", [])
    articles = [_article_display_fields(a) for a in articles_in]

    return {
        "generated_at": date_str,
        "page_title": data.get("headline") or f"{date_str} 医療福祉業界トピックス",
        "articles": articles,
    }


def build_html(data: dict) -> str:
    normalized = normalize(data)

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=True,
    )
    template = env.get_template(TEMPLATE_FILE)
    return template.render(**normalized)


def write_html_to_path(html: str, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    print(f"[render_html] HTML を生成しました: {output_path}")


def render(data: dict, output_path: Path) -> None:
    write_html_to_path(build_html(data), output_path)


def list_report_date_dirs(site_dir: Path) -> list[str]:
    """site 直下の YYYY-MM-DD 形式ディレクトリ名を降順で返す。"""
    if not site_dir.is_dir():
        return []
    names: list[str] = []
    for p in site_dir.iterdir():
        if p.is_dir() and _DATE_DIR_PATTERN.match(p.name):
            names.append(p.name)
    return sorted(names, reverse=True)


def write_site_index(site_dir: Path) -> Path:
    """
    site/index.html を「最新リンク＋過去一覧」の最小構成で生成する。
    """
    site_dir.mkdir(parents=True, exist_ok=True)
    dates = list_report_date_dirs(site_dir)
    if not dates:
        latest_html = (
            "<!DOCTYPE html><html lang='ja'><head><meta charset='utf-8'>"
            "<title>業界トピックス</title></head><body>"
            "<p>レポートがまだありません。</p></body></html>"
        )
        out = site_dir / "index.html"
        out.write_text(latest_html, encoding="utf-8")
        print(f"[render_html] トップページを生成しました: {out}")
        return out

    latest = dates[0]
    past = dates[1:]

    def esc(s: str) -> str:
        return html.escape(s, quote=True)

    lines = [
        "<!DOCTYPE html>",
        '<html lang="ja">',
        "<head>",
        '<meta charset="UTF-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">',
        "<title>業界トピックス一覧</title>",
        '<script src="https://cdn.tailwindcss.com"></script>',
        "</head>",
        '<body class="bg-slate-50 min-h-screen py-8 px-4">',
        '<div class="max-w-xl mx-auto bg-white rounded-xl border border-slate-200 shadow-sm p-6 space-y-6">',
        '<h1 class="text-lg font-bold text-slate-800">業界トピックス</h1>',
        '<div>',
        '<p class="text-xs font-semibold text-slate-500 mb-2">最新レポート</p>',
        f'<p class="text-sm"><a href="/{esc(latest)}/" class="text-blue-600 hover:underline font-medium">'
        f"{esc(latest)}</a></p>",
        "</div>",
        '<div>',
        '<p class="text-xs font-semibold text-slate-500 mb-2">過去一覧</p>',
        '<ul class="list-disc list-inside text-sm text-slate-700 space-y-1">',
    ]
    for d in past:
        lines.append(
            f'<li><a href="/{esc(d)}/" class="text-blue-600 hover:underline">{esc(d)}</a></li>'
        )
    if not past:
        lines.append('<li class="text-slate-400 text-sm">（他日付はまだありません）</li>')
    lines.extend(
        [
            "</ul>",
            "</div>",
            "</div>",
            "</body>",
            "</html>",
        ]
    )
    out = site_dir / "index.html"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"[render_html] トップページを生成しました: {out}")
    return out


def main():
    parser = argparse.ArgumentParser(description="HTMLダッシュボードを生成する")
    parser.add_argument(
        "--data",
        type=str,
        default=None,
        help="structured JSON ファイルのパス（省略時はダミーデータを使用）",
    )
    parser.add_argument(
        "--out",
        type=str,
        default=None,
        help="出力HTMLのパス（省略時: site/{今日のYYYY-MM-DD}/index.html）",
    )
    args = parser.parse_args()

    if args.data:
        data_path = Path(args.data)
        if not data_path.exists():
            print(f"ERROR: 指定されたJSONファイルが見つかりません: {data_path}")
            sys.exit(1)
        data = json.loads(data_path.read_text(encoding="utf-8"))
        print(f"[render_html] JSONファイルを読み込みました: {data_path}")
    else:
        data = DUMMY_DATA
        print("[render_html] ダミーデータを使用します")

    if args.out:
        output_path = Path(args.out)
    else:
        day = data.get("date", date.today().isoformat())
        output_path = SITE_DIR / day / "index.html"

    render(data, output_path)
    write_site_index(SITE_DIR)


if __name__ == "__main__":
    main()
