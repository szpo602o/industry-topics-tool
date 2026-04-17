"""
structured JSON（またはダミーデータ）を Jinja2 テンプレートに差し込み、
output/index.html を生成する。

使い方:
  python src/render/render_html.py              # ダミーデータで確認
  python src/render/render_html.py --data <path>  # 指定JSONファイルを使用
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

ROOT = Path(__file__).resolve().parent.parent.parent
TEMPLATE_DIR = ROOT / "src" / "render"
OUTPUT_DIR = ROOT / "output"
TEMPLATE_FILE = "template.html"


# ダミーデータ（AI処理前の表示確認用）
# structured JSON と同じスキーマで定義する
DUMMY_DATA = {
    "date": date.today().isoformat(),
    "articles": [
        {
            "title": "身体的拘束最小化に向けた加算新設と減算強化",
            "url": "https://gemmed.ghc-j.com/2026/02/18/example-1/",
            "published_at": "2026-02-18",
            "summary": "身体的拘束を減らした病院に新加算を付与し、基準未達は減算。医療安全対策加算も大幅増点される。",
            "points": [
                "入院患者への身体的拘束を減らした病院に新加算を付与",
                "拘束基準を満たさない場合は新たな減算が適用される",
                "医療安全対策加算が大幅増点され、体制整備の動機が強まる",
            ],
            "tags": ["診療報酬改定", "身体的拘束", "医療安全"],
            "business_impacts_our_company": [
                "診療報酬改定対応コンサルの需要増加が見込まれる",
                "医療安全体制整備の支援サービスへの引き合いが増える",
                "加算算定支援ツールの提供機会が拡大する",
            ],
            "business_impacts_customer": [
                "身体的拘束管理の見直しと院内マニュアル整備が急務",
                "加算取得に向けた体制整備コストが発生する",
                "未対応の場合は減算リスクがある",
            ],
        },
        {
            "title": "ベースアップ評価料の拡充と医療従事者の賃上げ",
            "url": "https://gemmed.ghc-j.com/2026/04/07/example-2/",
            "published_at": "2026-04-07",
            "summary": "医療従事者の大幅賃上げを目的にベースアップ評価料が拡充。算定には施設基準の届出が必要。",
            "points": [
                "医療従事者の大幅賃上げを目的にベースアップ評価料を拡充",
                "算定には施設基準の届出が必要で事務負担が増加",
                "賃上げを実施しない場合は競合病院との人材獲得格差が拡大",
            ],
            "tags": ["ベースアップ評価料", "賃上げ", "人材確保"],
            "business_impacts_our_company": [
                "届出支援サービスへの引き合いが増える",
                "人材獲得競争が激化し採用コストが上昇する",
                "給与水準見直しの検討が必要になる",
            ],
            "business_impacts_customer": [
                "従業員賃上げのための原資確保と加算届出の準備が必要",
                "届出未実施の場合は人材流出リスクが高まる",
                "経営収支への影響をシミュレーションすべき",
            ],
        },
        {
            "title": "在宅支援診療所・病院に求められる往診体制の詳細",
            "url": "https://gemmed.ghc-j.com/2026/04/08/example-3/",
            "published_at": "2026-04-08",
            "summary": "在支診・在支病の往診体制要件が疑義解釈で明確化。訪問看護療養費・遠隔診療の詳細も提示。",
            "points": [
                "在支診・在支病の往診体制の要件が疑義解釈で明確化",
                "包括型訪問看護療養費の算定要件が整理された",
                "D to P with N（看護師経由の遠隔診療）の詳細が提示",
            ],
            "tags": ["在宅医療", "訪問看護", "遠隔診療"],
            "business_impacts_our_company": [
                "在宅医療体制構築の支援ニーズが高まる",
                "遠隔診療システム提供の機会が拡大する",
                "在宅訪問系サービスの連携需要が増加する",
            ],
            "business_impacts_customer": [
                "在宅支援体制の整備・届出更新を早期に検討すべき",
                "訪問看護との連携体制の見直しが必要",
                "遠隔診療導入によるコスト削減効果を試算すべき",
            ],
        },
    ],
}


def normalize(data: dict) -> dict:
    """
    structured JSON のキー名をテンプレート用に変換する。
    データの再加工・再要約は行わない。

    変換内容:
      date        → generated_at
      headline    → なければ日付文字列をそのまま使用
      conclusion  → なければ articles[0].summary をそのまま使用
      summary     → 表示しない（空文字）
    """
    articles = data.get("articles", [])
    date_str = data.get("date", data.get("generated_at", ""))
    first_summary = articles[0].get("summary", "") if articles else ""

    return {
        "generated_at": date_str,
        "headline": data.get("headline") or f"{date_str} 医療政策トピックス",
        "conclusion": data.get("conclusion") or first_summary,
        "summary": data.get("summary", ""),
        "articles": articles,
    }


def build_html(data: dict) -> str:
    """
    structured JSON 相当の data を正規化し、テンプレート適用後の HTML 文字列を返す。
    """
    normalized = normalize(data)

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=True,
    )
    template = env.get_template(TEMPLATE_FILE)
    return template.render(**normalized)


def write_html_to_path(html: str, output_path: Path) -> None:
    """
    同一内容の HTML を任意パスに書き出す。親ディレクトリが無ければ作成する。
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    print(f"[render_html] HTML を生成しました: {output_path}")


def render(data: dict, output_path: Path) -> None:
    """
    data を正規化してから Jinja2 テンプレートに差し込み、output_path に HTML を書き出す。
    """
    write_html_to_path(build_html(data), output_path)


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
        default=str(OUTPUT_DIR / "index.html"),
        help="出力HTMLのパス（デフォルト: output/index.html）",
    )
    args = parser.parse_args()

    # データ読み込み
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

    output_path = Path(args.out)
    render(data, output_path)


if __name__ == "__main__":
    main()
