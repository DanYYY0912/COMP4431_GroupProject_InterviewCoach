# Seven-minute presentation and Q&A

## Executive summary

Four presenters, one part each, following the project description: basic features and the knowledge base, the interface and 3D interviewer, voice and the live demo, then the fine-tuned model and its evaluation. `VoxPrep-HK.pptx` has a divider slide per part and timed speaker notes on every slide. The demo uses a prepared three-question role scenario with one spoken Cantonese answer. Keep the backup recording ready and rehearse once on the presentation machine.

## Before rehearsal

The PPTX is editable in PowerPoint or compatible software. `build_deck.mjs` regenerates it but needs the `@oai/artifact-tool` authoring runtime; the application does not depend on it.

1. Run `make test`.
2. Start the app with the adapter loaded (`LORA_PATH` set, see README) and confirm `curl -s localhost:8080/lora-adapters` reports `"scale":1.0`.
3. Run `make demo-reset` to create the fictional role fixture.
4. Check microphone, captions, a local browser voice, and Jamie’s portrait fallback. Open port 4431 and review the four inference connections in Settings.
5. Open the deck and the app in separate windows and silence notifications.

## Timed run

| Time | Part · presenter | Slides | Content |
| --- | --- | --- | --- |
| 0:00–1:15 | 1 · YUEN Yiu Yeung | 1–5 | Problem, basic features against the project requirements, knowledge base and retrieval pipeline |
| 1:15–2:30 | 2 · SO Ngai Chun | 6–8 | Additional features overview, interface and 3D interviewer, their challenges |
| 2:30–3:00 | 3 · SHIH Richard | 9–10 | Speech-to-text and text-to-speech, their challenges |
| 3:00–5:00 | 3 · SHIH Richard | 11 | Live demo: import `data/demo-job.txt`, give the incomplete answer, answer the follow-up by voice in Cantonese, open the debrief and save the PDF |
| 5:00–7:00 | 4 · WONG Kin Chung | 12–16 | Fine-tuning pipeline, 119-prompt evaluation, model challenges, limitations and close |

Slide 17 is a Q&A appendix: each presenter answers questions on their own part. Replace the presenter names if the team splits the parts differently.

## Prepared answers

Incomplete first answer: “I worked on a team project and helped improve our API.”

Follow-up answer: “During our university project, I owned a slow Python API. I measured query latency, found a missing SQL index, added it, and wrote regression tests. I explained the tradeoff to the team. The median response time fell from 500 to 350 milliseconds on our test dataset. I would next test a larger dataset.”

Cantonese alternative: “喺大學小組專題入面，我負責一個回應好慢嘅 Python API。我量度查詢時間，發現欠咗一個 SQL 索引，加入索引之後寫回歸測試，亦同隊友解釋取捨。測試資料嘅回應時間中位數由五百毫秒減到三百五十毫秒。下一步我會用更大嘅資料集測試。”

These are fictional demonstration answers, not claims about a student's actual work.

## Recovery

- If speech fails, say “I will continue with the editable transcript” and type the prepared answer.
- If model generation fails, show the visible fallback status; do not describe fallback output as model output.
- If WebGL fails, Jamie’s portrait stays visible; keep the interview moving.
- If the app cannot continue, play `backup-demo.mp4` and say which configuration it used.

## Likely questions

- **Did you actually fine-tune?** Yes: show `ml/training_evidence/voxprep-qlora-v5/` (manifest, training log, loss curve) and the 119-prompt comparison in `evaluation/results/model.json`.
- **Why fine-tune if schema validity was already 100%?** Prompting alone drifted language on 7.6% of prompts; the adapter fixed all 9 cases with no regressions.
- **Does a citation prove correctness?** No. It identifies the passage the claim relies on, so the user can check it.
- **Why no employability score?** Practice feedback discusses evidence; it does not predict hiring outcomes or infer protected traits.
- **What is the weakest part?** The test split is mostly English reports, Cantonese speech accuracy is unmeasured, and there was no user study.
