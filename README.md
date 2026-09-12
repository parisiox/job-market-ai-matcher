# Job Market AI Matcher

Job market data pipeline for Austria (Adzuna API) plus an AI-powered CV-to-posting matcher built with the Claude API.

## Overview

Job-market data is scattered across postings, and manually comparing a CV against dozens of listings doesn't scale. This project is a two-phase Python tool: Phase 1 pulls and summarizes real job postings from Austria's IT and consultancy job market; Phase 2 uses Claude to rank those postings against a CV and explain why each one is (or isn't) a good match.

It was built as a learning project — the goal wasn't just to produce a working tool, but to go through a real prompt-engineering iteration cycle: build a baseline, evaluate it honestly, find its failure modes, try to fix them, and document what actually worked versus what didn't.

**Status: Phase 1, the Phase 2 evaluation pipeline, and the production matching script (`CV_match.py`) are all complete and working. What's left is mostly refinement — see [Status & Next Steps](#status--next-steps) below.**

## Phase 1 — Job Market Intelligence Tool

Pulls job postings from the [Adzuna API](https://developer.adzuna.com/) and produces a summary of what's actually in demand in the current Austrian IT/consultancy job market.

- **`fetch_data.py`** — `fetch_data()` pulls postings across a list of categories (e.g. `it-jobs`, `consultancy-jobs`), combines them, and saves the raw results to `data.json`. Handles bad HTTP responses, connection errors, malformed JSON, and timeouts per category without letting one failing category block the others.
- **`summarize_data.py`** — `summarize_data()` loads `data.json` and produces:
  - **Keyword ranking (TF-IDF)**: posting descriptions are vectorized with scikit-learn's `TfidfVectorizer` (German + English stopwords removed via spaCy, `min_df=3` so a term must appear in at least 3 postings to count) rather than ranked by raw frequency. Each word's per-posting TF-IDF scores are averaged only over the postings it actually appears in, so a term's rank reflects "how important is this word when it shows up," independent of how many postings happen to contain it.
  - **Seniority breakdown**: how often terms like `senior`, `junior`, `praktikant`, `werkstudent`, etc. appear across postings, matched as whole words against both title and description.
  - **Salary means**: average minimum and maximum salary across whichever postings disclosed those figures.
  - Output is saved to `summary.json`.

Both functions handle missing/malformed data gracefully — a single posting missing a `description` or `title` field, or a `data.json` that isn't valid JSON, won't crash the run.

### A note on the keyword ranking's limits

Switching from raw frequency to TF-IDF was meant to surface distinctive in-demand skills rather than generic frequent words. It partially worked: at the original 100-posting sample, `min_df` filtering alone removed one real class of noise (rare company names inflating a word's average score by appearing intensely in just 1-2 postings). Two follow-up tests — re-running the same pipeline on a larger, separately-pulled sample of 500 postings, and combining that larger sample with `min_df=3` — were done specifically to check whether more data would resolve the deeper issue, but ranked results looked essentially the same: generic German recruiting boilerplate ("führenden," "spannende," "leidenschaft," "bietet") still dominates the top of the list ahead of real skill terms. That result (not committed as new files — the 500-posting run was exploratory only) points to a structural mismatch rather than a data-volume problem: TF-IDF assumes documents differ enough in vocabulary that "distinctive" tracks "meaningful," which doesn't hold well across a homogeneous set of similarly-templated job ads. It's also compounded by the Adzuna API truncating descriptions at 500 characters, likely cutting off the requirements section where the more specific skill terms would actually appear.

## Phase 2 — AI-Powered CV Matching

Uses the Claude API to compare a CV against the postings pulled in Phase 1, returning a ranked shortlist with reasoning for each pick — instead of Phase 1's crude keyword count.

- **`CV_match.py`** is the production script. Point it at a CV as a PDF file and it sends that PDF directly to Claude via the API's native document support (no manual text extraction needed), alongside the postings fetched in Phase 1, and writes a ranked shortlist with reasoning to `cv_match_result.json`.
- **`prompt_evaluation_pipeline.py`** is the testing/eval harness used to build and validate the prompt `CV_match.py` runs. It generates 6 synthetic test CVs (2 each at intern/junior/senior seniority, across IT and IT-consulting) and runs an evaluation loop against them: generate a ranked match, then have a second Claude call independently grade the result. Each full run's results and scores are saved to `eval_v<version>.json`, and the exact prompt text used in every run is logged to `prompt.json` — added recently, so no `prompt.json` is committed to the repo yet, since it'll only start filling up once the pipeline is run again with a prompt version worth logging.

### Where the prompt stands

The core matching prompt went through many iterations. An early two-pass "regrade" approach (generate → grade → revise → grade again) was tried and dropped — it roughly triples the API calls per CV, and testing showed it sometimes made a good result worse rather than reliably fixing a bad one.

A large chunk of later iterations focused on getting the prompt to reliably reject postings whose seniority doesn't fit the CV — e.g. not recommending a role explicitly asking for "an experienced developer" to a recent graduate. Across many versions — including forcing the model to record an explicit `entry/junior/mid/senior` classification per posting and then re-check that classification against a hard rule — the model consistently found ways to include mismatched postings anyway (softening its own classification, or reasoning past the rule in its verdict). That turned out to be a real, structural limitation rather than a wording problem: a single generation pass doesn't reliably enforce a hard categorical rule against its own prior reasoning. The current plan is to move seniority filtering out of the prompt entirely and into plain Python — tagging each posting's seniority deterministically (reusing the keyword-matching approach `summarize_data()` already uses) and filtering the postings dataset *before* it's ever sent to Claude, rather than trusting the model to police itself. Not yet implemented.

## Status & Next Steps

**Current state:** Phase 1, the Phase 2 evaluation pipeline, and the production `CV_match.py` script are all complete and working end to end.

**What's still missing / left to do:**
- **Move seniority filtering into deterministic code** — see "Where the prompt stands" above. Tag each posting's required seniority via keyword matching, compare it against the CV's own experience level, and filter the postings dataset before it reaches the matching prompt, instead of relying on the LLM to self-enforce the rule.
- **A code-based/deterministic grader** alongside the LLM-based one — e.g. verifying returned `title`/`link` pairs actually correspond to a real entry in the fetched dataset, and checking for duplicate links.

## Setup

Requires Python 3.12+, an [Adzuna API](https://developer.adzuna.com/) app ID/key, and an [Anthropic API key](https://console.anthropic.com/).

1. Clone the repo and install dependencies:
```
   pip install requests python-dotenv spacy scikit-learn anthropic
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
5. Match a real CV against the fetched postings: place your CV as a PDF in the project folder, update the filename passed to `cv_match(...)` at the bottom of `CV_match.py` (defaults to the placeholder `Your_CV.pdf`), then run:
```
   python CV_match.py
```

## Repo contents

| File | Purpose |
|---|---|
| `fetch_data.py` | Phase 1 — fetches job postings from Adzuna, saves to `data.json` |
| `summarize_data.py` | Phase 1 — keyword (TF-IDF)/seniority/salary analysis, saves to `summary.json` |
| `prompt_evaluation_pipeline.py` | Phase 2 — CV-matching prompt, model-based grader, and the eval harness |
| `CV_match.py` | Phase 2 — production script, matches a real PDF CV against fetched postings |
| `data.json` | Example output of a real Adzuna pull (Austria, IT + consultancy categories) |
| `summary.json` | Example Phase 1 summary output |
| `test_CVs.json` | Fixed synthetic CV dataset used across all evaluation rounds, for comparable results |
| `eval_v1.json` – `eval_v4.json` | Saved results and scores for a representative sample of prompt iteration rounds (later rounds were tested but aren't all committed, to avoid cluttering the repo with near-duplicate files) |