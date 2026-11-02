# VoxPrep HK API contract v1

## Executive summary

The frontend and backend share the following local-only JSON contract. Sessions contain persisted turns and source citations. The default development provider is explicitly labelled `demo`; real llama.cpp inference is selected through configuration. No fine-tuning or measured quality is implied by the demonstration provider.

All JSON is snake_case. IDs are strings. Language is `en-HK` or `zh-HK`. Difficulty is `foundation`, `standard`, or `stretch`. Timestamps are ISO 8601. Errors use FastAPI `{detail: string | object[]}`.

## Objects

```typescript
type Citation = {chunk_id: string; source: string; text: string};
type CoachTurn = {interviewer_text: string; question_type: 'opening'|'behavioral'|'technical'|'follow_up'|'closing'; targeted_competencies: string[]; adaptive_follow_up_reason: string|null; citations: Citation[]};
type AnswerSubmission = {transcript: string; language: 'en-HK'|'zh-HK'; elapsed_seconds: number; corrected: boolean; speech_metrics?: {pause_count?: number; silence_seconds?: number}};
type Turn = {id: string; question: CoachTurn; answer: AnswerSubmission|null; created_at: string};
type Profile = {id: string; title: string; competencies: string[]; warnings: string[]; sources: Citation[]};
type Session = {id: string; job_profile_id: string; role_title: string; language: 'en-HK'|'zh-HK'; difficulty: string; question_count: number; state: string; current_question: number; turns: Turn[]; created_at: string; provider: string};
type Report = {session_id: string; role_title: string; language: string; summary: string; star: {element: 'Situation'|'Task'|'Action'|'Result'; present: boolean; evidence: string; coaching: string}[]; competencies: {name: string; evidence: string; feedback: string; citations: Citation[]}[]; strengths: string[]; prioritized_improvement: string; retry_exercise: string; speech_metrics: {word_count: number; duration_seconds: number; words_per_minute: number|null; filler_count: number; pause_count: number|null; silence_seconds: number|null; answer_count: number}; citations: Citation[]; limitations: string[]};
```

## Routes

- POST `/api/job-profiles` JSON `{text: string, title?: string}` or multipart `file` (TXT/PDF/DOCX <= 5 MB) returns Profile, 201.
- POST `/api/sessions` JSON `{job_profile_id, language, difficulty, question_count: 3|5|8, store_transcript: true}` returns Session, 201. The first question is already present.
- GET `/api/sessions` returns Session[]. GET `/api/sessions/{id}` returns Session.
- POST `/api/sessions/{id}/answer` AnswerSubmission returns Session (HTTP fallback).
- POST `/api/sessions/{id}/control` `{action: 'pause'|'resume'|'skip'|'retry'|'end'|'cancel'}` returns Session.
- GET `/api/sessions/{id}/report` returns Report. DELETE `/api/sessions/{id}` returns 204.
- GET `/api/health` returns `{status, database, llm, speech, retrieval, provider}`. Components are status strings.
- GET `/api/methodology/metrics` returns `{status: string, provider: string, training: object, evaluations: object[], limitations: string[]}`.
- POST `/api/speech/token` `{consent: true}` returns `{token, region, expires_in: 540}` or 503 if not configured.
- POST `/api/speech/transcribe` multipart `file`, `language` returns `{text, provider}` or 503.

## WebSocket

`/api/sessions/{id}/live`: client `{version:1,type:'answer',payload:AnswerSubmission}` or `{version:1,type:'control',payload:{action}}`.
Server `{version:1,type:'session',payload:Session}`, `{version:1,type:'state',payload:{state}}`, `{version:1,type:'text_delta',payload:{text}}`, or `{version:1,type:'error',payload:{message,recoverable:true}}`.
Only schema-validated model output may produce a final turn. HTTP and socket mutations must use the same state machine.
