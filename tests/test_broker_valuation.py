import unittest

from broker_valuation import parse_reports, broker_table
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


if __name__ == '__main__':
    unittest.main()
