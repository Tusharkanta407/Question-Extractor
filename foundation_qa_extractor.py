"""
Foundation pipeline QA extractor.

Parses .mmd files with the format:
    Q11. [FIB] The reaction that releases heat is called ______ reaction.
         ► Correct Answer: exothermic

    Q225. [INTEGER] How many moles of CO2 are produced?
          ► Correct Answer: 1

Rules applied after parsing (via validators.py):
- INTEGER questions → answer must be non-negative numeric
- FIB questions with word answers → converted to SCQ (MCQ)
"""
from __future__ import annotations
import re
from models import ExtractedDocument, Question, QuestionOption
from validators import extract_answer_from_raw, validate_document

# ── Regex patterns ─────────────────────────────────────────────────────────────

# Matches question header: Q11. [FIB] ... or Q225. [INTEGER] ...
_Q_HEADER_RE = re.compile(
    r"^Q(\d+)\.\s+\[([A-Z_]+)\]\s*(.*)", re.IGNORECASE
)

# Matches option lines: (a) text  or  a) text
_OPTION_RE = re.compile(r"^\s*\(?([a-dA-D])\)?\s+(.+)")

# Matches answer line: ► Correct Answer: value  or  Correct Answer: value
_ANSWER_RE = re.compile(
    r"[►▶]?\s*Correct Answer\s*[:：]\s*(.+)", re.IGNORECASE
)

# Section headers (e.g. ## Fill in the Blanks)
_SECTION_RE = re.compile(r"^#{1,3}\s*(.+)")

# Match table lines: | A | B |
_TABLE_RE = re.compile(r"^\|.+\|")


def extract(content: str, filename: str = "") -> ExtractedDocument:
    """
    Parse .mmd content and return an ExtractedDocument.
    Automatically validates INTEGER and FIB questions.
    """
    title = _extract_title(content, filename)
    doc = ExtractedDocument(
        title=title,
        source_format="foundation",
        source_file=filename,
    )

    current_section = "General"
    lines = content.splitlines()
    i = 0

    while i < len(lines):
        line = lines[i]

        # Track section headers
        sec_m = _SECTION_RE.match(line)
        if sec_m:
            current_section = sec_m.group(1).strip()
            i += 1
            continue

        # Question header
        q_m = _Q_HEADER_RE.match(line)
        if q_m:
            q_num = q_m.group(1)
            q_type = q_m.group(2).upper()
            q_stem_first = q_m.group(3).strip()

            # Collect multi-line stem, options, and answer
            stem_lines = [q_stem_first] if q_stem_first else []
            options: list[QuestionOption] = []
            answer: str | None = None
            raw_block: list[str] = [line]

            i += 1
            while i < len(lines):
                nxt = lines[i]

                # Stop at next question
                if _Q_HEADER_RE.match(nxt) or _SECTION_RE.match(nxt):
                    break

                raw_block.append(nxt)

                # Answer line
                ans_m = _ANSWER_RE.match(nxt.strip())
                if ans_m:
                    answer = ans_m.group(1).strip()
                    i += 1
                    continue

                # Option line
                opt_m = _OPTION_RE.match(nxt)
                if opt_m:
                    options.append(QuestionOption(
                        label=opt_m.group(1).lower(),
                        text=opt_m.group(2).strip(),
                    ))
                    i += 1
                    continue

                # Continuation of stem (non-empty, non-table, non-separator)
                stripped = nxt.strip()
                if stripped and not _TABLE_RE.match(stripped) and stripped != "---":
                    stem_lines.append(stripped)

                i += 1

            stem = " ".join(stem_lines).strip()
            q_type_normalised = _normalise_type(q_type, current_section)

            question = Question(
                id=f"foundation_Q{q_num}",
                section=current_section,
                number=q_num,
                type=q_type_normalised,
                stem=stem,
                options=options,
                answer=answer,
                raw_text="\n".join(raw_block),
            )
            doc.questions.append(question)
            continue

        i += 1

    # Apply validation rules: INTEGER check + FIB→SCQ conversion
    warnings = validate_document(doc)
    if warnings:
        # Attach warnings as metadata (optional — callers can inspect)
        doc.__dict__.setdefault("_warnings", []).extend(warnings)

    return doc


# ── Helpers ───────────────────────────────────────────────────────────────────

def _normalise_type(raw_type: str, section: str) -> str:
    """Map raw [TYPE] tags to canonical type strings."""
    mapping = {
        "SCQ": "SCQ",
        "MCQ": "MCQ",
        "FIB": "FIB",
        "INTEGER": "INTEGER",
        "ASSERTION": "ASSERTION",
        "MATCH": "MATCH",
        "TF": "TF",
        "SA": "SA",
        "LA": "LA",
        "DIAGRAM": "DIAGRAM",
    }
    return mapping.get(raw_type, raw_type)


def _extract_title(content: str, filename: str) -> str:
    """Extract document title from first heading or filename."""
    for line in content.splitlines():
        m = re.match(r"^#\s+(.+)", line)
        if m:
            return m.group(1).strip()
    if filename:
        return filename.replace("_", " ").replace(".mmd", "").title()
    return "Untitled"
