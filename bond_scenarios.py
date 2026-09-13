"""Exact parallel-yield repricing for regular fixed-coupon bonds."""
import math
import pandas as pd


def validate_bond(bond):
    b = dict(bond)
    for key in ("face_value", "coupon_rate", "years", "payments_per_year", "required_yield", "market_price"):
        try:
            b[key] = float(b[key])
        except (ValueError, TypeError, KeyError):
            raise ValueError("Thông số trái phiếu phải là số.") from None
        if not math.isfinite(b[key]):
            raise ValueError("Thông số trái phiếu phải hữu hạn.")
    if b["face_value"] <= 0 or b["market_price"] <= 0 or not 0 < b["years"] <= 100:
        raise ValueError("Mệnh giá, giá thị trường phải dương; kỳ hạn trong (0,100] năm.")
    if b["coupon_rate"] < 0 or b["payments_per_year"] not in (1,2,4,12):
        raise ValueError("Coupon không âm; tần suất 1, 2, 4 hoặc 12 kỳ/năm.")
    n = b["years"] * b["payments_per_year"]
    if n < 1 or not math.isclose(n, round(n), abs_tol=1e-8):
        raise ValueError("Mô phỏng cần số kỳ coupon nguyên. Ví dụ trả nửa năm dùng kỳ hạn 0,5; 1; 1,5 năm…")
    if b["required_yield"] <= -b["payments_per_year"]:
        raise ValueError("Lợi suất mỗi kỳ phải lớn hơn -100%.")
    b["code"] = str(b.get("code", "Trái phiếu"))[:80]
    return b


def price_at_yield(bond, annual_yield):
    b = validate_bond(bond)
    factor = 1 + annual_yield / b["payments_per_year"]
    if not math.isfinite(annual_yield) or factor <= 0:
        raise ValueError("Lợi suất kịch bản không hợp lệ.")
    n = round(b["years"] * b["payments_per_year"])
    coupon = b["face_value"] * b["coupon_rate"] / b["payments_per_year"]
    try:
        price = sum((coupon + (b["face_value"] if t == n else 0)) * math.exp(-t * math.log(factor)) for t in range(1,n+1))
    except OverflowError:
        raise ValueError("Lợi suất/kỳ hạn quá cực đoan để tính giá hữu hạn.") from None
    if not math.isfinite(price) or price <= 0:
        raise ValueError("Giá kịch bản không hữu hạn.")
    return price


def scenario_table(bond, shocks=(-1,-.5,0,.5,1)):
    b = validate_bond(bond)
    base = price_at_yield(b, b["required_yield"])
    rows = []
    for shock in sorted(set(shocks)):
        y = b["required_yield"] + shock/100
        price = price_at_yield(b,y)
        rows.append({"Trái phiếu": b["code"], "Thay đổi lợi suất (điểm %)": shock,
                     "Lợi suất (%/năm)": y*100, "Giá lý thuyết": price,
                     "Chênh lệch giá": price-base, "Biến động giá (%)": (price/base-1)*100,
                     "Giá / 100 mệnh giá": price/b["face_value"]*100})
    return pd.DataFrame(rows)
