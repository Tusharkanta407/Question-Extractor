# pipeline/ — post-extraction pipeline

Implements the stages that run **after** questions have been extracted and
classified into SCQ/MCQ/INTEGER (by `extract.py`, `foundation/`, or
`bypass_question/`):

```
extract -> classify (SCQ/MCQ/INTEGER) -> [pipeline/ starts here]
  1. embeddings.py   create embeddings for each question
  2. similarity.py   compare against an uploaded/reference question bank
  3. similarity.py   drop duplicate questions (vs. upload + within batch)
  4. cleaner.py      clean remaining questions (whitespace, stray numbering,
                      option-label normalization)
  5. mathml.py        convert leftover LaTeX ($...$ from Mathpix OCR) to MathML
  6. tagger.py        tag with competitive-exam metadata
                      (difficulty, Bloom level, topic, exam_tags, est. time)
-> JSON output
```

`runner.py` wires all six stages together. `routes.py` exposes it over HTTP.

## Usage (Python)

```python
from pipeline.runner import run_pipeline

result = run_pipeline(
    raw_questions,              # list[dict] - output of extract_document(...).to_dict()["questions"]
                                 #   or ConversionResult.to_dict()["questions"], etc.
    uploaded_questions=bank,    # optional: existing question bank to dedupe against
    similarity_threshold=0.93,  # cosine similarity >= this => duplicate
)

result.kept       # list[PipelineQuestion] - survived, cleaned, tagged
result.dropped    # list[PipelineQuestion] - duplicates / empties
result.stats      # counts at each stage
result.to_dict()  # JSON-serializable final output
```

## Usage (HTTP)

- `POST /api/pipeline/run` — upload a `.mmd` file; it's extracted/classified
  automatically (foundation or bypass format, auto-detected), then run
  through the full pipeline. Optional `uploaded_bank` file (`.json` or
  `.mmd`) to dedupe against.
- `POST /api/pipeline/run-json` — same, but `file` is already-extracted
  question JSON (skip extraction, start at embeddings).

Both accept `similarity_threshold`, `skip_embeddings` (for testing without
an API key), and `force_rule_based_tagging` (skip the LLM tagger) as form
fields.

## Requirements

- `OPENAI_API_KEY` — needed for `embeddings.py` (text-embedding-3-small)
  and for the LLM-based competitive tagger in `tagger.py`. Without it:
  - `embeddings.py` raises `RuntimeError` (pass `skip_embeddings=True` to
    bypass for testing — similarity/dedup stages then no-op).
  - `tagger.py` automatically falls back to a deterministic rule-based
    tagger (keyword/heuristic-based difficulty, Bloom level, topic).

Put the key in `pipeline/.env` (gitignored) or the environment, same as
`bypass_question/.env` / `foundation/.env`.

## Notes / design choices

- **Similarity model**: cosine similarity over OpenAI embeddings
  (`text-embedding-3-small`). Embedding input = stem + options text, so
  MCQs with the same stem but different options aren't falsely merged.
- **Dedup is two-pass**: first against the external `uploaded_questions`
  bank (your existing question bank), then within the new batch itself
  (keeps the first occurrence of internal near-duplicates).
- **MathML conversion** uses `latex2mathml` against `$...$` / `$$...$$`
  segments left in `.mmd` content from Mathpix OCR (e.g.
  `$\frac{1}{2}\mathrm{~kg}$`, `$70^{\circ}\mathrm{C}$`). Malformed LaTeX is
  left as-is rather than dropped.
- **Competitive tagger** assigns: `difficulty` (EASY/MEDIUM/HARD),
  `bloom_level`, `topic`, `exam_tags` (NTSE/OLYMPIAD/JEE_FOUNDATION/
  NEET_FOUNDATION/BOARD), `estimated_time_seconds`, `concept_importance`.
