# Dataset preparation and human review

## Executive summary

The repository contains 1,500 **synthetic curriculum drafts**, not 1,500 reviewed training examples. They provide the requested language/task proportions and fictional job contexts, but contain repeated templates and need substantial rewriting and human quality checks. Training is blocked by review, hash, schema, duplicate, and split-isolation gates. Twelve small examples support local software tests. No real applicant transcript or employer document was used to create these drafts, and no human approval has been invented.

## Included files

- `ml/data/drafts.jsonl`: 1,500 unreviewed rows; reproduce with `python -m ml.dataset generate`.
- `ml/data/seed_examples.jsonl`: one example per language/task combination for schema checks.
- `ml/dataset.py`: generation, validation, content hashing, and grouped splitting.
- `ml/schemas.py`: strict model-facing `ModelCoachTurn` and `ModelReport` output schemas.

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
