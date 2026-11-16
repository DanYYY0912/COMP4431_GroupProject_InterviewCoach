# Dataset preparation and human review

## Executive summary

The repository contains 1,500 **synthetic curriculum drafts**, not 1,500 reviewed training examples. They provide the requested language/task proportions and fictional job contexts, but contain repeated templates and need substantial rewriting and human quality checks. Training is blocked by review, hash, schema, duplicate, and split-isolation gates. Twelve small examples support local software tests. No real applicant transcript or employer document was used to create these drafts, and no human approval has been invented.

## Included files

- `ml/data/runtime_drafts.jsonl`: 1,000 unreviewed runtime-aligned rows; reproduce with `python -m ml.runtime_dataset`. Every prompt in this file is produced by the app's own builders (`backend/app/coach.py`), so a training row is byte-identical to a live request.
- `ml/scenarios/`: the fictional job descriptions (`jobs.json`), the original bilingual story library (`stories/*.json`) and the adversarial safety strings (`injections.json`). Data only; `ml/runtime_dataset.py` is the generator.
- `ml/data/drafts.jsonl`: 1,500 unreviewed rows; reproduce with `python -m ml.dataset generate`.
- `ml/data/seed_examples.jsonl`: one example per language/task combination for schema checks.
- `ml/dataset.py`: generation, validation, content hashing, and grouped splitting.
- `ml/schemas.py`: strict model-facing `ModelCoachTurn` and `ModelReport` output schemas.

`drafts.jsonl` is **superseded** and must not be trained on. Its prompts and competency
labels do not match the runtime payload, every row is missing the same STAR element
(`Result`), and its rows share a handful of template families, so `ml.dataset.split_dataset`
refuses it. It stays in the repository only as historical material; `runtime_drafts.jsonl`
is the corpus to review.

| Dimension | Count |
|---|---:|
| English (`en-HK`) | 900 |
| Traditional Chinese Cantonese (`zh-HK`) | 450 |
| Code-switching (`mixed`) | 150 |
| Questions / adaptive follow-ups | 600 |
| STAR feedback | 525 |
| Structured reports | 225 |
| Safety / language boundaries | 150 |
| Assigned independent second review | 230 |
| Completed human reviews | 0 |

The second-review selection rounds up within each language/task stratum of the full corpus, producing 230 assignments, slightly more than 15%. The quota is checked before splitting and training. Held-out subsets retain each example’s assigned review requirements; they are not forced to satisfy a newly sampled 15% quota. `mixed` is a dataset label; the application still chooses `en-HK` or `zh-HK` per answer.

## Runtime-aligned corpus (WS2)

`python -m ml.runtime_dataset` rebuilds `ml/data/runtime_drafts.jsonl` deterministically
(fixed seed, no network, no model call). Every row is a real runtime shape:

| Dimension | Count |
|---|---:|
| `question` (opening, STAR follow-up, next question) | 450 |
| `report` (STAR coaching, 1–2 answers) | 350 |
| `safety` (injected sources, hiring/accent requests) | 200 |
| English (`en-HK`) | 600 |
| Traditional Chinese Cantonese (`zh-HK`) | 400 |
| Assigned independent second review | 151 |
| Completed human reviews | 0 |

Fifteen role families get 66 or 67 rows each (ten families 67, five 66), and every family
appears in both languages and in both the question and report tasks. Generation enforces
the gates rather than hoping for them:

- `app.coach.question_messages` / `report_messages` build the prompts, and
  `check_question_output` / `check_report_output` validate every target, so citations,
  verbatim evidence, STAR coverage, competency subsets and Cantonese text are checked by
  the same code the app runs.
- `app.ingestion.profile_metadata` derives `allowed_competencies` from the fictional job
  description, so labels are always the app's English keys.
- `app.ingestion.chunk_text` plus `app.retrieval.lexical_ranking` over the job description
  and `knowledge/*.txt` reproduce the no-embedding retrieval path; the top four passages
  become `quoted_sources`.
- Two rows may never share the same normalised wording: the generator walks its phrasing
  table until `ml.dataset.normalized_text` is unique, then `near_duplicate_pairs` reports
  zero pairs at 0.90.
- Row length is checked with a token estimator calibrated offline against the
  Qwen3-4B-Instruct-2507 tokenizer: mean ≈1,340, p99 ≈1,830, max ≈1,880 of the 2,048-token
  budget in `ml/config.json`, with no row above the limit and no row above 1,900.

