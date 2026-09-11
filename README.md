# Stock News AI Dashboard V4

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
Production: https://stock-news-nhom.streamlit.app

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
