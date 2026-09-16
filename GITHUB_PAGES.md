# TÀNG THƯ — GitHub Pages / $0 architecture

This branch of the project uses a fully static GitHub Pages catalog.

## Architecture

```text
Google Drive shared folders
        |
        | GitHub Actions (hourly/manual)
        v
Go static generator
        |
        +--> Web catalog
        +--> OPDS catalog
        +--> catalog.json
        |
        v
GitHub Pages
        |
        +--> Browser
        +--> Xteink X4 / OPDS reader
                     |
                     v
             Google Drive direct download
```

No VPS, Cloud Run, Railway, database, or always-on backend is required.

## Google account recommendation

Contributors should use a **dedicated Google Account for TÀNG THƯ**, not their personal/main Google Account.

The shared library folder should be shared as **Anyone with the link — Viewer** if it is intended to be publicly readable by the OPDS client.

## Important privacy trade-off

A static GitHub Pages site cannot proxy a file request. Therefore the OPDS acquisition link must ultimately point to a Google Drive download URL.

The Web catalog does not show a Google Drive download button, but the OPDS XML necessarily contains the acquisition URL because the reading device needs a URL from which to download the file. A user who inspects the OPDS feed can therefore recover the Drive file ID.

This is deliberate for the $0 architecture. The dedicated Google Account recommendation reduces the consequence of that exposure, but it does **not** make the Drive URL secret.

## GitHub setup

1. Add repository secret `TANGTHU_GOOGLE_API_KEY`.
2. Keep branch roots in `config/branches.json`.
3. In repository Settings → Pages, select **GitHub Actions** as the build/deployment source.
4. The workflow runs hourly and can also be started manually.
5. Shelf registration/change requests are submitted as GitHub Issues and processed by `.github/workflows/register-shelf.yml`.
6. After a successful shelf change, that workflow explicitly dispatches `pages.yml` so the Web + OPDS catalog is rebuilt immediately.
7. The default project URL is:

```text
https://zenkjt.github.io/tangthu-opds/
```

## Xteink X4 test

The first real-device test should use:

```text
https://zenkjt.github.io/tangthu-opds/opds/index.xml
```

Test:

1. OPDS root loads.
2. Branch appears.
3. Folder navigation works.
4. `Copy of Tam-ly-hoc-dam-dong-Gustave-Le-Bon.azw3` appears.
5. Download starts on X4.
6. A partial/resume download works if the X4 client supports HTTP resume against the Google Drive endpoint.

The direct Drive URL pattern is the conventional `uc?export=download&id=FILE_ID` form. Google officially documents API-based downloads and `webContentLink`; the `uc` direct-download pattern is commonly used for publicly shared files but is not the preferred documented Drive API interface. Therefore X4 compatibility must be validated empirically rather than assumed.

## Quy tắc làm việc với code trong repo

Đây là quy tắc bàn giao code giữa người dùng và ChatGPT cho dự án TÀNG THƯ.

### 1. Sửa rất nhỏ

Nếu thay đổi chỉ là **1–2 từ, một giá trị đơn giản, hoặc một dòng ngắn đã xác định rõ vị trí**, người dùng có thể sửa trực tiếp trên GitHub Web theo hướng dẫn.

Ví dụ:

- đổi một chuỗi hiển thị;
- đổi một URL;
- đổi một số nhỏ;
- bật/tắt một giá trị cấu hình đơn giản.

### 2. Sửa từ một đoạn code trở lên

Nếu thay đổi lớn hơn, đặc biệt là:

- sửa một function;
- sửa nhiều dòng JavaScript/Go/YAML;
- thêm hoặc thay đổi logic;
- sửa workflow;
- sửa nhiều file;

thì **ChatGPT phải tạo file hoàn chỉnh để người dùng tải về**, không yêu cầu người dùng tự ghép các đoạn code dài từ câu trả lời.

Nguyên tắc là:

```text
Thay đổi nhỏ  → hướng dẫn sửa trực tiếp
Thay đổi lớn  → tạo file hoàn chỉnh
```

### 3. Nếu có nhiều file thay đổi

Khi một yêu cầu làm thay đổi từ 2 file trở lên, ChatGPT nên:

1. tạo đầy đủ các file đã sửa;
2. giữ nguyên đường dẫn tương đối của chúng trong repo;
3. đóng gói tất cả vào **một file ZIP** để người dùng tải về;
4. người dùng giải nén và commit các file đó cùng một lần trên GitHub Web.

Không yêu cầu người dùng tự copy/ghép các đoạn code lớn.

### 4. Sau khi người dùng commit

Sau khi người dùng báo đã commit, ChatGPT phải **kiểm tra lại repo** trước khi tiếp tục:

- xác nhận đúng file đã thay đổi;
- kiểm tra nội dung/logic liên quan;
- kiểm tra GitHub Actions;
- nếu có build/deploy thì kiểm tra workflow run;
- chỉ coi thay đổi là hoàn tất sau khi repo và workflow đã được xác nhận.

### 5. Không tự thay đổi repo khi người dùng yêu cầu bàn giao file

Mặc định, khi người dùng yêu cầu **“tạo file để tao commit”**, ChatGPT chỉ tạo file/bộ file để người dùng tải xuống và commit.

Không tự commit trực tiếp vào `main`, trừ khi người dùng yêu cầu rõ ràng ChatGPT thực hiện commit.

### 6. Giữ nguyên cấu trúc repo

Khi tạo file bàn giao, phải giữ đúng path:

```text
cmd/generate/main.go
.github/workflows/register-shelf.yml
...
```

Nếu chỉ sửa một file thì chỉ bàn giao file đó. Nếu sửa nhiều file thì ZIP phải chứa đúng cây thư mục cần chép vào repo.

