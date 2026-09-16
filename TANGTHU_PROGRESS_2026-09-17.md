# TÀNG THƯ OPDS — Tiến độ & checkpoint

**Ngày checkpoint:** 2026-09-17  
**Repository:** `https://github.com/Zenkjt/tangthu-opds`  
**Branch:** `main`

> Đây là file checkpoint để đọc lại trước khi làm tiếp. Nội dung ghi lại kiến trúc, các quyết định đã chốt, trạng thái code/workflow và các việc còn lại. Không tự ý thay đổi các quyết định đã chốt nếu chưa bàn lại.

---

## 1. Mục tiêu dự án

**TÀNG THƯ OPDS** là một thư viện sách phân tán:

- Catalog tập trung trên GitHub Pages.
- Mỗi “tủ sách” là một thư mục Google Drive được chia sẻ.
- Tàng Thư chỉ giữ thông tin catalog và cấu hình tủ sách, không giữ file sách.
- Người dùng có thể truy cập catalog bằng web hoặc OPDS.
- Mục tiêu vận hành: **$0**, không dùng VPS/Railway/Cloud Run luôn chạy.
- Contributor không cần cài phần mềm; chỉ cần chia sẻ một Google Drive folder.

Kiến trúc MVP hiện tại:

```text
Google Drive
     │
     ▼
GitHub Actions
  scan / index
     │
     ├── EPUB metadata
     ├── EPUB cover extraction
     └── static catalog + OPDS
     │
     ▼
GitHub Pages
     │
     ├── Web catalog
     └── OPDS
```

Đang nghiên cứu thêm Google Apps Script như một lớp **realtime API/gateway**, nhưng **chưa thay thế kiến trúc hiện tại**.

---

# 2. Repository hiện tại

Repository:

`Zenkjt/tangthu-opds`

Trang:

`https://zenkjt.github.io/tangthu-opds/`

OPDS:

`https://zenkjt.github.io/tangthu-opds/opds/index.xml`

Các thành phần chính:

```text
cmd/generate/main.go
internal/drive/drive.go
internal/metadata/metadata.go
config/branches.json
.github/workflows/pages.yml
.github/workflows/register-shelf.yml
```

---

# 3. Kiến trúc catalog đã chốt

## 3.1 File-first

Catalog **không gom/merge file thành một “book record” duy nhất**.

Danh sách hiển thị giống như mở Google Drive:

- mỗi file là một dòng;
- giữ nguyên tên file;
- có size;
- modified date;
- MIME/type;
- checksum;
- Drive file ID;
- folder structure.

Metadata sách chỉ là **lớp thông tin bổ sung**:

- cover;
- title;
- author;
- publisher;
- year;
- ISBN;
- language;
- series;
- description;
- subjects/tags.

Nếu metadata không đọc được thì **file vẫn phải xuất hiện trong catalog**.

Đây là quyết định quan trọng, không được đổi sang kiểu “gom theo sách” nếu chưa bàn lại.

---

# 4. Mô hình Tủ sách

Mỗi branch/tủ sách hiện có dạng:

```json
{
  "id": "...",
  "display_name": "...",
  "root_folder_id": "...",
  "enabled": true
}
```

Ý nghĩa:

- `id`: ID nội bộ của Tàng Thư.
- `display_name`: tên hiển thị trên Tàng Thư.
- `root_folder_id`: Google Drive folder ID.
- `enabled`: tủ có hiển thị hay không.

### Tên tủ độc lập với tên Google Drive

Nếu contributor đổi `display_name` trong Tàng Thư:

- chỉ đổi tên trên Tàng Thư;
- **không rename Google Drive folder**.

Nếu Google Drive folder sau này bị rename thì tên Tàng Thư cũng **không tự đổi**.

---

# 5. Quy tắc sắp xếp tủ

Các tên bắt đầu chính xác bằng chữ hoa:

```text
VN
```

được ưu tiên lên trước.

Trong mỗi nhóm:

- alphabetical.

Web và OPDS phải dùng cùng thứ tự.

---

# 6. Quy tắc trạng thái tủ

Đã thống nhất về mặt thiết kế:

- `online`: hiển thị.
- `hidden`: không hiển thị nhưng giữ cấu hình.
- `unavailable`: không hiển thị nhưng giữ lại để sửa.

Trong MVP hiện tại cấu hình đang dùng chủ yếu `enabled: true/false`; phần trạng thái chi tiết chưa hoàn thiện.

---

# 7. Giao diện đã chốt

Phong cách:

**Windows 3.x / classic gray**

Bảng màu:

