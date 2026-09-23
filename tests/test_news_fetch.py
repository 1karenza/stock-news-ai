import unittest
from unittest.mock import Mock, patch

import requests

from news_fetch import ArticleUnavailable, read_source_article, resolve_source_url


GOOGLE_URL = "https://news.google.com/rss/articles/test-article?oc=5"
PUBLISHER_URL = "https://example.com/tin-doanh-nghiep.html"
TITLE = "Doanh nghiệp công bố kế hoạch phát hành cổ phiếu thưởng"
ARTICLE = (
    "Doanh nghiệp công bố kế hoạch phát hành cổ phiếu thưởng cho cổ đông hiện hữu. "
    "Ngày đăng ký cuối cùng dự kiến là 20/09/2026 với tỷ lệ thực hiện 10:1. "
    "Doanh nghiệp dự kiến phát hành 171 triệu cổ phiếu từ nguồn lợi nhuận chưa phân phối."
)


def response_with(content, status=200):
    response = Mock()
    response.status_code = status
    response.content = content
    response.url = PUBLISHER_URL
    response.raise_for_status.return_value = None
    if status >= 400:
        response.raise_for_status.side_effect = requests.HTTPError(f"HTTP {status}")
    return response


class NewsFetchTests(unittest.TestCase):
    @patch("news_fetch.gnewsdecoder")
    def test_direct_publisher_url_skips_google_decoder(self, decoder):
        self.assertEqual(resolve_source_url(PUBLISHER_URL), PUBLISHER_URL)
        decoder.assert_not_called()

    @patch("news_fetch.gnewsdecoder")
    def test_google_url_resolves_to_publisher(self, decoder):
        decoder.return_value = {"status": True, "decoded_url": PUBLISHER_URL}
        self.assertEqual(resolve_source_url(GOOGLE_URL), PUBLISHER_URL)
        decoder.assert_called_once_with(GOOGLE_URL, interval=1)

    @patch("news_fetch.gnewsdecoder")
    def test_failed_or_unresolved_google_url_raises(self, decoder):
        failures = [
            {"status": False, "message": "Could not decode"},
            {"status": True, "decoded_url": GOOGLE_URL},
            {"status": True, "decoded_url": ""},
            {"status": True, "decoded_url": "javascript:alert(1)"},
        ]
        for result in failures:
            with self.subTest(result=result):
                decoder.return_value = result
                with self.assertRaises(ArticleUnavailable):
                    resolve_source_url(GOOGLE_URL)

    @patch("news_fetch.gnewsdecoder", side_effect=requests.Timeout("decode timed out"))
    def test_decoder_exception_raises_article_unavailable(self, decoder):
        with self.assertRaises(ArticleUnavailable):
            resolve_source_url(GOOGLE_URL)

    @patch("news_fetch.requests.get")
    def test_request_failures_raise_article_unavailable(self, get):
        for error in (requests.Timeout("timed out"), requests.ConnectionError("offline")):
            with self.subTest(error=type(error).__name__):
                get.side_effect = error
                with self.assertRaises(ArticleUnavailable):
                    read_source_article(PUBLISHER_URL, TITLE)

    @patch("news_fetch.requests.get")
    def test_http_error_is_not_returned_as_article(self, get):
        get.return_value = response_with(b"Access denied", status=403)
        with self.assertRaises(ArticleUnavailable):
            read_source_article(PUBLISHER_URL, TITLE)

    @patch("news_fetch.extract_article", return_value="")
    @patch("news_fetch.requests.get")
    def test_empty_extraction_raises_article_unavailable(self, get, extract):
        get.return_value = response_with(b"<html>Nothing to extract</html>")
        with self.assertRaises(ArticleUnavailable):
            read_source_article(PUBLISHER_URL, TITLE)

    @patch("news_fetch.extract_article", return_value=ARTICLE)
    @patch("news_fetch.requests.get")
    @patch("news_fetch.resolve_source_url", return_value=PUBLISHER_URL)
    def test_fetch_passes_original_bytes_and_title_to_extractor(self, resolve, get, extract):
        document = f'<meta charset="utf-8"><article><p>{ARTICLE}</p></article>'.encode("utf-8")
        get.return_value = response_with(document)
        self.assertEqual(read_source_article(GOOGLE_URL, TITLE), ARTICLE)
        resolve.assert_called_once_with(GOOGLE_URL)
        self.assertEqual(get.call_args.args[0], PUBLISHER_URL)
        self.assertEqual(get.call_args.kwargs["timeout"], (5, 15))
        extract.assert_called_once_with(document, title=TITLE)

    @patch("news_fetch.requests.get")
    def test_vietnamese_article_text_is_returned_without_mojibake(self, get):
        document = f'<meta charset="utf-8"><article><p>{ARTICLE}</p></article>'.encode("utf-8")
        get.return_value = response_with(document)
        self.assertEqual(read_source_article(PUBLISHER_URL, TITLE), ARTICLE)


if __name__ == "__main__":
    unittest.main()
