# Tàng Thư — Bổ sung 4 định dạng và bỏ giới hạn dung lượng

Patch này chỉ thay đổi nhận diện file, nhãn định dạng, thống kê và hướng dẫn đăng ký. Không tích hợp đọc metadata bên trong sách.

## Thay đúng 6 file

1. `internal/drive/drive.go`
2. `internal/drive/drive_test.go`
3. `cmd/generate/main.go`
4. `scripts/postprocess_bookshelf.py`
5. `scripts/postprocess_ui.py`
6. `scripts/postprocess_registration.py`

## Cách áp dụng bằng GitHub web

Với từng file:
1. Mở đúng đường dẫn trong repository `Zenkjt/tangthu-opds`.
2. Chọn Edit.
3. Thay toàn bộ nội dung bằng file cùng đường dẫn trong ZIP.
4. Commit vào `main`.

Có thể thay cả 6 file trong một commit. Không thay workflow, cấu hình Cloudflare, Apps Script, cache rules hoặc các file khác.

## Thay đổi

- Bỏ giới hạn 25 MiB trong bước nhận diện file. Không có nghĩa là tải file về: Drive scan vẫn chỉ liệt kê thông tin file qua API.
- Thêm `.doc`, `.docx`, `.txt`, `.md` vào allowlist của Drive scanner.
- Bổ sung nhãn `MD` trong GUI.
- Thống kê 13 định dạng sách: EPUB, MOBI, AZW3, CBZ, LIT, CHM, PRC, PDF, ZIP, DOC, DOCX, TXT, MD.
- Giữ font CPFont/TTF/OTF ở nhóm thống kê riêng.
- Cả giao diện Bookshelves và Views chỉ hiển thị định dạng có số lượng lớn hơn 0.
- Cập nhật hướng dẫn đăng ký tủ, bỏ thông tin giới hạn 25 MB.

## Không thay đổi

- Không đọc nội dung file hoặc trích xuất metadata sách.
- Không tạo thumbnail.
- Không thay đổi OPDS, URL tải trực tiếp, Refresh, Drive Check, cache, Cloudflare workflow hay cơ chế incremental build.

## Kiểm tra đã thực hiện

- `gofmt` cho các file Go.
- `GO111MODULE=off go test ./...` trong GOPATH tạm: đạt cả ba package.
- `python -m py_compile` cho ba script postprocess: đạt.

Sau commit, chờ GitHub Actions deploy thành công rồi thử từng định dạng mới, trong đó có một file lớn hơn 25 MiB. Việc file xuất hiện trong catalog không đồng nghĩa thiết bị đọc sách chắc chắn hỗ trợ mở định dạng đó; đây là thay đổi ở khâu nhận diện/catalog của Tàng Thư.
