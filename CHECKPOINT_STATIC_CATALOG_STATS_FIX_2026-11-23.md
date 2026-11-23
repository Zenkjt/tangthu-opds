# CHECKPOINT — Static catalog statistics / shelf request fan-out
**Ngày:** 2026-11-23  
**Nguồn chuẩn:** ZIP mới nhất `tangthu-opds-main (1)(1).zip` do người dùng tải lên.

## Kết quả rà soát
- `catalog.json` version 2 chưa có `book_count`, `font_count`, `format_counts`.
- `postprocess_bookshelf.py` vẫn khiến màn hình giá sách gọi `loadAllFiles()` cho từng tủ; footer cũng tải toàn bộ shard để cộng tổng.
- Generator chấp nhận manifest R2 `complete:false`, có nguy cơ đọc generation chưa hoàn tất.
- Resolver incremental chỉ kiểm tra version 2, chưa kiểm tra schema thống kê.
- Lifecycle merge chưa ghi các trường thống kê cho tủ suspended.

## Thay đổi trong patch
1. `cmd/generate/main.go`
   - Bổ sung `book_count`, `font_count`, `format_counts` trong mỗi branch của catalog.
   - Đếm 14 định dạng sách đã được `isSupportedBookName()` hỗ trợ; font gồm `.cpfont`, `.ttf`, `.otf`. Bỏ qua folder và file không thuộc nhóm hỗ trợ.
   - Incremental merge cập nhật thống kê tủ thay đổi và giữ nguyên metadata của các tủ khác.
   - Chỉ chấp nhận R2 snapshot manifest có `complete:true`.
   - Chỉ bật incremental nếu catalog version 2 có đủ schema thống kê.
2. `cmd/generate/catalog_shards_test.go`
   - Test đếm sách/font, loại trừ folder và định dạng không hỗ trợ.
   - Test incremental merge cập nhật đúng tủ và bảo toàn stats tủ khác.
   - Test từ chối snapshot generation chưa complete.
3. `scripts/postprocess_bookshelf.py`
   - Giá sách đọc thống kê trực tiếp từ catalog, không tải directory shards.
   - Footer cộng tổng `book_count` và `font_count` từ catalog.
   - `loadAllFiles()` vẫn được giữ cho chức năng tìm kiếm toàn bộ nội dung.
4. `scripts/resolve_build_mode.py`
   - Repository dispatch tự chuyển full build khi catalog thiếu một trong các trường thống kê.
5. `scripts/tangthu_lifecycle.py`
   - Tủ suspended được gán `book_count:0`, `font_count:0`, `format_counts:{}`.

## Kiểm tra đã chạy
- `go test ./...`: PASS.
- `python3 -m py_compile` cho 3 script Python: PASS.
- Static source assertions xác nhận renderer/footer không còn gọi `loadAllFiles(shelf)`: PASS.
- Resolver fixture với catalog version 2 thiếu stats: chọn full build: PASS.
- `git diff --check` không thực hiện được vì ZIP không chứa `.git` metadata.
- Chưa chạy full GitHub Actions build với R2 thật; chưa kiểm tra trực tiếp số liệu trên dữ liệu production.

## Triển khai
Thay đúng 5 file trong patch vào repo trên GitHub:
- `cmd/generate/main.go`
- `cmd/generate/catalog_shards_test.go`
- `scripts/postprocess_bookshelf.py`
- `scripts/resolve_build_mode.py`
- `scripts/tangthu_lifecycle.py`

Commit các file trên. Không thay `DrivePriorityV4.gs`: patch này không đụng Apps Script. Workflow sẽ tự chạy full build khi catalog hiện tại chưa có stats; các lần repository_dispatch sau đó mới đủ điều kiện incremental.
