"""Local filesystem storage — saves raw files under workspace/documents/{doc_id}/."""

import hashlib
import shutil
from pathlib import Path

from config import settings
from domain.enums import SUFFIX_TO_FILETYPE
from domain.errors import AppError
from logging_config import get_logger

logger = get_logger(__name__)

MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB
ALLOWED_EXTENSIONS: frozenset[str] = frozenset(SUFFIX_TO_FILETYPE.keys())


class DocumentStorage:
    """Local filesystem operations for document raw files."""

    def __init__(self, root: str | None = None) -> None:
        self._root = Path(root or settings.workspace_root) / "documents"
        self._root.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def upload(self, *, filename: str, content: bytes, doc_id: str) -> dict:
        """Persist raw file bytes. Returns {source_path, file_hash, file_size}.

        Raises:
            AppError if file is too large, extension unsupported, or doc_id invalid.
        """
        self._validate_doc_id(doc_id)
        self._validate(content, filename)

        target_dir = self._root / doc_id
        target_dir.mkdir(parents=True, exist_ok=True)

        target_path = target_dir / filename
        target_path.write_bytes(content)

        file_hash = hashlib.sha256(content).hexdigest()

        logger.info(
            "document.stored",
            doc_id=doc_id,
            filename=filename,
            size=len(content),
            hash=file_hash[:16],
        )
        return {
            "source_path": str(target_path),
            "file_hash": file_hash,
            "file_size": len(content),
        }

    def delete(self, doc_id: str) -> None:
        """Remove all files for a document."""
        self._validate_doc_id(doc_id)
        target_dir = self._root / doc_id
        if target_dir.exists():
            shutil.rmtree(target_dir)
            logger.info("document.removed", doc_id=doc_id)

    def exists(self, doc_id: str) -> bool:
        return (self._root / doc_id).exists()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_doc_id(doc_id: str) -> None:
        if ".." in doc_id or "/" in doc_id or "\\" in doc_id:
            raise AppError(
                code="INVALID_DOC_ID",
                message="Document ID contains path separators",
                status_code=400,
            )

    @staticmethod
    def _validate(content: bytes, filename: str) -> None:
        if len(content) == 0:
            raise AppError(
                code="EMPTY_FILE",
                message="Uploaded file is empty",
                status_code=422,
            )
        if len(content) > MAX_FILE_SIZE:
            raise AppError(
                code="FILE_TOO_LARGE",
                message=f"File exceeds {MAX_FILE_SIZE // (1024 * 1024)} MB limit",
                status_code=413,
            )
        suffix = Path(filename).suffix.lower()
        if suffix not in ALLOWED_EXTENSIONS:
            raise AppError(
                code="UNSUPPORTED_FILE_TYPE",
                message=f"Unsupported file type '{suffix}'.",
                status_code=415,
            )
