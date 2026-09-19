import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional
from fastapi import HTTPException, status
from fastapi.responses import FileResponse, RedirectResponse

from app.config import settings


class StorageService(ABC):
    @abstractmethod
    def save(
        self,
        file_bytes: bytes,
        filename: str,
        folder: str = "",
        content_type: str = "image/jpeg",
    ) -> str:
        """Saves a file and returns its stored path or public URL."""
        pass

    @abstractmethod
    def get_file_response(self, path_or_url: str):
        """Returns a FileResponse or RedirectResponse for serving the image."""
        pass

    @abstractmethod
    def get_public_url(self, path_or_url: str) -> str:
        """Returns the public URL for the image."""
        pass


class LocalStorageService(StorageService):
    def __init__(self, base_dir: Optional[Path] = None):
        if base_dir is None:
            # backend/uploads
            self.base_dir = Path(__file__).resolve().parent.parent.parent / "uploads"
        else:
            self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save(
        self,
        file_bytes: bytes,
        filename: str,
        folder: str = "",
        content_type: str = "image/jpeg",
    ) -> str:
        target_dir = self.base_dir / folder if folder else self.base_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / filename
        with open(target_path, "wb") as f:
            f.write(file_bytes)

        rel = f"uploads/{folder.strip('/')}/{filename}" if folder else f"uploads/{filename}"
        return rel.replace("\\", "/")

    def get_file_response(self, path_or_url: str):
        if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
            return RedirectResponse(
                url=path_or_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT
            )

        # Remove leading "uploads/" if path starts with it and search within base_dir or workspace
        clean = path_or_url.lstrip("/")
        file_path = Path(__file__).resolve().parent.parent.parent / clean
        if not file_path.is_file():
            # Also try relative to self.base_dir
            if clean.startswith("uploads/"):
                file_path = self.base_dir / clean[len("uploads/") :]
        if not file_path.is_file():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Image file not found",
            )
        return FileResponse(file_path)

    def get_public_url(self, path_or_url: str) -> str:
        if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
            return path_or_url
        clean = path_or_url.lstrip("/")
        return f"/{clean}"


class S3StorageService(StorageService):
    def __init__(self):
        import boto3
        from botocore.config import Config

        s3_config = Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
        )
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT_URL or None,
            aws_access_key_id=settings.S3_ACCESS_KEY_ID or None,
            aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY or None,
            region_name=settings.S3_REGION or "us-east-1",
            config=s3_config,
        )
        self.bucket = settings.S3_BUCKET
        self.public_base_url = settings.S3_PUBLIC_BASE_URL.rstrip("/") if settings.S3_PUBLIC_BASE_URL else ""

    def save(
        self,
        file_bytes: bytes,
        filename: str,
        folder: str = "",
        content_type: str = "image/jpeg",
    ) -> str:
        key = f"{folder.strip('/')}/{filename}" if folder else f"submissions/{filename}"
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=file_bytes,
            ContentType=content_type,
        )
        if self.public_base_url:
            return f"{self.public_base_url}/{key}"
        return key

    def get_file_response(self, path_or_url: str):
        if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
            return RedirectResponse(
                url=path_or_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT
            )

        # Check if local file exists on disk (backward compatibility for legacy database rows)
        clean = path_or_url.lstrip("/")
        local_path = Path(__file__).resolve().parent.parent.parent / clean
        if local_path.is_file():
            return FileResponse(local_path)

        # Fall back to public S3 URL redirect if S3_PUBLIC_BASE_URL is configured
        if self.public_base_url:
            public_url = f"{self.public_base_url}/{clean}"
            return RedirectResponse(
                url=public_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT
            )

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Image file not found",
        )

    def get_public_url(self, path_or_url: str) -> str:
        if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
            return path_or_url
        if self.public_base_url:
            return f"{self.public_base_url}/{path_or_url.lstrip('/')}"
        return f"/{path_or_url.lstrip('/')}"


def get_storage() -> StorageService:
    if settings.STORAGE_BACKEND.lower() == "s3":
        return S3StorageService()
    return LocalStorageService()
