import json
import unittest

from news_content import extract_article, news_table, summary_sentences


ARTICLE = (
    "Công ty công bố kế hoạch phát hành cổ phiếu thưởng cho cổ đông hiện hữu. "
    "Ngày đăng ký cuối cùng dự kiến là 20/09/2026 với tỷ lệ thực hiện 10:1. "
    "Doanh nghiệp dự kiến phát hành 171 triệu cổ phiếu từ nguồn lợi nhuận chưa phân phối. "
    "Việc phát hành nhằm tăng vốn điều lệ và hỗ trợ kế hoạch đầu tư dài hạn. "
    "Trong sáu tháng đầu năm, doanh thu tăng 15% so với cùng kỳ năm trước. "
    "Ban lãnh đạo cho biết tiến độ còn phụ thuộc vào phê duyệt của cơ quan quản lý. "
    "Công ty công bố kế hoạch phát hành cổ phiếu thưởng cho cổ đông hiện hữu."
)


class NewsContentTests(unittest.TestCase):
    def test_summary_keeps_context_facts_order_and_no_duplicates(self):
        item = {"title": "Tiêu đề", "article_text": ARTICLE}
        overview = summary_sentences(item)
        detail = summary_sentences(item, detail=True)
        self.assertEqual(len(overview), 4)
        self.assertEqual(len(detail), 6)
        self.assertTrue(overview[0].startswith("Công ty"))
        self.assertIn("171 triệu", " ".join(detail))
        self.assertIn("phê duyệt", " ".join(detail))
        self.assertLessEqual(len(" ".join(detail).split()), 220)
        self.assertEqual(len(detail), len(set(detail)))

    def test_sparse_source_is_not_padded(self):
        title = "Doanh nghiệp công bố ngày chốt quyền cổ tức"
        self.assertEqual(summary_sentences({"title": title}), [title])

    def test_utf8_bytes_preserve_vietnamese(self):
        document = f'<meta charset="utf-8"><article><p>{ARTICLE}</p></article>'
        self.assertEqual(extract_article(document.encode('utf-8')), ARTICLE)

    def test_unrelated_publisher_description_is_rejected(self):
        document = '<meta property="og:description" content="Chuyến thăm chính thức tại Paris của đoàn đại biểu.">'
        self.assertEqual(extract_article(document, title='FPT phát hành cổ phiếu thưởng'), '')

    def test_structured_article_body_survives_script_removal(self):
        document = '<script type="application/ld+json">' + json.dumps({"@graph": [{"articleBody": ARTICLE}]}) + '</script>'
        self.assertEqual(extract_article(document), ARTICLE)

    def test_article_excludes_unrelated_navigation(self):
        document = f'<nav><p>UNRELATED NAVIGATION</p></nav><article><p>{ARTICLE}</p></article>'
        self.assertEqual(extract_article(document), ARTICLE)
        self.assertEqual(extract_article('<nav><p>Login to read more</p></nav>'), '')

    def test_table_escapes_content_and_has_no_bond_column(self):
        row = {"Ngày": "11/09/2026", "Mã CK": "FPT", "Tóm tắt thông tin": '<script>alert(1)</script>',
               "Source": "A & B", "Loại tin": "Doanh nghiệp", "Đọc tin gốc": "javascript:alert(1)"}
        result = news_table([row])
        self.assertNotIn('<script>', result)
        self.assertNotIn('href=', result)
        self.assertNotIn('Trái phiếu', result)
        self.assertIn('&lt;script&gt;', result)


if __name__ == '__main__':
    unittest.main()
