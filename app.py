"""Web app: upload .mmd files and download extracted Q&A as txt, docx, or json."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

from document_export import (
    document_to_docx_bytes,
    document_to_json,
    document_to_json_bytes,
    document_to_plain_text,
    output_filename,
)
from bypass_question.routes import router as bypass_router
from foundation.routes import router as foundation_router
from extract import detect_format, extract_document

APP_DIR = Path(__file__).resolve().parent
STATIC_DIR = APP_DIR / "static"
BYPASS_STATIC_DIR = APP_DIR / "bypass_question" / "static"
FOUNDATION_STATIC_DIR = APP_DIR / "foundation" / "static"

app = FastAPI(title="MMD Q&A Extractor")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/bypass-static", StaticFiles(directory=BYPASS_STATIC_DIR), name="bypass-static")
app.mount("/foundation-static", StaticFiles(directory=FOUNDATION_STATIC_DIR), name="foundation-static")
app.include_router(bypass_router)
app.include_router(foundation_router)


async def _read_upload(file: UploadFile) -> tuple[str, str]:
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


@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    return HTMLResponse((STATIC_DIR / "index.html").read_text(encoding="utf-8"))


@app.post("/api/extract")
async def extract(file: UploadFile = File(...)) -> dict:
    text, name = await _read_upload(file)
    fmt = detect_format(text)
    stem = Path(name).stem
    orig_lines = text.count("\n") + (1 if text and not text.endswith("\n") else 0)

    if fmt == "foundation":
        from foundation.formatter import output_filename as foundation_output_filename
        from foundation.pipeline import process_to_question_bank

        content, fdoc = process_to_question_bank(text, source_file=name)
        if not fdoc.questions:
            raise HTTPException(status_code=422, detail="No questions found in this file.")
        out_lines = content.count("\n") + 1
        return {
            "filename_txt": foundation_output_filename(stem, "mmd"),
            "filename_json": foundation_output_filename(stem, "json"),
            "title": fdoc.title,
            "format": "foundation",
            "content": content,
            "json": __import__("json").dumps(fdoc.to_dict(), ensure_ascii=False, indent=2) + "\n",
            "question_count": len(fdoc.questions),
            "stats": {
                "input_lines": orig_lines,
                "output_lines": out_lines,
                "questions": len(fdoc.questions),
                "paired_answers": fdoc.paired_answers,
            },
        }

    doc = extract_document(text, source_file=name)
    if not doc.questions:
        raise HTTPException(
            status_code=422,
            detail="No questions found in this file.",
        )

    stem = Path(name).stem
    plain = document_to_plain_text(doc)
    orig_lines = text.count("\n") + (1 if text and not text.endswith("\n") else 0)

    return {
        "filename_txt": output_filename(stem, "txt"),
        "filename_docx": output_filename(stem, "docx"),
        "filename_json": output_filename(stem, "json"),
        "title": doc.title,
        "format": doc.source_format,
        "content": plain,
        "json": document_to_json(doc),
        "question_count": len(doc.questions),
        "stats": {
            "input_lines": orig_lines,
            "output_lines": plain.count("\n") + 1,
            "questions": len(doc.questions),
        },
    }


@app.post("/api/extract/download")
async def extract_download(
    file: UploadFile = File(...),
    output_format: str = Form("txt"),
) -> Response:
    text, name = await _read_upload(file)
    doc = extract_document(text, source_file=name)
    if not doc.questions:
        raise HTTPException(
            status_code=422,
            detail="No questions found in this file.",
        )

    stem = Path(name).stem
    fmt_lower = output_format.lower().strip()

    if fmt_lower == "docx":
        body = document_to_docx_bytes(doc)
        filename = output_filename(stem, "docx")
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    elif fmt_lower == "json":
        body = document_to_json_bytes(doc)
        filename = output_filename(stem, "json")
        media_type = "application/json; charset=utf-8"
    elif fmt_lower == "txt":
        body = document_to_plain_text(doc).encode("utf-8")
        filename = output_filename(stem, "txt")
        media_type = "text/plain; charset=utf-8"
    else:
        raise HTTPException(status_code=400, detail="output_format must be txt, docx, or json.")

    return Response(
        content=body,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
