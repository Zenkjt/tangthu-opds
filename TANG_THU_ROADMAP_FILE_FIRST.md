# TÀNG THƯ OPDS — ROADMAP KIẾN TRÚC
## File-first • Branch-sharded • Directory-sharded • Incremental Metadata

**Repository:** `Zenkjt/tangthu-opds`  
**Branch:** `main`  
**GitHub Pages:** `https://zenkjt.github.io/tangthu-opds/`

---

## 1. Mục tiêu kiến trúc

TÀNG THƯ được thiết kế như một thư viện sách tĩnh, chạy với:

```text
Google Drive
    ↓
GitHub Actions
    ↓
Static catalog + metadata cache
    ↓
GitHub Pages
    ↓
Browser / OPDS
```

Không dùng VPS, database server, Cloud Run, Railway hoặc backend luôn chạy.

Nguyên tắc quan trọng nhất:

> **File catalog phải xuất hiện trước. Metadata là lớp bổ sung và được xử lý dần dần.**

Một thư viện lớn không được bị chặn xuất bản chỉ vì phải tải và đọc hàng nghìn ebook.

---

# 2. Nguyên tắc thiết kế đã chốt

## 2.1 File-first

Mỗi file trên Google Drive là một thực thể độc lập trong catalog.

Catalog phải giữ được:

- Google Drive file ID
- filename
- parent folder ID
- size
- modified time
- checksum / MD5 nếu Drive cung cấp
- MIME/type
- download URL
- folder structure

Metadata sách không được dùng để gộp các file thành một record duy nhất.

Ví dụ:

```text
Book A.epub
Book A.mobi
Book A.azw3
```

vẫn là ba file riêng trong catalog.

---

## 2.2 Metadata là lớp bổ sung

Metadata có thể gồm:

- title
- authors
- publisher
- year/date
- ISBN
- language
- series
- description
- subjects/tags
- cover

Nếu metadata extraction thất bại:

> **File vẫn phải xuất hiện trong catalog và OPDS.**

Không được để lỗi metadata làm mất file.

---

## 2.3 Catalog và metadata tách riêng

Không tạo một JSON khổng lồ chứa toàn bộ thông tin của toàn thư viện.

Có hai lớp:

```text
FILE CATALOG
    ↓
filename / size / modified / checksum / type / download URL

METADATA CACHE
    ↓
title / author / ISBN / publisher / cover / ...
```

Catalog được tạo nhanh bằng Drive listing.

Metadata được bổ sung sau.

---

# 3. Kiến trúc dữ liệu

## 3.1 Catalog

Dữ liệu catalog được shard theo branch và thư mục.

Dự kiến:

```text
docs/
├── catalog/
│   ├── g-xxxx/
│   │   ├── root.json
│   │   ├── dir-001.json
│   │   ├── dir-002.json
│   │   └── ...
│   │
│   └── g-yyyy/
│       ├── root.json
│       └── ...
│
├── metadata/
│   ├── g-xxxx/
│   │   ├── FILE_ID_A.json
│   │   ├── FILE_ID_B.json
│   │   └── ...
│   │
│   └── g-yyyy/
│       └── ...
│
├── covers/
│   ├── g-xxxx/
│   │   ├── FILE_ID_A.jpg
│   │   └── ...
│   └── ...
│
└── opds/
    ├── g-xxxx/
    │   ├── root-001.xml
    │   ├── root-002.xml
    │   └── ...
    └── ...
```

### Lưu ý

`branches.json` chỉ là registry.

Nó không chứa catalog sách.

---

# 4. Vai trò của từng JSON

## 4.1 `root.json`

Không chứa toàn bộ sách.

Nó là manifest/điều hướng của một tủ:

```json
{
  "branch_id": "g-xxxx",
  "display_name": "Tủ sách Marketing",
  "root_folder_id": "123456",
  "generated_at": "...",
  "children": [
    {
      "folder_id": "abc",
      "name": "Marketing",
      "catalog": "dir-001.json"
    }
  ]
}
```

Mục đích:

- mở tủ nhanh
- biết các thư mục con
- không tải toàn bộ catalog

---

## 4.2 Directory catalog JSON

Mỗi thư mục có thể có một JSON riêng.

Ví dụ:

```json
{
  "folder_id": "abc",
  "name": "Marketing",
  "items": [
    {
      "id": "FILE_A",
      "name": "Marketing.epub",
      "type": "EPUB",
      "size": 1827345,
      "modified": "2026-09-17T07:20:00Z",
      "checksum": "xxxx",
      "download": "https://drive.google.com/uc?export=download&id=FILE_A"
    }
  ]
}
```

