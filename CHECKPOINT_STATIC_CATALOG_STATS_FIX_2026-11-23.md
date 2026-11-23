# CHECKPOINT — Static catalog statistics and request fan-out fix

**Ngày:** 2026-11-23  
**Nguồn chuẩn:** `tangthu-opds-main(20261123-044123).zip` do người dùng cung cấp.

## Vấn đề xác nhận

- `catalog.json` đang là version 2 nhưng mỗi branch chưa có `book_count`, `font_count`, `format_counts`.
- `scripts/postprocess_bookshelf.py` dựng thống kê bằng `loadAllFiles()` cho toàn bộ tủ. Hàm này tải root shard và các directory shard, gây hàng nghìn request khi mở trang.
- Footer cũng gọi `loadAllFiles()` trên tất cả tủ để tự tính tổng số ấn phẩm.
- `apps-script/DrivePriorityV4.gs` còn publish manifest `complete:false` ở checkpoint, trái với nguyên tắc atomic generation. Bản `DrivePriorityV4.gs` tại root đã có logic staging đúng.

## Thay đổi

1. `cmd/generate/main.go`
   - Giữ `catalog.json` version 2 để tương thích.
   - Bổ sung `book_count`, `font_count`, `format_counts` cho từng branch.
   - Nhóm sách gồm EPUB, MOBI, AZW3, CBZ, LIT, CHM, PRC, PDF, ZIP, RAR, DOC, DOCX, TXT, MD.
   - Nhóm font gồm CPFONT, TTF, OTF.
   - Incremental merge cập nhật thống kê của tủ được build và giữ nguyên thống kê của các tủ khác.
   - Chỉ cho phép incremental nếu catalog hiện tại đã có schema thống kê tĩnh.
2. `scripts/postprocess_bookshelf.py`
   - Giá sách đọc số liệu trực tiếp từ `catalog.json`.
   - Footer cộng tổng từ metadata catalog.
   - Không gọi `loadAllFiles()` khi mở trang giá sách; hàm tải shard vẫn giữ cho thao tác duyệt thư mục/tìm kiếm.
3. `scripts/resolve_build_mode.py`
   - Ép full build nếu catalog thiếu một trong các trường thống kê.
4. `scripts/tangthu_lifecycle.py`
   - Tủ suspended được gán thống kê bằng 0 và `format_counts: {}`.
5. `apps-script/DrivePriorityV4.gs`
   - Đồng bộ với bản root đã có atomic publish: checkpoint chỉ giữ generation mới ở staging; chỉ publish manifest khi scan hoàn tất.

## Kiểm tra

- `go test ./...`: PASS.
- `python -m py_compile` cho ba script Python đã sửa: PASS.
- Apps Script syntax bằng `node --check`: PASS.
- Tạo HTML fixture từ `writeWeb()`, chạy `postprocess_ui.py` và `postprocess_bookshelf.py`: PASS.
- Kiểm tra HTML sau postprocess: renderer giá sách đọc `book_count`; không còn gọi `loadAllFiles()` để dựng giá sách hoặc footer; `loadAllFiles()` vẫn còn cho tìm kiếm: PASS.
- Kiểm tra thống kê định dạng và logic ép full build với catalog cũ: PASS qua Go unit tests.

## Triển khai

- Thay các file trong ZIP patch vào đúng đường dẫn repo, commit trên GitHub Web.
- Workflow Pages sẽ tự chọn full build khi catalog hiện tại chưa có metadata thống kê. Full build này cần đọc snapshot R2 để tái tạo catalog; các lần repository_dispatch tiếp theo mới có thể incremental.
- Apps Script: thay nội dung `DrivePriorityV4.gs` bằng bản trong patch và lưu project. Không cần deploy Web App mới nếu không thay endpoint/deployment version.
- Không thay đổi Cloudflare Worker, OPDS endpoint, directory shard format hoặc chu kỳ DriveCheck.
