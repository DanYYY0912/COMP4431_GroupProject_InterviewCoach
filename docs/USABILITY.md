# Usability study: run protocol and scoring

This is the procedure for the release gate **five to eight usability participants,
≥90% flow completion, mean SUS ≥80** (`docs/RELEASE_CHECKLIST.md`). It is written so
one facilitator and one note-taker can run a participant in **15 minutes**, and so the
reported numbers come only from rows a real participant filled in.

Nothing in this document is a result. `evaluation/results/usability_metrics.json` is
created only after real sessions by `scripts/score_sus.py`, which refuses empty input
and never imputes an answer.

## 1. Before the first participant

- Use the build the team will demo. Record the commit/configuration in the session log;
  do not change model provider or settings between participants.
- Warm the stack up (API, model, frontend) with one throwaway practice session so model
  load time is not counted as a participant's latency.
- Rehearse once with a team member. That rehearsal is **not** a study participant and
  must never be entered in the data sheet.
- Prepare per participant: a fresh incognito window (or clean browser profile),
  a clipboard containing the job description in Appendix A, a stopwatch, the printed
  questionnaire (`docs/usability_sus_form.md`, pages 1–2), and a moderator sheet
  (page 3).
- Assign IDs in arrival order: **P1 … P8**. Never reuse or reassign an ID.
- Book 20-minute slots and aim to finish inside 15. A slow report generation is data
  about the product, not a reason to skip a task.

## 2. Ethics and consent

Read this aloud before anything else and record only the fact that consent was given:

> "We're testing a prototype interview-practice tool for our course project, not
> testing you. The session takes about 15 minutes. Please think aloud as you work.
> I won't help with the interface, because we need to see where it fails. You can stop
> at any time and ask us to delete your data. We store only an anonymous ID like P3 —
> no name or student number — and we don't record your face or voice unless you
> separately agree to audio notes, which we delete after writing anonymised notes.
> Your participation and your answers have no effect on anyone's grade. Do you agree
> to take part?"

Rules:

- **No names in any data file, note, screenshot or quote.** Participant IDs only.
- Recruit people who are not on the project team. Do not use lecturers or anyone who
  can influence assessment.
- Do not record audio or video by default. If a recording is genuinely needed, get
  separate explicit consent, keep it outside the repository, and delete it within 24
  hours of verifying the notes. Delete the file, not just the reference.
- Write moderator notes under `artifacts/usability/` (git-ignored). The anonymous CSV
  may live in `evaluation/raw/`.
- The participant may withdraw at any point: stop, delete their row and notes, and
  retire the ID. Do not replace a withdrawn participant with a hand-picked "better"
  one; recruit the next person instead.
- If a participant pastes a real employer's job description containing personal
  details, do not save it; use the fictional job description in Appendix A.
- Delete the downloaded `voxprep-session-*.json` and the browser session after the
  export is confirmed unless the participant agrees the transcript may be kept. The
  study needs the fact that T6 succeeded, not the transcript content.
- If a small thank-you token is offered, it must not depend on completing tasks or on
  giving positive ratings.
- Debrief afterwards: explain that the interface, not the person, was being tested,
  and answer questions.

## 3. Session script (15 minutes)

| Time | Step | What the moderator does |
| --- | --- | --- |
| 0:00–0:01:30 | Consent and setup | Read the consent script, assign the ID, hand over the questionnaire face-down, start the browser at the dashboard |
| 0:01:30–0:03:00 | T1 | Read the task card. Participant sets up the job description, English, 5 questions, Standard, and starts |
| 0:03:00–0:07:00 | T2 | Participant answers the first three questions in English, thinking aloud |
| 0:07:00–0:09:30 | T3 | Participant changes **Answer language** to 廣東話 (zh-HK) and answers the remaining two questions |
| 0:09:30–0:11:00 | T4 | Participant opens the report (Finish & review, then the debrief) |
| 0:11:00–0:12:00 | T5 | Participant finds the evidence for one STAR element |
| 0:12:00–0:12:30 | T6 | Participant exports the transcript with **Export full session** |
| 0:12:30–0:15:00 | SUS and debrief | Participant fills the ten-item questionnaire alone; moderator does not comment |

Task card text to read verbatim:

> "Using the job description in front of you, set up an interview in English with five
> questions at Standard level and start it. Answer the first three questions in
> English. Then switch the answer language to Cantonese and answer the last two.
> When the interview ends, open your report, find the evidence for one STAR element,
> and export the transcript. Please think aloud while you work."

The participant may ask what a task means; reread the card. The moderator may **not**
say where to click, which label to use, what to type, or whether an action was right.
Neutral prompts only: "What would you do next?", "Take your time.", "Keep talking
through what you're seeing."

If the participant is blocked for 3 minutes on one task, stop that task, mark the flow
incomplete, and move on. Record the blocker; do not demonstrate the fix. If the clock
reaches 15 minutes before the export, stop the session, mark the flow incomplete and
record the last task reached; do not rush the participant through the remaining tasks.

## 4. What counts as a completed flow

A flow is **completed** only when all six tasks were done **unaided**:

| # | Task | Success criterion (observed) |
| --- | --- | --- |
| T1 | Set up a job description | A job profile is created/accepted, English and 5 questions selected, interview starts |
| T2 | Answer three questions in English | Three answers submitted; questions and feedback are in English |
| T3 | Switch to zh-HK and answer two | Answer language changed to 廣東話; two further answers submitted |
| T4 | Open the report | The debrief/report for this session is displayed |
| T5 | Find STAR evidence | "Your STAR evidence" is opened and the participant reads or points to the evidence line for one element (or correctly states that no evidence was found for it) |
| T6 | Export the transcript | A `voxprep-session-*.json` download appears from **Export full session** |