```text
Background:       #c0c0c0
Panels:            white
Section/title bar: #dfdfdf
Brand/notice:      #ffffcc
Text:              black
Selection:         light gray + dotted outline
```

Không dùng nền đen/dark content.

## Toolbar

Không có menu.

Các nút:

```text
Up
Home
Refresh
Search
Tủ sách
Views
Info
```

Không có nút `Tủ sách` bị lặp.

## Layout

Hai panel chính:

```text
┌──────────────────────┬──────────────────────┐
│ TỦ SÁCH              │ NỘI DUNG             │
│                      │                      │
│                      │ file list             │
│                      │                      │
└──────────────────────┴──────────────────────┘
```

Desktop:

- hai panel cạnh nhau.

Mobile:

- hai panel xếp dọc;
- toolbar tự wrap;
- cover thumbnail nhỏ hơn.

## Danh sách file

**List view**, không phải Grid.

Mỗi file có:

- cover thumbnail nhỏ;
- tên;
- author/metadata nếu có;
- format;
- size;
- year/date tùy dữ liệu có được.

## Brand

```text
TÀNG THƯ
A book is a dream holding in your hands.
```

## Search

Có search bar ở cuối giao diện.

---

# 8. Info / giới thiệu

Nội dung đã thống nhất:

> Tàng thư là thư viện phân tán, sách được liệt kê theo chuẩn OPDS, bạn chép đường dẫn `https://...` vào OPDS list của máy đọc sách để truy cập.
>
> Tàng thư có nhiều “tủ sách”, mỗi tủ sách là một thư mục đã được chia sẻ trên google drive của người chia sẻ, không nên dùng tài khoản chính cho việc này.
>
> Bạn có thể đặt tên/đổi tên tủ mà bạn chia sẻ, các tên bắt đầu bằng `VN` sẽ được ưu tiên hiển thị.
>
> Vì các hạn chế của máy đọc sách nên mỗi tủ sách không nên để quá nhiều sách.
>
> Happy reading.
>
> *A book is a dream holding in your hands.*

---

# 9. Đăng ký / đổi tên / xóa Tủ sách

Chỉ có **một nút `Tủ sách`**.

Modal gồm:

```text
Drive link
Tên tủ

[Kiểm tra link]

[ Tạo tủ / Đổi tên / Xóa tủ ]
```

## Kiểm tra link

User paste Google Drive folder link.

Đã sửa parser để chấp nhận cả:

```text
/drive/folders/<ID>
/drive/u/1/folders/<ID>
/folders/<ID>
?id=<ID>
```

Ví dụ thực tế đã test thành công:

```text
https://drive.google.com/drive/u/1/folders/...
```

## Logic action button

### Tủ mới

Sau khi `Kiểm tra link` thành công:

```text
Tạo tủ
```

### Tủ đã tồn tại

Tự điền tên Tàng Thư hiện tại:

```text
Đổi tên
```

### Xóa

Nếu tủ đã tồn tại và người dùng nhập chính xác:

```text
DELETE
```

không phân biệt hoa thường:

```text
Xóa tủ
```

Điều kiện:

- chỉ xóa registration khỏi Tàng Thư;
- **không bao giờ xóa Google Drive folder**.

Button bị disabled cho tới khi `Kiểm tra link` thành công.

---

# 10. Cơ chế GitHub Issue

Tàng Thư không sửa trực tiếp `config/branches.json` từ browser.

Sau khi user bấm action:

```text
Tạo tủ
Đổi tên
Xóa tủ
```

website mở GitHub Issue được prefill.

User bấm **Create issue**.

Workflow:

```text
Issue
  ↓
register-shelf.yml
  ↓
parse request
  ↓
verify Google Drive folder
  ↓
read config/branches.json
  ↓
create / update / delete registration
  ↓
commit config to main
  ↓
workflow_dispatch pages.yml
  ↓
rebuild + deploy Pages
```

---

# 11. Self-service workflow đã test

File:

```text
.github/workflows/register-shelf.yml
```

Workflow chỉ xử lý Issue có title bắt đầu:

```text
[TANGTHU]
```

Body có các field:

```text
- Google Drive:
- Tên tủ:
- Hành động:
```

Workflow:

- validate hostname Google Drive;
- parse folder ID;
- gọi Google Drive API;
- kiểm tra folder còn tồn tại;
- đọc `config/branches.json`;
- create/update/delete;
- commit config;
- dispatch Pages build;
- comment kết quả vào Issue;
- đóng Issue.

ID branch mới được tạo dạng:

```text
g-<sha256(folderId)[:12]>
```

---

# 12. Test đăng ký đã thành công

