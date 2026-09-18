# OPDS / X4 — Tổng hợp khảo sát phiên 18/09/2026

## 1. Mục tiêu
Điều tra vì sao OPDS của Tàng Thư hiển thị được trên CrossPoint X4 nhưng tải EPUB thất bại, trong khi Mayberry — mô hình mà Tàng Thư được phát triển theo — tải sách tốt trên X4.

## 2. Tàng Thư hiện tại
Acquisition link hiện trỏ trực tiếp tới Google Drive:
```xml
<link rel="http://opds-spec.org/acquisition"
      href="https://drive.google.com/uc?id=..."
      type="application/epub+zip"/>
```
Test Google Drive bằng `curl -I` cho response thực tế gồm `Content-Type: application/octet-stream`, `Content-Disposition: attachment`, `Content-Length: 309520`, `Accept-Ranges: bytes`.

OPDS XML khai báo `application/epub+zip`, nhưng HTTP response của Google là `application/octet-stream`. Chưa có bằng chứng MIME type là nguyên nhân lỗi X4.

## 3. Log X4 khi tải Tàng Thư
Log quan trọng:
```text
[ERR] [HTTP] wolfSSL incomplete: got 368428 of 0 bytes
[ERR] [OPDS] Download failed: 1
```
X4 còn báo:
```text
[INF] [OPDS] Feed truncated to fit memory
```

Trong `HttpDownloader`, `sink.total` chỉ được lấy từ Content-Length khi `SecureHttpClient` báo có Content-Length. Vì vậy `of 0` không chứng minh server gửi Content-Length=0. Quyết định cuối cùng là `http.responseComplete()`. Nếu false, X4 coi response là incomplete và xóa/fail download.

Do đó nghi vấn chính hiện tại là HTTP response/body framing + completion detection của SecureHttpClient/wolfSSL, chưa phải OPDS parser.

## 4. Catalog memory
`Feed truncated to fit memory` cho thấy feed XML lớn hơn phần bộ nhớ X4 dành cho OPDS parser.

Hệ quả có thể là:
- X4 không hiện toàn bộ sách trong một feed lớn.
- Giảm summary/category/metadata sẽ làm XML nhỏ hơn.
- Nên chia feed/phân trang và giữ navigation feed nhỏ.
- Đây là vấn đề riêng với download failure.

## 5. Mayberry catalog
Mayberry dùng acquisition URL dạng:
```text
/download/<book-id>
```
Ví dụ:
```text
/download/9786043128000
/download/MB02580f7d5306
/download/MB183fdd40f0d9
```
Catalog không chứa URL Google Drive/storage.

## 6. Mayberry download chain đã kiểm chứng
Không có Basic Auth:
```text
HTTP/1.1 401 Unauthorized
www-authenticate: Basic realm="Mayberry"
```

Có credentials:
```text
HTTP/1.1 302 Found
location: https://zenkjt-vn.branch.pub/download/9786043128000?token=...
```

Token là JWT, có các claim quan sát được như `branch_id`, `isbn`, `purpose=download`, `iss`, `exp`, `iat`. Token thật không đưa vào repo/MD.

Gọi URL branch với token cho:
```text
HTTP/1.1 200 OK
content-disposition: attachment; filename="9786043128000.epub"
Content-Type: application/epub+zip
Content-Length: 397990
```

Đây là response cuối cùng mà X4 đang nhận khi Mayberry download thành công.

## 7. Mô hình Mayberry
```text
X4
 |
 | GET /download/<book-id> + Basic Auth
 v
Mayberry
 |
 | 302 Location: branch download URL + JWT
 v
Branch server
 |
 | 200
 | Content-Type: application/epub+zip
 | Content-Length: chính xác
 | Content-Disposition: attachment
 | EPUB body
 v
X4
```

Điểm quan trọng: X4 không cần biết EPUB nằm ở storage nào. Acquisition URL chỉ là endpoint của server.

## 8. CrossPoint source đã khảo sát
Build hiện tại dùng `FREEINK_NET_WOLFSSL` và `SecureHttpClient`.

`HttpDownloader.cpp` có redirect handling riêng, tối đa 5 redirect. Sau mỗi hop nó tạo/request qua `SecureHttpClient` và cuối cùng kiểm tra `responseComplete()`.

Nếu response incomplete:
```text
wolfSSL incomplete: got <downloaded> of <total> bytes
```
và download fail.

Source cũng có xử lý backend khác trong đó `Content-Length` có thể bằng 0 khi response chunked. Vì vậy không thể kết luận rằng X4 bắt buộc phải có Content-Length chỉ từ log `of 0`.

Các PR CrossPoint liên quan đã xem:
- #2475: đưa wolfSSL vào các luồng HTTP/TLS liên quan.
- #2661: sửa duplicate User-Agent khi dùng SecureHttpClient.
- #2561: có sửa `authorization header upon OPDS redirects`, đồng thời test download file lớn trên X4.
- #3114: liên quan hợp nhất HTTP transport quanh SecureHttpClient và response completion/truncated response.

## 9. Giả thuyết hiện tại
Chưa đủ bằng chứng để khẳng định nguyên nhân là:
1. `application/octet-stream`
2. Google redirect
3. HTTP body framing
4. Transfer-Encoding
5. Content-Length ở một hop
6. TLS EOF/wolfSSL completion
7. header cụ thể
8. tổ hợp redirect + Google + SecureHttpClient

Điểm bất thường cần giải thích:
```text
curl thấy Content-Length: 309520
X4 log: got 368428 of 0 bytes
```
Do đó response mà X4 thực sự xử lý không đơn giản tương đương với response mà `curl -I` quan sát được.

## 10. Kết luận kiến trúc
Mayberry không giải quyết bằng một Google Drive URL đặc biệt. Nó dùng server-side download endpoint.

Hướng Tàng Thư có cơ sở:
```text
Tàng Thư OPDS
    |
    | /download/<book-id>
    v
Tàng Thư download endpoint
    |
    | fetch/stream storage
    v
Google Drive
    |
    v
Tàng Thư trả response EPUB sạch
    |
    v
X4
```

Mục tiêu là để X4 chỉ nhìn thấy một HTTP download response kiểu Mayberry.

## 11. Hướng tiếp theo
### Bước 1
Đào tiếp implementation thật của `SecureHttpClient`, đặc biệt:
- `responseComplete()`
- `hasContentLength()`
- `getContentLength()`
- xử lý Content-Length
- chunked encoding
- EOF
- TLS close/termination.

### Bước 2
Đào sâu implementation download của Mayberry/branch để xác định chính xác server tạo response thế nào.

### Bước 3
Tạo POC Tàng Thư `/download/<book-id>` trả EPUB trực tiếp, không redirect:
```http
HTTP/1.1 200 OK
Content-Type: application/epub+zip
Content-Length: <exact size>
Content-Disposition: attachment; filename="<name>.epub"
```

Backend vẫn có thể lấy file từ Google Drive; X4 không tiếp xúc trực tiếp với Google.

### Bước 4
Nếu direct-200 thành công, mới test thêm 302/token theo mô hình Mayberry.

### Bước 5
Sau khi download ổn định, xử lý riêng vấn đề catalog memory/truncation bằng cách giảm metadata và chia feed.

## 12. Trạng thái cuối buổi
Chưa sửa downloader của X4.
Chưa thay acquisition URL production của Tàng Thư.
Đã xác minh Mayberry download thành công và xác định được mô hình server-side download endpoint.
Buổi sau tiếp tục từ `SecureHttpClient`/`responseComplete()` và thiết kế POC `/download/<book-id>`.