- If the moderator points, names a control, or takes the mouse/keyboard, that task is
  **not** completed unaided.
- A participant who gives up or is stopped at 3 minutes has an incomplete flow even if
  the page later works.
- Record the first failed task on the moderator sheet.
- Flow completion rate = completed flows ÷ participants who started T1. Report the
  numerator and denominator, e.g. 5/6, not just a percentage.
- Do not drop a participant because their flow failed or their SUS is low. Failures are
  the useful part of the study.

## 5. Timing

- Start the clock when the participant begins **T1** (after consent and questionnaire
  hand-over). Do not start it during the consent conversation.
- Stop when the exported file appears (**T6**), or at the 3-minute stop rule.
- Record **minutes to one decimal** in `duration_minutes`. Include think-aloud pauses
  and model latency; exclude consent, the SUS questionnaire and the debrief.
- Also note in the session log any single turn or report generation over 60 seconds.
  `duration_minutes` stays the participant's measured total; never adjust it to remove
  latency.
- Target flow time is ≤11 minutes so the whole session stays inside 15. If a session
  runs long, record the real duration.

## 6. SUS administration

- Give the questionnaire **immediately after T6 and before any discussion of the
  session**, so the rating reflects the experience rather than the conversation.
- The participant answers alone, on paper or on their own device. Do not read items
  aloud unless asked, and then only reread the printed wording; do not explain what an
  item "means".
- All ten items are required. There is no N/A option. If an item is skipped, ask the
  participant to choose the closest number; if they decline, the row is incomplete and
  must not be scored.
- Do not discuss the participant's ratings until the form is handed back.
- Do not compute by hand. Use `scripts/score_sus.py`; its odd/even direction handling
  is covered by `evaluation/tests/test_sus_scoring.py`.

## 7. Data capture

Create one CSV per study round, for example `evaluation/raw/usability_20261116.csv`:

```csv
participant_id,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,flow_completed,duration_minutes
```

- `q1` … `q10` are the numbers the participant circled, in questionnaire order
  (1 = strongly disagree, 5 = strongly agree). **Do not reverse items when entering
  them**; the scorer applies the direction.
- `flow_completed` is `true`/`false` from the task log, not from whether the app
  eventually worked.
- `duration_minutes` is the T1→T6 time in minutes, one decimal.
- JSONL is also accepted, with `sus_answers` instead of `q1`…`q10`.
- One row per participant, distinct IDs, no extra participants. An incomplete row is
  fixed with the participant's real answer or removed — never filled in later.

Score and write the metrics file:

```sh
.venv/bin/python scripts/score_sus.py evaluation/raw/usability_20261116.csv \
  --out evaluation/results/usability_metrics.json
```

The command prints a markdown table and summary, and writes the JSON only when at
least one valid row exists. It exits with status 2 and writes nothing for an empty
sheet. If any answer is missing, non-integer, outside 1–5, or an ID is duplicated, it
names the row and refuses the whole run rather than scoring a partial sheet.

## 8. Reporting rules

The scorer reports per-participant SUS, mean, median, sample standard deviation,
minimum/maximum, flow completion count and percentage, mean duration, and a
`release_gates` block for:

| Gate | Threshold |
| --- | --- |
| Participants | 5 to 8 |
| Flow completion | ≥90% |
| Mean SUS | ≥80 (0–100 scale) |

- SUS is a 0–100 **score**, not a percentage. Do not write "82% SUS".
- Report the real denominator and n. With fewer than five participants the result is a
  pilot: state that the release gate is not met, regardless of the mean.
- Report failures and negative comments alongside the score. Do not average away a
  participant or exclude an outlier.
- If the gate is missed, say so in the presentation and progress notes. The script's
  `all_met` field is the only automated verdict, and it is not a substitute for the
  written caveat about sample size and configuration.
- A round with a changed build is a new round with its own date and file; do not merge
  rows from different configurations into one mean.

## 9. Verification

```sh
.venv/bin/python -m pytest evaluation/tests -q
.venv/bin/python -m ruff check scripts/score_sus.py evaluation/tests/test_sus_scoring.py
```

Known checks: all-neutral answers (ten 3s) score 50; straight positive answers score
100; straight negative answers score 0; empty input is refused; out-of-range and
missing answers are rejected.

## 10. Sign-off (fill only after real sessions)

| Field | Value |
| --- | --- |
| Study date | |
| Build / commit | |
| Participants (IDs) | |
| Completed flows | ____ / ____ (____%) |
| Mean SUS (SD) | ____ (____) |
| Median SUS | |
| Mean duration | ____ min |
| Gate met? | ☐ Yes ☐ No — reason: |
| Moderator / note-taker | |

## Appendix A — Fictional job description for T1

> **Junior Backend Engineer — Harbourline Logistics (fictional)**
>
> We build route-planning services in Python and PostgreSQL for a small Hong Kong
> delivery team. You will ship REST APIs, write tests, and work with operations on
> reliability. We look for one production or coursework project you can explain
> end-to-end, clear debugging habits, and comfort with SQL. Hybrid, Hong Kong.
> Salary range HKD 22,000–28,000 per month.

This text is fictional and contains no real person's data. Put it on the clipboard
before the session and keep a printed copy on the desk.
