"""FastAPI routes for the post-extraction pipeline:

extract -> classify -> embeddings -> similarity-vs-uploaded -> drop
duplicates -> clean -> MathML -> competitive tagging -> JSON output.

Two ways to feed it questions:
  1. Upload a .mmd file: it is run through the existing extractor/converter
     first (foundation or bypass_question, auto-detected), then through
     this pipeline.
  2. POST raw question JSON directly (already-extracted questions from any
     source) to /api/pipeline/run-json.

In both cases you can optionally attach an `uploaded_bank` file/JSON - the
existing question bank to check new questions against - so true duplicates
already in your system get dropped rather than re-added.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from extract import detect_format, extract_document
from pipeline.runner import run_pipeline

router = APIRouter(tags=["pipeline"])


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


async def _read_json(file: UploadFile) -> list[dict]:
    raw = await file.read()
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON file: {exc}") from exc
    if isinstance(data, dict) and "questions" in data:
        data = data["questions"]
    if not isinstance(data, list):
        raise HTTPException(status_code=400, detail="JSON file must be a list of questions.")
    return data


def _extract_questions_from_mmd(text: str, name: str) -> list[dict]:
    """Run the existing extractor/converter to get classified (SCQ/MCQ/
    INTEGER/...) questions, returned as plain dicts ready for the pipeline."""
    fmt = detect_format(text)

    if fmt == "foundation":
        from foundation.pipeline import process_to_question_bank

        _, fdoc = process_to_question_bank(text, source_file=name)
        return fdoc.to_dict()["questions"]

    doc = extract_document(text, source_file=name)
    return doc.to_dict()["questions"]


@router.post("/api/pipeline/run")
async def pipeline_run(
    file: UploadFile = File(...),
    uploaded_bank: UploadFile | None = File(None),
    similarity_threshold: float = Form(0.93),
    skip_embeddings: str = Form("false"),
    force_rule_based_tagging: str = Form("false"),
) -> dict:
    """Upload a .mmd file: extract -> classify -> run the full post-
    extraction pipeline (embeddings, dedup, clean, MathML, tagging)."""
    text, name = await _read_mmd(file)
    raw_questions = _extract_questions_from_mmd(text, name)
    if not raw_questions:
        raise HTTPException(status_code=422, detail="No questions found in this file.")

    uploaded_questions: list[dict] = []
    if uploaded_bank is not None and uploaded_bank.filename:
        if uploaded_bank.filename.lower().endswith(".json"):
            uploaded_questions = await _read_json(uploaded_bank)
        elif uploaded_bank.filename.lower().endswith(".mmd"):
            up_text, up_name = await _read_mmd(uploaded_bank)
            uploaded_questions = _extract_questions_from_mmd(up_text, up_name)
        else:
            raise HTTPException(
                status_code=400,
                detail="uploaded_bank must be a .json or .mmd file.",
            )

    skip_embed = skip_embeddings.lower() in ("true", "1", "yes", "on")
    rule_based = force_rule_based_tagging.lower() in ("true", "1", "yes", "on")

    try:
        result = run_pipeline(
            raw_questions,
            uploaded_questions=uploaded_questions,
            similarity_threshold=similarity_threshold,
            skip_embeddings=skip_embed,
            force_rule_based_tagging=rule_based,
        )
    except RuntimeError as exc:
        # e.g. missing OPENAI_API_KEY for embeddings
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        "source_file": name,
        **result.to_dict(),
    }


@router.post("/api/pipeline/run-json")
async def pipeline_run_json(
    file: UploadFile = File(...),
    uploaded_bank: UploadFile | None = File(None),
    similarity_threshold: float = Form(0.93),
    skip_embeddings: str = Form("false"),
    force_rule_based_tagging: str = Form("false"),
) -> dict:
    """Same pipeline, but `file` is already-extracted question JSON
    (e.g. output from /api/extract, /api/foundation/extract, or the
    bypass_question converter) rather than a raw .mmd file."""
    raw_questions = await _read_json(file)
    if not raw_questions:
        raise HTTPException(status_code=422, detail="No questions in uploaded JSON.")

    uploaded_questions: list[dict] = []
    if uploaded_bank is not None and uploaded_bank.filename:
        uploaded_questions = await _read_json(uploaded_bank)

    skip_embed = skip_embeddings.lower() in ("true", "1", "yes", "on")
    rule_based = force_rule_based_tagging.lower() in ("true", "1", "yes", "on")

    try:
        result = run_pipeline(
            raw_questions,
            uploaded_questions=uploaded_questions,
            similarity_threshold=similarity_threshold,
            skip_embeddings=skip_embed,
            force_rule_based_tagging=rule_based,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return result.to_dict()
