"""
mmd_qa_extractor.py
=====================
Extract question/answer content from textbook .mmd files into *_qa.mmd files.

Output keeps only:
  - Example N.N (+ Answer)
  - Activity N.N section + its prompt
  - Pause and Ponder (incl. ID variant) + numbered items
  - MCQ options (a/b/c/d)

Narrative theory, figures, Meet a Scientist, Threads of Curiosity, and
Ready to Go Beyond sidebars are removed.

Usage:
    python mmd_qa_extractor.py file1.mmd [file2.mmd ...]
    python mmd_qa_extractor.py file1.mmd -o output_dir/
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

EXAMPLE_RE = re.compile(r"Example\s+\d+[\.\d]*\s*:", re.IGNORECASE)
ACTIVITY_SECTION_RE = re.compile(
    r"\\section\*\{[^}]*Activity\s+\d+[\.\d]*[^}]*\}", re.IGNORECASE
)
PONDER_SECTION_RE = re.compile(
    r"\\section\*\{(?:ID\s+)?Pause\s+and\s+Ponder[^}]*\}", re.IGNORECASE
)
NUMBERED_Q_RE = re.compile(r"^\s*(\d+)[\.\)]\s+")
MCQ_OPTION_RE = re.compile(r"^\s*(?:\([a-dA-D]\)|[a-dA-D][\.\)])\s+\S")

ANSWER_START_RE = re.compile(
    r"^\s*(?:Answer|Solution|Ans\.?|Sol\.?)\s*:", re.IGNORECASE
)

# Sidebar / narrative blocks — always skipped (header + following text)
SKIP_SECTION_RE = re.compile(
    r"""
      \\section\*\{(?![^}]*(?:Activity|Exercise|Ponder|Question|Practice|Try|Example))
    | ^\s*Meet\s+a\s+Scientist\b
    | ^\s*Threads\s+of\s+Curiosity\b
    | ^\s*Ready\s+to\s+Go\s+Beyond\b
    | ^\s*Next\s+Level\s+Up\b
    | ^\s*Key\s+Terms?\b
    | ^\s*Summary\b
    | ^\s*Learning\s+Outcomes?\b
    """,
    re.VERBOSE | re.IGNORECASE | re.MULTILINE,
)

DROP_LINE_RE = re.compile(
    r"""
      ^\s*\\begin\{figure\}
    | ^\s*\\end\{figure\}
    | ^\s*\\includegraphics
    | ^\s*\\caption(?:setup)?
    | ^\s*!\[
    | ^\s*\\label\{
    | ^\s*\\maketitle
    | ^\s*\\tableofcontents
    | ^\s*\\begin\{document\}
    | ^\s*\\end\{document\}
    """,
    re.VERBOSE | re.IGNORECASE,
)

# Paragraph likely continues a worked answer (not fresh narrative theory)
ANSWER_CONT_RE = re.compile(
    r"^\s*(?:Now|Hence|Therefore|Thus|Also|Note|Naturally|But\s+if|One\s+way|We\s+also|"
    r"Multiplying|So,|Hence,|Therefore,|This\s+means|In\s+this\s+way|For\s+example,)",
    re.IGNORECASE,
)

FOLLOWUP_Q_WORDS = frozenset(
    "what why how when where who which if or and but is are was were do does "
    "can could should would will may might shall must have has had be been being "
    "a an the you your we they it this that these those".split()
)


def extract_title(text: str) -> str:
    m = re.search(r"\\title\{\s*\n?(.+?)\n?\}", text, re.DOTALL)
    return m.group(1).strip() if m else ""


def remove_figure_blocks(text: str) -> str:
    return re.sub(
        r"\\begin\{figure\}.*?\\end\{figure\}", "", text, flags=re.DOTALL | re.IGNORECASE
    )


def preprocess(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = remove_figure_blocks(text)
    lines = [ln for ln in text.splitlines() if not DROP_LINE_RE.match(ln)]
    text = "\n".join(lines)

    # Split merged Examples / numbered items from preceding theory
    text = re.sub(r"(\S)\s+(Example\s+\d+[\.\d]*\s*:)", r"\1\n\n\2", text, flags=re.IGNORECASE)
    text = re.sub(r"(\S)\s+(\d+[\.\)]\s+\S)", r"\1\n\n\2", text)
    text = re.sub(r"(\\section\*\{[^}]+\})", r"\n\n\1\n\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_blocks(text: str) -> list[str]:
    return [b.strip() for b in re.split(r"\n{2,}", text) if b.strip()]


def is_skip_section(block: str) -> bool:
    return bool(SKIP_SECTION_RE.search(block))


def is_qa_section(block: str) -> bool:
    return bool(
        ACTIVITY_SECTION_RE.search(block)
        or PONDER_SECTION_RE.search(block)
    )


def is_question_block(block: str) -> bool:
    return bool(
        EXAMPLE_RE.search(block)
        or ACTIVITY_SECTION_RE.search(block)
        or PONDER_SECTION_RE.search(block)
        or NUMBERED_Q_RE.match(block)
        or MCQ_OPTION_RE.match(block)
    )


def is_answer_block(block: str) -> bool:
    return bool(ANSWER_START_RE.match(block))


def is_answer_continuation(block: str) -> bool:
    return bool(ANSWER_CONT_RE.match(block))


def clean_numbered_question(block: str) -> str:
    """Strip theory accidentally merged after a numbered Ponder question."""
    m = NUMBERED_Q_RE.match(block)
    if not m:
        return block

    prefix = block[: m.end()]
    body = block[m.end() :]

    for match in re.finditer(r"\?\s+([A-Za-z]+)", body):
        word = match.group(1).lower()
        if word not in FOLLOWUP_Q_WORDS:
            body = body[: match.start() + 1]
            break

    return (prefix + body).strip()


def split_example_qa(block: str) -> list[str]:
    m = re.search(
        r"^(.*?Example\s+\d+[\.\d]*\s*:.*?)(\s+Answer\s*:.*)$",
        block,
        re.IGNORECASE | re.DOTALL,
    )
    if m:
        return [m.group(1).strip(), m.group(2).strip()]
    return [block]


def extract_qa_blocks(text: str) -> list[str]:
    blocks = split_blocks(preprocess(text))
    output: list[str] = []
    # idle | after_activity | after_ponder | in_answer | skip
    state = "idle"

    for block in blocks:
        if state == "skip":
            if is_question_block(block) and not is_skip_section(block):
                state = "idle"
            else:
                continue

        if is_skip_section(block):
            state = "skip"
            continue

        if ACTIVITY_SECTION_RE.search(block):
            output.append(block)
            state = "after_activity"
            continue

        if PONDER_SECTION_RE.search(block):
            output.append(block)
            state = "after_ponder"
            continue

        if is_answer_block(block):
            output.append(block)
            state = "in_answer"
            continue

        if EXAMPLE_RE.search(block):
            for part in split_example_qa(block):
                if is_answer_block(part):
                    output.append(part)
                    state = "in_answer"
                else:
                    output.append(part)
                    state = "idle"
            continue

        if state == "after_ponder" and NUMBERED_Q_RE.match(block):
            output.append(clean_numbered_question(block))
            continue

        if state == "after_activity":
            output.append(block)
            state = "idle"
            continue

        if state == "in_answer":
            if is_question_block(block):
                if EXAMPLE_RE.search(block):
                    for part in split_example_qa(block):
                        if is_answer_block(part):
                            output.append(part)
                            state = "in_answer"
                        else:
                            output.append(part)
                            state = "idle"
                elif PONDER_SECTION_RE.search(block):
                    output.append(block)
                    state = "after_ponder"
                elif ACTIVITY_SECTION_RE.search(block):
                    output.append(block)
                    state = "after_activity"
                elif NUMBERED_Q_RE.match(block):
                    output.append(clean_numbered_question(block))
                    state = "after_ponder"
                elif MCQ_OPTION_RE.match(block):
                    output.append(block)
                else:
                    output.append(block)
                    state = "idle"
            elif is_answer_continuation(block):
                output.append(block)
            else:
                state = "idle"
            continue

        if MCQ_OPTION_RE.match(block):
            output.append(block)

    return output


def process_text(text: str) -> str:
    title = extract_title(text)
    blocks = extract_qa_blocks(text)
    parts: list[str] = []
    if title:
        parts.append(f"\\title{{\n{title}\n}}")
    parts.extend(blocks)
    return "\n\n".join(parts) + "\n" if parts else ""


def process_file(input_path: Path, output_dir: Path | None = None) -> Path:
    text = input_path.read_text(encoding="utf-8")
    result = process_text(text)
    out_dir = output_dir or input_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{input_path.stem}_qa{input_path.suffix}"
    out_path.write_text(result, encoding="utf-8")
    return out_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Extract Q&A content from .mmd textbook files."
    )
    parser.add_argument("inputs", nargs="+", help="Input .mmd file(s)")
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory (default: same folder as each input file)",
    )
    args = parser.parse_args(argv)

    for arg in args.inputs:
        path = Path(arg)
        if not path.exists():
            print(f"  [SKIP] {path} not found", file=sys.stderr)
            continue
        out = process_file(path, args.output_dir)
        orig_lines = path.read_text(encoding="utf-8").count("\n")
        out_lines = out.read_text(encoding="utf-8").count("\n")
        print(f"  [OK]  {path.name}  ->  {out.name}  ({orig_lines} lines -> {out_lines} lines)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
