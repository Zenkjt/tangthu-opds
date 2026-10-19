# TÀNG THƯ — CHECKPOINT NEWS UI v2
## 2026-10-19

### Chốt UI “Thư viện nguồn tin”

Khu vực **Thêm nguồn mới** chỉ gồm:

1. URL nguồn.
2. Nút `Kiểm tra`.
3. Chú giải nhỏ: `Không bắt buộc`.

Sau khi kiểm tra:
- Hệ thống canonicalize URL.
- Hệ thống tự xác định tên nguồn từ hostname.
- Kiểm tra source đã tồn tại trong Bulletin Registry hay chưa.
- Nếu đã có: hiển thị tên + `Nguồn này đã có trong thư viện`, không cho thêm.
- Nếu chưa có: nút `Kiểm tra` đổi thành `Thêm nguồn`.

`Thêm nguồn` mở GitHub Issue `[TIN TỨC]` với URL và action `add`; không yêu cầu người dùng nhập tên nguồn.

### Nguồn đang có

Sau khi workflow đăng ký xong và người dùng `Refresh`:
- source mới xuất hiện trong danh sách.
- checkbox = subscribe.
- số bài `5–25` chỉ cấu hình tại đây.
- tên source là hyperlink tới URL nguồn và mở tab mới.

### Không thay đổi

- Bulletin Registry data model.
- Subscription Registry data model.
- crawler / ArticleCache / EPUB.
- shelf lifecycle.
- Drive / OPDS logic hiện tại.
- UI đăng ký tủ sách hiện tại.

### Ghi chú kỹ thuật

Tên nguồn được xác định nhất quán bằng hostname ở cả UI và GitHub Action.
