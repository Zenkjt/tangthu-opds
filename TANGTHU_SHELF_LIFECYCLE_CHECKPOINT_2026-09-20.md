# TÀNG THƯ — Shelf Lifecycle Checkpoint

**Date:** 2026-09-20  
**Status:** DECISION LOCKED

## Chốt lifecycle tủ sách

### 1. ACTIVE
- `enabled: true`
- Tủ xuất hiện trên website và OPDS.
- GitHub Actions scan và build catalog bình thường.

### 2. SUSPENDED
Khi Tàng Thư xác nhận thư mục Google Drive không còn truy cập được do quyền chia sẻ bị thu hồi:
- `enabled: false`
- `status: "suspended"`
- Tủ không xuất hiện trên website/OPDS.
- Không xóa registration record.
- Không xóa catalog/cache ngay.
- Khi quyền truy cập được khôi phục, tủ có thể chuyển lại `ACTIVE`.

### 3. DELETED
Chỉ xảy ra khi chủ tủ chủ động dùng chức năng **Xóa tủ**:
- Xóa registration khỏi `config/branches.json`.
- Catalog/cache/generated data của tủ sẽ được garbage-collect qua lần build tiếp theo.
- Tuyệt đối không xóa hoặc sửa nội dung Google Drive của người dùng.

## Dữ liệu branch dự kiến

```json
{
  "id": "g-...",
  "display_name": "Tên tủ",
  "root_folder_id": "...",
  "enabled": true,
  "status": "active",
  "last_mutation": "..."
}
```

## Nguyên tắc quan trọng

- Hủy chia sẻ Drive **không đồng nghĩa với xóa tủ**.
- Lỗi API tạm thời/quota/network không được tự động coi là hủy chia sẻ.
- Chỉ trạng thái truy cập được xác nhận là mất quyền mới chuyển sang `SUSPENDED`.
- Xóa tủ là thao tác chủ động và khác hoàn toàn với `SUSPENDED`.
- Không bao giờ xóa dữ liệu gốc trên Google Drive.

## Trạng thái hiện tại

`config/branches.json` hiện vẫn dùng `enabled` và chưa có `status`; Apps Script đã bật lại cooldown 24 giờ. Việc triển khai lifecycle cần cập nhật đồng bộ Apps Script + generator/CI + registration UI để tránh trường hợp branch suspended bị chặn không cho khôi phục.
