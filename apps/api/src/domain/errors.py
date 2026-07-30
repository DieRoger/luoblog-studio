"""Exception classes and error codes.

All application errors extend AppError. Handlers registered in api/errors.py
map these to the standard JSON error response format.
"""

from http import HTTPStatus


class AppError(Exception):
    """Base application error with machine-readable code."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = HTTPStatus.BAD_REQUEST,
        details: dict | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


# --- Domain Errors ---


class NotFoundError(AppError):
    def __init__(self, entity: str, entity_id: str) -> None:
        super().__init__(
            code=f"{entity.upper()}_NOT_FOUND",
            message=f"{entity} with id {entity_id} not found",
            status_code=HTTPStatus.NOT_FOUND,
        )


class InvalidStateTransition(AppError):
    def __init__(self, entity: str, current: str, target: str) -> None:
        super().__init__(
            code="INVALID_STATE_TRANSITION",
            message=f"Cannot transition {entity} from '{current}' to '{target}'",
            status_code=HTTPStatus.CONFLICT,
        )


# --- Infrastructure Errors ---


class ParsingError(AppError):
    def __init__(self, file_type: str, reason: str) -> None:
        super().__init__(
            code="PARSING_FAILED",
            message=f"Failed to parse {file_type}: {reason}",
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        )


class EmbeddingError(AppError):
    def __init__(self, reason: str) -> None:
        super().__init__(
            code="EMBEDDING_SERVICE_ERROR",
            message=f"Embedding service error: {reason}",
            status_code=HTTPStatus.SERVICE_UNAVAILABLE,
        )


class LLMError(AppError):
    def __init__(self, reason: str) -> None:
        super().__init__(
            code="LLM_SERVICE_ERROR",
            message=f"LLM service error: {reason}",
            status_code=HTTPStatus.SERVICE_UNAVAILABLE,
        )


# --- Validation Errors ---


class ValidationError(AppError):
    def __init__(self, field: str, reason: str) -> None:
        super().__init__(
            code="VALIDATION_ERROR",
            message=f"Validation error on '{field}': {reason}",
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        )


class DuplicateFileError(AppError):
    """Raised when a file with the same content hash already exists (DB unique constraint)."""

    def __init__(self, file_hash: str) -> None:
        super().__init__(
            code="DUPLICATE_FILE",
            message=f"File with hash {file_hash[:16]}... already exists",
            status_code=HTTPStatus.CONFLICT,
        )
