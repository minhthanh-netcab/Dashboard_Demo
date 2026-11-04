# Câu hỏi mở & giả định

Cập nhật file này khi một mục được trả lời. Mục **Giả định Phase 1** là những gì code hiện đang làm, **không phải** quy định đã được công ty xác nhận.

## A. Giả định đang áp dụng trong code Phase 1

| # | Giả định | Vị trí trong code | Cần ai xác nhận |
|---|---|---|---|
| A1 | Thành viên dự án chỉ thấy dự án mình tham gia hoặc quản lý; PM thấy tất cả | `projects/permissions.py` | Trưởng phòng Dự án |
| A2 | Mọi PM quản lý được mọi dự án (chưa giới hạn theo dự án mình phụ trách) | `permissions.can_manage_project` | Trưởng phòng Dự án |
| A3 | Trường tài chính (giá trị bán, giá trị HĐ, đơn giá, số tiền đề nghị) chỉ PM và FINANCE_VIEWER thấy; SALES_VIEWER cũng **không** thấy giá trị bán | `accounts/roles.can_view_finance` | Ban giám đốc / Kế toán |
| A4 | Chỉ PM tạo/sửa đề nghị mua hàng/thanh toán và ghi nhận trạng thái; thành viên chỉ xem | `procurement`, `payments` views | Phòng Dự án |
| A5 | Ở Phase 1, PM nhập hồ sơ bàn giao thay cho Sales | `handover_views.HandoverCreateView` | Sales + Dự án |
| A6 | Trạng thái tiếp nhận bàn giao: Chờ tiếp nhận / Cần bổ sung / Chấp nhận / Từ chối; chỉ tạo dự án từ bàn giao đã chấp nhận; 1 bàn giao → tối đa 1 dự án | `projects/models.py`, `services.py` | Sales + Dự án |
| A7 | Trạng thái dự án, task, mốc, vấn đề, hợp đồng là nhãn demo | `projects/models.py` (TextChoices) | Phòng Dự án |
| A8 | Không có công thức tiến độ; hiển thị % gần nhất do người dùng báo cáo | `ProgressUpdate`, `latest_project_percent` | Trưởng phòng Dự án |
| A9 | Timeline = ngày kế hoạch của dự án + danh sách mốc; chưa có phê duyệt hay phiên bản hoá timeline | `Project`, `ProjectMilestone` | Trưởng phòng Dự án |
| A10 | Tài liệu chỉ lưu metadata và vị trí file, không upload | `ProjectDocument` | Phòng Dự án / IT |
| A11 | Mã dự án dạng `PRJ-YYYY-NNN`; đề nghị dạng `PR-…` và `PAY-…` khi để trống | `core/utils.next_sequential_code` | Phòng Dự án / Kế toán |
| A12 | Trạng thái mua hàng/thanh toán là nhãn tự do + nguồn; không mã hoá chuỗi phê duyệt | `core.StatusEntryBase` | Dự án + Kế toán |
| A13 | Sức khoẻ dự án (RAG): **Nguy cơ cao** = quá ngày kết thúc kế hoạch, có vấn đề Nghiêm trọng đang mở, hoặc ≥ 3 task quá hạn; **Cần theo dõi** = có task quá hạn, mốc trễ hạn, task vướng mắc hoặc vấn đề Cao đang mở; còn lại **Ổn định**. Đề nghị mua hàng/thanh toán "chờ cập nhật" = không có trạng thái mới trong 7 ngày; mốc "sắp đến hạn" = 14 ngày; task "cần cập nhật" = đang làm và không có cập nhật trong 7 ngày | `dashboard/overview.py` | Trưởng phòng Dự án |
| A14 | Giao diện tiếng Việt; tiền tệ mặc định VND | templates, models | Nhóm phát triển |
| A15 | Thành viên chỉ chọn được task của mình khi gửi cập nhật tiến độ; chỉ người báo cáo, người xử lý hoặc PM sửa được vấn đề | `ProgressUpdateForm`, `permissions.can_edit_issue` | Phòng Dự án |
| A16 | Opportunity thắng → tự tạo bàn giao "Chờ tiếp nhận"; quan hệ 1 Opportunity ↔ 1 bàn giao | `sales/services._ensure_pending_handover` | Sales + Dự án |
| A17 | OplaCRM được cập nhật trường `committed_*` của bàn giao chỉ khi bàn giao còn Chờ tiếp nhận / Cần bổ sung; sau đó chỉ cảnh báo | `sales/services.py` | Sales + Dự án |
| A18 | Chỉ SYSTEM_ADMIN chạy đồng bộ từ giao diện; PM chỉ xem trạng thái | `roles.can_manage_integrations` | IT / Ban giám đốc |
| A19 | Chỉ FINANCE_VIEWER được nhập file CSV tài chính | `roles.can_import_finance` | Kế toán |
| A20 | Mẫu CSV công nợ/tồn kho là **đề xuất** của nhóm (cột trong `docs/samples/`), UTF-8, dấu `.` thập phân, không phân cách hàng nghìn | `finance/csv_import.py` | Kế toán |
| A21 | Số dư công nợ và tồn kho lấy dạng snapshot đầy đủ; lô mới nhất (API hoặc CSV) là lô "đang hiệu lực" | `finance/services.store_snapshot` | Kế toán |
| A22 | Record chuẩn hoá (`integrations/records.py`) chứa các trường tối thiểu do nhóm chọn; có thể phải bổ sung khi biết schema thật | `integrations/records.py` | Nhóm phát triển |

