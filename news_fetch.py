"""Article retrieval. Failures raise so Streamlit never caches empty results."""
from urllib.parse import urlparse, urljoin
import re
import unicodedata
import feedparser
from bs4 import BeautifulSoup

import requests
from googlenewsdecoder import gnewsdecoder

from news_content import extract_article


class ArticleUnavailable(Exception):
    """Temporary retrieval failure, safe to retry on the next request."""


def publisher_feed_url(title):
    """Resolve an exact headline through the publisher's own public feed.

    This avoids Google News decoding for recent VnEconomy stories. Never guess
    article slugs or substitute a merely similar story.
    """
    if not title.casefold().endswith(' - vneconomy'):
        return None
    def normalized(value):
        return re.sub(r'\W+', '', unicodedata.normalize('NFC', value).casefold())
    expected = normalized(title.rsplit(' - ', 1)[0])
    try:
        response = requests.get('https://vneconomy.vn/chung-khoan.rss', timeout=(5, 15))
        response.raise_for_status()
        for entry in feedparser.parse(response.content).entries:
            link = entry.get('link', '')
            if (normalized(entry.get('title', '')) == expected
                    and urlparse(link).scheme == 'https'
                    and urlparse(link).hostname == 'vneconomy.vn'):
                return link
    except requests.RequestException:
        pass
    # The publisher's RSS can lag behind its current category page.
    try:
        response = requests.get('https://vneconomy.vn/chung-khoan.htm', timeout=(5, 15))
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        for anchor in soup.select('a[href]'):
            link = urljoin('https://vneconomy.vn/', anchor['href'])
            if (normalized(anchor.get_text(' ', strip=True)) == expected
                    and urlparse(link).scheme == 'https'
                    and urlparse(link).hostname == 'vneconomy.vn'):
                return link
    except requests.RequestException:
        pass
    return None


def resolve_source_url(url):
    if urlparse(url).scheme not in ("http", "https"):
        raise ArticleUnavailable("Đường dẫn bài báo không hợp lệ.")
    if urlparse(url).hostname != "news.google.com":
        return url
    try:
        result = gnewsdecoder(url, interval=1)
        decoded = result.get("decoded_url", "")
        if (result.get("status") and urlparse(decoded).scheme in ("http", "https")
                and urlparse(decoded).hostname != "news.google.com"):
            return decoded
    except Exception as exc:
        raise ArticleUnavailable("Chưa mở được đường dẫn Google News.") from exc
    raise ArticleUnavailable("Chưa mở được đường dẫn Google News.")


def read_source_article(url, title=""):
    publisher_url = (publisher_feed_url(title) if urlparse(url).hostname == 'news.google.com' else None)
    publisher_url = publisher_url or resolve_source_url(url)
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36"}
    for attempt in range(2):
        try:
            response = requests.get(publisher_url, headers=headers, timeout=(5, 15))
            if response.status_code in (502, 503, 504) and attempt == 0:
                continue
            response.raise_for_status()
            text = extract_article(response.content, title=title)
            if not text.strip():
                raise ArticleUnavailable("Nguồn báo chưa cung cấp nội dung đọc được.")
            return text
        except (requests.Timeout, requests.ConnectionError) as exc:
            if attempt == 0:
                continue
            raise ArticleUnavailable("Kết nối nguồn báo bị gián đoạn.") from exc
        except requests.RequestException as exc:
            raise ArticleUnavailable(f"Nguồn báo trả lỗi HTTP {response.status_code}; chưa tải được bài gốc.") from exc
    raise ArticleUnavailable("Chưa tải được bài gốc.")
