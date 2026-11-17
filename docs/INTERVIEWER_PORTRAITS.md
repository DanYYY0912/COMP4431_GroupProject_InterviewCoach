# Jamie’s 3D interviewer

## Executive summary

Jamie is the only included appearance, as requested by the user. Setup previews Jamie before starting and saves the choice with the session. The locally bundled fictional portrait is mapped onto an animated 3D facial surface, with subtle head motion, blinking and approximate speech-driven mouth movement. The camera remains frontal: this is a shallow reconstruction from one image, not a scanned or complete rotatable head. Static portrait fallback keeps interviews usable without WebGL.

## Runtime behavior

The frontend lazily loads Three.js, `jamie.png` and `jamie.mesh.json`. No webcam, runtime face detection or external image service is used. Local browser speech reads each new question once by default, with an opt-out checkbox and manual replay. Actual speech start/end and boundary events drive mouth motion. Boundaries are browser-dependent, so mouth movement is an approximate speaking animation, not phoneme-accurate lip sync. Missing or blocked local voices leave the written question available and do not pretend speech is playing.

Pause and reduced-motion preferences stop animation. Hide releases the renderer; showing it creates a new scene. Mesh/image failure and context loss fall back to the image. Sessions created before this feature default to Jamie through migration `0003`.

## Mesh provenance

The offline generator uses [Google’s Face Landmarker](https://developers.google.com/edge/mediapipe/solutions/vision/face_landmarker) and the [canonical MediaPipe face topology](https://github.com/google-ai-edge/mediapipe/blob/a908d668c730da128dfa8d9f6bd25d519d006692/mediapipe/modules/face_geometry/data/canonical_face_model.obj). The generated mesh contains 468 detected facial landmarks and 64 portrait-border vertices, with 980 triangles. Removing the 18 inner-mouth cap triangles creates an aperture; a separate dark interior is rendered behind the moving lips. Earcut joins the outer portrait frame to the face oval. Small projected folds in the facial topology are retained and rendered double-sided.

The asset records source PNG, generator, model and topology hashes, preprocessing package versions, image dimensions and geometry validation results. Tests verify boundary continuity, coverage, valid indices, finite coordinates, source integrity and the mouth aperture. The source PNG is unchanged. MediaPipe topology attribution and Apache-2.0 license are bundled beside the assets; the preprocessing model is excluded from Docker and the source archive.

Regenerate only when changing the portrait or generator:

```sh
python3.12 -m venv artifacts/avatar-tools
artifacts/avatar-tools/bin/pip install -r scripts/requirements-avatar.txt
artifacts/avatar-tools/bin/python scripts/build_interviewer_faces.py --download-model
```

The initial model download is verified against its pinned SHA-256. Omit `--download-model` on subsequent offline runs. The optional environment is separate from the application. Its MediaPipe 0.10.21 universal2 wheel contains working arm64 code but incorrectly declares an x86_64 internal wheel tag; `pip check` reports that upstream packaging mismatch on Apple Silicon. Actual arm64 extraction was verified. The shipped app does not depend on that Python environment.

## Portrait generation

`frontend/public/interviewers/jamie.png` is a fictional adult image generated with the built-in image tool on 2026-11-18, not a photograph of an actual interviewer. Alex and Sam were removed at the user’s request and are not selectable or packaged. The portrait’s source SHA-256 is `216109c1e4a6059f279fb44930302fca03337188332e9983638858e1590deb91`.

Original generation prompt:

> Use case: photorealistic-natural. Asset type: a fictional virtual interviewer's portrait displayed in a local interview-practice app. Make ONE highly realistic natural photograph, portrait orientation, head and shoulders to mid-chest, subject centered looking directly at the camera at eye level, whole head and hair fully visible with modest headroom. Plain soft light gray studio background. Soft daylight, realistic pores and facial texture, natural proportions, understated professional expression with a gentle closed-mouth smile, business casual clothing. Believable ordinary professional, not fashion model, no beauty filter. Crisp clear face, subtle depth of field. No text, no watermark, no logos, no borders, no graphic elements, no headphones, no hands visible. This must be a new fictional adult person, not resembling a celebrity. Subject: an East Asian man in his late thirties with neatly styled short dark hair, clean-shaven, wearing a navy blazer over a pale blue open-collar shirt with no tie, calm attentive approachable expression.
