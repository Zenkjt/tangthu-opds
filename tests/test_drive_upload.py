\
import base64
import json
from pathlib import Path

import pytest

from tangthu_crawler.drive_upload import DriveUploadError, upload_epub


class FakeResponse:
    def __init__(self, body):
        self.body = body
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self):
        return self.body.encode()


def test_upload_sends_encoded_file_and_settings(tmp_path, monkeypatch):
    f = tmp_path / "0neNews.epub"
    f.write_bytes(b"EPUB_TEST")
    monkeypatch.setenv("TANGTHU_APPS_SCRIPT_URL", "https://example.test/exec")
    monkeypatch.setenv("TANGTHU_UPLOAD_TOKEN", "secret")
    monkeypatch.setenv("TANGTHU_NEWS_DRIVE_FOLDER_ID", "folder123")

    calls = {}
    def fake_urlopen(req, timeout):
        calls["url"] = req.full_url
        calls["headers"] = req.headers
        calls["payload"] = json.loads(req.data)
        calls["timeout"] = timeout
        return FakeResponse(json.dumps({
            "ok": True, "filename": "0neNews.epub",
            "file_id": "abc123", "operation": "updated"
        }))

    monkeypatch.setattr("tangthu_crawler.drive_upload.urllib.request.urlopen", fake_urlopen)
    result = upload_epub(f)

    assert result["ok"] is True
    assert calls["payload"]["action"] == "upload_epub"
    assert calls["payload"]["folder_id"] == "folder123"
    assert calls["payload"]["filename"] == "0neNews.epub"
    assert base64.b64decode(calls["payload"]["content_base64"]) == b"EPUB_TEST"


def test_upload_requires_all_configuration(tmp_path, monkeypatch):
    f = tmp_path / "0neNews.epub"
    f.write_bytes(b"EPUB_TEST")
    for key in ("TANGTHU_APPS_SCRIPT_URL", "TANGTHU_UPLOAD_TOKEN", "TANGTHU_NEWS_DRIVE_FOLDER_ID"):
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(DriveUploadError):
        upload_epub(f)