Đã từng test với:

```text
VN - vhnn
```

Issue:

`#2`

Kết quả:

- registration thành công;
- workflow success;
- Pages được dispatch;
- tủ xuất hiện trên web;
- sau đó đã test xóa.

Google Drive folder thực tế được giữ nguyên.

---

# 13. Test xóa đã thành công

Quy trình đã test:

```text
Tủ sách
→ paste Drive link
→ Kiểm tra link
→ hệ thống nhận ra tủ hiện có
→ nhập DELETE
→ nút đổi thành Xóa tủ
→ Xóa tủ
→ GitHub Issue
→ Create issue
```

Kết quả:

**xóa registration thành công.**

Google Drive không bị xóa.

---

# 14. Google Drive API

MVP hiện tại dùng Google Drive API với API key cho các folder được chia sẻ phù hợp.

Ý tưởng listing:

```text
'<FOLDER_ID>' in parents and trashed = false
```

Nguồn tài liệu tham khảo:

- Google Drive API — Search files
- Google Drive API — Files.get
- Google Drive API — Manage downloads
- Google Drive API — Resource keys

API key nằm trong GitHub Actions Secret:

```text
TANGTHU_GOOGLE_API_KEY
```

Không commit key vào repository.

---

# 15. Ebook allowlist hiện tại

`internal/drive/drive.go` hiện đang lọc ebook:

```text
EPUB
MOBI
AZW3
```

Có giới hạn:

```text
25 MiB / file
```

Folder structure vẫn được giữ.

Các file khác bị loại khỏi catalog.

**Lưu ý:** giới hạn 25 MiB và allowlist này là quyết định kỹ thuật đã được đưa vào code, nhưng ban đầu là giả định của implementation chứ chưa phải yêu cầu nghiệp vụ được user chốt. Nếu quay lại phần này cần xác nhận lại trước khi mở rộng/siết tiếp.

---

# 16. Metadata EPUB

File:

```text
internal/metadata/metadata.go
```

Đã triển khai hướng đọc metadata trực tiếp từ EPUB.

Các trường mục tiêu:

- title;
- author;
- publisher;
- year/date;
- ISBN;
- language;
- series;
- description;
- subjects/tags.

Nguyên tắc:

> Metadata extraction fail thì file vẫn phải được index.

Không để lỗi metadata làm mất ebook khỏi catalog.

---

# 17. Cover EPUB

Đã chuyển từ việc chỉ dùng thumbnail Drive sang hướng:

```text
Google Drive EPUB
        ↓
download EPUB trong GitHub Actions
        ↓
parse EPUB ZIP
        ↓
META-INF/container.xml
        ↓
OPF
        ↓
tìm cover
        ↓
docs/covers/<file-id>.<ext>
```

Các cách tìm cover đã được code theo thứ tự:

1. `meta name="cover"`
2. image có `properties="cover-image"`
3. fallback theo tên/path có dấu hiệu cover.

Cover được static hóa vào GitHub Pages.

Mục tiêu là tránh phụ thuộc vào thumbnail Google Drive.

---

# 18. Thay đổi UI cover gần nhất

Cover trong list đã được tăng kích thước từ khoảng:

```text
44 × 58
```

lên khoảng:

```text
64 × 90
```

và có giảm nhẹ trên mobile.

Book detail modal cũng được đổi để hiển thị cover lớn hơn.

Quan trọng:

Detail modal **không còn các nút**:

```text
Truy cập / tải
Mở OPDS
```

vì thiết kế đã thống nhất:

> Click vào sách chủ yếu để **xem thông tin**, không phải biến nó thành một màn hình download.

---

# 19. Vấn đề cover hiện tại

Trước commit cover mới, user phản ánh:

> hình bìa sách không lên.

Sau đó đã commit code mới để:

- extract cover thật từ EPUB;
- lưu cover static;
- hiển thị cover lớn hơn;
- detail modal hiển thị cover + metadata;
- bỏ action download/OPDS khỏi detail.

**Cần kiểm tra thực tế sau khi Pages build xong**:

1. cover có xuất hiện trong list không;
2. URL `/covers/...` có tồn tại không;
3. cover có đúng sách không;
4. cover có bị lỗi với EPUB không có cover không;
5. metadata có xuất hiện đúng không;
6. click file chỉ mở detail view, không còn download/open OPDS action.

---

# 20. Checkpoint GitHub gần nhất

Commit gần nhất được kiểm tra trước checkpoint này:

```text
5e91beb53641506e0cc1728dae7adad5c4e3c4f7
```

Nội dung liên quan:

