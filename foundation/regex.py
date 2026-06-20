"""Shared regex patterns for Foundation parsing."""

from __future__ import annotations

import re

EXERCISE_START_RE = re.compile(
    r"\\section\*\{((?:ADVANCED\s*)?Exercise[^}]*)\}", re.IGNORECASE
)
SOLUTIONS_START_RE = re.compile(
    r"\\section\*\{(?:SOLUTIONS|Answer\s*Key|Answers)\b", re.IGNORECASE
)
SECTION_HEADER_RE = re.compile(r"^\\section\*\{(.+)\}$")

QUESTION_SECTION_RE = re.compile(
    r"""
      Multiple\s+Choice
    | Assertion\s*(?:\\&|&)\s*Reason
    | Fill\s+in\s+the\s+Blanks
    | True\s*/\s*False
    | Match(?:ing)?\s+(?:the\s+Following|Questions)
    | Multiple\s+Matching
    | Passage\s+Based
    | Case\s+Study
    | Very\s+Short\s+Answer
    | Short\s+Answer
    | Long\s+Answer
    | Reasoning\s+Based
    | Integer(?:\s*/\s*Numerical\s+Value)?\s+Type
    | Numerical\s+Value\s+Type
    | HOTS
    | Exemplar\s+Questions
    | Text\s*-\s*Book\s+Questions
    | Text\s*-\s*Book\s+Exercise
    """,
    re.VERBOSE | re.IGNORECASE,
)

PLAIN_EXERCISE_RE = re.compile(r"^(Exercise\s+\d+[^}]*)$", re.IGNORECASE)
PLAIN_SUBSECTION_RE = re.compile(
    r"^(Master\s+Boards|Master\s+NCERT.*|Foundation\s+Builder|CONNECTING\s+TOPIC.*)$",
    re.IGNORECASE,
)
SUBSECTION_RE = PLAIN_SUBSECTION_RE

SKIP_SECTION_RE = re.compile(
    r"""
      ^Think\s+out\s+of\s+the\s+Box
    | ^Case\s+Study-\d+
    | ^SOLUTION$
    | ^REDOX\s+REACTIONS$
    | ^Oxidation\s+Number\s+Method
    | ^Ion\s+Electron\s+Method
    """,
    re.VERBOSE | re.IGNORECASE,
)

NUMBERED_Q_RE = re.compile(r"^(\d+)[\.\)]\s*(.*)")
MCQ_OPTION_RE = re.compile(r"^\(([a-d])\)\s*(.*)$", re.IGNORECASE)
SHARED_OPTION_RE = re.compile(r"^\(([a-d])\)\s+If\b", re.IGNORECASE)
COLUMN_I_RE = re.compile(r"^\(([A-D])\)\s*(.*)$")
COLUMN_II_RE = re.compile(r"^\(([p-t])\)\s*(.*)$", re.IGNORECASE)
ROMAN_SUB_RE = re.compile(r"^\(([ivx]+)\)\s*(.*)$", re.IGNORECASE)
DIRECTIONS_RE = re.compile(r"^DIRECTIONS\b", re.IGNORECASE)
REASON_RE = re.compile(r"^Reason\s*:", re.IGNORECASE)
COLUMN_LABEL_RE = re.compile(r"^Column\s+(I{1,3}|II)\b", re.IGNORECASE)
PASSAGE_HEADER_RE = re.compile(r"^Passage\s+Based\s+Questions\b", re.IGNORECASE)

ANSWER_LINE_RE = re.compile(
    r"^(\d+)[\.\)]\s*(?:\(([a-dA-D])\)\s*)?(.*)$",
    re.IGNORECASE,
)

DROP_LINE_RE = re.compile(
    r"""
      ^\s*\\begin\{figure\}
    | ^\s*\\end\{figure\}
    | ^\s*\\includegraphics
    | ^\s*\\caption
    | ^\s*!\[
    | ^\s*\\label\{
    | ^\s*\\captionsetup
    """,
    re.VERBOSE | re.IGNORECASE,
)

TABULAR_START_RE = re.compile(r"\\begin\{tabular\}")
TABULAR_END_RE = re.compile(r"\\end\{tabular\}")
