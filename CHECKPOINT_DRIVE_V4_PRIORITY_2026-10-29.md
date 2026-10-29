# CHECKPOINT — Drive V4 Priority Scheduler — 2026-10-29

## Chốt kiến trúc

Bỏ Drive Changes API V5. Quay lại V4 recursive metadata scan, nhưng scheduler theo priority từng tủ.

### Priority

- Level 1: scan mỗi 30 phút; quản lý thủ công; không tự hạ.
- Level 2: scan mỗi 2 ngày; 10 lần liên tiếp không đổi -> Level 3.
- Level 3: scan mỗi 7 ngày; 2 lần liên tiếp có thay đổi -> Level 2.
- Level 2 không tự lên Level 1.
- Tủ mới: mặc định Level 1.
- Có `setShelfPriority(branchId, level)` để đổi thủ công.

### Priority ban đầu

Level 1 — 17:
Anchi; Anki's book; BOOK; eNaga001; FeliciaLee; Haideng; Harry's eBooks; j test; Kindle của Kai; Naga001; Ptrungtu; Quin ít đọc; Sách hay; Tàng thư của Khang; Tủ sách của Ca; Tủ sách x3; Zenkjt - đang đọc.

Level 2 — 3:
Crosspoint font; Font ttf; My Ebook.

Level 3 — 8:
Azw3 books; Epub books; Kho NCN bigg; Kiếm hiệp; Lịch sử; Mobi books; Thich Nhat Hanh; Truyen chu.

Tổng: 17 + 3 + 8 = 28.

### State

`TANGTHU_DRIVE_PRIORITY_STATE_V2`

Priority lưu theo stable `branch_id`, không theo tên.

### Reload

GUI có nút `↻` cạnh từng tủ.

POST:
`{"action":"reload","branch_id":"..."}`

Reload không thay đổi priority. Nếu fingerprint thay đổi thì dispatch `drive_changed`.

### Files

- `apps-script/DrivePriorityV4.gs`
- `scripts/postprocess_shelf_reload.py`
- `.github/workflows/cloudflare.yml`

`config/branches.json` không cần sửa.

### Code.gs

Không thay cả Code.gs. Chỉ thêm đúng một dòng router.

Ngay sau:
`var action = String(body.action || '').trim().toLowerCase();`

thêm:
`if (action === 'reload') return jsonResponse(reloadShelf(body));`

Sau khi cài `DrivePriorityV4.gs`, chạy `setupDrivePriorityTrigger()` một lần.
