# Assessed release gates

## Executive summary

The runnable application and automated checks are development evidence. The complete supplied plan additionally requires genuinely trained weights, human-reviewed data, measured service performance, participant studies and a presentation rehearsal. This checklist prevents a working demo from being described as a completed assessed system. Mark a gate complete only with linked evidence from the final configuration.

## Application

- [x] English and Cantonese setup, interview, report, retry, resume, report export and deletion pass in isolated browser contexts (development configuration; see `VERIFICATION.md`).
- [ ] Actual Azure speech, editable captions, visemes and interruption verified on the presentation Mac.
- [ ] Local Whisper, typed input, WebGL fallback, model timeout and DB restart verified.
- [ ] Real hybrid retrieval and reranking measured with the intended models.
- [ ] No unsupported competency claims or injected document instructions accepted in evaluation cases.

## Training and evidence

- [ ] 971 reviewed examples (1,000 generated, 29 rejected) with provenance, reviewer records and stratified second reviews.
- [ ] Leakage-safe 80/10/10 splits and hashes retained.
- [ ] GPU QLoRA training completed, best adapter and raw logs retained.
- [ ] Loss curves, model manifest, merged Q4_K_M and reproducible conversion retained.
- [ ] 119 held-out cases (the whole reviewed test split) across base+RAG, LoRA-only and LoRA+RAG.
- [ ] Automated schema validity >=98% and citation ids present in the quoted sources; requested-language detection reported as an automated proxy, never as human language review. Blinded preference >=65% on 30 pairs with two reviewers.
- [ ] Automated retrieval diagnostic on the synthetic corpus recorded as `diagnostic` (no human labels); recall@5 from unauthored expectations is a pipeline check, not a release threshold.
- [ ] Demo-machine latency: p50/p95 first token and speech-end-to-first-audio recorded with hardware and model hash.
- [ ] p95 first-token <=4s, speech-end-to-first-audio <=8s, avatar >=30 FPS.
- [ ] Five usability participants, >=90% flow completion, SUS >=80.

## Submission

- [ ] Four names/IDs and actual contribution matrix completed.
- [x] Slides state actual implemented features, limitations and measured results (`presentation/validation.json`; final classroom rehearsal remains below).
- [ ] Seven-minute live rehearsal and Q&A preparation completed.
- [ ] 60–90 second backup recording from final configuration retained.
- [x] Development source ZIP checksum and every manifest entry verified; credentials, session databases, private transcripts and base weights excluded. Rebuild after completing the remaining release gates.
- [ ] Small trained adapter included separately with manifest/checksum if excluded from source packaging.
- [ ] Clean-machine setup and final classroom Mac rehearsal passed.
