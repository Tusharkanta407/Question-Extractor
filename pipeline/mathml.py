"""Stage: convert inline LaTeX math (Mathpix-style `$...$` segments left
over from .mmd OCR) into MathML, leaving surrounding plain text untouched.

NCERT .mmd files use `$...$` for inline math and `$$...$$` for display
math (e.g. `$\\frac{1}{2} \\mathrm{~kg}$`, `$70^{\\circ} \\mathrm{C}$`,
`$H_2O$`). This stage finds those segments and replaces them with their
MathML equivalent via latex2mathml, which handles fractions, sub/superscripts,
sqrt, Greek letters, and the \\mathrm{} / \\circ / \\% constructs NCERT
content commonly uses.
"""

from __future__ import annotations

import re

from pipeline.models import PipelineQuestion

# $$...$$ (display) must be matched before $...$ (inline) so display blocks
# aren't accidentally split into two inline matches.
_DISPLAY_MATH_RE = re.compile(r"\$\$(.+?)\$\$", re.DOTALL)
_INLINE_MATH_RE = re.compile(r"\$(.+?)\$", re.DOTALL)

# Segments like `$\_\_\_\_$` are blank-fill markers, not real math - skip them.
_BLANK_RE = re.compile(r"^[\s\\_]+$")


def _convert_latex(latex: str, *, display: bool) -> str:
    import latex2mathml.converter as c

    try:
        return c.convert(latex, display="block" if display else "inline")
    except Exception:
        # Malformed LaTeX (common in OCR output) - leave the original
        # delimited text in place rather than dropping content.
        wrapped = f"$${latex}$$" if display else f"${latex}$"
        return wrapped


def _replace_math(text: str) -> tuple[str, int]:
    if "$" not in text:
        return text, 0

    count = 0

    def _display_sub(m: re.Match) -> str:
        nonlocal count
        latex = m.group(1).strip()
        if not latex or _BLANK_RE.match(latex):
            return m.group(0)
        count += 1
        return _convert_latex(latex, display=True)

    def _inline_sub(m: re.Match) -> str:
        nonlocal count
        latex = m.group(1).strip()
        if not latex or _BLANK_RE.match(latex):
            return m.group(0)
        count += 1
        return _convert_latex(latex, display=False)

    text = _DISPLAY_MATH_RE.sub(_display_sub, text)
    text = _INLINE_MATH_RE.sub(_inline_sub, text)
    return text, count


def convert_question_mathml(q: PipelineQuestion) -> PipelineQuestion:
    content_mathml, n1 = _replace_math(q.question_content)
    solution_mathml, n2 = _replace_math(q.solution_content)

    q.question_content_mathml = content_mathml
    q.solution_content_mathml = solution_mathml

    converted_options = []
    for opt in q.options:
        opt_text_mathml, _ = _replace_math(opt.get("text", ""))
        converted_options.append({**opt, "text_mathml": opt_text_mathml})
    if converted_options:
        q.meta["options_mathml"] = converted_options

    q.meta["mathml_conversions"] = n1 + n2
    return q


def convert_questions_mathml(questions: list[PipelineQuestion]) -> list[PipelineQuestion]:
    return [convert_question_mathml(q) for q in questions]
