# CHECKPOINT — TÀNG THƯ CROSSPOINT STORY NATIVE DOWNLOAD V2

Date: 2026-10-31

## Chốt kiến trúc

CrossPoint native `device.json` dùng:

1. `browse.url` → Apps Script `story_catalog` để hiển thị PREVIOUS / NEXT.
2. Khi chọn item, CrossPoint dùng `download.method = POST` và `body` để gọi `story_download`.
3. Apps Script gọi lại `storyTrigger_()` hiện có.
4. Apps Script chờ `0neStory.epub` của đúng shelf được tạo/cập nhật.
5. Apps Script trả JSON:

```json
{"url":"<stable direct download URL>"}
```

6. `url_path: "url"` bảo CrossPoint lấy URL này làm file URL.
7. CrossPoint tải EPUB vào `/Books/0neStory.epub`.

## Stable URL

Story upload/update phải giữ nguyên Drive file ID của `0neStory.epub`.
Vì vậy URL download được tạo từ file ID và giữ nguyên qua các lần cập nhật.

## Shelf

V1/V2 test cố định `shelf_no = 1`.
Backend ưu tiên `branch.shelf_no`; có fallback vị trí `branches[shelf_no - 1]` để tương thích config cũ.

## Không thay đổi

- Story Worker trigger chain hiện tại.
- StoryState model.
- TOC order.
- DriveCheck / OPDS build architecture.
- `story_trigger` action hiện có.

## Backend file

`Code.gs` trong package là bản thay thế đầy đủ dựa trên Code.gs người dùng cung cấp, bổ sung:

- GET `story_catalog`
- POST `story_download`
- chờ file `0neStory.epub` cập nhật
- trả stable Google Drive download URL

## Cần kiểm tra trước khi production

- `0neStory.epub` của shelf phải được chia sẻ theo cách CrossPoint có thể tải trực tiếp.
- Story trigger hiện tại phải thực sự cập nhật file Drive trước khi timeout 180 giây.
- Test đầu tiên chỉ dùng `shelf_no = 1`.