- cover extraction;
- metadata;
- UI cover/detail.

Pages workflow lúc kiểm tra đang chạy:

```text
Pages workflow #24
run id: 35126119903
event: push
head SHA: 5e91beb53641506e0cc1728dae7adad5c4e3c4f7
status: in_progress
```

Build job:

```text
104895457422
Generate static catalog: in progress
```

Vì vậy checkpoint này **không khẳng định deployment #24 đã hoàn tất**. Việc đầu tiên khi quay lại dự án là kiểm tra Actions và deployed site.

---

# 21. Config tại thời điểm checkpoint

`config/branches.json` lúc kiểm tra đang có một tủ:

```json
{
  "branches": [
    {
      "id": "g-773c046e560b",
      "display_name": "Zenkjt - đang đọc",
      "root_folder_id": "1jbUFnfzkseLrcWISBwaKwoJK6hZY6bl7",
      "enabled": true
    }
  ]
}
```

Folder này là:

```text
https://drive.google.com/drive/folders/1jbUFnfzkseLrcWISBwaKwoJK6hZY6bl7
```

---

# 22. Google Apps Script — hướng nghiên cứu tiếp theo

Sau khi MVP GitHub Actions + Pages chạy ổn, bắt đầu nghiên cứu:

**Google Apps Script Web App**

Ý tưởng:

```text
                 Google Drive
                     │
          ┌──────────┴──────────┐
          │                     │
          ▼                     ▼
    GitHub Actions         Apps Script
      batch                 realtime
          │                     │
          ▼                     ▼
 static catalog            API / cover
          │                     │
          └──────────┬──────────┘
                     ▼
                GitHub Pages
                     │
                     ▼
                    OPDS
```

## GitHub Actions vẫn phụ trách

- scan toàn bộ tủ;
- batch indexing;
- EPUB parsing;
- metadata extraction;
- cover extraction;
- static web;
- static OPDS.

## Apps Script có thể phụ trách

- verify folder realtime;
- lấy metadata realtime;
- cover fallback;
- search/API;
- các endpoint động;
- có thể hỗ trợ registration nếu thấy hợp lý.

---

# 23. Những gì đã biết về Apps Script

Google Apps Script có:

```javascript
DriveApp.getFolderById(id)
DriveApp.getFileById(id)
```

và các API để lấy:

- file;
- blob;
- name;
- MIME type;
- last updated;
- ID;
- download URL.

Apps Script có thể deploy thành Web App.

Có các chế độ:

```text
execute as me
execute as user accessing
```

và access:

```text
ANYONE_ANONYMOUS
ANYONE
DOMAIN
MYSELF
```

Quota đáng chú ý:

```text
6 phút / execution
```

với tài khoản Gmail cá nhân.

Vì vậy Apps Script rất hợp với:

```text
catalog API
metadata API
cover API
folder verification
```

nhưng **không nên biến nó thành proxy download EPUB chính**.

---

# 24. Điểm bảo mật quan trọng của Apps Script

Nếu Web App chạy:

```text
ANYONE_ANONYMOUS
```

và:

```text
execute as deployer
```

thì tuyệt đối không được cho phép client gửi tùy ý:

```text
fileId
```

rồi Apps Script lấy bất kỳ file nào trong Drive của account deployer.

Phải whitelist:

```text
registered root folder
        ↓
requested file
        ↓
kiểm tra file có nằm dưới root không
```

Chỉ phục vụ những tủ đã đăng ký.

Đây là điểm phải thiết kế kỹ trước khi triển khai Apps Script.

---

# 25. Google Account

Thiết kế hiện tại vẫn khuyến nghị contributor dùng:

**một Google Account riêng cho việc chia sẻ sách**

thay vì tài khoản cá nhân chính.

Điều này giảm rủi ro privacy nhưng:

> hidden URL ≠ security.

Nếu acquisition URL trỏ trực tiếp tới Google Drive thì URL đó vẫn có thể xuất hiện trong OPDS/XML và có thể bị quan sát.

---

# 26. Câu hỏi kiến trúc cần nghiên cứu tiếp

Ngày mai cần đào sâu nhất vào câu hỏi:

> **Apps Script có thể làm một OPDS endpoint động hoàn chỉnh đến mức nào?**

Cần nghiên cứu cụ thể:

```text
/index.xml
/feed
/shelf/<id>
/folder/<id>
/book/<id>
/cover/<id>
/download/<id>
```

và:

- OPDS 1.x / 2.x;
- acquisition links;
- cover URL;
- pagination;
- navigation;
- search;
- Google Drive file streaming;
- resource key;
- caching;
- quota;
- anonymous access;
- security boundary;
- có cần Apps Script làm gateway hay chỉ cần API phụ trợ.