## B. Nghiệp vụ dự án

- Trường nào bắt buộc trong hồ sơ bàn giao từ Sales?
- Ai tiếp nhận/chấp nhận bàn giao?
- Trạng thái dự án chính thức và tiêu chí hoàn thành là gì?
- Ai sở hữu timeline, và timeline có cần phê duyệt không?
- Tiến độ task và tiến độ tổng thể dự án được tính thế nào?
- Quy trình mua hàng: các bước, ngưỡng, cách xử lý khi bị từ chối? (ghi chú phỏng vấn: Sales → Sales Manager → PM → Project Director → MISA, *chưa xác nhận*)
- Quy trình thanh toán: các bước và vai trò giám đốc? (ghi chú phỏng vấn: Project Director → Kế toán → Giám đốc → MISA, *chưa xác nhận*)
- Ai soạn, xem xét và ký hợp đồng với khách hàng?
- Giao hàng, nghiệm thu và đóng dự án được xử lý thế nào?
- Đang dùng những mẫu file Excel/Word nào, và có chuẩn hoá được không?
- Có mã dự án chung giữa OplaCRM, MISA, hợp đồng, mua hàng và nghiệm thu không?
- Một dự án có thể gắn nhiều Opportunity không? (hiện tại: 1 bàn giao ↔ tối đa 1 dự án)

## C. Truy cập & vận hành

- Những ai cần truy cập, và trường nào là nhạy cảm?
- Thành viên dự án được xem tất cả dự án hay chỉ dự án được giao? (hiện tại: chỉ dự án được giao, xem A1)
- PM và thành viên được xem những trường tài chính nào?
- Cần dữ liệu cập nhật với tần suất nào?
- Hosting ở đâu, và ai duyệt mô hình bảo mật?
- Có cần upload file thật không? Nếu có thì lưu ở đâu, giới hạn loại và dung lượng thế nào?

## D. Sales / OplaCRM (Phase 2)

- Công ty đang dùng gói OplaCRM nào, bao nhiêu seat? API đã được bật trên tenant chưa?
- Có endpoint cho báo giá, BOQ, hợp đồng, activity, file không?
- Rate limit, trường hỗ trợ đồng bộ tăng dần (incremental), các sự kiện Webhook, cơ chế chữ ký/retry?
- Xác thực dùng token, OAuth client hay cách khác? (`.env` đang để sẵn `OPLACRM_API_TOKEN`, chỉ là chỗ giữ, chưa dùng)
- Stage nào được coi là "Won"? Có trường cờ riêng không?
- Có sandbox để chạy thử đồng bộ không?

## E. Tài chính / MISA (Phase 3)

- Công ty dùng sản phẩm/gói AMIS nào? Gói đó có cho dùng ACT Open API không?
- AMISKT trên Developer Portal và ACT Open API có phải hai API khác nhau không? Nên dùng API nào?
- Có endpoint đọc hoá đơn, chứng từ, phiếu thu/chi, trạng thái thanh toán không? meInvoice có phải nguồn riêng không?
- Rate limit, quyền dữ liệu, sandbox, quyền chỉ đọc?
- Kế toán xuất được những báo cáo CSV/XLSX nào, và ai phụ trách xuất/nhập? Mẫu cột đề xuất trong `docs/samples/` có dùng được không?
- Các điểm trong ghi chú cần MISA xác nhận trước khi bật live: đường dẫn connect/sync, tên trường request connect (`app_id`, `access_code`, `org_company_code`), response connect có bọc trong envelope chung không, định dạng `expired_time`, header `X-MISA-AccessToken`, giới hạn `take` = 100.
- Schema dòng dữ liệu của `get_list_acc_obj_debt` và `get_list_inventory_balance` là gì? Số dư phải thu và phải trả tách thành hai cột hay một cột có dấu?
- Callback: thuật toán ký chính xác (HMAC-SHA256 với khoá `app_id`?) và cách chuẩn hoá chuỗi trước khi ký.
- Có cách nào gắn công nợ với dự án (mã dự án trên chứng từ, mã hợp đồng…) không?

## F. Kỹ thuật (nhóm phát triển)

- Bootstrap và Chart.js đang tải từ CDN jsdelivr. Nếu môi trường triển khai không có Internet, cần vendor các file này vào `static/`.
- Hàm sinh mã tuần tự chưa an toàn khi tạo đồng thời; unique constraint là chốt chặn cuối cùng. Cần xem lại nếu khối lượng tăng.
- `.gitignore` đang chặn `*.csv`, `*.xlsx` để tránh commit file nghiệp vụ; riêng `docs/samples/*.csv` (dữ liệu hư cấu) được cho phép.
- Chưa có khoá chống chạy chồng hai lượt đồng bộ cùng loại; cần thêm khi gắn scheduler.
- Import XLSX chưa hỗ trợ (cần thêm dependency như `openpyxl`); hiện chỉ nhận CSV.
- Chưa có bảng đối chiếu khách hàng OplaCRM ↔ đối tượng MISA ↔ dự án; cần quy tắc ghép mã trước khi xây (không ghép theo tên).
