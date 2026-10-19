# CHECKPOINT — News Bulletin Registry — 2026-10-19

## Đã chốt

### 1. Registry
Nguồn tin dùng registry riêng:
`config/config_news_sources.json`

Subscription dùng file riêng:
`config/config_news_subscriptions.json`

Không trộn với `config/branches.json`.

### 2. Bulletin Registry workflow
Tạo workflow riêng:
`.github/workflows/register-news-source.yml`

Workflow nhận GitHub Issue có title:
`[TIN TỨC]`

Các field:
```text
- Tên nguồn: ...
- URL: ...
- Hành động: add
```

Hành động hỗ trợ:
- `add`: thêm nguồn mới
- `update`: nếu URL đã tồn tại thì cập nhật tên
- `delete` / `remove`: xóa nguồn

### 3. Source schema

Mỗi source:
```json
{
  "id": "s-xxxxxxxxxxxx",
  "name": "Tên nguồn",
  "url": "https://...",
  "enabled": true,
  "order": 1
}
```

`id` được tạo ổn định từ SHA-256 của normalized URL.

Duplicate source được xác định theo normalized URL.

### 4. URL normalization
- Chỉ nhận HTTP/HTTPS.
- Bỏ fragment `#...`.
- Bỏ trailing slash ở pathname.
- Query parameters được giữ nguyên.

### 5. Sau khi thay đổi registry
Workflow commit config và trigger `pages.yml` để Web/OPDS build lại.

## Chưa làm

- UI tạo Issue `[TIN TỨC]`.
- Subscription workflow.
- `news_subscriptions.json` logic.
- ArticleCache implementation.
- News selection / edition generation.
