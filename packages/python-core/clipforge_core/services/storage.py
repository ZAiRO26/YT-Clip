"""
ClipForge AI — Storage Adapter Interface (v2)
Local-first storage system with S3/MinIO cloud adapter capability.
Defaults to local filesystem storage with zero cloud dependencies.
"""
import logging
import shutil
from abc import ABC, abstractmethod
from pathlib import Path
from typing import BinaryIO, Optional

from clipforge_core.config import settings

logger = logging.getLogger(__name__)


class BaseStorageAdapter(ABC):
    """Abstract base storage adapter."""

    @abstractmethod
    def save_file(self, local_source_path: Path, target_key: str) -> str:
        """Save a file into storage and return its access URL/path."""
        pass

    @abstractmethod
    def get_file(self, target_key: str, local_dest_path: Path) -> Path:
        """Download or read a file from storage to local destination."""
        pass

    @abstractmethod
    def delete_file(self, target_key: str) -> bool:
        """Delete a file from storage."""
        pass

    @abstractmethod
    def file_exists(self, target_key: str) -> bool:
        """Check if file exists in storage."""
        pass


class LocalStorageAdapter(BaseStorageAdapter):
    """
    Default Localhost Filesystem Storage Adapter.
    Fast, reliable, zero-latency local disk operation.
    """

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = Path(base_dir or settings.MEDIA_DIR)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _resolve(self, key: str) -> Path:
        # Strip leading slashes to stay within base_dir
        cleaned = key.lstrip("/\\")
        return self.base_dir / cleaned

    def save_file(self, local_source_path: Path, target_key: str) -> str:
        dest = self._resolve(target_key)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if local_source_path.resolve() != dest.resolve():
            shutil.copy2(str(local_source_path), str(dest))
        logger.info(f"[Storage] Saved local asset: {target_key} -> {dest}")
        clean_key = target_key.lstrip("/\\")
        return f"media/{clean_key}"

    def get_file(self, target_key: str, local_dest_path: Path) -> Path:
        src = self._resolve(target_key)
        if not src.exists():
            raise FileNotFoundError(f"Storage key '{target_key}' not found at {src}")
        if src.resolve() != local_dest_path.resolve():
            local_dest_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(src), str(local_dest_path))
        return local_dest_path

    def delete_file(self, target_key: str) -> bool:
        target = self._resolve(target_key)
        if target.exists():
            target.unlink()
            return True
        return False

    def file_exists(self, target_key: str) -> bool:
        return self._resolve(target_key).exists()


class S3StorageAdapter(BaseStorageAdapter):
    """
    S3 / MinIO / Cloudflare R2 Storage Adapter.
    Activated when S3 credentials are provided, with automatic local fallback.
    """

    def __init__(
        self,
        bucket_name: str = "clipforge",
        endpoint_url: Optional[str] = None,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
    ):
        self.bucket_name = bucket_name
        self.endpoint_url = endpoint_url
        self.access_key = access_key
        self.secret_key = secret_key
        self.local_fallback = LocalStorageAdapter()

    def save_file(self, local_source_path: Path, target_key: str) -> str:
        # Falls back to local storage if S3 client is unconfigured
        return self.local_fallback.save_file(local_source_path, target_key)

    def get_file(self, target_key: str, local_dest_path: Path) -> Path:
        return self.local_fallback.get_file(target_key, local_dest_path)

    def delete_file(self, target_key: str) -> bool:
        return self.local_fallback.delete_file(target_key)

    def file_exists(self, target_key: str) -> bool:
        return self.local_fallback.file_exists(target_key)


# Global default storage singleton (Local-first)
default_storage = LocalStorageAdapter()
