# Interviewer portraits

## Executive summary

Three fictional adult portraits replace the procedural 3D avatar. Users choose Alex, Jamie or Sam during an interview; the browser remembers the appearance without changing the interview or voice settings. The images are bundled locally and require no external image service at runtime. These are generated depictions, not photographs of actual interviewers. Question playback remains available, with no simulated lip movement.

## Assets and generation

Generated with the built-in image-generation tool on 2026-11-18. The final Alex and Sam portraits follow the user's request for more glamorous adult female appearances. The initial rejected variants are not included in the application. Source PNGs are copied into the project; original generator outputs remain outside the repository.

### Alex

File: `frontend/public/interviewers/alex.png`.

Final prompt:

> Use case: photorealistic-natural. Create one highly photorealistic portrait of a fictional adult woman, clearly 28 years old, for a selectable virtual interviewer. The user wants a more sexy, glamorous and feminine look: strikingly beautiful face with natural adult proportions, confident slightly alluring eye contact, softly parted lips with a small warm smile, tasteful polished makeup, softly defined brows and subtle rose lip gloss. Long silky dark brown hair with a loose side part, tucked behind one ear, fine small gold earrings. She wears an elegant fitted ivory blazer over a black V-neck silk top with a tasteful modest neckline; attractive styling but fully clothed, no nudity. Head and shoulders down to mid-chest, facing the camera, seated professional portrait. Soft light gray studio background, flattering soft daylight with subtle directional shape, realistic skin texture, natural pores, crisp eyes, warm true-to-life color, no plastic skin or exaggerated anatomy. Portrait 3:4 framing, entire hair/top of head visible with small headroom, shoulders visible, centered. No hands, text, watermark, border, logos, collage. A new fictional adult person, not a celebrity.

### Jamie

File: `frontend/public/interviewers/jamie.png`.

Final prompt:

> Use case: photorealistic-natural. Asset type: a fictional virtual interviewer's portrait displayed in a local interview-practice app. Make ONE highly realistic natural photograph, portrait orientation, head and shoulders to mid-chest, subject centered looking directly at the camera at eye level, whole head and hair fully visible with modest headroom. Plain soft light gray studio background. Soft daylight, realistic pores and facial texture, natural proportions, understated professional expression with a gentle closed-mouth smile, business casual clothing. Believable ordinary professional, not fashion model, no beauty filter. Crisp clear face, subtle depth of field. No text, no watermark, no logos, no borders, no graphic elements, no headphones, no hands visible. This must be a new fictional adult person, not resembling a celebrity. Subject: an East Asian man in his late thirties with neatly styled short dark hair, clean-shaven, wearing a navy blazer over a pale blue open-collar shirt with no tie, calm attentive approachable expression.

### Sam

File: `frontend/public/interviewers/sam.png`.

Final prompt:

> Use case: photorealistic-natural. Create one highly photorealistic portrait of a fictional adult woman, clearly 30 years old, for a selectable virtual interviewer. Glamorous, sexy, confident and feminine, in the style of an elegant contemporary fashion headshot while still appropriate for a professional interview. Beautiful balanced natural adult facial anatomy, warm hazel-brown eyes looking directly into camera, inviting slight smile, full natural lips with muted peach lipstick, tasteful luminous makeup. Shoulder-length chestnut-brown hair in soft loose waves, asymmetric side part, small elegant earrings. Tailored black blazer with an elegant muted burgundy silk V-neck camisole, tasteful modest neckline, fully clothed. Head and shoulders to mid-chest, straight-on eye-level camera, whole hair and head in frame, small headroom, portrait3:4 composition centered. Light gray studio background matching a professional portrait set. Soft natural studio light, realistic detailed skin and fine hair, flattering without smoothing skin into plastic, no exaggerated anatomy. No nudity, hands, text, watermark, border, logos, collage. A new fictional adult person, not a celebrity.

