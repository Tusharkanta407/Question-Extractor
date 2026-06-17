"""FastAPI routes for bypass question converter."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, Response

from bypass_question.converter import convert_single, estimate_tokens_for_file, run_pipeline
from bypass_question.export import output_filename, questions_to_json, questions_to_plain_text
from bypass_question.llm import DEFAULT_MODEL
from bypass_question.models import ConvertedQuestion, ParsedQuestion
from bypass_question.parser import parse_bypass_mmd
from bypass_question.scorer import score_question

_PKG_DIR = Path(__file__).resolve().parent
STATIC_DIR = _PKG_DIR / "static"

router = APIRouter(tags=["bypass"])


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


def _dict_to_converted(d: dict) -> ConvertedQuestion:
    return ConvertedQuestion(**{k: v for k, v in d.items() if k in ConvertedQuestion.__dataclass_fields__})


@router.get("/bypass", response_class=HTMLResponse)
async def bypass_page() -> HTMLResponse:
    return HTMLResponse((STATIC_DIR / "bypass.html").read_text(encoding="utf-8"))


@router.post("/api/bypass/estimate")
async def bypass_estimate(file: UploadFile = File(...)) -> dict:
    text, name = await _read_mmd(file)
    parsed = parse_bypass_mmd(text, source_file=name)
    if not parsed.questions:
        raise HTTPException(status_code=422, detail="No questions found in bypass file.")
    est = estimate_tokens_for_file(parsed)
    preview = [asdict(score_question(q)) for q in parsed.questions]
    return {
        "source": parsed.source,
        "subject": parsed.subject,
        "class_level": parsed.class_level,
        "question_count": len(parsed.questions),
        "preview_scores": preview,
        **est,
    }


@router.post("/api/bypass/convert")
async def bypass_convert(file: UploadFile = File(...)) -> dict:
    text, name = await _read_mmd(file)
    parsed = parse_bypass_mmd(text, source_file=name)
    if not parsed.questions:
        raise HTTPException(status_code=422, detail="No questions found in bypass file.")

    try:
        result = run_pipeline(parsed, model=DEFAULT_MODEL)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    stem = Path(name).stem
    payload = result.to_dict()
    payload["filename_json"] = output_filename(stem, "json")
    payload["filename_txt"] = output_filename(stem, "txt")
    payload["json"] = questions_to_json(result.questions)
    payload["content"] = questions_to_plain_text(result.questions)
    payload["preview_stem"] = {q.question_id: q.stem for q in parsed.questions}
    return payload


@router.post("/api/bypass/regenerate")
async def bypass_regenerate(
    stem: str = Form(...),
    question_id: str = Form(...),
    subject: str = Form(...),
    class_level: int = Form(...),
    source: str = Form(...),
    question_type: str = Form("scq"),
    line_start: int = Form(0),
    line_end: int = Form(0),
) -> dict:
    from bypass_question.models import ParsedBypassFile

    parsed = ParsedBypassFile(
        source=source,
        subject=subject,
        class_level=class_level,
        source_file="",
    )
    question = ParsedQuestion(
        question_id=question_id,
        stem=stem,
        line_start=line_start,
        line_end=line_end,
    )

    try:
        item, usage = convert_single(
            question,
            parsed,
            question_type=question_type.lower(),
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if not item:
        raise HTTPException(
            status_code=422,
            detail=f"Question {question_id} could not be converted. It may need to stay eliminated.",
        )

    return {
        "question": item.to_dict(),
        "tokens": usage,
    }


@router.post("/api/bypass/export")
async def bypass_export(
    payload: str = Form(...),
    output_format: str = Form("json"),
    filename_stem: str = Form("bypass_converted"),
) -> Response:
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON payload.") from exc

    questions_raw = data if isinstance(data, list) else data.get("questions", [])
    questions = [_dict_to_converted(q) for q in questions_raw]
    fmt = output_format.lower().strip()
    stem = filename_stem.replace("_rephrase", "")

    if fmt == "txt":
        body = questions_to_plain_text(questions).encode("utf-8")
        filename = output_filename(stem, "txt")
        media = "text/plain; charset=utf-8"
    elif fmt == "json":
        body = questions_to_json(questions).encode("utf-8")
        filename = output_filename(stem, "json")
        media = "application/json; charset=utf-8"
    else:
        raise HTTPException(status_code=400, detail="output_format must be json or txt.")

    return Response(
        content=body,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
