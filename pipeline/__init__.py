"""Post-extraction pipeline: embeddings -> similarity dedup -> clean ->
MathML conversion -> competitive tagging -> JSON output.

This package is intentionally decoupled from the extractors (extract.py,
foundation/, bypass_question/). It accepts a flat list of question dicts
(anything with at least an "id"/"qid" and "question_content"/"stem" field)
and runs the remaining stages of the pipeline:

    extract -> classify (SCQ/MCQ/INTEGER) -> [THIS PACKAGE STARTS HERE]
    -> embeddings -> similarity-vs-uploaded -> drop duplicates -> clean
    -> MathML conversion -> competitive tagging -> JSON output
"""

from __future__ import annotations
