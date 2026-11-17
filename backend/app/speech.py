import httpx
from fastapi import HTTPException

from .config import Settings
from .providers import bearer_headers


async def speech_token(settings: Settings) -> dict:
    if not settings.azure_speech_key or not settings.azure_speech_region:
        raise HTTPException(
            503, "Azure Speech is not configured. Use local transcription or typed answers."
        )
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                f"https://{settings.azure_speech_region}.api.cognitive.microsoft.com/sts/v1.0/issueToken",
                headers={
                    "Ocp-Apim-Subscription-Key": settings.azure_speech_key,
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                content=b"",
            )
            response.raise_for_status()
            token = response.text.strip()
            if not token or len(token) > 16000:
                raise ValueError("Invalid token response")
        return {"token": token, "region": settings.azure_speech_region, "expires_in": 540}
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(
            503, "Azure Speech is unavailable. Continue with local transcription or typed answers."
        ) from exc


async def transcribe(content: bytes, filename: str, language: str, settings: Settings) -> dict:
    if language not in {"en-HK", "zh-HK"}:
        raise HTTPException(422, "Choose en-HK or zh-HK.")
    if not content or len(content) > 10 * 1024 * 1024:
        raise HTTPException(413, "Recordings must be non-empty and no larger than 10 MB.")
    # Determine MIME and extension from the recording bytes, not an untrusted upload name.
    if content.startswith(b"RIFF"):
        extension, mime = ".wav", "audio/wav"
    elif content.startswith(b"\x1aE\xdf\xa3"):
        extension, mime = ".webm", "audio/webm"
    elif content.startswith(b"OggS"):
        extension, mime = ".ogg", "audio/ogg"
    elif content[4:8] == b"ftyp":
        extension, mime = ".m4a", "audio/mp4"
    else:
        raise HTTPException(415, "Upload a WAV, WebM, Ogg, or M4A audio recording.")
    compatible = bool(settings.asr_base_url)
    data = {
        "language": "en" if language == "en-HK" else ("zh" if compatible else "yue"),
        "response_format": "json",
        "temperature": "0.0",
    }
    if compatible:
        data["model"] = settings.asr_model
    try:
        async with httpx.AsyncClient(timeout=90, follow_redirects=False) as client:
            response = await client.post(
                f"{settings.asr_base_url}/audio/transcriptions"
                if compatible
                else f"{settings.whisper_base_url}/inference",
                headers=bearer_headers(settings.asr_api_key) if compatible else {},
                files={"file": ("recording" + extension, content, mime)},
                data=data,
            )
            response.raise_for_status()
            text = response.json().get("text")
            if not isinstance(text, str) or len(text) > 12000:
                raise ValueError("Invalid transcription response")
            return {
                "text": text.strip(),
                "provider": "openai-compatible" if compatible else "whisper.cpp",
            }
    except (httpx.HTTPError, ValueError, TypeError, AttributeError) as exc:
        raise HTTPException(
            503,
            "Transcription is unavailable. Type your answer or check the configured ASR service.",
        ) from exc
