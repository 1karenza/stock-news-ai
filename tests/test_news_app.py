import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import streamlit as st
from streamlit.testing.v1 import AppTest

from news_fetch import ArticleUnavailable


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"
ARTICLE = (
    "Doanh nghiệp công bố kế hoạch phát hành cổ phiếu thưởng cho cổ đông hiện hữu. "
    "Ngày đăng ký cuối cùng dự kiến là 20/09/2026 với tỷ lệ thực hiện 10:1. "
    "Doanh nghiệp dự kiến phát hành 171 triệu cổ phiếu từ nguồn lợi nhuận chưa phân phối. "
    "Việc phát hành nhằm tăng vốn điều lệ và hỗ trợ kế hoạch đầu tư dài hạn. "
    "Trong sáu tháng đầu năm, doanh thu tăng 15% so với cùng kỳ năm trước."
)


class NewsAppTests(unittest.TestCase):
    def setUp(self):
        st.cache_data.clear()

    def tearDown(self):
        st.cache_data.clear()

    def test_retry_recovers_after_failed_read_without_caching_the_failure(self):
        item = {
            "ticker": "FPT",
            "tickers": {"FPT"},
            "title": "Doanh nghiệp công bố kế hoạch phát hành cổ phiếu thưởng",
            "source": "Nguồn kiểm thử",
            "published": "11/09/2026 09:00",
            "date": "11/09/2026",
            "published_dt": datetime(2026, 9, 11, 2, tzinfo=timezone.utc),
            "summary": "Doanh nghiệp công bố kế hoạch phát hành cổ phiếu thưởng.",
            "url": "https://example.com/cache-retry-regression.html",
            "article_text": "",
            "bond_info": "-",
        }
        app = AppTest.from_file(str(APP_PATH), default_timeout=30)
        app.session_state["merged_news"] = [item]

        with patch("news_fetch.read_source_article", side_effect=[ArticleUnavailable("offline"), ARTICLE]) as read:
            app.run()
            self.assertEqual(len(app.exception), 0)
            read.assert_not_called()

            app.button(key="retry_missing_articles").click().run()
            self.assertEqual(len(app.exception), 0)
            self.assertEqual(read.call_count, 1)
            self.assertEqual(app.session_state["merged_news"][0]["article_text"], "")
            self.assertIn("retry_missing_articles", [button.key for button in app.button])

            app.button(key="retry_missing_articles").click().run()
            self.assertEqual(len(app.exception), 0)
            self.assertEqual(read.call_count, 2, "The failed read must be retried instead of cached.")
            self.assertEqual(app.session_state["merged_news"][0]["article_text"], ARTICLE)
            self.assertNotIn("retry_missing_articles", [button.key for button in app.button])
            self.assertTrue(any("171 triệu" in element.value for element in app.markdown))


if __name__ == "__main__":
    unittest.main()
