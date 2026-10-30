# CHECKPOINT — TÀNG THƯ CROSSPOINT STORY TRIGGER V5

Date: 2026-10-30

## Final UI decision

Plugin GUI là giao diện điều khiển duy nhất.

```text
- Online story controller -
   by tangthu.pages.dev

Shelf number
[     12     ]

[  PREVIOUS  ]
[    NEXT    ]
```

## Interaction

Không có nút Save.

Khi người dùng nhập `shelf_no` và bấm PREVIOUS hoặc NEXT:

1. Validate `shelf_no`.
2. Lưu `shelf_no` vào `config.json` trong thư mục plugin.
3. Gửi:
   {
     "action": "story_trigger",
     "shelf_no": <number>,
     "direction": "previous" | "next"
   }
   tới Apps Script.
4. Lần mở plugin tiếp theo tự nạp `shelf_no` đã lưu.

NEXT/PREVIOUS vừa là action vừa là Save.

## Architecture

CrossPoint browser plugin
→ Apps Script `story_trigger`
→ shelf_no → branch/root_folder_id
→ Story Worker `/story/trigger`
→ shelf-local StoryState
→ existing Story request queue
→ Story Scraper

## Deliberate exclusions

- Không có nút Save.
- Không có nút Đổi tủ.
- Không yêu cầu nhập lại shelf_no mỗi lần.
- Không lưu `story_id`.
- Không lưu `entry_id`.
- Không truy cập Google Drive trực tiếp.
- Không dùng `device.json` cho giao diện điều khiển.
- Không sửa firmware.

## Files

- `manifest.json`
- `plugin.js`
- `README.md`
