# CHECKPOINT — Drive V4 Priority Scheduler: 300s global / 50s shelf

Date: 2026-10-29

## Chốt kiến trúc

Kết hợp V4 recursive scanner với priority scheduler:

- Global execution budget: **300 seconds**.
- Per-shelf budget: **50 seconds**.
- Nếu shelf hoàn tất trước 50s: ghi kết quả, cập nhật cursor và chuyển ngay sang shelf kế tiếp.
- Nếu shelf chưa hoàn tất sau 50s: lưu checkpoint ở Drive API page level, cập nhật cursor sang shelf kế tiếp và **tiếp tục cùng execution**. Không `return` giữa chừng.
- Nếu global budget 300s hết: lưu cursor/state và kết thúc execution.
- Execution kế tiếp tiếp tục từ cursor đã lưu.

## Priority / skip

- L1: scan khi đến hạn, chu kỳ 30 phút.
- L2: scan khi đến hạn, chu kỳ 2 ngày.
- L3: scan khi đến hạn, chu kỳ 7 ngày.
- L2/L3 đã baseline và chưa đến hạn sẽ bị `SKIP`.
- Shelf có checkpoint chưa hoàn tất luôn được `RESUME`, bất kể priority/due time.
- Baseline chưa hoàn tất cũng luôn được tiếp tục.
- Cursor được lưu trong priority state để vòng sau tiếp tục đúng vị trí.

## Round behavior

Mỗi execution chạy tối đa một vòng qua danh sách 28 shelf kể từ cursor hiện tại. Các shelf được skip được ghi thành `SKIP LIST` cuối round.

Các shelf bị checkpoint không làm kết thúc execution; scheduler chuyển cursor sang shelf tiếp theo giống cơ chế V4 cũ.

## Logging

Giữ cơ chế log chi tiết của V4 và bổ sung:

- `ROUND START`
- `SCAN ... | DUE/RESUME/FORCED`
- `SKIP ... | BASELINE_DONE/NOT_DUE`
- `CHECKPOINT-QUICK`
- `CHECKPOINT-FULL`
- `CHECKPOINT ... | next_cursor=...`
- `ROUND END`
- `SKIP LIST`
- `RESULT ...`
- `DISPATCH GitHub`
- `END`

Checkpoint log có cả shelf elapsed và global elapsed.

## Storage checkpoint

Không lưu toàn bộ metadata rows vào Script Properties. Full scan dùng:

- queue
- visited
- current folder
- Drive page token
- row count
- SHA-256 digest accumulator 32 byte

để tránh lỗi `Argument too large`.

## File thay thế

`DrivePriorityV4.gs` trong gói này là file thay thế cho bản priority scheduler hiện tại.

Sau khi thay file trên Apps Script, hard refresh/reload project rồi chạy manual `driveCheckPriority()` để kiểm tra log.
