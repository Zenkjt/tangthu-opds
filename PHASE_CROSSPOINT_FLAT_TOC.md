# Checkpoint — CrossPoint native TOC

## Vấn đề

CrossPoint non-touch chỉ hiển thị tầng đầu của EPUB native TOC trong `Select Chapter`.

EPUB cũ tạo native TOC theo cấu trúc:

```text
Mục lục
Nguồn A
  ├── Bài 1
  ├── Bài 2
Nguồn B
  ├── Bài 3
```

Vì vậy máy không cảm ứng chỉ thấy `Mục lục`, không chọn trực tiếp được các bài.

## Quyết định

Tách hai vai trò:

- `toc.xhtml`: vẫn giữ TOC HTML 2 tầng `Nguồn → Bài`, để máy cảm ứng có thể mở và bấm link.
- EPUB native TOC (`toc.ncx` / navigation): chuyển thành **flat list**, mỗi bài là một `navPoint` cấp cao nhất.
- Không đưa `toc.xhtml` vào native TOC.
- Không dùng `epub.Section()` trong native TOC.

Native TOC mới:

```text
Bài 1
Bài 2
Bài 3
...
```

## Phạm vi sửa

- `src/tangthu_crawler/epub.py`
- `tests/test_epub.py`

Không thay đổi crawler, ArticlePool, extraction, policy, ảnh hoặc upload Drive.

## Test mới

Kiểm tra `toc.ncx`:

- Có đúng số `navPoint` bằng số bài.
- Mọi bài đều là `navPoint` cấp cao nhất.
- Không có nested `navPoint`.
- Không có `toc.xhtml` trong native chapter selection.
- Thứ tự bài được giữ nguyên.

## Trạng thái

Đã sửa test để phản ánh đúng thiết kế: native `nav.xhtml` flat theo từng bài, không chứa `toc.xhtml`. Lỗi CI vừa gặp là assertion cũ của test, không phải lỗi EPUB.
