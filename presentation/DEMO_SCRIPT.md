# Seven-minute demonstration and Q&A

## Executive summary

Use one lead presenter and a prepared three-question role scenario to show setup, an incomplete answer, an adaptive follow-up and the evidence-linked debrief. Explain the actual provider and evidence available on the presentation day. The PowerPoint contains speaker notes and an honest pending-evaluation slide. Replace pending evidence only after the corresponding training, measurements and participant reviews exist. Keep a 60–90 second recording of the final configuration as backup, and rehearse on the classroom Mac with the network disabled once.

## Before rehearsal

The PPTX is portable and editable in PowerPoint or compatible slide software. `build_deck.mjs` is an optional source generator that uses the Codex-bundled `@oai/artifact-tool` authoring runtime; rebuilding that script requires that runtime. Running the interview application does not depend on it.

1. Run `make test`, then the real evaluation commands supported by the available evidence.
2. Start `make demo` and open `http://localhost:8000`.
3. Run `make demo-reset` to create the fictional role fixture. This touches only fixture session IDs previously recorded by that command.
4. Check the displayed provider. A base Qwen model and the deterministic demo provider are never described as a trained adapter.
5. Verify microphone, captions, speaker output, interruption and static avatar fallback. Confirm actual cloud consent before Azure use.
6. Open `presentation/VoxPrep-HK.pptx` and the app in separate windows. Silence unrelated notifications.

## Timed run

| Time | Action | Evidence to show |
| --- | --- | --- |
| 0:00–0:30 | Explain role-specific bilingual practice | Slide 1 |
| 0:30–1:00 | Explain app, local model, retrieval and voice | Slide 2 |
| 1:00–1:30 | Import `data/demo-job.txt`, select language and three questions | Setup and provider badge |
| 1:30–2:15 | Answer: “I worked on a team project and helped improve our API.” | Editable transcript and question |
| 2:15–3:00 | Answer the follow-up with specific personal action and result | Adaptive prompt, source citation |
| 3:00–3:40 | Finish the final answer, demonstrate one interruption if time permits | Listening/speaking state and controls |
| 3:40–4:40 | Open debrief and one citation, show retry exercise | Transcript evidence, STAR feedback and metric limitations |
| 4:40–5:35 | Explain review, QLoRA and export evidence | Slide 5 and actual training manifest if available |
| 5:35–6:25 | Present achieved measurements and failures | Slide 6 updated from genuine raw results |
| 6:25–7:00 | Explain privacy, fallbacks and limits | Slide 7 |

## Prepared follow-up answer

“During our university project, I owned a slow Python API. I measured query latency, found a missing SQL index, added it, and wrote regression tests. I explained the tradeoff to the team. The median response time fell from 500 to 350 milliseconds on our test dataset. I would next test a larger dataset.”

This is a fictional demonstration answer. It is not a claim about a student's actual work or measured project performance.

Cantonese alternative: “喺大學小組專題入面，我負責一個回應好慢嘅 Python API。我量度查詢時間，發現欠咗一個 SQL 索引，加入索引之後寫回歸測試，亦同隊友解釋取捨。測試資料嘅回應時間中位數由五百毫秒減到三百五十毫秒。下一步我會用更大嘅資料集測試。”

## Recovery

- If speech fails, say “I will continue with the editable transcript,” then type the prepared answer.
- If model generation fails, show the visible fallback status and explain the failure. Do not describe fallback output as local model output.
- If WebGL fails, use the static interviewer and keep the interview moving.
- If the main app cannot continue, play the final backup recording and explain which configuration it used.
- Keep the results slide honest if training or participant studies are still pending.

## Q&A specialties and contribution log

| Planned owner | Prepare to explain | Actual contribution evidence |
| --- | --- | --- |
| Student 1 | UI states, accessibility, original avatar and mouth animation | Add commits, review and tests after team work |
| Student 2 | Azure tokens, language selection, visemes, Whisper and WER/CER | Add recordings, measurements and failure cases |
| Student 3 | Data provenance, review, split leakage, NF4/LoRA and base comparison | Add review records, GPU logs and adapter hashes |
| Student 4 | Ingestion, retrieval, citations, state recovery and privacy | Add integration tests and retrieval results |

## Likely questions

- **Did you actually fine-tune?** Show the reviewed data hash, GPU log, adapter and base comparison. Until those exist, answer that the workflow is implemented and training is pending.
- **Does a citation prove correctness?** No. It identifies a passage. Citation precision and unsupported-claim evaluation test whether that passage supports the claim.
- **Why no employability score?** Practice feedback can discuss evidence without claiming to predict hiring outcomes or infer protected traits.
- **Why local inference?** It keeps transcripts on the Mac and avoids dependence on a paid LLM API. Azure speech remains an explicitly consented exception.
- **What is the weakest part?** Discuss actual failures, including Cantonese transcription, heuristics, inference latency or retrieval quality as measured.
