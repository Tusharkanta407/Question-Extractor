"""FastAPI routes for Foundation question bank extractor."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, Response

from foundation.answer_llm import needs_llm_answer
from foundation.docx_export import document_to_docx_bytes, subjective_docx_bytes
from foundation.formatter import (
    format_subjective_bank,
    output_filename,
    subjective_output_filename,
    SUBJECTIVE_TYPES,
    EXCLUDED_TYPES,
)
from foundation.pipeline import (
    estimate_file_tokens,
    estimate_llm_for_file,
    is_foundation_format,
    process_to_question_bank,
)

_PKG_DIR = Path(__file__).resolve().parent
STATIC_DIR = _PKG_DIR / "static"

router = APIRouter(tags=["foundation"])


async def _read_mmd(file: UploadFile) -> tuple[str, str]:
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file selected.")
    name = Path(file.filename).name
    if not name.lower().endswith(".mmd"):
        raise HTTPException(status_code=400, detail="Only .mmd files are supported.")
    raw = await file.read()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="File must be UTF-8 text.") from exc
    if not text.strip():
        raise HTTPException(status_code=400, detail="File is empty.")
    return text, name


def _stats_from_doc(doc) -> dict:
    _excluded = SUBJECTIVE_TYPES | EXCLUDED_TYPES
    obj_missing = sum(1 for q in doc.questions if needs_llm_answer(q))
    subjective_count = sum(1 for q in doc.questions if q.question_type in _excluded)
    objective_count = len(doc.questions) - subjective_count
    return {
        "objective_missing": obj_missing,
        "llm_skipped_subjective": doc.llm_skipped_subjective,
        "llm_queued": doc.llm_tokens.get("queued", 0),
        "subjective_count": subjective_count,
        "objective_count": objective_count,
    }


@router.get("/foundation", response_class=HTMLResponse)
async def foundation_page() -> HTMLResponse:
    return HTMLResponse((STATIC_DIR / "foundation.html").read_text(encoding="utf-8"))


@router.post("/api/foundation/estimate")
async def foundation_estimate(file: UploadFile = File(...)) -> dict:
    text, name = await _read_mmd(file)
    if not is_foundation_format(text):
        raise HTTPException(status_code=422, detail="Not a Foundation format .mmd file.")
    return {
        "source_file": name,
        "file_tokens": estimate_file_tokens(text),
        "llm_estimate": estimate_llm_for_file(text),
    }


@router.post("/api/foundation/extract")
async def foundation_extract(
    file: UploadFile = File(...),
    use_llm: str = Form("false"),
) -> dict:
    text, name = await _read_mmd(file)
    if not is_foundation_format(text):
        raise HTTPException(status_code=422, detail="Not a Foundation format .mmd file.")

    llm_on = use_llm.lower() in ("true", "1", "yes", "on")
    try:
        content, doc = process_to_question_bank(text, source_file=name, use_llm=llm_on)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if not doc.questions:
        raise HTTPException(status_code=422, detail="No questions found.")

    stem = Path(name).stem
    extra = _stats_from_doc(doc)

    # Build subjective content for preview
    subjective_content = format_subjective_bank(doc)

    return {
        "title": doc.title,
        "subject": doc.subject,
        "class_level": doc.class_level,
        "format": "foundation",
        "filename_mmd": output_filename(stem, "mmd"),
        "filename_json": output_filename(stem, "json"),
        "filename_docx": output_filename(stem, "docx"),
        "filename_subjective_mmd": subjective_output_filename(stem, "mmd"),
        "filename_subjective_docx": subjective_output_filename(stem, "docx"),
        "content": content,
        "subjective_content": subjective_content,
        "json": json.dumps(doc.to_dict(), ensure_ascii=False, indent=2) + "\n",
        "question_count": len(doc.questions),
        "paired_answers": doc.paired_answers,
        "answer_entries": doc.answer_entries,
        "llm_filled": doc.llm_filled,
        "use_llm": llm_on,
        "file_tokens": estimate_file_tokens(text),
        "llm_tokens": doc.llm_tokens,
        **extra,
    }


@router.post("/api/foundation/download")
async def foundation_download(
    file: UploadFile = File(...),
    output_format: str = Form("mmd"),
    use_llm: str = Form("false"),
) -> Response:
    text, name = await _read_mmd(file)
    if not is_foundation_format(text):
        raise HTTPException(status_code=422, detail="Not a Foundation format .mmd file.")

    llm_on = use_llm.lower() in ("true", "1", "yes", "on")
    try:
        content, doc = process_to_question_bank(text, source_file=name, use_llm=llm_on)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    stem = Path(name).stem
    fmt = output_format.lower().strip()

    if fmt == "json":
        body = json.dumps(doc.to_dict(), ensure_ascii=False, indent=2).encode("utf-8")
        filename = output_filename(stem, "json")
        media = "application/json; charset=utf-8"
    elif fmt == "docx":
        body = document_to_docx_bytes(doc)
        filename = output_filename(stem, "docx")
        media = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    else:
        body = content.encode("utf-8")
        filename = output_filename(stem, "mmd")
        media = "text/plain; charset=utf-8"

    return Response(
        content=body,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/api/foundation/download-subjective")
async def foundation_download_subjective(
    file: UploadFile = File(...),
    output_format: str = Form("mmd"),
    use_llm: str = Form("false"),
) -> Response:
    """Download the subjective (non-convertible) questions as a separate file."""
    text, name = await _read_mmd(file)
    if not is_foundation_format(text):
        raise HTTPException(status_code=422, detail="Not a Foundation format .mmd file.")

    llm_on = use_llm.lower() in ("true", "1", "yes", "on")
    try:
        _, doc = process_to_question_bank(text, source_file=name, use_llm=llm_on)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    subj_count = sum(1 for q in doc.questions if q.question_type in (SUBJECTIVE_TYPES | EXCLUDED_TYPES))
    if not subj_count:
        raise HTTPException(
            status_code=404,
            detail="No subjective questions found in this file.",
        )

    stem = Path(name).stem
    fmt = output_format.lower().strip()

    if fmt == "docx":
        body = subjective_docx_bytes(doc)
        filename = subjective_output_filename(stem, "docx")
        media = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    else:
        body = format_subjective_bank(doc).encode("utf-8")
        filename = subjective_output_filename(stem, "mmd")
        media = "text/plain; charset=utf-8"

    return Response(
        content=body,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
