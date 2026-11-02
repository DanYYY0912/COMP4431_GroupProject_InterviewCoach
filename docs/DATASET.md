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

The second-review selection rounds up within each language/task stratum, producing 230 assignments, slightly more than 15%. `mixed` is a dataset label; the application still chooses `en-HK` or `zh-HK` per answer.

## Review workflow

1. Copy the draft file to `ml/data/reviewed_examples.jsonl`. Keep original draft provenance.
2. Assign authors distinct examples. Replace repetitive templates with realistic, independently written scenarios. Include complete and incomplete STAR answers, uncertain claims, technical trade-offs, refusals, language boundaries, and malicious source instructions. Avoid copying private CVs or proprietary interview materials.
3. Verify each source statement, the exact answer evidence, Cantonese phrasing, output schema, and absence of invented measurements. The draft feedback often quotes an entire answer; replace that with the exact supporting span for each STAR element.
4. Set `template_family` to the actual writing/template family. Do not give duplicated content a new ID to evade leakage checks. Keep source provenance and license accurate.
5. Run `python -m ml.dataset refresh-hashes --input ml/data/reviewed_examples.jsonl`. Changed content loses old approvals.
6. A real reviewer records an approval or rejection for the current hash. Examples assigned second review need two **different** reviewers. A review is a human judgement; automated validators cannot substitute for it.
7. Run the validation command below. Resolve every quality/duplication finding before splitting.

A review record has this shape; fill real values only:

```json
{
  "reviewer": "actual-team-member-id",
  "decision": "approved",
  "reviewed_at": "actual ISO-8601 time",
  "content_sha256": "the current row content_sha256"
}
```

```sh
python -m ml.dataset validate --input ml/data/reviewed_examples.jsonl --require-review --check-duplicates
python -m ml.dataset split --input ml/data/reviewed_examples.jsonl --output ml/data/reviewed
python -m ml.train --config ml/config.json --validate-only
```

## Model contract

Question and safety examples emit citation IDs. Feedback and report examples emit exactly four STAR records, competency evidence with citation IDs, grounded strength records, and actionable next steps. The backend attaches original citation text and computes session metadata and speech metrics; the model never authors those fields. A parity test validates all 1,500 drafts against the actual backend Pydantic models.

## Leakage prevention

The splitter keeps connected role families, job source IDs, and template families together. It targets 80/10/10 by row count and refuses fewer than three independent groups. Large groups can prevent exact ratios; inspect the manifest and author additional independent groups when needed. The generated draft set intentionally shares template families, so it cannot be promoted unchanged.

Five-character shingle similarity catches near duplicates across languages without relying on whitespace tokenization. Digits are normalized so changing a project number does not create a new example. This is an automated screen, not a proof of semantic independence; reviewers must also check paraphrases. The training command rechecks all split hashes, reviews, schemas, expected 1,500-row proportions, and disjoint groups before loading GPU libraries.

## Provenance and limitations

Draft job briefs and responses are fictional, generated for this project, and marked CC0-1.0 in each row. They are not O*NET content or authentic employer job descriptions. Human edits must retain attribution and comply with the source license. The included 120 model prompts are diagnostic samples from these drafts and **must be replaced** with a sample from the final reviewed test split before assessed evaluation. Never report results on them as held-out fine-tuning performance.
