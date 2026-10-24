# CHECKPOINT — Story GUI/API contract fix — 2026-10-24

## Đã sửa

`postprocess_story.py` được thay thế để Story GUI dùng đúng API contract:

- `POST /register` → `{ user_id, url }`
- `POST /next` → `{ user_id, story_id }`
- `POST /previous` → `{ user_id, story_id }`
- `POST /jump` → `{ user_id, story_id, chapter_number }`

`branch.id` được dùng làm `user_id` ổn định cho Story state/cache. `folder_id` chỉ là context của UI/shelf, không gửi xuống Story Scraper.

## Không thay đổi

- Story GUI vẫn nằm trong `tangthu-opds`.
- Story Scraper không chứa GUI.
- Không cache chapter content.
- Không tạo `.tangthu/` trong Drive.
- Output vẫn là `0neStory.epub` và `0neStoryTOC.epub`.

## Còn thiếu để chạy E2E

`TANGTHU_STORY_API_URL` vẫn phải trỏ tới Story Worker thật. Package này không tự bịa endpoint production.

Bước kế tiếp: nối Worker → `repository_dispatch` → Story Scraper Action → Drive write → cập nhật GitHub story cache.
