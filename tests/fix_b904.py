"""Fix B904: raise-without-from-inside-except."""
import re

files = {
    "src/api/routers/agents.py": [
        ('raise AppError(code="WRITE_FAILED", message=str(exc), status_code=500)',
         'raise AppError(code="WRITE_FAILED", message=str(exc), status_code=500) from exc'),
        ('raise AppError(code="REVIEW_FAILED", message=str(exc), status_code=500)',
         'raise AppError(code="REVIEW_FAILED", message=str(exc), status_code=500) from exc'),
        ('raise AppError(code="DEBATE_FAILED", message=str(exc), status_code=500)',
         'raise AppError(code="DEBATE_FAILED", message=str(exc), status_code=500) from exc'),
    ],
    "src/api/routers/documents.py": [
        ('raise AppError(code="UPLOAD_FAILED", message=f"Failed to process file: {exc}", status_code=500)',
         'raise AppError(code="UPLOAD_FAILED", message=f"Failed to process file: {exc}", status_code=500) from exc'),
    ],
    "src/api/routers/knowledge.py": [
        ('raise AppError(code="PROCESS_FAILED", message=f"Failed to process document: {exc}", status_code=500)',
         'raise AppError(code="PROCESS_FAILED", message=f"Failed to process document: {exc}", status_code=500) from exc'),
        ('raise AppError(code="SEARCH_FAILED", message=f"Search failed: {exc}", status_code=500)',
         'raise AppError(code="SEARCH_FAILED", message=f"Search failed: {exc}", status_code=500) from exc'),
    ],
    "src/api/routers/publish.py": [
        ('raise AppError(code="PUBLISH_FAILED", message=str(exc), status_code=500)',
         'raise AppError(code="PUBLISH_FAILED", message=str(exc), status_code=500) from exc'),
    ],
    "src/services/knowledge.py": [
        ('raise AppError(code="PIPELINE_FAILED", message=f"Document pipeline failed: {exc}", status_code=500)',
         'raise AppError(code="PIPELINE_FAILED", message=f"Document pipeline failed: {exc}", status_code=500) from exc'),
    ],
}

for path, replacements in files.items():
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    for old, new in replacements:
        text = text.replace(old, new)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)

print("B904 fixes applied")