Second review is assigned per `(language, task)` stratum at 15% rounded up. `reviews` is
empty on every row: reviewers fill it with `ml.review`, and the review, hash, duplicate and
split gates still block training until they do.

`ml.review start` shows one row at a time by default. Two speed options, both of which keep
the decision with the human:

- `--compact` prints a condensed one-screen view (candidate excerpt, target question or the
  four STAR lines with evidence, automatic checks) instead of the full JSON.
- `--batch N` prints N rows and then asks for one confirmation; the reviewer must retype `N`,
  so a stray Enter approves nothing, and the batch size actually used is recorded below so
  the review depth is never overstated.

| Review run | Reviewer(s) | Batch size | Rows |
|---|---|---|---|
| _(not started)_ | | | |

## Market grounding for the runtime-aligned corpus

The role families, competency mix and seniority mix mirror Hong Kong postings. The job
descriptions themselves are fictional originals written for this project — no employer,
person or posting text is copied — and the two datasets below are used only as evidence for
which roles and skills to cover:

| Source | Use |
|---|---|
| Kaggle `asterfung/ds-obsdbhk` — Data Science Jobs on JobsDB Hong Kong, 349 HK postings (Dec 2022) | Titles: data analyst 17, data engineer 11, data scientist 5, quantitative researcher/developer 5, business analyst 5, software engineer 4, business intelligence analyst 3, data programmer 3, database administrator 3, system analyst 2. Career level: entry 77, middle 153, senior 34. Skill frequency: SQL 309 (88%), Python 183 (52%), Excel 179 (51%), Git 160 (46%), Tableau 116 (33%), machine learning 114 (33%), statistics 113 (32%), ETL 88 (25%), Power BI 86 (25%), Java 77 (22%), Azure 69 (20%), AWS 60 (17%), Spark 30, Hadoop 29, NLP 17, Docker 14, Airflow 12. |
| Kaggle `sergeychekurin/it-jobs-in-asia-pacific-region-may-june-2024` — 3,969 HK postings (May–Jun 2024) | Specialisation: Java 297, IT Support 240, Project Management 105, Network 77, .NET 61, Business Analysis 45, Cloud 43, Security 40, AI 37, Data Analytics 36, Web Development 35, C# 33, ERP 30, IT Infrastructure 30. Level: Junior 618, Middle 1,461, Senior 1,200. |

The fifteen families are: backend software engineer (Java/.NET, the largest specialisation),
web developer, data analyst/BI, data engineer/ETL, ML/AI engineer, QA/UAT engineer, IT
support engineer, business systems analyst, cloud/DevOps engineer, mobile app developer,
security analyst (SOC), network/infrastructure engineer, IT project coordinator, digital
marketing executive, and pre-sales consultant. Stories span entry level, 1–3 years and 4–6
years in roughly 25/50/25 proportion, and hiring contexts vary between agency, in-house,
bank, vendor, contract and government-adjacent work.

## Review workflow (human CLI)

Use WS2's runtime-aligned drafts when available. The old `drafts.jsonl` is retained as historical material and cannot be trained unchanged: its prompts and competency labels differ from the app, all missing elements are Result, and shared templates prevent an independent split. Do not copy it as the new training corpus. WS2 owns generation of `runtime_drafts.jsonl`.

1. The coordinator copies `ml/data/runtime_drafts.jsonl` to `ml/data/reviewed_examples.jsonl` once, preserving provenance, IDs, and the second-review assignments. Share the same frozen input with all four reviewers. Do not reorder or regenerate it during review: shards use zero-based file order modulo four.
2. Each person starts their own shard with their real name (replace the example name):

   ```sh
   python -m ml.review start --input ml/data/reviewed_examples.jsonl --reviewer "Your real name" --shard 3/4
   ```

   Use shards `1/4`, `2/4`, `3/4`, `4/4` once each. The CLI displays task, language, user JSON (source passages shortened **only for display**), formatted assistant JSON, marked exact answer evidence `⟦…⟧`, and automatic checks. With WS1 available it runs the same grounding/evidence/language validators as the app; before WS1 is installed it checks `ml.schemas.validate`.
