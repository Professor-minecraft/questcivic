import io
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from fastapi import HTTPException
from fastapi.responses import FileResponse, RedirectResponse

from app.config import Settings
from app.services.storage import LocalStorageService, S3StorageService, get_storage


def test_local_storage_save_and_response(tmp_path):
    storage = LocalStorageService(base_dir=tmp_path)
    content = b"test-image-data-local"
    filename = "test_img.jpg"

    stored_path = storage.save(content, filename, folder="")
    assert stored_path == "uploads/test_img.jpg"
    assert (tmp_path / filename).read_bytes() == content

    # Response for existing file
    resp = storage.get_file_response(stored_path)
    assert isinstance(resp, FileResponse)

    # Response for non-existent file
    with pytest.raises(HTTPException) as exc:
        storage.get_file_response("uploads/nonexistent.jpg")
    assert exc.value.status_code == 404

    # Response when path is already an external URL
    ext_resp = storage.get_file_response("https://example.com/photo.jpg")
    assert isinstance(ext_resp, RedirectResponse)
    assert ext_resp.status_code == 307


def test_local_storage_folder_subdirectories(tmp_path):
    storage = LocalStorageService(base_dir=tmp_path)
    content = b"complaint-image-data"
    filename = "comp_123.png"

    stored_path = storage.save(content, filename, folder="complaints")
    assert stored_path == "uploads/complaints/comp_123.png"
    assert (tmp_path / "complaints" / filename).read_bytes() == content


@patch("boto3.client")
def test_s3_storage_upload_and_response(mock_boto_client):
    mock_s3 = MagicMock()
    mock_boto_client.return_value = mock_s3

    with patch("app.services.storage.settings") as mock_settings:
        mock_settings.S3_ENDPOINT_URL = "https://my-ref.supabase.co/storage/v1/s3"
        mock_settings.S3_BUCKET = "civicquest-uploads"
        mock_settings.S3_ACCESS_KEY_ID = "test-access-key"
        mock_settings.S3_SECRET_ACCESS_KEY = "test-secret-key"
        mock_settings.S3_REGION = "ap-south-1"
        mock_settings.S3_PUBLIC_BASE_URL = "https://my-ref.supabase.co/storage/v1/object/public/civicquest-uploads"
        mock_settings.STORAGE_BACKEND = "s3"

        storage = S3StorageService()

        # Check boto3 client configuration
        mock_boto_client.assert_called_once()
        call_kwargs = mock_boto_client.call_args[1]
        assert call_kwargs["endpoint_url"] == "https://my-ref.supabase.co/storage/v1/s3"
        assert call_kwargs["aws_access_key_id"] == "test-access-key"
        assert call_kwargs["aws_secret_access_key"] == "test-secret-key"
        assert call_kwargs["region_name"] == "ap-south-1"
        assert call_kwargs["config"].signature_version == "s3v4"
        assert call_kwargs["config"].s3["addressing_style"] == "path"

        # Test S3 save
        content = b"fake-s3-image-bytes"
        url = storage.save(content, "photo123.jpg", folder="submissions", content_type="image/jpeg")

        mock_s3.put_object.assert_called_once_with(
            Bucket="civicquest-uploads",
            Key="submissions/photo123.jpg",
            Body=content,
            ContentType="image/jpeg",
        )
        assert url == "https://my-ref.supabase.co/storage/v1/object/public/civicquest-uploads/submissions/photo123.jpg"

        # Test get_file_response with full S3 URL
        resp = storage.get_file_response(url)
        assert isinstance(resp, RedirectResponse)
        assert resp.status_code == 307
        assert resp.headers["location"] == url


@patch("boto3.client")
def test_s3_storage_backward_compatibility(mock_boto_client, tmp_path):
    mock_s3 = MagicMock()
    mock_boto_client.return_value = mock_s3

    with patch("app.services.storage.settings") as mock_settings:
        mock_settings.S3_ENDPOINT_URL = "https://my-ref.supabase.co/storage/v1/s3"
        mock_settings.S3_BUCKET = "civicquest-uploads"
        mock_settings.S3_ACCESS_KEY_ID = "test-access-key"
        mock_settings.S3_SECRET_ACCESS_KEY = "test-secret-key"
        mock_settings.S3_REGION = "ap-south-1"
        mock_settings.S3_PUBLIC_BASE_URL = "https://my-ref.supabase.co/storage/v1/object/public/civicquest-uploads"
        mock_settings.STORAGE_BACKEND = "s3"

        storage = S3StorageService()

        # When path is a relative path not found on disk, redirects to S3 public URL
        resp = storage.get_file_response("uploads/legacy_item.jpg")
        assert isinstance(resp, RedirectResponse)
        assert resp.status_code == 307
        assert resp.headers["location"] == "https://my-ref.supabase.co/storage/v1/object/public/civicquest-uploads/uploads/legacy_item.jpg"


def test_get_storage_factory():
    with patch("app.services.storage.settings") as mock_settings:
        mock_settings.STORAGE_BACKEND = "local"
        storage = get_storage()
        assert isinstance(storage, LocalStorageService)

    with patch("app.services.storage.settings") as mock_settings, patch("boto3.client"):
        mock_settings.STORAGE_BACKEND = "s3"
        mock_settings.S3_ENDPOINT_URL = "https://s3.example.com"
        mock_settings.S3_BUCKET = "my-bucket"
        mock_settings.S3_ACCESS_KEY_ID = "key"
        mock_settings.S3_SECRET_ACCESS_KEY = "secret"
        mock_settings.S3_REGION = "us-east-1"
        mock_settings.S3_PUBLIC_BASE_URL = "https://s3.example.com/my-bucket"
        storage = get_storage()
        assert isinstance(storage, S3StorageService)


def test_production_s3_validation():
    # When ENVIRONMENT=production and STORAGE_BACKEND=s3, missing S3 vars must raise ValueError
    with pytest.raises(ValueError, match="STORAGE_BACKEND=s3"):
        Settings(
            ENVIRONMENT="production",
            STORAGE_BACKEND="s3",
            SECRET_KEY="super-secret-key-min-12-chars",
            ADMIN_PASSWORD="secure-admin-pass-12-chars",
            AUDITOR_PASSWORD="secure-auditor-pass-12-chars",
            S3_ENDPOINT_URL="",  # Missing
            S3_BUCKET="my-bucket",
            S3_ACCESS_KEY_ID="key",
            S3_SECRET_ACCESS_KEY="secret",
            S3_PUBLIC_BASE_URL="https://s3.example.com/my-bucket",
        )

    # When all S3 variables are valid, it succeeds
    s = Settings(
        ENVIRONMENT="production",
        STORAGE_BACKEND="s3",
        SECRET_KEY="super-secret-key-min-12-chars",
        ADMIN_PASSWORD="secure-admin-pass-12-chars",
        AUDITOR_PASSWORD="secure-auditor-pass-12-chars",
        S3_ENDPOINT_URL="https://my-ref.supabase.co/storage/v1/s3",
        S3_BUCKET="civicquest-uploads",
        S3_ACCESS_KEY_ID="actual-access-key",
        S3_SECRET_ACCESS_KEY="actual-secret-key",
        S3_REGION="ap-south-1",
        S3_PUBLIC_BASE_URL="https://my-ref.supabase.co/storage/v1/object/public/civicquest-uploads",
    )
    assert s.STORAGE_BACKEND == "s3"
    assert s.S3_BUCKET == "civicquest-uploads"