Đặc biệt phải so sánh:

### Phương án A

```text
GitHub Pages
+ static OPDS
+ Google Drive acquisition URL
```

### Phương án B

```text
GitHub Pages
+ Apps Script dynamic OPDS/API
+ Google Drive
```

### Phương án C

```text
GitHub Pages
+ static OPDS
+ Apps Script chỉ làm API/cover fallback
+ Google Drive acquisition
```

Chưa chọn phương án nào ở thời điểm checkpoint này.

---

# 27. Nguyên tắc không nên phá vỡ

1. **$0 runtime** là mục tiêu chính.
2. Không dùng VPS/Railway/Cloud Run nếu chưa có lý do rõ ràng.
3. GitHub Pages vẫn là public front-end chính của MVP.
4. Google Drive vẫn là storage.
5. Tàng Thư không lưu sách.
6. Catalog file-first.
7. Metadata là lớp bổ sung.
8. Không để metadata lỗi làm mất file.
9. Tên Tàng Thư độc lập với tên Google Drive.
10. `DELETE` chỉ xóa registration, không xóa Drive.
11. User thao tác đăng ký qua GitHub Issue.
12. GitHub Actions là batch engine.
13. Apps Script chỉ được thêm khi nó giải quyết được vấn đề thực tế.
14. Không biến Apps Script thành download proxy nếu quota/hiệu năng không phù hợp.
15. Không commit secret/API key vào repo.

---

# 28. Quy tắc làm việc với code

User đã chốt workflow:

> Chỉ tự sửa những đoạn cực ngắn 1–2 từ/giá trị nếu thật sự cần.  
> Code thay đổi lớn hơn → tạo **file hoàn chỉnh** để user download và commit.

Không dùng patch cho workflow này.

Nếu cần nhiều file:

- tạo từng file hoàn chỉnh;
- ghi rõ target path;
- user commit từng file;
- sau đó kiểm tra repo + Actions + deployment.

---

# 29. Việc đầu tiên khi quay lại

Checklist:

- [ ] Kiểm tra Pages workflow #24 đã success chưa.
- [ ] Mở deployed web.
- [ ] Kiểm tra cover có hiện không.
- [ ] Kiểm tra cover có đúng kích thước mong muốn.
- [ ] Click một ebook → kiểm tra detail view.
- [ ] Xác nhận không còn nút Download / Open OPDS trong detail.
- [ ] Kiểm tra metadata.
- [ ] Nếu cover/metadata lỗi: debug trước, **chưa chuyển sang Apps Script**.
- [ ] Nếu MVP ổn: bắt đầu nghiên cứu Apps Script OPDS/API.
- [ ] So sánh A/B/C ở mục 26.
- [ ] Chỉ sau khi có kết luận mới quyết định có thêm Apps Script vào kiến trúc.

---

# 30. Trạng thái tổng quát

### Đã làm

- [x] Repository
- [x] GitHub Pages
- [x] static OPDS
- [x] Google Drive branch model
- [x] Drive folder parser
- [x] branch registration
- [x] branch rename
- [x] branch delete
- [x] GitHub Issue workflow
- [x] automatic Pages rebuild
- [x] file-first catalog
- [x] Windows 3.x UI direction
- [x] responsive layout direction
- [x] metadata extraction
- [x] EPUB cover extraction code
- [x] larger cover UI
- [x] detail view redesigned toward “view information only”

### Đang chờ xác nhận thực tế

- [ ] Pages build/deploy của commit `5e91beb...`
- [ ] cover xuất hiện thực tế
- [ ] cover đúng sách
- [ ] metadata hiển thị đúng trên production

### Chưa làm

- [ ] Apps Script integration
- [ ] dynamic OPDS qua Apps Script
- [ ] API/search realtime
- [ ] cover fallback qua Apps Script
- [ ] pagination/search nâng cao
- [ ] hoàn thiện branch states `hidden/unavailable`
- [ ] xác nhận lại allowlist + giới hạn 25 MiB
- [ ] hoàn thiện production hardening

---

## 31. Next session

**Ưu tiên 1:** kiểm tra production sau commit cover/metadata.

**Ưu tiên 2:** nếu production ổn, đào sâu Google Apps Script.

**Ưu tiên 3:** nghiên cứu khả năng xây dựng OPDS động bằng Apps Script và so sánh với static OPDS hiện tại.

**Chưa thay đổi kiến trúc chính cho tới khi có kết luận từ bước nghiên cứu trên.**