3. Press `a` to approve this exact target, `r` to reject with a mandatory reason, `e` to edit assistant JSON using `$EDITOR`, `s` to skip, or `q` to quit. Set `export EDITOR='nano'` or another editor first. Every edit is validated and displayed again; it is **not** an approval. Invalid output cannot be approved. Judge semantic source support, precise evidence, natural Cantonese, missing STAR details and invented measurements yourself. Automated success is not human review.
4. Resume using the same command after quitting or interruption. Decisions for the current content are skipped; `s` remains pending. Add `--revisit` to revisit your own rejections. To revise source/user metadata, coordinate a new frozen input with accurate leakage groups and provenance; conflicting saved edits fail visibly.
5. Each reviewer commits only their own `ml/data/reviews/<reviewer-slug>.jsonl` and their assigned `ml/data/edits/<example-id>.json`. Names are nonblank and slugs include a stable digest, including for Chinese names. Files are saved after every decision/edit using a temporary file, flush/fsync, and `os.replace`. Leave `reviewed_examples.jsonl` unchanged until the coordinator merges; this avoids conflicts in the shared corpus. Do not run two CLI sessions with the same reviewer identity simultaneously.
6. Collect all first-review logs/edits before second review. Rotate shard ownership (reviewer 1 takes shard 2, reviewer 2 takes shard 3, reviewer 3 takes shard 4, reviewer 4 takes shard 1), adding `--second`:

   ```sh
   python -m ml.review start --reviewer "Your real name" --shard 4/4 --second
   ```

   This lists only `double_review_required` rows approved on the **current hash** by another reviewer. You cannot provide your own second approval. If you edit, the previous approval becomes stale; collect two independent approvals on the final target again. Use `status` to find remaining work, then rerun a first-review pass or `--second` as appropriate.
7. The coordinator merges logs and edits, then validates and splits:

   ```sh
   python -m ml.review status
   python -m ml.review merge
   python -m ml.dataset validate --input ml/data/reviewed_examples.jsonl --require-review --check-duplicates
   python -m ml.dataset split --input ml/data/reviewed_examples.jsonl --output ml/data/reviewed
   python -m ml.train --config ml/config.json --validate-only
   ```

`merge` recomputes content hashes and retains only each reviewer's latest decision matching the final content. A later rejection revokes an earlier approval. It is safe to merge repeatedly, including into the default input path. Merge can output an incomplete corpus; **only** the subsequent `validate --require-review` and split/train gates establish readiness. Status reports each reviewer's current approvals, rejections and remaining decisions, overall unfinished examples, and completed/remaining independent second reviews.

All subcommands accept `--input`, `--reviews-dir`, and `--edits-dir`; `merge` also accepts `--output`. Defaults place logs and edits beside the input file. Review records contain `example_id`, the real `reviewer`, a manually selected `decision`, current UTC ISO `reviewed_at`, `content_sha256`, and rejection `reason`. The tool has no batch approval mode. Tests use explicitly named test reviewers and temporary fixtures only; they never write approvals into repository data.

## Model contract

Question and safety examples emit citation IDs. Feedback and report examples emit exactly four STAR records, competency evidence with citation IDs, grounded strength records, and actionable next steps. The backend attaches original citation text and computes session metadata and speech metrics; the model never authors those fields. A parity test validates all 1,500 drafts against the actual backend Pydantic models.

## Leakage prevention

The splitter keeps connected role families, job source IDs, and template families together. It targets 80/10/10 by row count and refuses fewer than three independent groups. Large groups can prevent exact ratios; inspect the manifest and author additional independent groups when needed. The generated draft set intentionally shares template families, so it cannot be promoted unchanged.

Five-character shingle similarity catches near duplicates across languages without relying on whitespace tokenization. Digits are normalized so changing a project number does not create a new example. This is an automated screen, not a proof of semantic independence; reviewers must also check paraphrases. The training command rechecks all split hashes, reviews, schemas, configured example count, and disjoint groups before loading GPU libraries.

## Provenance and limitations

Draft job briefs and responses are fictional, generated for this project, and marked CC0-1.0 in each row. They are not O*NET content or authentic employer job descriptions. Human edits must retain attribution and comply with the source license. The included 120 model prompts are diagnostic samples from these drafts and **must be replaced** with a sample from the final reviewed test split before assessed evaluation. Never report results on them as held-out fine-tuning performance.
