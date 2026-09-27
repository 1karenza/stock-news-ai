"""Article retrieval. Failures raise so Streamlit never caches empty results."""
from urllib.parse import urlparse, urljoin
import re
import logging
import unicodedata
import feedparser
from bs4 import BeautifulSoup

import requests
from news_transport import gnewsdecoder

from news_content import extract_article


class ArticleUnavailable(Exception):
    """Temporary retrieval failure, safe to retry on the next request."""


# Publisher indexes are independent of ticker and Google's redirect service.
# Only exact headline matches on the expected publisher are accepted.
PUBLISHER_INDEXES = {
    'moneyf': ['https://moneyf.vn/'],
    'chứng khoán dnse': ['https://www.dnse.com.vn/senses/tin-tuc'],
    '24hmoney': ['https://24hmoney.vn/'],
    'kinhtechungkhoan.vn': ['https://kinhtechungkhoan.vn/chung-khoan', 'https://kinhtechungkhoan.vn/bao-cao-phan-tich'],
    'cafef': ['https://cafef.vn/'],
    'vnexpress': ['https://vnexpress.net/kinh-doanh'],
    'vnexpress.net': ['https://vnexpress.net/kinh-doanh'],
    'vietstock': ['https://vietstock.vn/'],
    'nguoiquansat.vn': ['https://nguoiquansat.vn/'],
    'báo dân trí': ['https://dantri.com.vn/'],
    'dantri.com.vn': ['https://dantri.com.vn/'],
    'báo dân việt': ['https://danviet.vn/'],
    'danviet.vn': ['https://danviet.vn/'],
    'baodautu.vn': ['https://baodautu.vn/'],
    'mekong asean': ['https://mekongasean.vn/'],
    'tin nhanh chứng khoán': ['https://www.tinnhanhchungkhoan.vn/'],
}


def publisher_index_url(title):
    headline, separator, publisher = title.rpartition(' - ')
    if not separator:
        return None
    def norm(value):
        return re.sub(r'\W+', '', unicodedata.normalize('NFC', value).casefold())
    expected = norm(headline)
    indexes = list(PUBLISHER_INDEXES.get(publisher.casefold(), []))
    if publisher.casefold() == 'nguoiquansat.vn':
        # Its ticker archives retain older stories no longer on the homepage.
        tickers = list(dict.fromkeys(re.findall(r'\b[A-Z]{3}\b', headline)))[:3]
        indexes = [f'https://nguoiquansat.vn/{ticker.lower()}-ptag.html' for ticker in tickers] + indexes
    for index in indexes:
        try:
            response = requests.get(index, headers={'User-Agent': 'Mozilla/5.0', 'Accept-Language': 'vi,en;q=0.8'}, timeout=(5, 15))
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            host = urlparse(index).hostname.removeprefix('www.')
            for anchor in soup.select('a[href]'):
                if expected not in {norm(anchor.get_text(' ', strip=True)), norm(anchor.get('title', ''))}:
                    continue
                link = urljoin(index, anchor['href'])
                parsed = urlparse(link)
                if parsed.scheme in ('https', 'http') and (parsed.hostname or '').removeprefix('www.') == host:
                    return link
        except requests.RequestException:
            continue
    return None


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


def publisher_permalink_article(title):
    """Read Vietnam.vn's verified permalink when Google News blocks decoding."""
    headline, separator, publisher = title.rpartition(' - ')
    if not separator or publisher.casefold() != 'vietnam.vn':
        return None
    slug = unicodedata.normalize('NFKD', headline.casefold().replace('đ', 'd'))
    slug = ''.join(char for char in slug if not unicodedata.combining(char))
    slug = re.sub(r'[^a-z0-9]+', '-', slug).strip('-')
    if not slug:
        return None
    url = f'https://www.vietnam.vn/{slug}'
    try:
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36'}, timeout=(5, 15))
        response.raise_for_status()
        if urlparse(response.url).hostname not in {'vietnam.vn', 'www.vietnam.vn'}:
            logging.warning('Vietnam.vn article redirected to an unexpected host: %s', response.url)
            return None
        soup = BeautifulSoup(response.content, 'html.parser')
        heading = soup.find('h1')
        normalize = lambda value: re.sub(r'\W+', '', unicodedata.normalize('NFC', value).casefold())
        if not heading or normalize(heading.get_text(' ', strip=True)) != normalize(headline):
            logging.warning('Vietnam.vn article headline did not match: %s', url)
            return None
        text = extract_article(response.content, title=title).strip()
        if len(text.split()) < 80:
            logging.warning('Vietnam.vn article text too short (%s words): %s', len(text.split()), url)
        return text if len(text.split()) >= 80 else None
    except requests.RequestException as exc:
        logging.warning('Vietnam.vn article request failed: %s', exc)
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
        if isinstance(exc, requests.HTTPError) and exc.response is not None and exc.response.status_code == 429:
            raise ArticleUnavailable("Google News đang giới hạn lượt truy cập (429). Vui lòng thử lại sau.") from exc
        raise ArticleUnavailable("Chưa mở được đường dẫn Google News.") from exc
    raise ArticleUnavailable("Chưa mở được đường dẫn Google News.")


def read_source_article(url, title=""):
    if urlparse(url).hostname == 'news.google.com':
        direct_text = publisher_permalink_article(title)
        if direct_text:
            return direct_text
    publisher_url = (publisher_feed_url(title) if urlparse(url).hostname == 'news.google.com' else None)
    if not publisher_url and urlparse(url).hostname == 'news.google.com':
        publisher_url = publisher_index_url(title)
    if not publisher_url:
        return _read_publisher_article(resolve_source_url(url), title)
    primary_error = None
    try:
        text = _read_publisher_article(publisher_url, title)
    except ArticleUnavailable as exc:
        primary_error, text = exc, ""
    if len(text.split()) >= 80:
        return text
    # A publisher archive can link to a teaser. Try the original RSS target
    # once as a fallback, retaining usable text if Google is unavailable.
    try:
        original_url = resolve_source_url(url)
        if original_url != publisher_url:
            alternative = _read_publisher_article(original_url, title)
            if len(alternative.split()) > len(text.split()):
                text = alternative
    except ArticleUnavailable:
        pass
    if text:
        return text
    raise primary_error or ArticleUnavailable("Nguồn báo chưa cung cấp nội dung đọc được.")


def _read_publisher_article(publisher_url, title):
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
