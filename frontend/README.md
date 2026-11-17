# VoxPrep HK interface

## Executive summary

This React interface supports job-description setup, English and Cantonese interviews, editable transcripts, source-linked debriefs, retry, export, history and deletion. It calls the local FastAPI service and validates session, profile and report responses before display. Speech and the interviewer portrait are optional; the same workflow works with typed answers. The default demo provider is labelled as scripted. Inference settings connect the agent, ASR, embedding and reranker to selected OpenAI-compatible servers; saved changes apply to new requests without a restart.

## Development

Run `pnpm install --frozen-lockfile`, then `pnpm dev` with the API on `127.0.0.1:4431`. The development server proxies `/api` and its WebSocket connection. `pnpm build` runs TypeScript and writes `dist/`; the API can serve that directory for the single-origin demonstration.

The root route opens the practice setup. Only the job description and interview options are editable there; the right column summarizes configuration and service readiness. A valid pasted or uploaded job description enables starting without a separate consent or provider-configuration gate. Saved sessions remain available through the plain History page at `/#/history`.

Checks: `pnpm test`, `pnpm lint`, and `pnpm build`. The root `e2e/` suite exercises the integrated browser journey and accessibility checks. Routes use URL hashes so a static server can resume `/interview/:id` and `/report/:id` without special routing.

History can compare two completed sessions side by side. Each column retains its role, language, observable answer data, STAR evidence, competency feedback and limitations; no aggregate quality score is generated. Full-session downloads are available in history and debrief and contain saved questions, transcripts, citations, session metadata and the completed report. Incomplete sessions export with `report: null`. Downloads are generated in the browser without contacting an external service.

The Settings page at `/#/settings` (also available through the previous `/#/methodology` route) reads redacted connection details from `/api/inference-settings`. Model discovery uses the unsaved URL and key through the app server; manual model entry remains available when a server does not list models. Saving updates all four services together. A blank key retains a saved key only while the URL is unchanged; **Clear key** explicitly removes it. Changing the URL never silently reuses the old key. Keys are held only in form memory until saving, stored locally by the app server, and never written to browser storage or returned by the settings API.

## Speech and privacy

- Sessions are stored locally, but selected external inference servers receive prompts, audio or source passages needed for their task. The Settings page discloses this boundary. Local servers may omit an API key. Public services require HTTPS; local and private network servers may use HTTP. Clearing the URL and model selects the scripted demo coach for Agent, native Whisper for ASR, lexical search for Embedding, or no reranking for Reranker.
- The microphone is acquired only after a user action. A five-minute cap bounds recordings, and audio stays in memory until transcription. The complete recording is encoded as mono 16 kHz PCM WAV and sent through `/api/speech/transcribe` when recording finishes. The app server routes it to the configured ASR service or native Whisper.
- **Read question** uses only a browser voice marked `localService`. No automatic playback runs. If a compatible local voice is unavailable, the written question remains available. The portrait stays still during speech.
- Pause, cancellation, leaving the page and finishing stop playback. The microphone stream is released after recording or teardown. Pending transcription is aborted and late results cannot replace a newer draft. Typed drafts are sent when the user selects **Send answer**; recorded audio is sent for transcription when recording finishes.
- Pause counts and silence duration use a simple amplitude threshold; they are descriptive estimates, not judgments of speaking ability. Real multi-speaker speech benchmarks and hardware frame-rate measurements are still required.

## Interviewer portraits and assets

Three fictional, photorealistic interviewer portraits—Alex, Jamie and Sam—are bundled in `public/interviewers/` and served by the app. The **Interviewer appearance** radio choices change only the portrait; they never change the session, questions or interview settings. The known face ID is saved under `voxprep.interviewer` in browser local storage. Invalid stored values fall back to Alex, and unavailable browser storage still permits selection for the current page.

**Hide interviewer portrait** replaces the large photograph with a quiet placeholder. If an image fails to load, text identifies the interviewer and the interview controls remain usable. There is no 3D canvas, simulated mouth movement, animated photograph or external image request.

## Resilience

The live interview normally uses a versioned WebSocket protocol and falls back to HTTP when the socket is unavailable. Submitted answers include their turn ID to prevent accidental replay. Only one answer can be pending, but pause, cancel and end remain available to interrupt slow generation. HTTP responses from an earlier interrupted mutation cannot overwrite newer state. A disconnected in-flight socket reloads the saved session before the next attempt.