Đây là dữ liệu chính để hiển thị file list.

---

# 5. Metadata cache

Mỗi ebook có thể có một metadata JSON riêng:

```text
metadata/
└── g-xxxx/
    └── FILE_A.json
```

Ví dụ:

```json
{
  "file_id": "FILE_A",
  "modified": "2026-09-17T07:20:00Z",
  "checksum": "xxxx",

  "title": "Marketing Management",
  "authors": [
    "Philip Kotler"
  ],
  "publisher": "Pearson",
  "year": 2019,
  "isbn": "978...",
  "language": "en",
  "series": "",
  "description": "...",
  "subjects": [
    "Marketing"
  ],
  "cover": "/covers/g-xxxx/FILE_A.jpg"
}
```

Metadata JSON phải lưu fingerprint của file:

```text
file_id
modified
checksum
```

để biết metadata còn hợp lệ hay phải extract lại.

---

# 6. Cover

Cover cũng được xử lý incremental.

Không tải toàn bộ ebook chỉ để lấy cover trong mỗi lần build.

Ví dụ:

```text
covers/
└── g-xxxx/
    └── FILE_A.jpg
```

Metadata chỉ tham chiếu:

```json
{
  "cover": "/covers/g-xxxx/FILE_A.jpg"
}
```

Nếu chưa có cover:

```text
cover = null
```

File vẫn hiển thị icon sách mặc định.

---

# 7. Pipeline mới

## Giai đoạn A — Scan Drive

Mỗi lần build:

```text
Google Drive
    ↓
files.list
    ↓
lấy:
    ID
    name
    parent
    size
    modified
    checksum
    MIME
```

Không download ebook ở bước này.

---

## Giai đoạn B — Tạo catalog

Từ kết quả scan:

```text
Drive listing
    ↓
directory tree
    ↓
catalog shards
```

Ví dụ:

```text
g-xxxx/
    root.json
    dir-001.json
    dir-002.json
    dir-003.json
```

Đây là bước bắt buộc để tủ sách có thể xuất hiện nhanh.

---

# 8. Metadata worker

Metadata extraction trở thành một pipeline riêng.

```text
Catalog
    ↓
tìm file chưa có metadata
    ↓
chọn một batch giới hạn
    ↓
download ebook
    ↓
extract metadata
    ↓
extract cover
    ↓
ghi cache
```

Ví dụ mỗi workflow chỉ xử lý:

```text
50 ebooks
```

hoặc một giới hạn phù hợp khác sau khi benchmark.

Không cố xử lý 5.000 ebook trong một workflow.

---

# 9. Incremental metadata

Đây là yêu cầu bắt buộc.

Nếu:

```text
Drive file ID = A
modified = X
checksum = Y
```

và metadata cache cũng có:

```text
file_id = A
modified = X
checksum = Y
```

thì:

```text
KHÔNG download
KHÔNG extract
```

Dùng metadata cache hiện có.

---

Nếu file mới:

```text
file chưa có cache
```

→ extract.

Nếu file thay đổi:

```text
modified khác
OR
checksum khác
```

→ extract lại.

---

# 10. Metadata queue

Không cần database queue.

GitHub repository chính là state store.

Có thể xác định queue bằng:

```text
catalog files
        ↓
metadata tồn tại?
        ↓
fingerprint giống?
        ↓
NO
        ↓
metadata pending
```

Như vậy không cần Redis, PostgreSQL hay backend.

---

# 11. Workflow GitHub Actions

## Workflow 1 — Catalog build

Mục tiêu:

> Luôn ưu tiên đưa file mới lên catalog.

```text
trigger
    ↓
read branches.json
    ↓
scan enabled branches
    ↓
build catalog shards
    ↓
garbage collect deleted branches
    ↓
publish Pages
```

Workflow này **không được download toàn bộ ebook**.

---

## Workflow 2 — Metadata enrichment

Chạy định kỳ hoặc sau catalog build.

```text
trigger
    ↓
scan metadata gaps
    ↓
select limited batch
    ↓
download only selected ebooks
    ↓
extract metadata + cover
    ↓
write cache
    ↓
publish updated catalog
```

Giới hạn batch phải được benchmark thực tế.

---

# 12. Branch garbage collection

Khi branch bị xóa khỏi:

```text
config/branches.json
```

GitHub Actions phải xóa dữ liệu generated tương ứng:

```text
docs/catalog/g-xxxx/
docs/metadata/g-xxxx/
docs/covers/g-xxxx/
docs/opds/g-xxxx/
```

Nhưng:

> **Không bao giờ xóa file nguồn trên Google Drive.**

