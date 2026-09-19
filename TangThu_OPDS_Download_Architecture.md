# Tàng Thư — OPDS Download Architecture & Conclusions

## Status

**Checkpoint: 2026-09-19**

The Tàng Thư OPDS download flow has been successfully tested end-to-end on the CrossPoint X4.

The X4 can now download an EPUB from Tàng Thư and open/read it successfully.

---

## 1. Problem originally observed

The original Tàng Thư download flow used:

```text
X4
 ↓
Tàng Thư OPDS
 ↓
Cloudflare Worker
 ↓ 302 Redirect
Google Drive
 ↓
EPUB
 ↓
X4
```

This produced a download failure on X4.

The relevant X4 log was:

```text
[ERR] [HTTP] wolfSSL incomplete: got 368428 of 0 bytes
[ERR] [OPDS] Download failed: 1
```

The important observation was that the X4 had actually received the EPUB bytes, but the final HTTP response did not provide the response semantics expected by the X4 downloader.

---

## 2. Mayberry / Branch investigation

The working Mayberry model was studied as the reference implementation because Mayberry downloads already work correctly on the X4.

The relevant conceptual download contract is:

```text
GET /download/<resource>
        ↓
HTTP 200 OK
Content-Type: application/epub+zip
Content-Disposition: attachment; filename="..."
Content-Length: <exact file size>
        ↓
EPUB byte stream
```

Mayberry/Branch performs authorization and branch-specific logic around this endpoint, but those parts are not required for the initial Tàng Thư implementation.

The important part for X4 compatibility is the **final HTTP response**, not the federation/branch infrastructure.

---

## 3. What was retained from Mayberry

Tàng Thư Worker intentionally models the useful HTTP portion of the Mayberry Branch download response:

- HTTPS download endpoint
- `GET /download/<resource>`
- final response is `200 OK`
- `Content-Type: application/epub+zip`
- `Content-Disposition: attachment`
- exact `Content-Length`
- EPUB body is streamed

---

## 4. What was deliberately removed

The following Mayberry mechanisms are NOT required by Tàng Thư's current architecture:

- JWT authentication
- Ed25519 signing
- `branch_id`
- ISBN binding inside the token
- `purpose=download`
- Branch registration
- Branch heartbeat
- WebSocket tunnel
- Mayberry federation
- Mayberry database
- local Branch filesystem

Tàng Thư uses Google Drive as the EPUB storage backend, so the Worker replaces the local Branch file lookup with an upstream `fetch()`.

Authentication/security can be added later if needed. It is not part of the X4 compatibility proof.

---

## 5. Final Tàng Thư architecture

The working architecture is:

```text
X4
 ↓
Tàng Thư OPDS
 ↓
GitHub Pages
 ↓
/download/<Google Drive File ID>
 ↓
Cloudflare Worker
 ↓
fetch Google Drive
 ↓
Worker returns HTTP 200
   Content-Type: application/epub+zip
   Content-Length: exact upstream size
   Content-Disposition: attachment
   streamed body
 ↓
X4
 ↓
EPUB
```

The Worker is effectively acting as a small, simplified "Branch download endpoint".

---

## 6. Why the Worker must NOT redirect

The earlier architecture:

```text
Worker
 ↓
302
 ↓
Google Drive
```

was tested and resulted in an X4 download failure.

Therefore:

**Do not revert the Worker to a redirect-based download.**

The Worker must fetch the upstream EPUB and return the file response itself.

---

## 7. Current Worker behavior

The current Worker:

1. Receives:

```text
GET /download/<file-id>
```

2. Extracts the Google Drive file ID.

3. Fetches:

```text
https://drive.usercontent.google.com/download?id=<file-id>&export=download&confirm=t
```

4. Follows upstream redirects.

5. Checks that the upstream request succeeded.

6. Creates a new response with:

```http
Content-Type: application/epub+zip
Content-Length: <upstream Content-Length>
Content-Disposition: attachment; filename="<file-id>.epub"
```

7. Returns:

```javascript
new Response(upstream.body, {
  status: 200,
  headers,
});
```

The important implementation detail is that the EPUB body is **streamed**.

The Worker must NOT use `arrayBuffer()` or otherwise buffer the entire EPUB in memory.

---

## 8. Verified HTTP response

The Worker was tested from Windows using:

```powershell
curl.exe -I "https://tangthu-download-test.mienluonngon.workers.dev/download/<FILE_ID>"
```

The actual successful response was:

```text
HTTP/1.1 200 OK
Content-Type: application/epub+zip
Content-Length: 309520
Content-Disposition: attachment; filename="<FILE_ID>.epub"
```

This confirmed that the Worker is providing the HTTP information required by the X4.

---

## 9. Final X4 verification

After the Worker was changed from redirect mode to the Mayberry-style HTTP response:

**Tàng Thư → X4 → Download EPUB succeeded.**

The EPUB was successfully downloaded to the X4.

This is the definitive compatibility test.

The previous X4 error:

```text
wolfSSL incomplete: got ... of 0 bytes
```

no longer prevents the download.

---

## 10. OPDS pagination

This download solution is independent of the OPDS pagination work.

The current Tàng Thư OPDS catalog uses:

```text
25 books per page
```

Pagination was already verified to work on the X4 and other OPDS applications.

The current acquisition URL points to the Cloudflare Worker download endpoint.

Therefore the two pieces are now:

```text
OPDS pagination
        +
Mayberry-style Worker download endpoint
```

Both are working.

---

## 11. Current baseline — DO NOT CHANGE casually

The following architecture should be treated as the current working baseline:

```text
GitHub Pages
    = OPDS catalog + pagination

Cloudflare Worker
    = download proxy / acquisition endpoint

Google Drive
    = EPUB storage

X4
    = verified OPDS reader/download client
```

The critical property is:

```text
Worker → HTTP 200 → exact Content-Length → streamed EPUB → X4
```

Do not replace this with a simple redirect unless a new test proves that the X4 accepts it.

---

## 12. Future improvements

These are NOT required for the current working state.

Possible later work:

### A. Better filename

Currently the Worker uses:

```text
<Google Drive File ID>.epub
```

A later version could use a proper book filename if that metadata is available.

### B. Error handling

Improve differentiation between:

- missing file ID
- Google Drive 404
- Google Drive permission failure
- upstream timeout
- invalid/non-EPUB response

### C. Security / authorization

If public access becomes a concern, add short-lived authorization similar to Mayberry.

This should be treated as a separate security layer and must not break the working HTTP download contract.

### D. HTTP Range support

Range/partial-content behavior can be investigated later if X4 or other readers need it.

Do not add it merely for theoretical completeness.

### E. Monitoring / limits

If the library grows significantly, review:

- Cloudflare Worker limits
- bandwidth usage
- Google Drive download behavior
- concurrent downloads

These are operational considerations, not part of the current X4 compatibility problem.

---

## 13. Key conclusion

The original download failure was not solved by changing the OPDS catalog or by changing the EPUB storage.

It was solved by changing the **final HTTP acquisition response**.

The successful model is:

```text
Mayberry Branch model
        ↓
HTTP 200
Content-Type
Content-Disposition
Content-Length
streamed EPUB
        ↓
adapted to

Tàng Thư Worker
        ↓
Google Drive upstream
        ↓
HTTP 200
Content-Type: application/epub+zip
Content-Disposition: attachment
Content-Length: exact upstream size
streamed EPUB
        ↓
X4
```

This has now been verified on real hardware.

**Checkpoint: download works on X4.**
