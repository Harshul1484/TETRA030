"""Syllabus upload.

Proves the pipeline is live rather than fixture-backed. The seeded data
path remains the primary one: an unattended visitor must never have to
upload something before they can see results.
"""

import logging
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.api.deps import get_pipeline
from app.pipeline.ingest import parse_syllabus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["syllabi"])

ALLOWED_SUFFIXES = {".pdf", ".docx", ".doc", ".txt", ".md"}
MAX_UPLOAD_BYTES = 10 * 1024 * 1024


@router.post("/syllabi")
async def upload_syllabus(file: UploadFile = File(...)) -> dict:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type {suffix or '(none)'}. "
            f"Accepted: {', '.join(sorted(ALLOWED_SUFFIXES))}",
        )

    payload = await file.read()
    if len(payload) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds 10 MB")

    with tempfile.TemporaryDirectory() as workdir:
        path = Path(workdir) / (file.filename or f"upload{suffix}")
        path.write_bytes(payload)

        document = parse_syllabus(path)
        if document is None:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Could not extract usable text. Scanned PDFs without a "
                    "text layer are not supported."
                ),
            )

        try:
            course_code = get_pipeline().ingest_syllabus(document)
        except Exception as exc:
            logger.exception("Ingest failed for %s", file.filename)
            raise HTTPException(
                status_code=500, detail=f"Ingest failed: {exc}"
            ) from exc

    return {
        "course_code": course_code,
        "title": document.title,
        "characters_parsed": len(document.raw_text),
        "gaps_url": f"/api/courses/{course_code}/gaps",
    }
