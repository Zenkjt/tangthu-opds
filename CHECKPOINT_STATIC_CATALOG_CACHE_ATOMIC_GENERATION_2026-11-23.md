# CHECKPOINT — Static catalog statistics & atomic R2 generation

**Ngày:** 2026-11-23  
**Nguồn chuẩn:** ZIP mới nhất `tangthu-opds-main (2).zip` do người dùng cung cấp.  
**Mục tiêu:** Trang Tàng thư chỉ đọc số liệu thống kê đã build sẵn; trong lúc DriveCheck chạy, website tiếp tục phục vụ snapshot hoàn chỉnh trước đó.

## Quyết định triển khai

### 1. Thống kê tĩnh trong `catalog.json`
- Giữ nguyên manifest version 2 để không phá các consumer hiện có.
- Mỗi branch có thêm:
  - `book_count`: tổng số file thuộc 14 định dạng sách hiện đang hỗ trợ.
  - `font_count`: tổng số font `.cpfont`, `.ttf`, `.otf`.
  - `format_counts`: số lượng theo từng định dạng sách.
- `cmd/generate` tính các số liệu từ snapshot R2 trong lúc build.
- Incremental merge cập nhật metadata của tủ được chọn và giữ nguyên thống kê của các tủ còn lại.
- Frontend dựng thống kê từng tủ và footer trực tiếp từ `catalog.json`; không gọi `loadAllFiles()` hay tải directory shards khi mở trang.
- Nếu catalog cũ chưa có các trường thống kê, `resolve_build_mode.py` buộc chạy full build đầu tiên.
- Tủ bị suspend được ghi các trường thống kê bằng 0 / map rỗng để manifest luôn đồng nhất.

### 2. Atomic publish cho R2 snapshot
- DriveCheck vẫn ghi các page của generation mới vào đường dẫn generation riêng.
- Tại checkpoint giữa chừng, không ghi `snapshots/{shelf}/manifest.json`.
- Manifest đang hoạt động tiếp tục trỏ đến generation hoàn chỉnh gần nhất.
- Chỉ khi quét hoàn tất mới ghi manifest `complete: true`, chuyển sang generation mới.
- Generator từ chối mọi manifest `complete: false`, tránh build catalog/OPDS từ snapshot dở dang.
- Partial scan không dispatch build; chỉ scan hoàn tất mới đưa tủ vào danh sách build.

## File thay đổi

1. `apps-script/DrivePriorityV4.gs`
2. `cmd/generate/main.go`
3. `cmd/generate/catalog_shards_test.go`
4. `scripts/postprocess_bookshelf.py`
5. `scripts/resolve_build_mode.py`
6. `scripts/tangthu_lifecycle.py`

## Kiểm tra đã chạy

- `go test ./...`: PASS.
- Python compile cho các script đã sửa: PASS.
- Apps Script `.gs` syntax qua `node --check`: PASS.
- Tạo HTML fixture từ `writeWeb()` và chạy chuỗi `postprocess_ui.py` → `postprocess_shelf_reload.py` → `postprocess_bookshelf.py` → `postprocess_shelf_number.py`: PASS.
- Kiểm tra HTML sau postprocess: hàm render giá sách không gọi `loadAllFiles()` hoặc `fetch()`, footer dùng `book_count`: PASS.
- Kiểm tra resolver với catalog version 2 cũ nhưng thiếu thống kê: chọn `full` build: PASS.
- Kiểm tra không còn publish manifest `complete: false` tại checkpoint: PASS.

## Lưu ý triển khai

- Đây là thay đổi trên mã nguồn trong ZIP mới nhất, chưa commit hoặc deploy.
- Sau khi thay các file và commit, workflow sẽ tự chọn full build nếu catalog hiện tại chưa có thống kê tĩnh.
- Nếu R2 đang còn manifest `complete: false` từ phiên bản cũ, generator sẽ dừng an toàn cho tủ đó cho đến khi DriveCheck tiếp tục và hoàn tất generation đang dở.
- Không cần đổi URL OPDS, Cloudflare Worker, R2 bucket, chu kỳ DriveCheck hay cấu trúc directory shards.
