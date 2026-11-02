import httpx
from fastapi import HTTPException

from .config import Settings


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
    # WAV, WebM, Ogg and MP4/M4A headers; whisper-server requires --convert for browser formats.
    if not (content.startswith((b"RIFF", b"\x1aE\xdf\xa3", b"OggS")) or content[4:8] == b"ftyp"):
        raise HTTPException(415, "Upload a WAV, WebM, Ogg, or M4A audio recording.")
    try:
        async with httpx.AsyncClient(timeout=90) as client:
            response = await client.post(
                f"{settings.whisper_base_url}/inference",
                files={
                    "file": (
                        "recording" + (".wav" if content.startswith(b"RIFF") else ".webm"),
                        content,
                        "application/octet-stream",
                    )
                },
                data={
                    "language": "en" if language == "en-HK" else "yue",
                    "response_format": "json",
                    "temperature": "0.0",
                },
            )
            response.raise_for_status()
            text = response.json().get("text")
            if not isinstance(text, str) or len(text) > 12000:
                raise ValueError("Invalid transcription response")
            return {"text": text.strip(), "provider": "whisper.cpp"}
    except (httpx.HTTPError, ValueError, TypeError) as exc:
        raise HTTPException(
            503,
            "Local transcription is unavailable. Type your answer or check whisper-server and FFmpeg.",
        ) from exc
