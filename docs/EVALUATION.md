# Evaluation protocol and current evidence

## Executive summary

The evaluation suite can check model JSON, retrieval recall, citation support labels, speech error rates, latency, blinded preferences and usability. Current evidence consists of local software checks and synthetic diagnostic fixtures; **none of the assessed model, speech, avatar, or usability release thresholds has been demonstrated**. Raw failures stay in the output, human ratings are never generated, and language-script heuristics are not reported as Cantonese fluency. The methodology endpoint reads `evaluation/results/latest.json`, which retains this distinction.

## Run local software checks

```sh
python -m unittest discover -s ml/tests
python -m unittest discover -s evaluation/tests
python -m evaluation.run smoke
```

The smoke run validates twelve schema examples and five known metric calculations. It does not call a model, synthesize speech, or measure user satisfaction. `evaluation/results/smoke.json` records exactly what ran.

## Model experiment: 120 held-out prompts

1. Complete real data review and QLoRA training. Use the final group-isolated test split, never the diagnostic prompt file bundled here.
2. `python -m evaluation.run prepare --input ml/data/reviewed/test.jsonl --output evaluation/fixtures/model_prompts.jsonl`
3. Run the base and exported fine-tuned GGUF in separate local llama.cpp servers: the example uses port 8084 for the comparison base model and 8080 for the fine-tuned model. Ports 8082 and 8083 remain reserved for embeddings and reranking. Copy `evaluation/model_endpoints.example.json` and set the endpoint/model identifiers for `base_rag`, `lora_only`, and `lora_rag`.
4. `python -m evaluation.run model --input evaluation/fixtures/model_prompts.jsonl --training-data ml/data/reviewed/train.jsonl --config PATH_TO_ENDPOINT_CONFIG`
5. Retain the configuration, artifact hashes, `model_raw.jsonl`, and `model.json`. All variants use temperature 0, seed 42 and 1,536 maximum generated tokens. Base+RAG and LoRA+RAG receive the identical prompt and source context; LoRA-only receives the same request with retrieved context removed.

The runner records all 360 outcomes, including malformed output, truncation and timeouts. JSON validity is scored against a strict task schema. First-token latency is measured from request start to the first nonempty streamed content; failed requests are counted separately and cannot disappear from the denominator. The protocol uses preselected, fixed source contexts so the model comparison does not mix in changing retrieval quality. Benchmark retrieval independently.

Target schema validity is 98%. The script-language proxy is diagnostic only. Reviewers must assess actual requested-language adherence, especially colloquial Traditional-Chinese Cantonese; target 95%. Add a `language_reviews` array to the human input with one final record per prompt: `example_id`, `reviewer_id`, and boolean `adheres`. The runner reports this actual human measure separately from its script proxy. The 120 provided diagnostic prompts come from synthetic drafts and require `--diagnostic`, which labels results accordingly.

## Blinded model preference

```sh
python -m evaluation.blind --input evaluation/results/model_raw.jsonl
```

The command deterministically samples 30 paired outcomes and shuffles the A/B model labels. It includes service failures rather than selecting only successful answers. Share `reviewer_packet.json` and separate rating forms with two reviewers. Keep `operator_key.json` with the operator until both sets of ratings are final.

After unblinding, create the input for `python -m evaluation.run human --input PATH`:

```json
{
  "preference": [
    {"pair_id":"pair-01", "reviewer_id":"actual-reviewer", "choice":"A", "lora_label":"B"}
  ],
  "usability": [
    {"participant_id":"actual-participant", "completed":true, "sus_answers":[1,2,3,4,5,1,2,3,4,5]}
  ]
}
```

The example shows structure only and is not an observed rating. Collect 30 pairs, two distinct reviewers per pair, and 5–8 usability participants. Preference is wins divided by all ratings; ties are reported and remain in the denominator. The runner reports Cohen's kappa; unanimous single-category ratings have undefined kappa and are shown as null. Target LoRA+RAG preference is 65%. Peer tests should use a clean browser, record completion of setup → interview → review, and administer the standard ten-item System Usability Scale with 1–5 responses. Targets: completion at least 90%, SUS at least 80.

## Retrieval: 40 supporting-passage questions

With backend dependencies installed, run the actual retrieval implementation on an isolated corpus:

```sh
python -m evaluation.collect
python -m evaluation.run retrieval --input evaluation/results/retrieval_observations.jsonl --diagnostic
```

This uses a synthetic corpus and an in-memory SQLite database. It does not alter local interview history and does not establish production pgvector/RAG quality. For assessed work, author/review 40 queries over the final knowledge corpus and preserve observed retrieval results in JSONL:

```json
{"id":"query-01","retrieved_ids":["observed-chunk"],"relevant_ids":["reviewed-supporting-chunk"],"reviewed_by":["actual-reviewer"],"cited_ids":["generated-citation"],"supported_citation_ids":["human-verified-citation"],"unsupported_claims":0,"total_claims":1,"injection_failed":false}
```

Run without `--diagnostic` after replacing the example fields with actual evidence. Recall@5 uses known relevant passages as its denominator. Citation precision needs human support labels; an existing chunk ID alone is not evidence that it supports a claim. Missing citation ratings remain null. Targets: recall@5 ≥85%, citation precision ≥90%. Record unsupported-claim and prompt-injection failure rates, including a source that tells the assistant to ignore its instructions.

## Speech and latency

Use `evaluation/fixtures/speech_collection_template.jsonl` to collect 24 consented recordings from at least four speakers, balanced 12 English/12 Cantonese with clean and noisy conditions. Store each recording hash, reviewer-checked reference transcript, recognizer hypothesis, corrections, failures, and speech-end-to-first-audio time. Empty references fail validation; silence belongs in a separate robustness test. A failed recognizer with an empty hypothesis counts as deletions, not an excluded case.

```sh
python -m evaluation.run speech --input PATH_TO_COMPLETED_RECORDS
```

English uses corpus word error rate; Cantonese uses corpus character error rate. The normalizer removes punctuation, preserves alphanumeric characters and does not convert traditional/simplified characters. Errors may exceed 100% when insertions are numerous. Report conditions, language and speaker coverage. Targets: p95 first-token latency ≤4 s and p95 speech-end-to-first-audio ≤8 s. No WER/CER threshold was specified in the plan; report the measurements without inventing a pass criterion.

## Manual release evidence still required

- Avatar ≥30 FPS on the presentation Mac; correct listening/thinking/speaking states.
- TTS and visemes stop together on repeat, interruption, pause, navigation and cancellation.
- Denied microphone, expired Azure token, network loss, WebGL failure and model restart recovery.
- Incorrect language choice, noise, silence, long answers, corrupt/oversized/scanned files and prompt-injection attempts.
- Keyboard-only journey, captions, reduced motion, AA contrast and an avatar-disabled journey.
- Clean-machine rehearsal, a 60–90 second backup recording and final package inspection.

Use actual recordings, browser traces and reviewer notes as evidence. The existence of a test script or a passing synthetic diagnostic is not a substitute for these observations.
