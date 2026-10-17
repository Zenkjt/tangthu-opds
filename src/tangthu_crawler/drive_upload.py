\
from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request
from pathlib import Path


class DriveUploadError(RuntimeError):
    """Raised when the Google Drive upload endpoint rejects an edition."""


def upload_epub(
    epub_path: str | Path,
    *,
    endpoint: str | None = None,
    token: str | None = None,
    folder_id: str | None = None,
    filename: str = "0neNews.epub",
    timeout: int = 120,
) -> dict:
    """
    Upload an EPUB through the Tàng Thư Apps Script Web App.

    Secrets and destination are configured by GitHub Actions:
      TANGTHU_APPS_SCRIPT_URL
      TANGTHU_UPLOAD_TOKEN
      TANGTHU_NEWS_DRIVE_FOLDER_ID

    Apps Script must expose action=upload_epub and validate the shared token.
    The folder is supplied explicitly and the existing named file is updated
    in place to preserve its Drive file ID.
    """
    endpoint = (endpoint or os.getenv("TANGTHU_APPS_SCRIPT_URL", "")).strip()
    token = token or os.getenv("TANGTHU_UPLOAD_TOKEN", "")
    folder_id = (folder_id or os.getenv("TANGTHU_NEWS_DRIVE_FOLDER_ID", "")).strip()

    if not endpoint:
        raise DriveUploadError("Missing TANGTHU_APPS_SCRIPT_URL.")
    if not token:
        raise DriveUploadError("Missing TANGTHU_UPLOAD_TOKEN.")
    if not folder_id:
        raise DriveUploadError("Missing TANGTHU_NEWS_DRIVE_FOLDER_ID.")

    path = Path(epub_path)
    if not path.is_file():
        raise DriveUploadError(f"EPUB file does not exist: {path}")

    payload = {
        "action": "upload_epub",
        "token": token,
        "folder_id": folder_id,
        "filename": filename,
        "mime_type": "application/epub+zip",
        "content_base64": base64.b64encode(path.read_bytes()).decode("ascii"),
    }
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=data,
        headers={"Content-Type": "text/plain;charset=utf-8", "Accept": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            text = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace")
        raise DriveUploadError(f"Apps Script HTTP {exc.code}: {text[:1000]}") from exc
    except urllib.error.URLError as exc:
        raise DriveUploadError(f"Could not reach Apps Script: {exc}") from exc

    try:
        result = json.loads(text)
    except json.JSONDecodeError as exc:
        raise DriveUploadError(f"Apps Script returned non-JSON: {text[:500]}") from exc

    if not result.get("ok"):
        raise DriveUploadError(result.get("error", "Unknown Apps Script upload error"))
    return result