Xóa branch chỉ là xóa catalog/cache đã generate.

---

# 13. Branch disabled / hidden

`branches.json` vẫn là registry.

Ví dụ:

```json
{
  "id": "g-xxxx",
  "display_name": "Tủ sách A",
  "root_folder_id": "...",
  "enabled": false
}
```

Branch disabled:

- không hiển thị trên website
- không xuất hiện trong OPDS
- không cần scan
- dữ liệu generated có thể được giữ lại cho tới khi garbage collection policy quyết định xóa

---

# 14. Web architecture

Website không tải toàn bộ thư viện.

Luồng:

```text
Trang chủ
    ↓
Danh sách tủ sách
    ↓
root.json của tủ
    ↓
chọn thư mục
    ↓
dir-xxx.json
    ↓
hiển thị file
```

Với thư mục rất lớn:

```text
dir-xxx.json
    ↓
pagination
```

Website chỉ tải phần dữ liệu cần thiết.

---

# 15. Book detail

Khi người dùng chọn một file:

```text
catalog entry
      +
metadata/<file-id>.json
      ↓
Book detail
```

Nếu metadata chưa tồn tại:

```text
Tên file
Dung lượng
Ngày sửa
Loại
Download

Metadata: đang cập nhật...
```

Nếu metadata đã có:

```text
Title
Author
Publisher
Year
ISBN
Language
Series
Description
Cover
Download
```

---

# 16. Download

Download URL thuộc về catalog file entry.

Ví dụ:

```text
https://drive.google.com/uc?export=download&id=FILE_ID
```

Metadata không quyết định việc download.

Do đó:

> Metadata lỗi không được làm hỏng acquisition.

---

# 17. OPDS

OPDS được generate từ:

```text
catalog shard
      +
metadata cache
```

OPDS phải hỗ trợ pagination.

Ví dụ:

```text
opds/
└── g-xxxx/
    ├── root-001.xml
    ├── root-002.xml
    ├── root-003.xml
    └── ...
```

Mỗi entry luôn có acquisition link từ catalog.

Nếu metadata chưa có:

```xml
<title>Original filename.epub</title>
```

vẫn phải có acquisition link.

Khi metadata có:

```xml
<title>Real Book Title</title>
<author>...</author>
```

và acquisition link vẫn giữ nguyên.

---

# 18. Search

Search không được dựa trên việc tải toàn bộ catalog khổng lồ vào browser.

Giai đoạn sau sẽ xây:

```text
search index
```

theo shard.

Search có thể kết hợp:

- filename
- title
- author
- ISBN
- publisher
- subjects
- language

Ban đầu có thể ưu tiên filename/title/author, sau đó mở rộng.

---

# 19. Registration

Apps Script tiếp tục chỉ làm nhiệm vụ registry mutation:

```text
Browser
    ↓
Apps Script
    ↓
GitHub Contents API
    ↓
config/branches.json
    ↓
GitHub Actions
```

Apps Script không scan thư viện và không tạo catalog.

---

# 20. UX khi tạo / xóa / đổi tên tủ

Sau mutation thành công:

```text
Apps Script OK
```

không có nghĩa:

```text
GitHub Pages đã cập nhật
```

GitHub Actions có thể mất nhiều phút.

UI phải báo rõ:

> **Đã ghi nhận thành công. Tàng Thư đang cập nhật thư viện. Thường mất khoảng 10–20 phút để thay đổi xuất hiện trong danh sách.**

Không tự đóng modal sau vài giây.

Không tự reload ngay lập tức.

Người dùng có thể đóng cửa sổ và quay lại sau.

---

# 21. Roadmap triển khai

## STEP 0 — Ổn định registration

Mục tiêu:

- create ổn định
- rename ổn định
- delete ổn định
- không reload giả
- thông báo rõ thời gian Pages update

**Chưa làm catalog lớn ở bước này nếu registration chưa ổn.**

---

## STEP 1 — File-first catalog

Thay generator hiện tại bằng:

```text
Drive scan
    ↓
catalog shards
```

Không metadata extraction.

Kết quả:

```text
Tủ lớn xuất hiện nhanh
```

Đây là bước quan trọng nhất.

---

## STEP 2 — Branch + directory sharding

Implement:

```text
docs/catalog/<branch-id>/root.json
docs/catalog/<branch-id>/dir-xxx.json
```

Không còn catalog JSON khổng lồ.

---

## STEP 3 — Web pagination

Website đọc catalog shard thay vì toàn bộ catalog.

Desktop:

```text
TỦ SÁCH | NỘI DUNG
```

Mobile:

```text
TỦ SÁCH
↓
NỘI DUNG
```

