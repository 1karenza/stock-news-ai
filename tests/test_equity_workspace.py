import unittest
from unittest.mock import patch
from pathlib import Path
from streamlit.testing.v1 import AppTest
from equity_fixture import make_bundle
from equity_data import company_events, comparable_rows, relative_valuation, source_date, EquityUnavailable, parse_cafef_ownership, ownership_chart_rows
from equity_report import build_report
from news_content import news_table


class EquityTests(unittest.TestCase):
    def test_cafef_shareholders_and_invalid_pie_total(self):
        markup='<table><tr><td>Trần Đình Long</td><td>2.178.000.179</td><td>25,8</td><td>25/05/2026</td></tr><tr><td>Chủ tịch</td><td>Tên</td><td>65</td><td>Chi tiết</td></tr></table>'
        rows=parse_cafef_ownership(markup,'HPG')
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['Số cổ phiếu'],2178000179)
        self.assertEqual(rows[0]['Tỷ lệ (%)'],25.8)
        self.assertEqual(ownership_chart_rows(rows)[-1]['Tỷ lệ (%)'],74.2)
        self.assertEqual(ownership_chart_rows(rows*4),[])
        with self.assertRaises(EquityUnavailable):
            parse_cafef_ownership('<html>Unavailable</html>','HPG')

    def test_dates_are_distinct_and_publication_never_becomes_execution(self):
        bundle=make_bundle()
        self.assertEqual([e['Ngày'] for e in bundle['events']],['2026-06-10','2026-05-29','2026-05-28'])
        c=bundle['company']
        c['companyNews']=[{'title':'Phát hành thêm','createdDate':'12/09/2026','executionDate':''}]
        event=company_events(c)[0]
        self.assertEqual(event['Loại ngày'],'Ngày công bố (không phải ngày thực hiện)')
        self.assertEqual(source_date('01/12/2025'),'2025-12-01')
        self.assertEqual(source_date('31/02/2025'),'')

    def test_peers_must_match_industry_and_target_excluded(self):
        c=make_bundle()['company']; c['stocks']=[{'ticker':'CMG'},{'ticker':'BANK'}]
        def fetch(code):
            other=make_bundle(code)['company']
            if code=='BANK': other['summary']['bcIndustryGroupId']=99
            return other
        rows,_=comparable_rows(c,fetch)
        self.assertEqual([r['Mã'] for r in rows],['FPT','CMG'])
        rows=make_bundle()['peers']; rows[0]['P/E (TTM)']=999
        self.assertEqual(relative_valuation(rows)[0]['Trung vị nhóm'],15)
        rows[0]['EPS (TTM, đ/CP)']=-1
        self.assertEqual([r['Phương pháp'] for r in relative_valuation(rows)],['P/B (FQ)'])
        rows[1]['P/B (FQ)']=None
        self.assertEqual(relative_valuation(rows),[])

    def test_report_is_portable_safe_and_contains_all_sections(self):
        b=make_bundle(); b['events'][0]['Sự kiện']='<script>alert(1)</script>'
        report=build_report(b,[{'Tiêu đề':'<img src=x onerror=alert(1)>','Nguồn':'javascript:alert(1)'}],['FPT'])
        for label in ['I / Stock News','II / Lịch doanh nghiệp','III / Giá cổ phiếu','IV / Định giá']:
            self.assertIn(label,report)
        self.assertIn('<svg',report)
        self.assertNotIn('<script',report)
        self.assertNotIn('<img',report)
        self.assertNotIn('href="javascript:',report)

    def test_auto_loading_and_switching_ticker_without_price_button(self):
        app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=30)
        app.session_state['profile_ready']=True
        with patch('equity_views.load_equity',side_effect=make_bundle) as load:
            app.run()
            self.assertFalse(app.exception)
            load.assert_called_with('FPT','3mo')
            self.assertNotIn('Tải biểu đồ giá',[b.label for b in app.button])
            app.selectbox(key='equity_ticker').select('TCB').run()
            self.assertFalse(app.exception)
            load.assert_called_with('TCB','3mo')
            self.assertTrue(any('Định giá · TCB' in m.value for m in app.markdown))

    def test_news_title_column_precedes_source(self):
        row={'Ngày':'2026-09-17','Mã CK':'FPT','Tóm tắt thông tin':'Tóm tắt','Tiêu đề bài báo':'Tiêu đề',
             'Source':'Nguồn','Loại tin':'Doanh nghiệp','Đọc tin gốc':'https://example.com'}
        rendered=news_table([row])
        self.assertLess(rendered.index('<th scope="col">Tiêu đề bài báo'), rendered.index('<th scope="col">Nguồn'))
