import json
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import patch
import pandas as pd
from streamlit.testing.v1 import AppTest
from investor_events import (classify_event, cluster_events, extract_event_dates, validate_manual_event,
                             calendar_html, events_ics, official_source)
from investor_profile import default_profile, validate_profile, article_id, portable_article
from bond_scenarios import price_at_yield, scenario_table
from market_prices import import_prices, validate_prices, align_news, PriceUnavailable

APP = str(Path(__file__).resolve().parents[1] / "app.py")
ARTICLE = {"title":"FPT phát hành 171 triệu cổ phiếu thưởng", "tickers":{"FPT"}, "ticker":"FPT",
           "url":"https://example.com/fpt", "source":"Nguồn kiểm tra", "date":"10/09/2026",
           "published":"10/09/2026 12:00", "published_dt":datetime(2026,9,10,5,tzinfo=timezone.utc),
           "summary":"FPT phát hành 171 triệu cổ phiếu thưởng.",
           "article_text":"Ngày đăng ký cuối cùng dự kiến là 22/09/2026. Ngày thanh toán là 20/10/2026.", "bond_info":"-"}
BOND = dict(code="A",face_value=100, coupon_rate=.08, years=5, payments_per_year=2, required_yield=.08, market_price=100)


class EventTests(unittest.TestCase):
    def test_distinct_milestones_and_no_publication_date_fallback(self):
        entries=extract_event_dates(ARTICLE)
        self.assertEqual([(e["milestone"],e["event_date"]) for e in entries],[("record","2026-09-22"),("payment","2026-10-20")])
        self.assertEqual(entries[0]["status"],"expected")
        self.assertEqual(extract_event_dates({"title":"FPT doanh thu tăng 10%", "summary":"Dữ liệu tính đến 20/09/2026."}),[])

    def test_missing_year_and_invalid_dates_require_review(self):
        for d in ("22/09","31/02/2026"):
            events=extract_event_dates({"title":"Ngày đăng ký cuối cùng là "+d})
            self.assertEqual(events[0]["status"],"needs_review")
            self.assertIsNone(events[0]["event_date"])

    def test_groups_only_matching_events(self):
        same={**ARTICLE,"url":"https://b.test/fpt","source":"B"}
        other={**ARTICLE,"title":"FPT phát hành 200 triệu cổ phiếu thưởng","url":"https://b.test/other"}
        self.assertEqual(classify_event(ARTICLE),"issuance")
        groups=cluster_events([ARTICLE,same,other])
        self.assertEqual(sorted(len(g["articles"]) for g in groups),[1,2])

    def test_calendar_html_and_ics_preserve_unicode_without_injection(self):
        event=validate_manual_event({"title":"Cổ tức <script>\nBEGIN:VEVENT", "event_date":"2026-09-22", "tickers":"FPT", "type":"dividends"})
        self.assertNotIn("<script>",calendar_html(2026,9,[event]))
        payload=events_ics([event])
        self.assertEqual(payload.count(b"\r\nBEGIN:VEVENT\r\n"),1)
        self.assertIn(b"DTSTART;VALUE=DATE:20260922",payload)
        self.assertTrue(all(len(line)<=75 for line in payload.split(b"\r\n")))
        self.assertFalse(official_source("https://fpt.com.evil.test/",["FPT"]))
        self.assertTrue(official_source("https://fpt.com/vi/nha-dau-tu",["FPT"]))