Giữ giao diện Windows 3.x đã chốt.

---

## STEP 4 — OPDS pagination

Tạo:

```text
opds/<branch-id>/...
```

OPDS phải:

- phân trang
- giữ acquisition link
- hoạt động dù metadata chưa có

---

## STEP 5 — Metadata cache

Thêm:

```text
docs/metadata/<branch-id>/<file-id>.json
```

Chỉ extract:

- file mới
- file thay đổi
- file chưa có metadata

---

## STEP 6 — Cover cache

Thêm:

```text
docs/covers/<branch-id>/<file-id>.<ext>
```

Không extract cover lại nếu fingerprint không thay đổi.

---

## STEP 7 — Metadata worker

Thiết kế batch processing:

```text
N files / workflow
```

Benchmark:

- thời gian
- RAM
- GitHub Actions runtime
- số ebook thực tế xử lý được

Sau benchmark mới quyết định batch size chính thức.

---

## STEP 8 — Garbage collection

Khi branch bị xóa:

```text
catalog
metadata
covers
OPDS
```

của branch phải biến mất khỏi HEAD hiện tại.

Không đụng Google Drive.

---

## STEP 9 — Search index

Sau khi catalog + metadata ổn định mới làm search.

Không xây search trước khi mô hình dữ liệu ổn định.

---

## STEP 10 — Optimization

Sau khi hệ thống chạy thực tế:

- giảm số API calls
- giảm GitHub Actions runtime
- tối ưu Drive pagination
- tối ưu metadata batch
- tối ưu OPDS
- tối ưu browser loading
- xử lý retry / lỗi Drive
- xử lý ebook lỗi
- xử lý file bị xóa/đổi tên/move

---

# 22. Trạng thái mong muốn cuối cùng

Một tủ 10.000 sách sẽ hoạt động theo kiểu:

```text
Tạo tủ
   ↓
GitHub Actions scan Drive
   ↓
10.000 file entries
   ↓
catalog xuất bản
   ↓
Tủ xuất hiện trên Tàng Thư
```

Sau đó:

```text
Metadata worker
   ↓
50 sách
   ↓
50 metadata
   ↓
50 cover
```

rồi:

```text
50 sách tiếp theo
```

cho tới khi hoàn thành.

Nếu ngày mai có:

```text
100 sách mới
```

thì chỉ 100 sách đó cần đi qua metadata extraction.

Nếu một ebook không đọc được:

```text
metadata lỗi
```

thì:

```text
file vẫn tồn tại
download vẫn hoạt động
OPDS vẫn có entry
```

---

# 23. Các nguyên tắc không được phá vỡ

1. **File catalog là nguồn dữ liệu hiển thị cơ bản.**
2. **Metadata không được quyết định file có xuất hiện hay không.**
3. **Không download toàn bộ ebook trong catalog build.**
4. **Không extract metadata lại nếu fingerprint không thay đổi.**
5. **Không tạo một JSON khổng lồ cho toàn thư viện.**
6. **Catalog phải shard theo branch và directory.**
7. **OPDS phải phân trang.**
8. **Download URL lấy từ file catalog.**
9. **Metadata và cover được cache riêng.**
10. **Xóa branch không xóa source trên Google Drive.**
11. **`branches.json` chỉ giữ registry.**
12. **Apps Script chỉ quản lý registry mutation.**
13. **GitHub Actions là nơi build catalog/metadata.**
14. **File lỗi metadata vẫn phải xuất hiện.**
15. **Ưu tiên tốc độ xuất bản catalog hơn tốc độ hoàn thiện metadata.**

---

# 24. Kiến trúc cuối cùng

```text
                         GOOGLE DRIVE
                              │
                              │ LIST ONLY
                              ▼
                     ┌─────────────────┐
                     │  DRIVE SCANNER  │
                     └────────┬────────┘
                              │
                ┌─────────────┴─────────────┐
                ▼                           ▼
         FILE CATALOG                 METADATA QUEUE
                │                           │
                │                           ▼
                │                    ebook download
                │                           │
                │                           ▼
                │                    metadata extract
                │                           │
                │                           ▼
                │                     metadata cache
                │                           │
                └─────────────┬─────────────┘
                              ▼
                       STATIC GENERATOR
                              │
              ┌───────────────┼────────────────┐
              ▼               ▼                ▼
           WEBSITE           OPDS           COVERS
              │               │                │
              └───────────────┴────────────────┘
                              ▼
                       GITHUB PAGES
```

**Triết lý cốt lõi:**

> **Catalog trước. Metadata sau. Mỗi file chỉ đọc khi thực sự cần.**
