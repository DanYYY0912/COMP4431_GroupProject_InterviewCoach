# VoxPrep HK interface

## Executive summary

This React interface supports job-description setup, English and Cantonese interviews, editable transcripts, source-linked debriefs, retry, export, history and deletion. It calls the local FastAPI service and validates session, profile and report responses before display. Speech and the original 3D interviewer are optional; the same workflow works with typed answers. Azure speech requires explicit consent and a short-lived server-issued token. The default demo provider is labelled as scripted, and the methodology page displays recorded evidence without inventing training or evaluation results.

## Development

Run `pnpm install --frozen-lockfile`, then `pnpm dev` with the API on `127.0.0.1:8000`. The development server proxies `/api` and its WebSocket connection. `pnpm build` runs TypeScript and writes `dist/`; the API can serve that directory for the single-origin demonstration.

Checks: `pnpm test`, `pnpm lint`, and `pnpm build`. The root `e2e/` suite exercises the integrated browser journey and accessibility checks. Routes use URL hashes so a static server can resume `/interview/:id` and `/report/:id` without special routing.

## Speech and privacy

- Azure recognition and synthesis use the official browser Speech SDK. The subscription key never enters the frontend. SDK telemetry is disabled for recognition.
- The microphone is acquired only after a user action. A five-minute cap bounds recordings, and audio stays in memory. If Azure fails, the complete recording is encoded as mono 16 kHz PCM WAV and offered to the local Whisper endpoint.
- An Azure recognition error triggers whole-recording local transcription even if Azure already returned a partial answer. The recording stream and Azure stream have separate track lifetimes.
- Synthesis collects Azure viseme timestamps, then schedules mouth changes against actual playback time. If no visemes arrive, an audio analyser drives mouth opening. Without Azure consent, only a browser voice marked `localService` is used; if none exists, captions remain available. Browser speech uses approximate mouth motion.
- Pause, cancellation, leaving the page and finishing stop playback. The microphone stream is released after recording or teardown. Drafts are not sent until the user selects **Send answer**.
- Pause counts and silence duration use a simple amplitude threshold; they are descriptive estimates, not judgments of speaking ability. Real multi-speaker speech benchmarks and hardware frame-rate measurements are still required.

## Avatar and assets

The interviewer is an original procedural Three.js model authored for this project. It consists of primitive meshes with independent mouth, head and eye motion. The fallback portrait and favicon are original SVGs. No third-party character, stock image, or externally hosted font is included. Reduced-motion preference or the avatar toggle selects the static portrait. A WebGL error boundary preserves the text workflow.

The initial 3D mesh is deliberately simple and does not require a VRM asset. React Three Fiber 9 is paired with React 19 as required by its [compatibility guide](https://r3f.docs.pmnd.rs/getting-started/installation). Azure integration follows the [SpeechRecognizer](https://learn.microsoft.com/en-us/javascript/api/microsoft-cognitiveservices-speech-sdk/speechrecognizer) and [SpeechSynthesizer](https://learn.microsoft.com/en-us/javascript/api/microsoft-cognitiveservices-speech-sdk/speechsynthesizer) APIs.

## Resilience

The live interview normally uses a versioned WebSocket protocol and falls back to HTTP when the socket is unavailable. Submitted answers include their turn ID to prevent accidental replay. Only one answer can be pending, but pause, cancel and end remain available to interrupt slow generation. HTTP responses from an earlier interrupted mutation cannot overwrite newer state. A disconnected in-flight socket reloads the saved session before the next attempt.
