# Speech accuracy study

Release checklist item this closes: *24 clean/noisy speech recordings across four
speakers, WER/CER and correction rate reported.*

Nothing here has been measured yet. This file is the protocol plus the scoring
harness; the checklist item stays unticked until
`evaluation/results/speech_metrics.json` is generated from real recordings and
quoted in the report. Synthetic or generated audio never counts, and a passing
unit test is not a result.

## What has to exist

| Requirement | Value |
| --- | --- |
| Clips | 24 |
| Speakers | 4 consenting people, 6 clips each |
| Conditions | 3 clean and 3 noisy per speaker (12 / 12 overall) |
| Languages | 3 `en-HK` and 3 `zh-HK` per speaker (12 / 12 overall) |
| Consent | `consent_recorded: true` on every row |
| Reference | written by a human, checked by a second person (`reference_reviewed_by`) |
| Hypotheses | produced by the recognizer the app ships with, one engine per sheet |
| Scored by | `scripts/score_speech.py` |

## Consent and personal data

- Record only people who have said yes on the record: team members or
  volunteers you asked directly. Nobody recorded in the background, no
  borrowed footage, no third-party audio.
- Tell each speaker: the clip is used to measure transcription accuracy, it is
  not published, and it is deleted once the sheet is reviewed and scored.
- The sheet carries `speaker_id` only (`participant-1` … `participant-4`).
  Never put names, student numbers, emails, employer or team names in the
  sheet, in `notes`, or in file names. `reference_reviewed_by` holds a reviewer
  label such as `reviewer-A`.
- Keep raw WAV files outside the repository (for example `~/speech-study/`), or
  delete them before committing. The repository stores transcript text, hashes
  and error rates, not voices.

## Recording setup

- One device and one microphone position for all 24 clips. Phone voice memo is
  fine; export or convert to mono WAV:

  ```bash
  ffmpeg -i clip.m4a -ac 1 -ar 16000 clip.wav
  ```

- Mouth 30–50 cm from the microphone, no desk echo, no fan directly behind the
  laptop. Quiet means a room with no TV, conversation or traffic audible to the
  listener.
- Noisy means the same room with steady background at conversational level:
  news radio on a phone speaker, a café, or a window onto traffic. Keep the
  speaker's own volume unchanged, and write what the noise was in `notes`
  (for example `cafe babble, phone speaker 2 m away`).
- One take per clip, 20–40 seconds. If you fluff a word, restart the whole
  clip and note it. Never splice two takes into one file.

## Prompts

Answer the prompt as you would in the real interview. Do not read a script: a
read script gives better-than-real accuracy, and the study is about the app's
real use. Three prompts per language, mapped to the clip index in the sheet
(`s2-zh-HK-3` is `zh-3` for speaker 2).

| Index | Language | Prompt |
| --- | --- | --- |
| 1 | en-HK | Tell me about a project you built and the hardest bug you fixed. |
| 2 | en-HK | Describe a time you disagreed with a teammate and how you resolved it. |
| 3 | en-HK | Why do you want this role, and what would you learn in the first three months? |
| 1 | zh-HK | 介紹一個你負責過嘅專案，同埋最難解決嘅問題。 |
| 2 | zh-HK | 講一次你同組員意見唔同，你最後點處理。 |
| 3 | zh-HK | 點解你想做呢份工？頭三個月你想學到啲咩？ |

The generated sheet alternates condition per prompt index, and even-numbered
speakers get the inverse assignment, so every prompt is recorded both clean and
noisy across the four speakers. Do not "fix" that ordering: it stops the prompt
set from coinciding with one condition.

## Workflow

1. Generate the blank sheet (24 rows, reviewed field names):

   ```bash
   .venv/bin/python scripts/score_speech.py --template --output ~/speech-study/sheet.jsonl
   ```

2. Record, convert to WAV, and note the SHA-256 so a later edit is detectable:

   ```bash
   shasum -a 256 ~/speech-study/clip.wav
   ```

3. Fill `recording_path`, `recording_sha256`, `consent_recorded`,
   `reference`, `reference_reviewed_by` and `notes`. Write the reference **by
   listening**, before you transcribe with the app or read any hypothesis. The
   reference is what the speaker actually said, including false starts that you
   both agree are part of the utterance.

