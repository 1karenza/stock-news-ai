import unittest

from broker_valuation import parse_reports, broker_table, latest_reports, filterable_broker_document
from equity_data import EquityUnavailable


class BrokerReportsTests(unittest.TestCase):
    def test_latest_per_broker_and_ticker_isolation(self):
        reports = [
            dict(ticker='FPT', source='SSI', issueDate='01/09/2026', targetPrice=90000),
            dict(ticker='FPT', source='SSI', issueDate='15/09/2026', targetPrice=85000,
                 recommend='MUA', title='<script>alert(1)</script>', attachedLink='javascript:alert(1)'),
            dict(ticker='VIC', source='VPS', issueDate='20/09/2026', targetPrice=100000),
            dict(ticker='FPT', source='MBS', issueDate='12/09/2026', targetPrice=0),
        ]
        rows = parse_reports({'ticker': 'FPT', 'analysisReports': reports}, 'FPT')
        self.assertEqual([r['broker'] for r in rows], ['SSI', 'MBS'])
        self.assertEqual(rows[0]['price'], 85000)
        self.assertIsNone(rows[1]['price'])
        rendered = broker_table(rows)
        self.assertIn('85.000 VND', rendered)
        self.assertIn('N/A', rendered)
        self.assertNotIn('javascript:', rendered)
        self.assertNotIn('<script>', rendered)

    def test_wrong_page_rejected_and_empty_supported(self):
        with self.assertRaises(EquityUnavailable):
            parse_reports({'ticker': 'VIC'}, 'FPT')
        self.assertEqual(parse_reports({'ticker': 'FPT'}, 'FPT'), [])

    def test_year_selected_before_latest_report(self):
        reports = [dict(ticker='FPT', source='SSI', issueDate=day, targetPrice=price)
                   for day, price in [('01/09/2026', 85000), ('01/12/2025', 95000), ('01/01/2025', 90000)]]
        rows = parse_reports({'ticker': 'FPT', 'analysisReports': reports}, 'FPT', latest_only=False)
        self.assertEqual(len(rows), 3)
        self.assertEqual(latest_reports(rows, 2025)[0]['price'], 95000)
        self.assertEqual(latest_reports(rows)[0]['price'], 85000)
        document = filterable_broker_document(rows)
        self.assertEqual(document.count('aria-label="Lọc '), 5)
        self.assertNotIn('data-column="4"', document)
        self.assertNotIn('data-column="6"', document)
        self.assertIn('data-sort="2025-12-01"', document)
        self.assertIn('data-sort="95000"', document)

    def test_year_control_without_broker_text_filter(self):
        from unittest.mock import patch
        from streamlit.testing.v1 import AppTest
        reports = [dict(ticker='FPT', source='SSI', issueDate=day, targetPrice=price)
                   for day, price in [('01/09/2026', 85000), ('01/12/2025', 95000)]]
        rows = parse_reports({'ticker': 'FPT', 'analysisReports': reports}, 'FPT', latest_only=False)
        app = AppTest.from_string("from equity_views import render_broker_valuation\nrender_broker_valuation('FPT')")
        with patch('equity_views.load_broker_reports', return_value=rows):
            app.run()
            self.assertFalse(app.exception)
            self.assertEqual(len(app.text_input), 0)
            app.selectbox(key='broker_year_FPT').select(2025).run()
            self.assertFalse(app.exception)
            self.assertEqual(app.selectbox(key='broker_year_FPT').value, 2025)


if __name__ == '__main__':
    unittest.main()
