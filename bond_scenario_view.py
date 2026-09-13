import pandas as pd
import streamlit as st
from bond_scenarios import scenario_table, validate_bond, comparison_conclusions


def render_bond_scenarios(current_bond):
    st.divider()
    st.markdown("### Nếu lợi suất thay đổi?")
    st.caption("Tính lại toàn bộ dòng tiền với các mức lợi suất mới. Kịch bản 0 là giá lý thuyết theo lợi suất bạn nhập, không phải giá thị trường.")
    shock = st.slider("Kịch bản riêng — thay đổi lợi suất (điểm phần trăm)", -3.0, 3.0, 0.5, .1, key="bond_shock")
    try:
        table = scenario_table(current_bond, (-1,-.5,0,.5,1,round(shock,1)))
        row = table.loc[table["Thay đổi lợi suất (điểm %)"] == round(shock,1)].iloc[0]
        c1,c2,c3 = st.columns(3)
        c1.metric("Lợi suất kịch bản", f'{row["Lợi suất (%/năm)"]:.2f}%')
        c2.metric("Giá sau thay đổi", f'{row["Giá lý thuyết"]:,.0f}')
        c3.metric("So với giá cơ sở", f'{row["Biến động giá (%)"]:+.2f}%')
        st.line_chart(table, x="Lợi suất (%/năm)", y="Giá lý thuyết", color="#88465f")
        st.dataframe(table.round(3), hide_index=True, width="stretch")
        st.download_button("Xuất kịch bản CSV", table.to_csv(index=False).encode("utf-8-sig"), "bond-scenarios.csv", "text/csv")
    except ValueError as exc:
        st.warning(str(exc))
    st.markdown("#### So sánh trái phiếu dưới cùng kịch bản")
    st.caption("Hai dòng đầu là ví dụ minh họa có thể sửa. Dùng nút bên dưới để đưa trái phiếu đang tính vào bảng. Tối đa 3 trái phiếu; biểu đồ dùng % biến động để so sánh các mệnh giá khác nhau.")
    columns = {"code":"Tên", "face_value":"Mệnh giá", "coupon_rate":"Coupon (%/năm)",
               "years":"Kỳ hạn (năm)", "payments_per_year":"Kỳ/năm", "required_yield":"Lợi suất cơ sở (%)", "market_price":"Giá thị trường"}
    if "compare_bonds" not in st.session_state:
        st.session_state.compare_bonds = pd.DataFrame([
            {"Tên":"Ví dụ A", "Mệnh giá":100000., "Coupon (%/năm)":8., "Kỳ hạn (năm)":5., "Kỳ/năm":2,
             "Lợi suất cơ sở (%)":9., "Giá thị trường":96500.},
            {"Tên":"Ví dụ B", "Mệnh giá":100000., "Coupon (%/năm)":10., "Kỳ hạn (năm)":3., "Kỳ/năm":1,
             "Lợi suất cơ sở (%)":8., "Giá thị trường":104500.}])
    st.session_state.setdefault("compare_version",0)
    if st.button("Thêm trái phiếu đang tính vào bảng"):
        try:
            b = validate_bond(current_bond)
            if len(st.session_state.compare_bonds) >= 3:
                st.warning("Bảng đã có 3 dòng. Xóa một dòng trước khi thêm.")
            else:
                new = {label:b[key]*100 if key in ("coupon_rate","required_yield") else b[key] for key,label in columns.items()}
                st.session_state.compare_bonds = pd.concat([st.session_state.compare_bonds,pd.DataFrame([new])], ignore_index=True)
                st.session_state.compare_version += 1
        except ValueError as exc:
            st.warning(str(exc))
    edited = st.data_editor(st.session_state.compare_bonds, num_rows="dynamic", hide_index=True, width="stretch",
                            key=f'comparison_editor_{st.session_state.compare_version}',
                            column_config={"Kỳ/năm":st.column_config.SelectboxColumn(options=[1,2,4,12], required=True)})
    st.session_state.compare_bonds = edited
    if st.button("Tính so sánh", type="primary"):
        try:
            if not 2 <= len(edited) <= 3:
                raise ValueError("Nhập từ 2 đến 3 trái phiếu để so sánh.")
            tables=[]
            for i,row in edited.iterrows():
                b = {key:row[label]/100 if key in ("coupon_rate","required_yield") else row[label] for key,label in columns.items()}
                b["code"] = f'{i+1}. {b["code"]}'
                tables.append(scenario_table(b))
            st.session_state.bond_comparison_result = (edited.to_json(), pd.concat(tables, ignore_index=True))
        except (ValueError, TypeError) as exc:
            st.error(str(exc))
    result = st.session_state.get("bond_comparison_result")
    if result and result[0] == edited.to_json():
        comparison = result[1]
        st.line_chart(comparison, x="Thay đổi lợi suất (điểm %)", y="Biến động giá (%)", color="Trái phiếu")
        st.markdown("#### Kết luận sơ bộ")
        for conclusion in comparison_conclusions(comparison):
            st.write(conclusion)
        st.dataframe(comparison.round(3), hide_index=True, width="stretch")
        st.download_button("Xuất bảng so sánh", comparison.to_csv(index=False).encode("utf-8-sig"), "bond-comparison.csv", "text/csv")
    st.caption("Chỉ áp dụng coupon cố định, các kỳ thanh toán đều và dịch chuyển lợi suất song song. Không mô phỏng vỡ nợ, thuế, lãi tích lũy hoặc mua lại trước hạn.")