4. Optional: let the app's own speech path fill the hypotheses. Start the local
   services with `.venv/bin/python scripts/dev.py`, which launches
   `whisper-server` on port 8081 with `--convert`, then:

   ```bash
   .venv/bin/python scripts/score_speech.py --score ~/speech-study/sheet.jsonl \
       --audio --whisper-url http://127.0.0.1:8081 \
       --sheet-out ~/speech-study/sheet_scored.jsonl \
       --output ~/speech-study/speech_metrics.json
   ```

   Without `--whisper-url` or `WHISPER_BASE_URL`, `--audio` stops with an error
   rather than writing guessed text. If you use Azure Speech instead, transcribe
   through the browser and paste the caption into `hypothesis`; keep Azure rows
   and Whisper rows in separate sheets and report the engine with the numbers.

5. Score the finished sheet:

   ```bash
   .venv/bin/python scripts/score_speech.py --score ~/speech-study/sheet_scored.jsonl \
       --output evaluation/results/speech_metrics.json
   ```

   Add `--strict` to refuse to score anything other than a complete
   24-clip, 4-speaker, 12/12 split with consent and reviewed references.

6. Review each clip against the caption the app displayed. `corrected` is a
   human judgement: `true` if a person had to edit the caption before accepting
   it, `false` if it was accepted unchanged. `failure` records a recognizer
   error (`timeout`, `empty_response`, `unsupported_format`); the clip stays in
   the study and is scored as deletions.

## Sheet fields

| Field | Meaning |
| --- | --- |
| `id` | clip id from the template, `s{speaker}-{language}-{index}` |
| `speaker_id` | `participant-1` … `participant-4`; no names |
| `condition` | `clean` or `noisy` |
| `language` | `en-HK` or `zh-HK` |
| `recording_path` | WAV path (alias accepted on input: `wav_path`) |
| `recording_sha256` | SHA-256 of the WAV; `--audio` verifies it before transcribing |
| `reference` | human transcript of what was said (alias: `reference_text`) |
| `reference_reviewed_by` | reviewer label for the reference |
| `consent_recorded` | `true` only after the speaker agreed |
| `hypothesis` | recognizer output, or empty for a failed run (alias: `hypothesis_text`) |
| `corrected` | `true` if a human had to edit the caption |
| `failure` | recognizer error label, or `null` |
| `notes` | noise description, prompt remark, anything a reader needs |
| `speech_end_to_audio_seconds` | measured latency for this clip, or `null` |

## How to read the output

Output shape (the numbers below are illustrative, not measurements):

```
Overall | 24 | 12.4% (31/250) | 8.1% (20/247) | 16.7% | 83.3%
```

- `WER en-HK` counts English word tokens, `CER zh-HK` counts Chinese characters.
  The bracket is `edits / reference units`, so the number can be checked by hand.
- Group rows are corpus-level: total edits divided by total reference units, not
  an average of per-clip rates, because clips differ in length. Insertions can
  push a rate above 100%.
- `Correction rate` is the share of scored clips a human had to edit:
  `(corrected or failure) / clips`. A failed recognition counts as needing
  correction, because the user still had to write the text themselves.
  `Accepted without edit` is its complement.
- `by_speaker` and `by_condition` show whether one voice or the noisy room
  dominates the average. A single speaker with a much worse rate is a finding,
  not a row to delete.
- `coverage.gaps` lists what is missing. While `status` is
  `incomplete_coverage`, the release checklist item is not met; do not quote the
  partial numbers as the study result.
- There is no WER/CER threshold in the project plan. Report the measurement, the
  engine and the sample size: for example "Whisper large-v3-turbo, WER 12.4%
  (31/250 word tokens), CER 8.1% (20/247 characters), 24 clips, 4 speakers,
  3 clean and 3 noisy each". Do not convert 24 clips into a headline accuracy
  claim.

## What invalidates the study

- Editing a reference after seeing the hypothesis (it becomes a transcript of
  the recognizer, not of the speaker).
- Dropping failed clips, quiet clips, or the worst speaker from the sheet.
- Recording a fresh "clean" take after a noisy take failed and keeping only the
  good one.
- Mixing recognizers, model sizes or prompt settings inside one sheet without
  saying so.
- Fewer than four real speakers, or one person performing four voices.
- Using hand-written test strings or synthesized audio. The unit fixtures in
  `evaluation/tests/test_speech_scoring.py` exist to test the arithmetic and are
  labelled as such in the test file; they are not evidence.

## Algorithm notes

WER and CER are the usual `(S + D + I) / N` over Levenshtein edit distance,
computed with `evaluation.metrics.edit_distance` so the harness and
`evaluation/run.py` cannot drift. English tokens are case-folded word tokens
with internal apostrophes kept, Chinese tokens are single alphanumeric
characters: punctuation and spacing are removed and no traditional/simplified
conversion is applied. An empty reference raises instead of scoring 0%, so a
silence clip cannot silently improve the average.
