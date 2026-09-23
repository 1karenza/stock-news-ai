"""Article retrieval. Failures raise so Streamlit never caches empty results."""
from urllib.parse import urlparse

import requests
from googlenewsdecoder import gnewsdecoder

from news_content import extract_article


class ArticleUnavailable(Exception):
    """Temporary retrieval failure, safe to retry on the next request."""


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
    publisher_url = resolve_source_url(url)
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
            raise ArticleUnavailable("Nguồn báo tạm thời không cho tải bài.") from exc
    raise ArticleUnavailable("Chưa tải được bài gốc.")
