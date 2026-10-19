# CHECKPOINT — Tàng Thư News: Bulletin Registry Foundation
## 2026-10-19

### Trạng thái

Bắt đầu triển khai phần `tangthu-opds` cho hệ thống Tin tức.

Repository hiện tại vẫn giữ kiến trúc GitHub Pages + Google Drive shared folders; `config/branches.json` đang là registry của các tủ sách. fileciteturn63file0L1-L6

### Quyết định

Không trộn Bulletin Registry vào `config/branches.json`.

Tạo registry riêng:

```text
config/news_sources.json
```

Schema:

```json
{
  "sources": [
    {
      "bulletin_id": "...",
      "name": "...",
      "source_url": "...",
      "article_limit": 25,
      "description": "...",
      "status": "active",
      "created_at": "..."
    }
  ]
}
```

`article_limit` ở Registry là giới hạn crawl/discovery tối đa của source. Giá trị khởi đầu thiết kế là 25.

Subscription của từng tủ sách tách riêng:

```text
config/news_subscriptions.json
```

Schema:

```json
{
  "subscriptions": [
    {
      "branch_id": "...",
      "bulletin_id": "...",
      "folder_id": "...",
      "status": "active",
      "created_at": "..."
    }
  ]
}
```

### Nguyên tắc

- Registry mô tả **nguồn tin tồn tại trong Tàng Thư**.
- Subscription mô tả **tủ sách nào nhận nguồn nào**.
- Source không có subscription active sẽ không được đưa vào daily crawl.
- `ArticleCache` nằm ở `tangthu-news-crawler`, không nằm trong OPDS.
- Không đưa crawler/extraction/EPUB builder vào Apps Script hoặc `tangthu-opds`.
- `0neNews.epub` vẫn là file cố định của từng tủ sách.

### Quan hệ với kiến trúc hiện tại

Tàng Thư hiện dùng `config/branches.json` làm cấu hình tủ sách và GitHub Actions để build catalog. fileciteturn64file0L1-L6

Workflow đăng ký tủ hiện tại xử lý mutation thông qua GitHub Issue rồi cập nhật `config/branches.json`. fileciteturn70file0L1-L6

Do đó phần News sau này nên dùng cùng mô hình GitHub-backed configuration, thay vì thêm database.

### Chưa triển khai trong checkpoint này

- UI `Tin tức`
- workflow thêm/sửa/xóa nguồn
- canonicalize URL
- duplicate source detection
- Subscription UI
- edition selection
- kết nối crawler
- Drive upload

Đây là nền data model đầu tiên; bước kế tiếp là triển khai workflow quản lý Bulletin Registry và canonicalize/duplicate check trước khi làm UI.
