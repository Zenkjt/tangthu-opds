# CHECKPOINT — Tàng Thư: 13 định dạng, không đọc metadata

Ngày: 2026-11-13

## Quyết định kiến trúc

Giữ Drive scan thuần liệt kê file. Không gọi `metadata.Extract()` và không đọc nội dung EPUB/MOBI/AZW3/DOC/DOCX/TXT/MD trong quá trình scan hoặc generate catalog.

Lý do: GUI hiện tại hiển thị thông tin file lấy từ Google Drive API/catalog (tên, phần mở rộng, dung lượng, ngày sửa đổi, MIME, checksum). Tác giả và bìa sách chưa được trích xuất; không cần thêm công việc đọc nội dung để duy trì GUI này.

## Phạm vi patch

- Bỏ hard limit 25 MiB trong `internal/drive/drive.go`.
- Vẫn loại file có kích thước âm bất hợp lệ.
- Bổ sung `.doc`, `.docx`, `.txt`, `.md` vào allowlist.
- Bổ sung nhãn `MD` trong `cmd/generate/main.go`.
- Mở rộng thống kê Bookshelves và Views lên 13 định dạng sách.
- Chỉ hiển thị định dạng có số lượng > 0 trong cả hai chế độ thống kê.
- Font CPFont/TTF/OTF vẫn thống kê riêng, không tính vào 13 định dạng sách.
- Cập nhật nội dung hướng dẫn đăng ký tủ.

## Không đụng tới

- `internal/metadata/metadata.go`.
- OPDS, URL tải, Refresh, Drive Check.
- Cloudflare workflow, cache rules, Apps Script.
- Cơ chế incremental build/site-state.

## Kiểm tra

- `gofmt`: đạt.
- `GO111MODULE=off go test ./...`: đạt (cmd/generate, internal/drive, internal/metadata).
- `python -m py_compile` cho 3 script postprocess: đạt.

## Triển khai

Thay đúng 6 file trong ZIP bằng GitHub web. Sau đó đợi GitHub Actions hoàn tất và kiểm tra file mới, file >25 MiB, thống kê Bookshelves/Views.
