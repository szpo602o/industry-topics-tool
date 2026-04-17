"""
GemMedトップページから最新記事3件のURLを取得する。

GemMedのHTML構造:
  - "LATEST NEWS" セクション内に記事リンクが <h3><a> で並ぶ
  - 記事URLのパターン: https://gemmed.ghc-j.com/YYYY/MM/DD/slug/
"""

import re
import requests
from bs4 import BeautifulSoup

GEMMED_TOP_URL = "https://gemmed.ghc-j.com/"
ARTICLE_URL_PATTERN = re.compile(r"https://gemmed\.ghc-j\.com/\d{4}/\d{2}/\d{2}/.+")

def fetch_latest_urls(limit: int = 3) -> list[str]:
    """
    GemMedトップページから最新記事のURLを最大 limit 件返す。

    Args:
        limit: 取得する最大件数（デフォルト3）

    Returns:
        記事URL（絶対URL）のリスト

    Raises:
        RuntimeError: ページ取得失敗 or 記事が1件も見つからない場合
    """
    print(f"[list_pages] GemMedトップページを取得中: {GEMMED_TOP_URL}")

    try:
        resp = requests.get(GEMMED_TOP_URL, timeout=15, headers={
            "User-Agent": "Mozilla/5.0 (compatible; GemMedScraper/1.0)"
        })
        resp.raise_for_status()
    except requests.RequestException as e:
        raise RuntimeError(f"[list_pages] GemMedトップページの取得に失敗しました: {e}") from e

    soup = BeautifulSoup(resp.text, "html.parser")

    urls = _extract_article_urls(soup, limit)

    if not urls:
        raise RuntimeError(
            "[list_pages] 記事URLが1件も見つかりませんでした。"
            " GemMedのHTML構造が変わった可能性があります。"
        )

    print(f"[list_pages] {len(urls)} 件のURLを取得しました")
    for u in urls:
        print(f"  - {u}")

    return urls


def _extract_article_urls(soup: BeautifulSoup, limit: int) -> list[str]:
    """
    BeautifulSoupオブジェクトから記事URLを抽出する。
    複数のセレクタ戦略を順番に試す。
    """

    # 戦略1: 記事URLパターン（/YYYY/MM/DD/）にマッチする <a> を全件取得し、
    #         重複を除いて上位 limit 件を返す
    seen = []
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        # 相対URLを絶対URLに変換
        if href.startswith("/"):
            href = "https://gemmed.ghc-j.com" + href
        if ARTICLE_URL_PATTERN.match(href) and href not in seen:
            seen.append(href)
        if len(seen) >= limit:
            break

    if seen:
        return seen

    # 戦略2（フォールバック）: h3 > a のテキストが20文字以上のもの
    fallback = []
    for h3 in soup.find_all("h3"):
        a_tag = h3.find("a", href=True)
        if a_tag and len(a_tag.get_text(strip=True)) >= 20:
            href = a_tag["href"]
            if href.startswith("/"):
                href = "https://gemmed.ghc-j.com" + href
            if href not in fallback:
                fallback.append(href)
        if len(fallback) >= limit:
            break

    return fallback
