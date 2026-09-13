"""Reference daily prices, strict CSV import and news/session alignment."""
from io import BytesIO
import re
import numpy as np
import pandas as pd
import requests


class PriceUnavailable(ValueError):
    pass


def validate_prices(frame):
    if not {"date", "close", "volume"}.issubset(frame.columns):
        raise PriceUnavailable("CSV cần các cột date, close, volume.")
    frame = frame[["date", "close", "volume"]].copy()
    if not 2 <= len(frame) <= 10000:
        raise PriceUnavailable("Cần từ 2 đến 10.000 dòng giá.")
    if not pd.api.types.is_datetime64_any_dtype(frame["date"]):
        if not frame["date"].astype(str).str.fullmatch(r"\d{4}-\d{2}-\d{2}").all():
            raise PriceUnavailable("Ngày CSV cần định dạng YYYY-MM-DD để tránh nhầm ngày/tháng.")
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    for field in ("close", "volume"):
        frame[field] = pd.to_numeric(frame[field], errors="coerce")
    if frame.isna().any().any() or not np.isfinite(frame[["close", "volume"]].to_numpy()).all():
        raise PriceUnavailable("Ngày hoặc số không hợp lệ. Dùng ngày YYYY-MM-DD, số không có dấu phân cách hàng nghìn.")
    if frame["date"].duplicated().any() or (frame.close <= 0).any() or (frame.volume < 0).any():
        raise PriceUnavailable("Ngày không được trùng; giá phải dương và khối lượng không âm.")
    return frame.sort_values("date").reset_index(drop=True)


def import_prices(data):
    if len(data) > 2_000_000:
        raise PriceUnavailable("CSV tối đa 2 MB.")
    try:
        frame = pd.read_csv(BytesIO(data), encoding="utf-8-sig", sep=None, engine="python")
        return validate_prices(frame)
    except (ValueError, UnicodeError, pd.errors.ParserError) as exc:
        raise PriceUnavailable(str(exc)) from exc


def fetch_prices(ticker, period="3mo"):
    if not re.fullmatch(r"[A-Z0-9]{2,10}", ticker) or period not in {"1mo", "3mo", "6mo", "1y"}:
        raise PriceUnavailable("Mã hoặc khoảng giá không hợp lệ.")
    try:
        response = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}.VN",
                                params={"range": period, "interval": "1d"},
                                headers={"User-Agent": "Mozilla/5.0"}, timeout=(5,15))
        response.raise_for_status()
        result = response.json()["chart"]["result"][0]
        if result["meta"].get("currency") != "VND":
            raise PriceUnavailable("Nguồn giá không trả đơn vị VND cho mã này.")
        quote = result["indicators"]["quote"][0]
        frame = pd.DataFrame({"date": pd.to_datetime(result["timestamp"], unit="s", utc=True).tz_convert("Asia/Ho_Chi_Minh").tz_localize(None).normalize(),
                              "close": quote["close"], "volume": quote["volume"]}).dropna()
        frame = validate_prices(frame)
        return frame, {"source": "Yahoo Finance", "symbol": ticker+".VN", "currency": "VND",
                       "fetched": pd.Timestamp.now(tz="Asia/Ho_Chi_Minh").strftime("%d/%m/%Y %H:%M"),
                       "adjustment": "Giá close do nguồn cung cấp; không dùng adjusted close. Chưa xác minh điều chỉnh chia tách."}
    except (requests.RequestException, ValueError, KeyError, TypeError, IndexError) as exc:
        raise PriceUnavailable("Chưa lấy được giá mã này. Bạn có thể thử lại hoặc tải CSV của mình.") from exc


def align_news(prices, articles, ticker):
    rows = []
    for item in articles:
        if ticker not in item.get("tickers", [item.get("ticker")]):
            continue
        stamp = pd.to_datetime(item.get("published_dt"), utc=True, errors="coerce")
        if pd.isna(stamp):
            continue
        day = stamp.tz_convert("Asia/Ho_Chi_Minh").tz_localize(None).normalize()
        if day < prices.date.min() or day > prices.date.max():
            continue
        # Daily chart: same day if traded, otherwise next observed session.
        following = prices.loc[(prices.date >= day) & (prices.volume > 0)]
        if following.empty:
            continue
        bar = following.iloc[0]
        rows.append({"date": bar.date, "published_date": day.strftime("%Y-%m-%d"), "close": bar.close,
                     "title": item["title"], "source": item.get("source", ""), "url": item.get("url", "")})
    return pd.DataFrame(rows, columns=["date", "published_date", "close", "title", "source", "url"])
