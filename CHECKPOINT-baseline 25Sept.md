# CHECKPOINT — Restore Tàng Thư live pipeline

Mục tiêu:
- Chỉ sử dụng https://tangthu.pages.dev/
- OPDS chính thức: https://tangthu.pages.dev/opds
- Drive change detection dùng Google Drive Changes API.
- Trigger driveCheck: mỗi 30 phút.
- Khi Drive thay đổi: Apps Script dispatch workflow `cloudflare.yml`.
- Cloudflare Pages build phải bao gồm shelf lifecycle.
- Giữ nguyên CPFont preview/download.
- Không thay đổi drive.go, bookshelf UI hoặc OPDS generation logic.

Files thay:
1. `apps-script/Code.gs`
   - restore bản tham chiếu từ commit `c69cec8`
   - dùng `changes/startPageToken` + `changes.list`
   - dispatch `workflow_dispatch` cho `cloudflare.yml`

2. `.github/workflows/cloudflare.yml`
   - thêm `repository_dispatch: types: [drive_changed]`
   - thêm lifecycle preflight/persist/merge
   - đổi `contents: read` thành `contents: write` vì workflow có commit `config/branches.json`
   - giữ nguyên CPFont preview/download
   - giữ nguyên OPDS redirect `/opds` và `/opds/`
   - `TANGTHU_BASE_URL` giữ `https://tangthu.pages.dev`

Không thay:
- `.github/workflows/pages.yml`
- `internal/drive/drive.go`
- `scripts/postprocess_cpfont.py`
- `scripts/postprocess_bookshelf.py`
- `scripts/paginate_opds.py`
- `scripts/rewrite_opds_download_urls.py`

Test sau khi thay:
1. Commit 2 file.
2. Deploy/update Apps Script với Code.gs mới.
3. Chạy `setupDriveChangeTrigger()` một lần.
4. Chạy `driveCheck()` để tạo baseline nếu chưa có.
5. Thay đổi 1 EPUB trong Drive.
6. Chạy `driveCheck()` thủ công.
7. Kiểm tra GitHub: `Cloudflare Pages` phải chạy.
8. Sau build, kiểm tra:
   - `https://tangthu.pages.dev/`
   - `https://tangthu.pages.dev/opds`
   - tủ suspended
   - EPUB mới
   - CPFont preview/download.
