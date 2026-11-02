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

- [ ] 1,500 examples with provenance, first review and stratified second reviews.
- [ ] Leakage-safe 80/10/10 splits and hashes retained.
- [ ] GPU QLoRA training completed, best adapter and raw logs retained.
- [ ] Loss curves, model manifest, merged Q4_K_M and reproducible conversion retained.
- [ ] 120 held-out cases across base+RAG, LoRA-only and LoRA+RAG.
- [ ] Schema validity >=98%, language adherence >=95%, blinded preference >=65% on 30 pairs with two reviewers.
- [ ] 40 retrieval cases, recall@5 >=85%, citation precision >=90%.
- [ ] 24 clean/noisy speech recordings across four speakers, WER/CER and correction rate reported.
- [ ] p95 first-token <=4s, speech-end-to-first-audio <=8s, avatar >=30 FPS.
- [ ] Five to eight usability participants, >=90% flow completion, SUS >=80.

## Submission

- [ ] Four names/IDs and actual contribution matrix completed.
- [x] Slides state actual implemented features, limitations and measured results (`presentation/validation.json`; final classroom rehearsal remains below).
- [ ] Seven-minute live rehearsal and Q&A preparation completed.
- [ ] 60–90 second backup recording from final configuration retained.
- [x] Development source ZIP checksum and every manifest entry verified; credentials, session databases, private transcripts and base weights excluded. Rebuild after completing the remaining release gates.
- [ ] Small trained adapter included separately with manifest/checksum if excluded from source packaging.
- [ ] Clean-machine setup and final classroom Mac rehearsal passed.
