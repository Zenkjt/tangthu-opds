# Checkpoint — Khôi phục Drive Snapshot Polling

## Quyết định
Khôi phục kiến trúc đồng bộ Google Drive bằng snapshot/fingerprint, **không dùng Drive Changes API**.

## Luồng
Google Drive `files.list`
→ quét đệ quy từng tủ đang bật
→ fingerprint SHA-256
→ so với `TANGTHU_DRIVE_SNAPSHOT_V1`
→ nếu thay đổi: `repository_dispatch` event `drive_changed`
→ GitHub Actions build
→ chỉ sau khi dispatch thành công mới cập nhật snapshot.

## Trigger
- `driveCheck`: mỗi 30 phút.
- `setupDriveChangeTrigger()` xóa trigger `driveCheck` cũ, tạo baseline snapshot mới và tạo lại trigger 30 phút.
- Checkpoint cũ `TANGTHU_DRIVE_CHANGE_PAGE_TOKEN` bị xóa.

## Giữ nguyên
- Giới hạn mutation 24 giờ.
- `branches.json` và các hàm create/rename/delete.
- GitHub dispatch event `drive_changed`.

## Thao tác sau khi thay Code.gs
1. Deploy phiên bản Apps Script mới.
2. Chạy `setupDriveChangeTrigger()` **một lần** thủ công.
3. Không rollback commit GitHub Pages / workflow.
4. Kiểm tra lần thay đổi file Drive tiếp theo: tối đa khoảng 30 phút sẽ dispatch build.
