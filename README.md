# Stock News AI — Investor Workspace

Ứng dụng: https://stock-news-kngan.streamlit.app · Repo: `1karenza/stock-news-ai`.

## Năm tính năng dành cho nhà đầu tư

1. **Danh sách & tin lưu**: tạo/cập nhật tối đa 20 nhóm cổ phiếu, áp dụng nhóm từ
   thanh bên; đánh dấu đã đọc/chưa đọc, lưu tối đa 100 bài, lọc tin mới từ lần xem
   trước. Hồ sơ và 60 tin gần nhất lưu trong localStorage của trình duyệt, không
   dùng file hồ sơ chung trên server. JSON sao lưu dùng để chuyển thiết bị.
2. **Sự kiện**: lọc theo mã và loại sự kiện; gom các tiêu đề gần trùng có cùng mã,
   số liệu và thời gian gần nhau. Luôn giữ các bài nguồn để đối chiếu.
3. **Lịch doanh nghiệp**: lịch tháng tách ngày chốt quyền, ngày thanh toán, họp
   cổ đông và các mốc khác. Chỉ đưa ngày đầy đủ có bằng chứng vào lịch; mốc thiếu
   năm cần kiểm tra. Có thêm/sửa/xóa mốc của bạn, xuất CSV và ICS. File ICS nhập
   một lần vào ứng dụng lịch, không tự đồng bộ hay tự nhắc qua email.
4. **Giá & tin**: tải lịch sử giá ngày qua Yahoo Finance với mã `<TICKER>.VN`,
   biểu đồ giá/khối lượng và mốc tin. Nguồn có thể trễ, thiếu mã hoặc tạm ngừng;
   có CSV thay thế (date,close,volume; YYYY-MM-DD; VND; số không có dấu hàng nghìn).
   Hiển thị thời điểm tải, phiên cuối, nguồn và trạng thái điều chỉnh. Không dùng
   dữ liệu này để đặt lệnh; tin cùng ngày không chứng minh nguyên nhân biến động.
5. **Bond Valuation**: giữ công cụ cũ, thêm tính lại giá theo ±0,5/±1 điểm phần
   trăm và kịch bản riêng; so sánh 2–3 trái phiếu, chuẩn hóa theo % biến động và
   100 mệnh giá, xuất CSV. Dùng kỳ coupon đều, không mô phỏng rủi ro vỡ nợ.

LocalStorage bị xóa hoặc dùng trình duyệt khác sẽ không còn hồ sơ cũ nếu chưa
khôi phục JSON. Trình duyệt chặn lưu vẫn dùng được phiên hiện tại và xuất JSON.
Ngày lịch từ báo chí là dữ liệu cần đối chiếu; tên miền chính thức không đồng
nghĩa sự kiện đã được xác minh độc lập. Không có tự quét theo giờ trong bản này.

## Kiểm tra

Yêu cầu Streamlit >=1.63. Chạy `python -m pip install -r requirements.txt`, rồi:

```powershell
python -m unittest discover -s tests -v
python -m streamlit run app.py
```

Các module mới: `investor_profile.py`, `investor_events.py`, `event_views.py`,
`market_prices.py`, `price_view.py`, `bond_scenarios.py`, `bond_scenario_view.py`.
Khi deploy phải commit đủ các module này và `requirements.txt` cùng `app.py`.

## Tab 1 — Stock News
- Quét tin theo mã cổ phiếu.
- Đọc/tóm tắt nội dung bài gốc khi có thể.
- Giữ nút Đọc tin gốc.
- Trích thông tin trái phiếu nếu bài có đề cập.

## Tab 2 — Bond Valuation
- Nhập mã/tên trái phiếu.
- Mệnh giá.
- Coupon rate.
- Thời gian còn lại.
- Tần suất trả coupon.
- Giá thị trường.
- Required yield.

App tính:
- Giá lý thuyết.
- YTM.
- Premium / Par / Discount.
- Macaulay Duration.
- Modified Duration.
- Bảng cash flow và PV từng kỳ.
- Xuất CSV.

Có 3 bộ dữ liệu mẫu để test ngay.

## Chạy
Double-click START_HERE_WINDOWS.bat

## GitHub và deployment

Folder local được liên kết với https://github.com/1karenza/stock-news-ai,
nhánh `main`. Streamlit Cloud dùng file `app.py` tại root repo.
Production: https://stock-news-kngan.streamlit.app

Sau khi sửa code, chạy thử bằng `streamlit run app.py` hoặc
`START_HERE_WINDOWS.bat`. Mở terminal tại folder này rồi chạy:

```powershell
git status
git diff
git add app.py news_content.py news_fetch.py assets requirements.txt README.md .gitignore .streamlit/config.toml
git diff --cached
git commit -m "Update dashboard"
git push origin main
```

Nếu thêm file mới, dùng `git add <file>` để đưa file đó vào commit.
Git có thể yêu cầu đăng nhập GitHub trong lần push đầu tiên.
Nếu Git yêu cầu danh tính commit, cấu hình `git config user.name "Tên của bạn"`
và `git config user.email "Email GitHub của bạn"` rồi commit lại.

Streamlit Cloud tự redeploy sau khi push. Kiểm tra production URL sau đó;
nếu chưa cập nhật, dùng menu quản lý app để Reboot app.
Việc lưu file local không tự commit hoặc push.

Nếu GitHub có commit mới, dùng `git pull --rebase origin main` sau khi đã
commit thay đổi local, giải quyết conflict nếu có, rồi push lại. Không force push.

Không commit `.venv`, `.env`, API keys hoặc `.streamlit/secrets.toml`.
API key production được cấu hình trong Streamlit App Settings / Secrets.

## Giao diện editorial

Style chung nằm trong `assets/editorial.css`; phải commit cả folder `assets`
khi deploy. Theme native của Streamlit nằm trong `.streamlit/config.toml`.
League Spartan tải từ Google Fonts, với sans-serif dự phòng khi mất kết nối.
Giao diện hỗ trợ màn hình nhỏ, focus bàn phím và `prefers-reduced-motion`.
