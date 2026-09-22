# Tàng thư — Lifecycle: 404 → SUSPENDED → REMOVED

**Chốt ngày:** 2026-09-22

## Quy tắc

- HTTP **404** từ Google Drive API là tín hiệu duy nhất bắt đầu/tiếp tục lifecycle `suspended`.
- 403, 429, 5xx, timeout hoặc lỗi API khác **không** được tính vào thời hạn 7 ngày và vẫn làm build fail để tránh che giấu lỗi hệ thống.
- Khi folder trở lại truy cập được, tủ lập tức trở lại `active` và xóa `suspended_at`.
- Nếu folder trả 404 liên tục đủ **7 ngày**, tủ chuyển `removed` và bị loại khỏi catalog.
- Với chu kỳ Drive Check 30 phút, 7 ngày tương đương **336 chu kỳ kiểm tra**.
- `suspended_at` được lưu trong `config/branches.json`, nên không mất sau mỗi GitHub Actions run.
- Tủ `suspended` vẫn được giữ trên web nhưng không giữ sách cũ.
- Tủ `removed` không được đưa trở lại catalog.

## Flow

`ACTIVE → SUSPENDED → ACTIVE`

hoặc

`ACTIVE → SUSPENDED → REMOVED`

## Persistence

Workflow được cấp `contents: write` để commit thay đổi lifecycle vào `config/branches.json`.

Commit lifecycle dùng `[skip ci]` để không tạo thêm một vòng Pages build chỉ vì thay đổi metadata lifecycle.

## Test

1. Bỏ public một tủ → lần build kế tiếp phải ghi `suspended_at`.
2. Bật public lại trước 7 ngày → tủ trở lại `active`.
3. Giữ 404 đủ 7 ngày → tủ bị loại khỏi catalog.
4. Không dùng 403/timeout để kích hoạt đồng hồ 7 ngày.
