# Job Market AI Matcher

Job market data pipeline for Austria (Adzuna API) plus an AI-powered CV-to-posting matcher built with the Claude API.

## Overview

Job-market data is scattered across postings, and manually comparing a CV against dozens of listings doesn't scale. This project is a two-phase Python tool: Phase 1 pulls and summarizes real job postings from Austria's IT and consultancy job market; Phase 2 uses Claude to rank those postings against a CV and explain why each one is (or isn't) a good match.

It was built as a learning project — the goal wasn't just to produce a working tool, but to go through a real prompt-engineering iteration cycle: build a baseline, evaluate it honestly, find its failure modes, try to fix them, and document what actually worked versus what didn't.

**Status: complete.** Both phases run end to end, the seniority-filtering redesign described below is implemented and evaluated, and the project is being called finished deliberately — see [Status & Next Steps](#status--next-steps).

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

Switching from raw frequency to TF-IDF was meant to surface distinctive in-demand skills rather than generic frequent words. It partially worked: at the original 100-posting sample, `min_df` filtering alone removed one real class of noise (rare company names inflating a word's average score by appearing intensely in just 1-2 postings). Two follow-up tests — re-running the same pipeline on a larger, separately-pulled sample of 500 postings, and combining that larger sample with `min_df=3` — were done specifically to check whether more data would resolve the deeper issue, but ranked results looked essentially the same: generic German recruiting boilerplate ("führenden," "spannende," "leidenschaft," "bietet") still dominates the top of the list ahead of real skill terms. That result (not committed as new files — the 500-posting run was exploratory only) points to a structural mismatch rather than a data-volume problem: TF-IDF assumes documents differ enough in vocabulary that "distinctive" tracks "meaningful," which doesn't hold well across a homogeneous set of similarly-templated job ads. It's also compounded by the Adzuna API truncating descriptions, likely cutting off the requirements section where the more specific skill terms — and specific seniority requirements — would actually appear. This truncation turned out to matter again later, in Phase 2's seniority classification (see below).

## Phase 2 — AI-Powered CV Matching

Uses the Claude API to compare a CV against the postings pulled in Phase 1, returning a ranked shortlist with reasoning for each pick — instead of Phase 1's crude keyword count.

- **`CV_match.py`** is the production script. Point it at a CV as a PDF file and it sends that PDF directly to Claude via the API's native document support (no manual text extraction needed), matches it against the postings fetched in Phase 1, and writes a ranked shortlist with reasoning to `cv_match_result.json`.
- **`prompt_evaluation_pipeline.py`** is the testing/eval harness used to build and validate the prompts `CV_match.py` runs. It generates 6 synthetic test CVs (2 each at entry/junior/senior seniority, across IT and IT-consulting) and runs an evaluation loop against them: classify seniority, filter, generate a ranked match, then have a second Claude call independently grade the result. Each full run's results and scores are saved to `eval_v<version>.json`, and the exact matching prompt used in every run is logged to `prompt.json`.

### Architecture: three isolated calls, not one

Early versions asked a single Claude call to do everything at once — classify the CV's seniority, classify every posting's seniority, extract requirements, compare against the CV, and rank the result — all while writing directly into structured JSON with no room to reason before committing to output. That version consistently found ways to include seniority-mismatched postings anyway (e.g. recommending a role explicitly asking for "an experienced developer" to a recent graduate), even after the prompt was given an explicit hard rule against it. That turned out to be a structural limitation, not a wording problem: bundling many distinct judgment calls into one generation, especially across a long list of postings, makes each individual judgment less reliable — the model has less room to enforce a rule consistently against its own prior reasoning in the same breath.

The current pipeline splits this into deterministic, isolated stages:

1. **CV seniority classification** (Claude Haiku) — an isolated call that estimates total months of professional/skilled experience from the CV alone. Explicitly excludes unrelated survival jobs (retail, food service, etc.) from the count, and uses defined thresholds (0–6mo entry, 6mo–2yr junior, 2–5yr mid, 5yr+ senior) rather than leaving the boundary to the model's judgment.
2. **Posting seniority classification** (Claude Haiku, one batched call for the whole dataset) — classifies each posting's *required* seniority from explicit signals: stated years of experience, title keywords ("Junior"/"Senior"/"Lead"), leadership/mentoring language, or soft experience-implying phrases ("experienced," "fundierte/mehrjährige Erfahrung") that don't require an exact year count or title match. Postings with no seniority signal at all default to "mid" — a deliberate choice made after checking the actual dataset and finding the large majority of postings (roughly 70%) state no explicit seniority at all, so treating that silence as informative (rather than passing everything through unfiltered) was judged the safer default given the real data.
3. **Deterministic filtering (plain Python, no AI)** — compares the CV's classified level against each posting's classified level and keeps only postings at the CV's own tier or one tier below (with the CV's top tier, "senior," matching against senior-or-mid rather than everything below, following a specific bug found during evaluation — see below). This step is intentionally "dumb": no AI judgment happens here, only a lookup against labels already decided in steps 1–2.
4. **Final matching** (Claude Sonnet, using the pre-filtered posting list only) — compares the CV against the now-narrowed candidate list, with an explicit full-rescan step before compiling results (to reduce missed strong matches) and a discrete `match_quality` field (`excellent`/`good`/`moderate`/`poor`/`no_match`) that's checked against a hard filter rule before anything reaches the final output — rather than relying on a single free-text "verdict" to both explain and gate each result.

Because posting classification (step 2) doesn't depend on any particular CV, it only needs to run once per dataset pull, not once per CV matched against it.

### What moved the score, and what didn't

The core matching prompt went through many iterations, evaluated against the same fixed set of 6 synthetic CVs each round for comparability.

An early generate → critique → revise → regrade loop (each CV's match independently critiqued by a second call, then revised, then regraded by a third, separate call) was tested outside the main pipeline and produced the single best average score of any round (6.67/10), and was the only approach that fixed two specific bugs that had survived several rounds of prompt rewording untouched. It was ultimately not carried into the production pipeline — it roughly triples the API calls per CV, and a later, much cheaper fix (the explicit `match_quality` field and hard filter described above) reached a comparable score (6.5/10) without that added cost, so that's what shipped.

Two changes produced real, verifiable improvement:

- **The seniority-filtering split** (above) didn't move the raw eval average much on its own, but it eliminated an entire *category* of error outright: a junior CV being recommended a role requiring senior-level, unrelated professional experience stopped happening at all, rather than merely becoming less frequent. An aggregate score can't distinguish "one borderline extra posting included" from "recommended a job the candidate is wildly unqualified for" — the seniority split fixed the second, more damaging kind of error completely.
- **The `match_quality` field and explicit hard filter** closed a gap the seniority work didn't touch: cases where the model's own reasoning correctly concluded a posting was a poor fit, but the posting still made it into the final ranked output anyway. Forcing that judgment into a discrete, checkable field — rather than trusting a paragraph of free text to be consistently self-enforcing — measurably reduced (though did not entirely eliminate) that specific failure.

What was tried and didn't help: explicitly instructing the model to re-scan the full posting list a second time before finalizing its answer, aimed at cases where genuinely strong matches were missed for CVs with a large pool of eligible postings (e.g. a senior SAP consultant CV missing several clearly relevant senior SAP roles that were present in its own filtered candidate list). The instruction alone did not meaningfully change the model's actual coverage — the same postings were missed with or without it. The likely real fix (splitting the candidate postings into smaller batches across separate calls, rather than asking one call to hold and re-scan a long list) was identified but not implemented, given diminishing returns relative to the added complexity at this stage of the project.

### Known limitations (accepted, not pursued further)

- **Occasional residual instruction-compliance gap**: in one evaluated case, a posting explicitly labeled `"poor"` in its own `match_quality` field still appeared in the final output, in direct violation of the hard filter rule. This is a narrower, more specific failure than the original "the model doesn't realize this is a bad fit" problem (which the `match_quality` field did fix) — the model's own judgment is correct, but the output-compilation step doesn't always honor it.
- **Incomplete scanning on large candidate pools** for some CVs, per the explicit rescan experiment above — not resolved.
- **Posting seniority misclassification on postings well outside the IT/consultancy domain** (e.g. a hospitality management role pulled in by Adzuna's broader "consultancy" category classification). Real-world impact is low, since off-domain postings get excluded on content during the final matching step regardless of their seniority label — but it's a Phase 1 category-scoping issue worth narrowing if this project is extended later.
- **Posting description truncation** (see Phase 1 note above) limits how much signal the seniority classifier can extract from text alone for some postings; salary figures and soft experience-language were added as secondary signals specifically to reduce this, but coverage is still incomplete for postings with neither an explicit signal nor a disclosed salary.

## Status & Next Steps

This project is being called finished. Both phases run end to end, are individually explainable, and the seniority-filtering redesign — the main open item from earlier in the project — is implemented and evaluated. The limitations listed above are known, understood, and deliberately not chased further: continuing from here would mean incremental validation and edge-case hardening rather than the kind of structural learning (prompt architecture, evaluation methodology, deterministic-vs-AI task splitting) this project was actually meant to build.

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
| `prompt_evaluation_pipeline.py` | Phase 2 — seniority classification, CV-matching prompt, model-based grader, and the eval harness |
| `CV_match.py` | Phase 2 — production script, matches a real PDF CV against fetched postings |
| `data.json` | Example output of a real Adzuna pull (Austria, IT + consultancy categories) |
| `summary.json` | Example Phase 1 summary output |
| `test_CVs.json` | Fixed synthetic CV dataset used across all evaluation rounds, for comparable results |
| `eval_v1.json` – `eval_v12.json` | Saved results and scores for a representative sample of prompt iteration rounds, including the final version (later intermediate rounds were tested but aren't all committed, to avoid cluttering the repo with near-duplicate files) |