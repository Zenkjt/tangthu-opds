# TÀNG THƯ OPDS — prototype v0.3.0

A lightweight OPDS catalog prototype following the current Tàng Thư design.

## Current prototype focus

- Branches
- exact uppercase `VN` priority ordering
- hidden/unavailable Branch handling
- recursive folder model
- file-first catalog
- OPDS root -> Branches
- Web file-manager style UI
- persistent JSON catalog
- Google Drive adapter boundary

## Important

This prototype is deliberately small and is intended as the next implementation base.
Google Drive API credentials and production authentication/deployment are not bundled.

## Build

```sh
go build -o tangthu-opds ./cmd/tangthu
```

## Run

```sh
./tangthu-opds
```

Open the configured local HTTP address in a browser.

## License

This prototype contains an MIT license notice because the implementation is based on an MIT-licensed Mayberry codebase where applicable. See LICENSE.

## v0.3 architecture updates

- Registration flow: Google Drive link -> retrieved Drive folder name -> editable Branch display name.
- Duplicate root-folder detection and independent Branch rename.
- Website is catalog/management only; no file download.
- OPDS acquisition is mediated by Tàng Thư rather than redirecting to Google Drive.
- Added Storage Identity Isolation requirements.
