"""Where evidence files come from: Cloud Storage in production, a folder for samples and tests."""

from __future__ import annotations

import asyncio
import mimetypes
from pathlib import Path
from typing import Protocol

from google.cloud import storage


class EvidenceStore(Protocol):
    async def read(self, path: str) -> tuple[bytes, str]:
        """Return the file's bytes and its media type."""
        ...


class EvidenceRemover(Protocol):
    async def delete_prefix(self, prefix: str) -> int:
        """Delete every file whose path starts with ``prefix``; return how many there were."""
        ...


def _guess_type(path: str) -> str:
    return mimetypes.guess_type(path)[0] or "application/octet-stream"


class CloudStorageStore:
    def __init__(self, bucket: str, client: storage.Client | None = None) -> None:
        self._bucket = (client or storage.Client()).bucket(bucket)

    async def read(self, path: str) -> tuple[bytes, str]:
        def download() -> tuple[bytes, str]:
            blob = self._bucket.blob(path)
            data = blob.download_as_bytes()
            return data, blob.content_type or _guess_type(path)

        return await asyncio.to_thread(download)

    async def delete_prefix(self, prefix: str) -> int:
        def delete() -> int:
            blobs = list(self._bucket.list_blobs(prefix=prefix))
            # A file that is already gone is not an error: the aim is that none is left.
            self._bucket.delete_blobs(blobs, on_error=lambda _blob: None)
            return len(blobs)

        return await asyncio.to_thread(delete)


class FolderStore:
    def __init__(self, root: Path) -> None:
        self._root = root

    async def read(self, path: str) -> tuple[bytes, str]:
        file = (self._root / path).resolve()
        if not file.is_relative_to(self._root.resolve()):
            raise ValueError(f"{path} is outside the evidence folder")
        return file.read_bytes(), _guess_type(path)
