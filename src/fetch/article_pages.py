"""
記事URLからタイトル・公開日・本文を取得する。

GemMedの記事ページHTML構造:
  - タイトル: <h1 class="entry-title"> または <h1>
  - 公開日: <time datetime="..."> または記事内のテキスト
  - 本文: <div class="entry-content"> または <article> 内のテキスト
"""

import re
import requests
from bs4 import BeautifulSoup

BODY_MAX_CHARS = 800  # AIへ渡す本文の最大文字数

def fetch_article(url: str) -> dict:
    """
    記事URLからメタデータと本文を取得する。

    Args:
        url: 記事の絶対URL

    Returns:
        dict with keys: title, published_at, url, body
        取得失敗時もキーは揃えて返す（bodyが空になる）
    """
    print(f"[article_pages] 記事取得中: {url}")

    try:
        resp = requests.get(url, timeout=15, headers={
            "User-Agent": "Mozilla/5.0 (compatible; GemMedScraper/1.0)"
        })
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"[article_pages] ERROR: 記事取得失敗 ({url}): {e}")
        return _empty_article(url)

    soup = BeautifulSoup(resp.text, "html.parser")

    title = _extract_title(soup)
    published_at = _extract_date(soup, url)
    body = _extract_body(soup)

    print(f"[article_pages]   title: {title[:40]}...")
    print(f"[article_pages]   published_at: {published_at}")
    print(f"[article_pages]   body: {len(body)} 文字")

    return {
        "title": title,
        "published_at": published_at,
        "url": url,
        "body": body,
    }


def _extract_title(soup: BeautifulSoup) -> str:
    """タイトルを抽出する。複数セレクタを試す。"""
    # 優先順位順に試す
    for selector in ["h1.entry-title", "h1.post-title", "h1"]:
        el = soup.select_one(selector)
        if el:
            return el.get_text(strip=True)

    # <title> タグからドメイン部分を除いてフォールバック
    if soup.title:
        raw = soup.title.get_text(strip=True)
        return raw.split("|")[0].strip()

    return "（タイトル取得不可）"


def _extract_date(soup: BeautifulSoup, url: str) -> str:
    """公開日を抽出する。複数の方法を試す。"""
    # 1. <time datetime="YYYY-MM-DD...">
    time_el = soup.find("time", attrs={"datetime": True})
    if time_el:
        raw = time_el["datetime"]
        m = re.match(r"(\d{4}-\d{2}-\d{2})", raw)
        if m:
            return m.group(1)

    # 2. URLから日付を抽出: /YYYY/MM/DD/
    m = re.search(r"/(\d{4})/(\d{2})/(\d{2})/", url)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"

    # 3. ページ内テキストから "YYYY.MM.DD" や "YYYY年MM月DD日" を探す
    text = soup.get_text()
    m = re.search(r"(\d{4})[.\u5e74](\d{1,2})[.\u6708](\d{1,2})[.\u65e5]?", text)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"

    return "（日付不明）"


def _extract_body(soup: BeautifulSoup) -> str:
    """本文を抽出し、不要な空白を整理してから BODY_MAX_CHARS 文字に切る。"""
    # 優先順位順に本文コンテナを探す
    container = None
    for selector in [
        "div.entry-content",
        "div.post-content",
        "div.article-body",
        "article",
    ]:
        container = soup.select_one(selector)
        if container:
            break

    if container is None:
        # フォールバック: <main> 全体
        container = soup.find("main") or soup.body

    if container is None:
        return ""

    # スクリプト・スタイル・ナビ等を除去してテキスト取得
    for tag in container.find_all(["script", "style", "nav", "aside", "footer"]):
        tag.decompose()

    raw_text = container.get_text(separator="\n")

    # 連続する空白行・スペースを整理
    lines = [line.strip() for line in raw_text.splitlines()]
    lines = [line for line in lines if line]  # 空行除去
    body = "\n".join(lines)

    return body[:BODY_MAX_CHARS]


def _empty_article(url: str) -> dict:
    """取得失敗時のダミー構造を返す。"""
    return {
        "title": "（取得失敗）",
        "published_at": "（日付不明）",
        "url": url,
        "body": "",
    }
