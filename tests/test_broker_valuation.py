import unittest

from broker_valuation import parse_reports, broker_table, latest_reports, filterable_broker_document, report_years, fetch_broker_reports
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
        document = filterable_broker_document(rows, current_year=2026)
        self.assertEqual(document.count('aria-label="Lọc '), 4)
        self.assertIn('aria-label="Sắp xếp Giá mục tiêu"', document)
        self.assertIn('aria-label="Lọc Thời gian"', document)
        self.assertNotIn('data-column="4"', document)
        self.assertNotIn('data-column="6"', document)
        self.assertIn('data-sort="2025-12-01"', document)
        self.assertIn('data-sort="95000"', document)

    def test_three_year_history_is_paginated(self):
        from unittest.mock import patch, MagicMock
        response = lambda data, total: MagicMock(json=lambda: {'status': 200, 'data': data, 'total': total})
        reports = [dict(ticker='FPT', source='SSI', issueDate=f'01/09/{year}', targetPrice=year*10)
                   for year in [2026, 2025, 2024, 2023]]
        with patch('broker_valuation.report_years', return_value=[2026, 2025, 2024]), patch('broker_valuation.requests.Session') as session:
            get = session.return_value.__enter__.return_value.get
            get.side_effect = [response(reports[:1], 101), response(reports[1:], 101)]
            rows = fetch_broker_reports('FPT')
        self.assertEqual([r['date'].year for r in rows], [2026, 2025, 2024])
        self.assertEqual(get.call_count, 2)
        self.assertEqual(get.call_args.kwargs['params']['page'], 1)
        self.assertEqual(report_years(2026), [2026, 2025, 2024])

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
            self.assertEqual(len(app.selectbox), 0)


if __name__ == '__main__':
    unittest.main()
