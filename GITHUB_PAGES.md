# TÀNG THƯ — GitHub Pages / $0 architecture

This branch of the project changes the deployment model from a live Go server to a fully static GitHub Pages catalog.

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
5. The default project URL is:

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
