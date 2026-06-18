"""Foundation extraction pipeline."""

from __future__ import annotations

import re
from pathlib import Path

from foundation.formatter import format_question_bank, output_filename
from foundation.models import FoundationDocument
from foundation.preprocess import (
    extract_title,
    infer_class_level,
    infer_subject,
    preprocess,
    split_zones,
)
from foundation.questions_parser import parse_questions_zone
from foundation.regex import EXERCISE_START_RE
from foundation.solutions_parser import pair_answers, parse_solutions_zone


def is_foundation_format(text: str) -> bool:
    if EXERCISE_START_RE.search(text):
        return True
    if re.search(r"\\section\*\{Multiple\s+Choice", text, re.IGNORECASE):
        return True
    if re.search(r"DIRECTIONS\s*:.*multiple\s+choice", text, re.IGNORECASE):
        return True
    return False


def run_pipeline(
    text: str,
    source_file: str = "",
    *,
    use_llm: bool = False,
) -> FoundationDocument:
    text = preprocess(text)
    title = extract_title(text)
    subject = infer_subject(title, source_file)
    class_level = infer_class_level(source_file, title)

    questions_zone, solutions_zone = split_zones(text)
    questions = parse_questions_zone(questions_zone)

    paired = 0
    answer_total = 0
    if solutions_zone:
        answers = parse_solutions_zone(solutions_zone)
        answer_total = len(answers)
        paired, _ = pair_answers(questions, answers)

    doc = FoundationDocument(
        title=title,
        subject=subject,
        class_level=class_level,
        source_file=source_file,
        questions=questions,
        paired_answers=paired,
        answer_entries=answer_total,
    )

    if use_llm:
        from foundation.answer_llm import fill_missing_answers
        from foundation.llm import DEFAULT_MODEL

        filled, skipped_subj, llm_tokens = fill_missing_answers(doc, model=DEFAULT_MODEL)
        doc.llm_filled = filled
        doc.llm_skipped_subjective = skipped_subj
        doc.llm_tokens = llm_tokens

    return doc


def process_to_question_bank(
    text: str,
    source_file: str = "",
    *,
    use_llm: bool = False,
) -> tuple[str, FoundationDocument]:
    doc = run_pipeline(text, source_file=source_file, use_llm=use_llm)
    return format_question_bank(doc), doc


def estimate_file_tokens(text: str) -> dict:
    try:
        import tiktoken

        enc = tiktoken.get_encoding("cl100k_base")
        _, doc = process_to_question_bank(text, use_llm=False)
        out = format_question_bank(doc)
        return {
            "input_tokens": len(enc.encode(text)),
            "output_tokens": len(enc.encode(out)),
            "question_count": len(doc.questions),
        }
    except ImportError:
        _, doc = process_to_question_bank(text, use_llm=False)
        out = format_question_bank(doc)
        return {
            "input_tokens": len(text) // 4,
            "output_tokens": len(out) // 4,
            "question_count": len(doc.questions),
        }


def estimate_llm_for_file(text: str) -> dict:
    from foundation.answer_llm import estimate_llm_tokens

    doc = run_pipeline(text, use_llm=False)
    return estimate_llm_tokens(doc)


def process_file(input_path: Path, output_dir: Path | None = None, *, use_llm: bool = False) -> Path:
    text = input_path.read_text(encoding="utf-8")
    out_text, _ = process_to_question_bank(text, source_file=input_path.name, use_llm=use_llm)
    out_dir = output_dir or input_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / output_filename(input_path.stem)
    out_path.write_text(out_text, encoding="utf-8")
    return out_path


# backwards compat alias
estimate_output_tokens = estimate_file_tokens
