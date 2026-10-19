# TÀNG THƯ — Subscription Registry Checkpoint
## 2026-10-19

## Đã chốt

Subscription được quản lý riêng với Bulletin Registry.

### File

`config/config_news_subscriptions.json`

### Quan hệ

```text
Branch / tủ sách
      +
News Source
      ↓
Subscription
```

Không tạo crawler riêng cho từng tủ sách.

### Schema

```json
{
  "id": "sub-xxxxxxxxxxxx",
  "branch_id": "branch-id",
  "source_id": "s-xxxxxxxxxxxx",
  "article_count": 10,
  "edition_mode": "text",
  "enabled": true,
  "created_at": "ISO-8601",
  "updated_at": "ISO-8601"
}
```

`edition_mode`:

- `text`: edition chỉ chữ, giới hạn toàn edition tối đa 200 bài.
- `images`: edition có hình, giới hạn toàn edition tối đa 100 bài.

Mỗi source trong một tủ sách có `article_count` từ 5 đến 25.

### Identity

Một subscription được nhận diện bởi:

```text
branch_id + source_id
```

`subscription_id`:

```text
sub- + first 12 chars SHA-256(branch_id + ":" + source_id)
```

Không tạo duplicate subscription.

### Workflow

File:

`.github/workflows/register-news-subscription.yml`

Issue title:

```text
[TIN TỨC SUB]
```

Body:

```text
- Tủ sách ID: ...
- Source ID: ...
- Số bài: 10
- Chế độ: text
- Hành động: add
```

Hỗ trợ:

- `add`
- `update`
- `delete`
- `remove`

### Validation

Workflow kiểm tra:

1. Tủ sách tồn tại trong `config/branches.json`.
2. Source tồn tại trong `config/config_news_sources.json`.
3. `add/update` chỉ cho tủ sách `active`.
4. Source phải `enabled`.
5. Số bài phải 5–25.
6. Chế độ phải `text` hoặc `images`.
7. Delete có thể thực hiện khi subscription tồn tại.

### Lifecycle

`active/suspended` của tủ sách vẫn do Branch lifecycle quản lý.

Subscription không tự quyết định lifecycle của tủ sách.

Khi tủ sách `suspended`, crawler sẽ không xử lý subscription của tủ đó.

### Luồng sau khi hoàn tất

```text
Bulletin Registry
      ↓
Subscription Registry
      ↓
active subscriptions
      ↓
chỉ crawl các source đang được đăng ký
      ↓
ArticleCache
      ↓
personalized selection
      ↓
0neNews.epub
```

## Chưa làm

- UI `Thư viện nguồn tin`
- cơ chế tạo Issue subscription từ UI
- ArticleCache implementation trong `tangthu-news-crawler`
- selection engine
- daily edition build
- Drive upload integration cho news

## Quyết định không thay đổi

- Không crawl riêng từng user.
- Không dedup cross-source.
- `0neNews.epub` là file cố định.
- Không phụ thuộc DriveCheck 07:12 cho news.