class PriceAndBondTests(unittest.TestCase):
    def test_price_csv_validation(self):
        frame=import_prices(b"date,close,volume\n2026-09-11,70000,100\n2026-09-14,71000,200\n")
        self.assertEqual(len(frame),2)
        for data in (b"date,close,volume\n2026-09-11,1,2\n2026-09-11,2,3\n",
                     b"date,close,volume\n2026-09-11,-1,2\n2026-09-14,2,3\n",
                     b"date,close,volume\n2026-09-11,NaN,2\n2026-09-14,2,3\n"):
            with self.assertRaises(PriceUnavailable): import_prices(data)

    def test_weekend_and_after_hours_news_markers(self):
        prices=import_prices(b"date,close,volume\n2026-09-11,70000,100\n2026-09-14,71000,200\n")
        weekend={**ARTICLE,"published_dt":datetime(2026,9,12,5,tzinfo=timezone.utc)}
        future={**ARTICLE,"published_dt":datetime(2026,9,15,5,tzinfo=timezone.utc)}
        marks=align_news(prices,[weekend,future],"FPT")
        self.assertEqual(len(marks),1)
        self.assertEqual(marks.iloc[0].published_date,"2026-09-12")
        self.assertEqual(marks.iloc[0].date,pd.Timestamp("2026-09-14"))
        no_trade=import_prices(b"date,close,volume\n2026-09-12,70000,0\n2026-09-14,71000,200\n")
        self.assertEqual(align_news(no_trade,[weekend],"FPT").iloc[0].date,pd.Timestamp("2026-09-14"))

    def test_exact_bond_repricing(self):
        self.assertAlmostEqual(price_at_yield(BOND,.08),100)
        self.assertAlmostEqual(price_at_yield(BOND,0),140)
        self.assertGreater(price_at_yield(BOND,-.01),140)
        frame=scenario_table(BOND)
        self.assertTrue(frame["Giá lý thuyết"].is_monotonic_decreasing)
        self.assertAlmostEqual(frame.loc[frame["Thay đổi lợi suất (điểm %)"]==0,"Biến động giá (%)"].iloc[0],0)
        for bad in ({**BOND,"years":.7},{**BOND,"required_yield":-2},{**BOND,"face_value":float("nan")}):
            with self.assertRaises(ValueError): scenario_table(bad)

    def test_same_cashflows_scale_with_face(self):
        twice={**BOND,"face_value":200,"market_price":200}
        pd.testing.assert_series_equal(scenario_table(BOND)["Biến động giá (%)"],scenario_table(twice)["Biến động giá (%)"])


class WorkspaceTests(unittest.TestCase):
    def test_profile_json_roundtrip_and_isolation(self):
        p=default_profile()
        p["groups"]["Đang giữ"]=["FPT","TCB"]
        p["saved"][article_id(ARTICLE)]=portable_article(ARTICLE)
        p["recent_news"]=[portable_article(ARTICLE)]
        loaded=validate_profile(json.loads(json.dumps(p)))
        self.assertEqual(loaded["groups"]["Đang giữ"],["FPT","TCB"])
        self.assertNotIn("Đang giữ",default_profile()["groups"])
        self.assertEqual(loaded["recent_news"][0]["published_dt"],ARTICLE["published_dt"].isoformat())
        with self.assertRaises(ValueError): validate_profile({"version":99})

    def test_app_watchlist_read_save_calendar_and_bond_comparison(self):
        app=AppTest.from_file(APP,default_timeout=45)
        app.session_state["profile_ready"]=True
        app.session_state["merged_news"]=[ARTICLE]
        app.run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.tabs),6)
        next(x for x in app.text_input if x.label=="Tên danh sách").set_value("Danh mục thử")
        next(x for x in app.text_input if x.label=="Các mã trong danh sách").set_value("FPT, SSI")
        next(x for x in app.button if x.label=="Lưu danh sách").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state["investor_profile"]["groups"]["Danh mục thử"],["FPT","SSI"])
        app.selectbox(key="watch_group").select("Danh mục thử").run()
        app.button(key="apply_watchlist").click().run()
        self.assertEqual(app.text_input(key="news_tickers").value,"FPT, SSI")
        app.button(key="read_"+article_id(ARTICLE)).click().run()
        app.button(key="save_"+article_id(ARTICLE)).click().run()
        self.assertFalse(app.exception)
        self.assertIn(article_id(ARTICLE),app.session_state["investor_profile"]["read"])
        self.assertIn(article_id(ARTICLE),app.session_state["investor_profile"]["saved"])
        next(x for x in app.text_input if x.label=="Tên sự kiện").set_value("Họp cổ đông kiểm thử")
        next(x for x in app.button if x.label=="Lưu sự kiện").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.session_state["investor_profile"]["manual_events"]),1)
        next(x for x in app.button if x.label=="Tính so sánh").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.session_state["bond_comparison_result"][1]),10)


if __name__=="__main__": unittest.main()
