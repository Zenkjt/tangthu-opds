# CHECKPOINT — STORY GUI ASYNC — 2026-10-24

Story GUI đã được điều chỉnh để phù hợp Story Worker bất đồng bộ:

- `/story/register` trả request_id.
- `/story/next`, `/story/previous`, `/story/jump` trả request_id.
- GUI polling `/story/operation`.
- Payload luôn gửi `user_id + folder_id`; navigation thêm `story_id`.
- Nguồn sách dùng `/story/sources`.

Không thay đổi layout GUI đã duyệt.
