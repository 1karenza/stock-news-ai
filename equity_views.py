"""Four-tab equity workspace, using one ticker-bound snapshot for UI and report."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date
import altair as alt
import pandas as pd
import streamlit as st
from equity_data import (fetch_company, fetch_ownership, fetch_events, comparable_rows,
                         company_events, relative_valuation, EquityUnavailable, source_date, text_only, ownership_chart_rows)
from market_prices import fetch_prices, PriceUnavailable
from investor_events import calendar_html, safe_url, stable_id


@st.cache_data(ttl=300, show_spinner=False)
def load_equity(ticker, period):
    bundle = {"ticker":ticker,"period":period,"errors":[],"company":{},"ownership":[],
              "events":[],"peers":[],"relative":[],"prices":pd.DataFrame(),"price_meta":{}}
    with ThreadPoolExecutor(max_workers=4) as pool:
        jobs = {"company":pool.submit(fetch_company,ticker), "ownership":pool.submit(fetch_ownership,ticker),
                "events_raw":pool.submit(fetch_events,ticker), "price":pool.submit(fetch_prices,ticker,period)}
        for name, job in jobs.items():
            try:
                value = job.result()
                if name=="price":
                    bundle["prices"], bundle["price_meta"] = value
                else:
                    bundle[name] = value
            except (EquityUnavailable, PriceUnavailable) as exc:
                bundle["errors"].append(f"{name}: {exc}")
    company = bundle["company"]
    if company:
        company["events"] = bundle.pop("events_raw", [])
        bundle["events"] = company_events(company)
        bundle["peers"], unavailable = comparable_rows(company)
        bundle["relative"] = relative_valuation(bundle["peers"])
        if unavailable:
            bundle["errors"].append("Chưa tải được mã so sánh: " + ", ".join(unavailable))
    elif bundle.get("events_raw"):
        bundle["events"] = company_events({"ticker":ticker,"source_url":f"https://simplize.vn/co-phieu/{ticker}","events":bundle.pop("events_raw")})
    return bundle


def data_table(rows):
    if not rows:
        st.info("Nguồn chưa cung cấp dữ liệu cho mục này.")
        return
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch",
                 column_config={"Nguồn":st.column_config.LinkColumn("Nguồn",display_text="Mở nguồn")})


def provenance(bundle):
    c = bundle["company"]
    if c:
        st.caption(f'Simplize · ngày cập nhật trang: {c["summary"].get("analysisUpdated", "chưa rõ")} · tải lúc {c["fetched"]}. Chỉ số có thể khác kỳ cập nhật; không phải báo giá trực tiếp.')
        st.link_button("Đối chiếu hồ sơ nguồn", c["source_url"])


def render_equity_prices(bundle):
    ticker, frame = bundle["ticker"], bundle["prices"]
    st.markdown(f"### Giá cổ phiếu {ticker}")
    st.caption("Tự tải theo mã và khoảng thời gian ở thanh bên trái.")
    if not frame.empty:
        meta = bundle["price_meta"]
        st.caption(f'{meta["source"]} · VND/cổ phiếu · phiên cuối {frame.date.max():%d/%m/%Y} · tải lúc {meta["fetched"]} (UTC+7)')
        st.caption(meta["adjustment"])
        st.altair_chart(alt.Chart(frame).mark_line(color="#88465f").encode(
            x=alt.X("date:T", title="Ngày"), y=alt.Y("close:Q", title="Giá (đ/CP)",scale=alt.Scale(zero=False)),
            tooltip=[alt.Tooltip("date:T",title="Ngày"),alt.Tooltip("close:Q",title="Giá",format=",.0f")]).properties(height=320).interactive(),width="stretch")
        st.altair_chart(alt.Chart(frame).mark_bar(color="#e4a4bd").encode(
            x=alt.X("date:T",title=None),y=alt.Y("volume:Q",title="Khối lượng (CP)"),tooltip=["date:T","volume:Q"]).properties(height=110),width="stretch")
    else:
        st.info("Chưa tải được lịch sử giá mã này. Các phần thông tin doanh nghiệp bên dưới vẫn có thể xem.")
    st.markdown("### Cơ cấu sở hữu · CafeF")
    ownership = bundle["ownership"]
    chart_rows = ownership_chart_rows(ownership)
    if chart_rows:
        st.altair_chart(alt.Chart(pd.DataFrame(chart_rows)).mark_arc(innerRadius=85).encode(
            theta=alt.Theta("Tỷ lệ (%):Q"),color=alt.Color("Cổ đông:N",legend=alt.Legend(orient="bottom",columns=1)),
            tooltip=["Cổ đông:N",alt.Tooltip("Tỷ lệ (%):Q",format=".2f")]).properties(height=360),width="stretch")
    elif ownership:
        st.info("Các công bố có thể khác ngày hoặc chồng lặp; tổng tỷ lệ vượt 100% nên chỉ hiển thị bảng gốc.")
    data_table(ownership)
    st.caption("Nguồn CafeF · ngày cập nhật của từng cổ đông nằm trong bảng. Biểu đồ hiển thị 12 cổ đông lớn nhất; phần còn lại = 100% trừ các tỷ lệ hiển thị. Các công bố có thể khác ngày, không phải ảnh chụp sở hữu cùng thời điểm. Chưa có tỷ lệ sở hữu nước ngoài xác minh được từ nguồn này; room ngoại không được dùng thay thế.")
    provenance(bundle)


def render_equity_calendar(bundle):
    st.markdown(f'### Lịch doanh nghiệp · {bundle["ticker"]}')
    st.caption("Tự tải lịch sử từ nguồn doanh nghiệp, không phụ thuộc việc quét tin. Mỗi mốc ghi rõ loại ngày; ngày công bố không thay thế ngày thực hiện.")
    rows = bundle["events"]
    months = sorted({r["Ngày"][:7] for r in rows}, reverse=True)
    if not months:
        st.info("Nguồn chưa có lịch cho mã này.")
        return
    month = st.selectbox("Tháng có sự kiện", months, key="equity_month_"+bundle["ticker"])
    year, m = map(int,month.split("-"))
    shown = [r for r in rows if r["Ngày"].startswith(month)]
    calendar_events = [{"id":stable_id(r["Ngày"],r["Sự kiện"],r["Loại ngày"]),"event_date":r["Ngày"],
                        "title":r["Nhóm"] + " · " + r["Loại ngày"],"milestone":"manual",
                        "tickers":[r["Mã"]],"status":"announced"} for r in shown]
    st.markdown(calendar_html(year,m,calendar_events),unsafe_allow_html=True)
    data_table(shown)
    st.markdown("### Những mốc đã qua")
    historical = [r for r in rows if r["Ngày"]<=date.today().isoformat()]
    data_table(historical)
    st.caption("Lịch sử giới hạn trong dữ liệu công khai nguồn hiện trả về (tối đa 100 sự kiện quyền, cộng thông báo gần đây). Ngày đã qua không tự xác nhận sự kiện đã hoàn tất.")
    provenance(bundle)
    return month


def render_equity_valuation(bundle):
    st.markdown(f'### Định giá · {bundle["ticker"]}')
    peers = bundle["peers"]
    if not peers:
        st.info("Chưa có chỉ số định giá từ nguồn cho mã này.")
        return
    target = peers[0]
    st.caption(f'Ngành: {target["Ngành"]} · Dữ liệu Simplize. P/E dùng lợi nhuận 12 tháng gần nhất (TTM); P/B dùng giá trị sổ sách quý gần nhất (FQ).')
    a,b,c = st.columns(3)
    for box,key in [(a,"P/E (TTM)"),(b,"P/B (FQ)"),(c,"Vốn hóa (tỷ đồng)")]:
        box.metric(key, f'{target[key]:,.2f}' if target[key] is not None else "Chưa có")
    st.markdown("#### So sánh doanh nghiệp cùng ngành")
    st.caption("Tối đa 10 mã đối chiếu ngoài mã đang tra, ưu tiên vốn hóa lớn trong danh sách ngành nguồn trả về; xác minh cùng mã nhóm ngành và xếp theo vốn hóa. Ngành ít mã có thể không đủ 10; đây không phải xếp hạng chất lượng đầu tư.")
    data_table(peers)
    chart_rows = [{"Mã":r["Mã"],"Chỉ số":k,"Giá trị":r[k]} for r in peers for k in ("P/E (TTM)","P/B (FQ)") if r[k] is not None and r[k]>0]
    if chart_rows:
        st.altair_chart(alt.Chart(pd.DataFrame(chart_rows)).mark_bar().encode(x="Mã:N", y="Giá trị:Q",color=alt.Color("Chỉ số:N",scale=alt.Scale(range=["#88465f","#e4a4bd"])),column="Chỉ số:N",tooltip=["Mã:N","Chỉ số:N","Giá trị:Q"]),width="stretch")
    st.markdown("#### Tham chiếu theo mặt bằng nhóm")
    if bundle["relative"]:
        data_table(bundle["relative"])
        st.caption("App tính EPS × trung vị P/E hoặc BVPS × trung vị P/B của các mã đối chiếu, loại mã đang tra và bội số không dương; cần ít nhất 2 mã hợp lệ. Đây là phép tính tương đối từ dữ liệu nguồn, không phải giá mục tiêu do tổ chức phân tích công bố.")
    else:
        st.info("Chưa đủ ít nhất 2 mã có bội số dương hoặc EPS/BVPS của mã đang tra không dương để tính tham chiếu tương đối.")
    st.markdown("#### Giá mục tiêu từ báo cáo phân tích")
    reports=[]
    for r in bundle["company"].get("analysisReports",[]):
        reports.append({"Ngày báo cáo":source_date(r.get("issueDate")),"Đơn vị":r.get("source",""),
                        "Giá mục tiêu (đ/CP)":r.get("targetPrice"),"Tiêu đề":text_only(r.get("title")),"Nguồn":safe_url(r.get("attachedLink"))})
    data_table(reports)
    st.caption("Giá mục tiêu phản ánh quan điểm và giả định tại ngày báo cáo; có thể đã cũ. P/E, P/B thấp chưa đủ để kết luận cổ phiếu rẻ.")
    provenance(bundle)
