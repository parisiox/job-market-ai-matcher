# Job Market AI Matcher

Job market data pipeline for Austria (Adzuna API) plus an AI-powered CV-to-posting matcher built with the Claude API.

## Overview

Job-market data is scattered across postings, and manually comparing a CV against dozens of listings doesn't scale. This project is a two-phase Python tool: Phase 1 pulls and summarizes real job postings from Austria's IT and consultancy job market; Phase 2 uses Claude to rank those postings against a CV and explain why each one is (or isn't) a good match.

It was built as a learning project — the goal wasn't just to produce a working tool, but to go through a real prompt-engineering iteration cycle: build a baseline, evaluate it honestly, find its failure modes, try to fix them, and document what actually worked versus what didn't.

**Status: Phase 1 and the Phase 2 evaluation pipeline are complete and working. The end-user-facing production script (`job_match.py`) is the next step — see [Status & Next Steps](#status--next-steps) below.**

## Phase 1 — Job Market Intelligence Tool

Pulls job postings from the [Adzuna API](https://developer.adzuna.com/) and produces a summary of what's actually in demand in the current Austrian IT/consultancy job market.

- **`fetch_data.py`** — `fetch_data()` pulls postings across a list of categories (e.g. `it-jobs`, `consultancy-jobs`), combines them, and saves the raw results to `data.json`. Handles bad HTTP responses, connection errors, malformed JSON, and timeouts per category without letting one failing category block the others.
- **`summarize_data.py`** — `summarize_data()` loads `data.json` and produces:
  - **Keyword frequency**: the most common words across posting descriptions (German + English stopwords removed via spaCy, numbers filtered out).
  - **Seniority breakdown**: how often terms like `senior`, `junior`, `praktikant`, `werkstudent`, etc. appear across postings, matched as whole words against both title and description.
  - **Salary means**: average minimum and maximum salary across whichever postings disclosed those figures.
  - Output is saved to `summary.json`.

Both functions handle missing/malformed data gracefully — a single posting missing a `description` or `title` field, or a `data.json` that isn't valid JSON, won't crash the run.

## Phase 2 — AI-Powered CV Matching

Uses the Claude API to compare a CV against the postings pulled in Phase 1, returning a ranked shortlist with reasoning for each pick — instead of Phase 1's crude keyword count.

Built and validated inside `prompt_evaluation_pipeline.py`, which generates 6 synthetic test CVs (2 each at intern/junior/senior seniority, across IT and IT-consulting) and runs a full evaluation loop against them: generate a ranked match → have a second Claude call independently grade the result → revise based on that critique → grade the revision again. Each full run's results and scores are saved to `eval_v<version>.json`.

### Where the prompt stands

The core matching prompt went through four iterations (v1–v4), each getting more specific about how the model should evaluate fit. A separate two-pass "regrade" approach (generate → grade → revise → grade again) was also tried on top of that, aiming to catch and correct weak picks automatically — results there have been mixed so far, and it roughly triples the API calls per CV, so it's not currently part of the plan for the production script.

## Status & Next Steps

**Current state:** the project is close to done — Phase 1 and the Phase 2 evaluation pipeline both work end to end. The main open item is the production script (`job_match.py`), plus continuing to push the matching prompt's scores up.

**What's still missing / left to do:**
- **Improve prompt match quality further, while cutting back API usage** — the current approach makes a lot of calls per evaluation run (and resends the full postings dataset in each one), which gets expensive fast. The goal going forward is a version that scores better *and* costs less, not just one or the other.
- **`job_match.py`** — the actual end-user-facing production script does not exist yet. `prompt_evaluation_pipeline.py` has always been a testing/eval harness by design, not the deliverable. `job_match.py` will reuse the validated prompt logic to match a real CV against freshly fetched postings.
- **Error handling around `json.loads()`** in the evaluation pipeline — none of the parsing calls are currently wrapped in `try`/`except`, so one malformed model response partway through a run currently loses the whole run's progress.
- **A `prompt_versions.json` tracker** — save each prompt version's exact text as it's iterated on (`{"version": ..., "prompt": ...}`), so past versions don't have to be reconstructed from memory/conversation history after the fact.
- **A code-based/deterministic grader** alongside the LLM-based one — e.g. verifying returned `title`/`link` pairs actually correspond to a real entry in the fetched dataset, and checking for duplicate links.
- **PDF CV input** — CVs are plain text for now; Claude's API can reportedly accept a PDF directly as a document input, which would be more realistic for an end user. Not yet tried — worth checking how much (if any) extra work that actually needs before relying on it.
- **Extend `summarize_data()`'s keyword filtering beyond standard stopwords** — a custom exclusion list for generic job-posting boilerplate ("m/w/d", "Unternehmen", "Team", etc.) that survives stopword removal but doesn't reflect actual in-demand skills, so the keyword summary reflects real signal rather than posting-template noise.

## Setup

Requires Python 3.12+, an [Adzuna API](https://developer.adzuna.com/) app ID/key, and an [Anthropic API key](https://console.anthropic.com/).

1. Clone the repo and install dependencies:
   ```
   pip install requests python-dotenv spacy anthropic
   ```
2. Copy `.env.example` to `.env` and fill in your real keys:
   ```
   APP_ID=your_adzuna_app_id
   APP_KEY=your_adzuna_app_key
   ANTHROPIC_API_KEY=your_anthropic_api_key
   ```
3. Run Phase 1 to fetch and summarize postings:
   ```
   python fetch_data.py
   python summarize_data.py
   ```
4. Run the Phase 2 evaluation pipeline (note: this makes real, billed Claude API calls):
   ```
   python prompt_evaluation_pipeline.py
   ```

## Repo contents

| File | Purpose |
|---|---|
| `fetch_data.py` | Phase 1 — fetches job postings from Adzuna, saves to `data.json` |
| `summarize_data.py` | Phase 1 — keyword/seniority/salary analysis, saves to `summary.json` |
| `prompt_evaluation_pipeline.py` | Phase 2 — CV-matching prompt, model-based grader, revise/regrade loop, and the eval harness |
| `data.json` | Example output of a real Adzuna pull (Austria, IT + consultancy categories) |
| `summary.json` | Example Phase 1 summary output |
| `test_CVs.json` | Fixed synthetic CV dataset used across all evaluation rounds, for comparable results |
| `eval_v1.json` – `eval_v4.json` | Saved results and scores for each prompt iteration round |
