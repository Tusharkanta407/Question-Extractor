"""
Top-level extraction entry point.

Detects format from content/filename and routes to the correct extractor.
Validation (INTEGER check, FIB→SCQ conversion) runs automatically inside
each extractor via validators.validate_document().
"""
from __future__ import annotations
import re
from models import ExtractedDocument


def detect_format(content: str, filename: str = "") -> str:
    """
    Detect the source format of a .mmd file.
    Returns one of: 'foundation', 'ncert', 'bypass_question', 'unknown'
    """
    fn_lower = filename.lower()

    # Foundation files typically have 'foundation' in name or Q-number pattern
    if "foundation" in fn_lower:
        return "foundation"

    # Bypass question files
    if "bypass" in fn_lower:
        return "bypass_question"

    # NCERT files — Q&A with exercise blocks
    if re.search(r"Q\d+\.\s+\[", content):
        return "foundation"

    # Fallback to ncert
    return "ncert"


def extract_document(content: str, filename: str = "") -> ExtractedDocument:
    """
    Main entry point. Detects format, extracts, validates, and returns document.
    """
    fmt = detect_format(content, filename)

    if fmt == "foundation":
        from foundation_qa_extractor import extract
        return extract(content, filename)

    elif fmt == "bypass_question":
        # Route to bypass extractor if available, else fallback
        try:
            from bypass_question.extractor import extract
            return extract(content, filename)
        except ImportError:
            from foundation_qa_extractor import extract
            return extract(content, filename)

    else:
        # NCERT / default
        from ncert_qa_extractor import extract_document as ncert_extract
        doc = ncert_extract(content, filename)
        # NCERT extractor already calls validate_document internally
        return doc
