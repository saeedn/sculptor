"""Tests for the file upload endpoint.

Tests cover:
- POST /api/v1/upload-file (multipart file upload)
"""

from io import BytesIO

from fastapi.testclient import TestClient

from sculptor.config.settings import SculptorSettings


def test_upload_file_returns_file_id(client: TestClient) -> None:
    """Uploading a file returns a file_id preserving the original extension."""
    content = b"hello world"
    response = client.post(
        "/api/v1/upload-file",
        files={"file": ("test.png", BytesIO(content), "image/png")},
    )
    assert response.status_code == 200
    data = response.json()
    assert "fileId" in data
    assert data["fileId"].endswith(".png")


def test_upload_file_stores_content_on_disk(
    client: TestClient,
    test_settings: SculptorSettings,
) -> None:
    """Uploaded file content is written to the upload directory."""
    content = b"binary content here"
    response = client.post(
        "/api/v1/upload-file",
        files={"file": ("doc.pdf", BytesIO(content), "application/pdf")},
    )
    assert response.status_code == 200
    file_id = response.json()["fileId"]

    stored = test_settings.upload_path / file_id
    assert stored.is_file()
    assert stored.read_bytes() == content


def test_upload_file_rejects_oversized_file(client: TestClient) -> None:
    """Files exceeding MAX_UPLOAD_SIZE_BYTES (20 MB) are rejected with 413."""
    oversized = b"x" * (20 * 1024 * 1024 + 1)
    response = client.post(
        "/api/v1/upload-file",
        files={"file": ("big.bin", BytesIO(oversized), "application/octet-stream")},
    )
    assert response.status_code == 413


def test_upload_file_without_extension(client: TestClient) -> None:
    """Uploading a file with no extension produces a file_id without one."""
    response = client.post(
        "/api/v1/upload-file",
        files={"file": ("Makefile", BytesIO(b"all: build"), "text/plain")},
    )
    assert response.status_code == 200
    file_id = response.json()["fileId"]
    assert "." not in file_id
