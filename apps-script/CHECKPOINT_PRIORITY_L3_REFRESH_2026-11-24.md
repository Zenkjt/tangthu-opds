# Tàng thư — Checkpoint tách L3 và Refresh, giới hạn 15 phút

**Ngày:** 24/11/2026  
**File thay đổi:** `DrivePriorityV4.gs`

## Kiến trúc đã triển khai trong patch

- Normal scheduler `driveCheckPriority` chỉ xử lý L1/L2; giữ chu kỳ 30 phút và logic hiện có.
- L3 có controller riêng `driveCheckPriorityL3`, tạo 4 time trigger hàng tháng vào ngày 2, 10, 18, 26 lúc 03:00, timezone `Asia/Ho_Chi_Minh`.
- Mỗi chu kỳ L3 tạo một danh sách tủ cố định; mỗi tủ chỉ được quick-check một lần trong chu kỳ. Không thay đổi thì chuyển tủ; thay đổi thì đi tiếp full scan đến khi hoàn tất.
- L3 giữ `l3_job` trong priority state để nhớ chu kỳ, queue, index, tủ đang xử lý, kết quả đã xác nhận và checkpoint. Continuation không tạo lại danh sách giữa chừng.
- Refresh được đưa vào `refresh_queue`, bỏ quick scan và chạy thẳng full scan. Nếu full generation đang dở thì tiếp tục generation/checkpoint đó.
- L3 và Refresh dùng chung `driveCheckContinuation` và cùng lõi `scanPriorityQuick_` / `scanPriorityFull_` / R2 checkpoint.
- Mỗi execution xử lý tối đa khoảng 50 giây. Tổng thời gian xử lý một tủ được chia thành các đợt tối đa 15 phút; đạt ngưỡng thì giữ checkpoint và tiếp tục bằng một one-shot trigger sau khoảng 60 giây. Không giới hạn tổng số đợt để hoàn tất tủ.
- Chỉ có một continuation trigger dùng chung; không tạo trigger riêng cho từng tủ.
- Khi lỗi tạm thời, continuation thử lại tối đa 5 lần; sau đó giữ job ở trạng thái `paused_error`, không lặp vô hạn. Bấm Refresh lại sẽ mở lại job đã xếp hàng; L3 sẽ được thử tiếp ở trigger tháng kế tiếp.
- ScriptLock tuần tự hóa các luồng. Normal scheduler bỏ qua tủ có Refresh đang chờ; Refresh từ chối tủ thuộc phần còn lại của chu kỳ L3 để tránh quét trùng.
- Refresh chỉ cập nhật baseline, không tác động change streak tự động. Auto-upgrade/downgrade vẫn chỉ dựa trên các lượt kiểm tra L3/L2 theo lịch.
- Generator được dispatch đúng một lần cho từng tủ khi full scan của tủ đó hoàn tất; không dispatch ở các checkpoint trung gian. Refresh dispatch riêng cho tủ hoàn tất.

## Bảo toàn trạng thái

Patch không xóa `PRIORITY_STATE_KEY`, không reset fingerprint, baseline, cursor, full-scan checkpoint hoặc R2 generation. `setupDrivePriorityL3Trigger()` chỉ thay các trigger của handler L3 và tạo lịch tháng mới.

**Không chạy `setupDrivePriorityTrigger()` để áp dụng patch**: hàm cũ có thao tác xóa priority state.

## Cách áp dụng

1. Trong Apps Script, thay toàn bộ nội dung file `DrivePriorityV4.gs` bằng file trong patch.
2. Lưu project.
3. Chạy thủ công `setupDrivePriorityL3Trigger()` đúng một lần.
4. Kiểm tra Apps Script → Triggers: `driveCheckPriority` vẫn giữ lịch 30 phút; `driveCheckPriorityL3` có 4 trigger tháng; `driveCheckContinuation` chỉ xuất hiện khi có job cần tiếp tục.
5. Không chạy lại setup trigger L1/L2.

## Kiểm thử

- `node --check` trên nội dung `.gs`: PASS.
- Đã rà soát tĩnh: L3 không còn trigger hàng tuần; 4 ngày tháng đã cấu hình; continuation dùng một handler; L1/L2 filter vẫn loại priority 3.
- Chưa thể chạy tích hợp Apps Script / Google Drive / R2 / GitHub trong môi trường hiện tại. Sau deploy cần kiểm tra log thực tế và xác nhận một Refresh nhỏ, một Refresh lớn, một L3 unchanged và một L3 changed.

## Lưu ý

- Apps Script time triggers chạy gần thời điểm đã đặt, không cam kết đúng tuyệt đối 03:00:00.
- Mỗi execution được giới hạn 50 giây để an toàn; 15 phút là ngân sách xử lý cộng dồn cho một tủ trước khi nhường nhịp, không phải một execution dài 15 phút.
