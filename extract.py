"""Route .mmd files to the correct Q&A extractor."""

from __future__ import annotations

from pathlib import Path

import foundation_qa_extractor as foundation
import mmd_qa_extractor as exploration
import ncert_qa_extractor as ncert
from document_export import mmd_to_document
from models import ExtractedDocument


def detect_format(text: str) -> str:
    if foundation.is_foundation_format(text):
        return "foundation"
    if ncert.is_ncert_format(text):
        return "ncert"
    return "exploration"


def extract_title(text: str, fmt: str | None = None) -> str:
    fmt = fmt or detect_format(text)
    if fmt == "foundation":
        return foundation.extract_title(text)
    if fmt == "ncert":
        return ncert.extract_title(text)
    return exploration.extract_title(text)


def extract_document(text: str, source_file: str = "", fmt: str | None = None) -> ExtractedDocument:
    fmt = fmt or detect_format(text)
    title = extract_title(text, fmt)

    if fmt == "foundation":
        mmd = foundation.process_text(text)
        return mmd_to_document(mmd, fmt, title=title, source_file=source_file)
    if fmt == "ncert":
        return ncert.extract_document(text, source_file=source_file)
    mmd = exploration.process_text(text)
    return mmd_to_document(mmd, fmt, title=title, source_file=source_file)


def process_text(text: str, fmt: str | None = None) -> tuple[str, str]:
    """Return (mmd_output_text, format_name) — legacy helper."""
    doc = extract_document(text, fmt=fmt)
    from ncert_qa_extractor import document_to_mmd
    return document_to_mmd(doc), doc.source_format


def process_file(input_path: Path, output_dir: Path | None = None) -> tuple[Path, str]:
    text = input_path.read_text(encoding="utf-8")
    doc = extract_document(text, source_file=input_path.name)
    from ncert_qa_extractor import document_to_mmd
    result = document_to_mmd(doc)
    out_dir = output_dir or input_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{input_path.stem}_qa{input_path.suffix}"
    out_path.write_text(result, encoding="utf-8")
    return out_path, doc.source_format


def main() -> int:
    import argparse
    import sys

    from document_export import (
        document_to_docx_bytes,
        document_to_json,
        document_to_plain_text,
        output_filename,
    )
    from ncert_qa_extractor import document_to_mmd

    parser = argparse.ArgumentParser(
        description="Extract Q&A from .mmd files (Exploration / Foundation / NCERT)."
    )
    parser.add_argument("inputs", nargs="+", help="Input .mmd file(s)")
    parser.add_argument("-o", "--output-dir", type=Path, default=None)
    parser.add_argument(
        "-f",
        "--format",
        choices=("txt", "docx", "json", "mmd"),
        default="txt",
        help="Output file type (default: txt)",
    )
    args = parser.parse_args()

    for arg in args.inputs:
        path = Path(arg)
        if not path.exists():
            print(f"  [SKIP] {path} not found", file=sys.stderr)
            continue

        text = path.read_text(encoding="utf-8")
        doc = extract_document(text, source_file=path.name)
        out_dir = args.output_dir or path.parent
        out_dir.mkdir(parents=True, exist_ok=True)

        if args.format == "mmd":
            out_path = out_dir / f"{path.stem}_qa{path.suffix}"
            out_path.write_text(document_to_mmd(doc), encoding="utf-8")
        elif args.format == "docx":
            out_path = out_dir / output_filename(path.stem, "docx")
            out_path.write_bytes(document_to_docx_bytes(doc))
        elif args.format == "json":
            out_path = out_dir / output_filename(path.stem, "json")
            out_path.write_text(document_to_json(doc), encoding="utf-8")
        else:
            out_path = out_dir / output_filename(path.stem, "txt")
            out_path.write_text(document_to_plain_text(doc), encoding="utf-8")

        orig = text.count("\n")
        new = out_path.read_bytes() if args.format == "docx" else out_path.read_text(encoding="utf-8")
        new_lines = new.count(b"\n") if args.format == "docx" else new.count("\n")
        print(
            f"  [OK]  {path.name}  ->  {out_path.name}  "
            f"({doc.source_format}, {len(doc.questions)} questions, "
            f"{args.format}, {orig} -> {new_lines} lines)"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
