# Stock News AI — Investor Workspace

Ứng dụng: https://stock-news-kngan.streamlit.app · GitHub: `1karenza/stock-news-ai`.

## Bốn tab

1. **I / Stock News**: quét tin theo danh sách mã, đọc tóm tắt và tiêu đề bài báo,
   mở nguồn, lưu tin và đánh dấu đã đọc.
2. **II / Lịch doanh nghiệp**: tự tải các mốc của mã cổ phiếu đang phân tích,
   gồm lịch sử cổ tức, quyền cổ đông, đại hội và thông báo doanh nghiệp.
   Ngày giao dịch không hưởng quyền, đăng ký cuối cùng, thực hiện và công bố
   được phân biệt; mặc định mở tháng gần nhất có dữ liệu.
3. **III / Giá cổ phiếu**: tự tải biểu đồ giá và khối lượng, cơ cấu cổ đông,
   lịch sử cổ tức, phát hành thêm và thưởng cổ phiếu. Không ghép tin vào biểu đồ.
4. **IV / Định giá**: P/E, P/B, vốn hóa từ nguồn công khai; đối chiếu tối đa
   5 mã có cùng mã nhóm ngành, tham chiếu tương đối và báo cáo giá mục tiêu.

Nhập mã ở thanh trái; chọn **Mã đang phân tích (II–IV)** và khoảng biểu đồ.
Các tab II–IV tự tải, không cần bấm quét. Tin ở tab I dùng **Quét và phân tích**.
Nút **Xuất report 4 tabs · HTML** ở thanh trái tải báo cáo cùng dữ liệu hiện tại,
có biểu đồ nhúng và các bảng. Mở file bằng trình duyệt; Ctrl+P để lưu PDF.
Báo cáo ghi rõ phạm vi: tin đã quét cho danh sách mã, tab II–IV cho mã đang chọn.

## Nguồn và giới hạn

- Google News RSS và bài gốc cho tin tức; nếu bài gốc không đọc được, app chỉ
  sử dụng nội dung nguồn có sẵn, không tự tạo chi tiết.
- CafeF cho danh sách cổ đông, số cổ phiếu, tỷ lệ và ngày cập nhật từng công bố.
  Biểu đồ hiện 12 cổ đông lớn nhất và phần còn lại; không vẽ khi tổng vượt 100%.
  Chưa có tỷ lệ sở hữu nước ngoài xác minh được; không suy ra từ room ngoại.
- Simplize cho hồ sơ, quyền cổ đông, chỉ số và báo cáo phân tích.
  Lịch sử giới hạn ở bản ghi nguồn trả về, tối đa 100 sự kiện quyền và các
  thông báo gần đây. Ngày công bố không thay thế ngày thực hiện; ngày đã qua
  không tự chứng minh sự kiện hoàn tất.
- Yahoo Finance (`<TICKER>.VN`) cho giá đóng cửa và khối lượng ngày, đơn vị VND.
  Chưa xác minh điều chỉnh chia tách; phiên đang giao dịch có thể chưa hoàn tất.
- Dữ liệu doanh nghiệp được cache 5 phút. Nút **Làm mới dữ liệu doanh nghiệp**
  cho phép thử tải lại. Nguồn lỗi hoặc thiếu được ghi rõ, không thay bằng số giả.
- P/E dùng TTM, P/B dùng quý gần nhất. Tham chiếu tương đối do app tính bằng
  EPS/BVPS nhân trung vị bội số của ít nhất hai mã hợp lệ, loại mã đang tra.
  Giá mục tiêu của tổ chức phân tích được trình bày riêng kèm ngày và nguồn.
  Dữ liệu không phải báo giá trực tiếp hay khuyến nghị đầu tư.

## Chạy và kiểm tra

```powershell
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python -m streamlit run app.py
```

Cũng có thể mở `START_HERE_WINDOWS.bat`.
Các module cho bốn tab: `equity_data.py`, `equity_views.py`, `equity_report.py`,
cùng các module tin tức, hồ sơ và giá đã có. Cần commit đủ các file phụ thuộc.

## GitHub và triển khai

Repo `1karenza/stock-news-ai`, nhánh `main`, entry `app.py` tại root.
Streamlit Cloud tự redeploy sau khi push lên main. Lưu file local không tự push.

```powershell
git status
git diff
git add <cac-file-da-sua>
git diff --cached
git commit -m "Update dashboard"
git push origin main
```

Không commit `.venv`, `.env`, API keys hoặc `.streamlit/secrets.toml`.
App chạy không cần OpenAI key; nếu bật AI, thêm key trong Streamlit Secrets.
Theme nằm ở `.streamlit/config.toml`, style ở `assets/editorial.css`.
League Spartan có font dự phòng; giao diện hỗ trợ bàn phím và reduced motion.
