"""
GemMed 業界トピックスツール エントリポイント。

実行フロー:
  1. GemMedトップから最新3件のURLを取得
  2. 各記事の本文を取得
  3. data/raw_articles.json に保存

使い方:
  python src/main.py
"""

import json
import sys
from datetime import date
from pathlib import Path

# プロジェクトルート（industry-topics-tool/）を sys.path に追加
# これにより `python src/main.py` でも `python -m src.main` でも動く
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.fetch.list_pages import fetch_latest_urls
from src.fetch.article_pages import fetch_article

DATA_DIR = ROOT / "data"
OUTPUT_FILE = DATA_DIR / f"raw_articles_{date.today().strftime('%Y%m%d')}.json"


def main():
    print("=" * 50)
    print("GemMed 業界トピックス - 記事取得")
    print("=" * 50)

    # Step 1: URLリスト取得
    try:
        urls = fetch_latest_urls(limit=3)
    except RuntimeError as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    # Step 2: 各記事の本文を取得
    articles = []
    for url in urls:
        article = fetch_article(url)
        articles.append(article)

    # Step 3: JSON に保存
    DATA_DIR.mkdir(exist_ok=True)
    payload = {
        "fetched_at": date.today().isoformat(),
        "source": "https://gemmed.ghc-j.com/",
        "articles": articles,
    }
    OUTPUT_FILE.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print()
    print(f"✓ {len(articles)} 件の記事を取得しました")
    print(f"✓ 保存先: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
