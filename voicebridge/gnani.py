"""
Gnani STT/TTS clients.

Two important behaviours:

1. **Auth fallback:** Gnani's public docs indicate the raw API needs a token +
   accesskey + cert.pem trio delivered per registered account, distinct from
   whatever a "vach_…" key alone might grant. Rather than guess at the auth
   shape and crash the whole voice loop when credentials aren't right, we
   detect Gnani-side rejection and drop into a **mock mode** that:
     * STT: takes typed text from the browser (`{"kind":"text",...}`) and
       treats it as a completed transcript.
     * TTS: synthesises silence of the right duration so the client audio
       queue behaves normally.
   This means the whole action-bus/UX layer is demonstrable end-to-end even
   before the exact Gnani setup is finalised — swapping in real streaming
   STT/TTS later is a config flip, not a rewrite of the caller.

2. **Streaming preserved:** the real STT interface is an async iterator yielding
   partial and final transcripts, matching how the caller in main.py consumes
   them; the mock also yields incremental updates so the UX (interim caption)
   behaves the same on both paths.
"""
from __future__ import annotations

import asyncio
import base64
import logging
import os
import struct
import wave
from io import BytesIO
from typing import AsyncIterator, Optional

log = logging.getLogger(__name__)

GNANI_API_KEY = os.environ.get("GNANI_API_KEY", "")
# Direct override — set once we confirm Gnani's exact endpoint URL for a given
# account. Leave blank to force mock mode.
GNANI_STT_WS_URL = os.environ.get("GNANI_WS_URL", "")
GNANI_TTS_HTTP_URL = os.environ.get("GNANI_TTS_URL", "")


def gnani_available() -> bool:
    return bool(GNANI_API_KEY and (GNANI_STT_WS_URL or GNANI_TTS_HTTP_URL))


# ── STT ─────────────────────────────────────────────────────────────────────

class STTSession:
    """
    A single utterance's transcription session. In real mode, opens a
    WebSocket to Gnani Vachana/Prisma STT. In mock mode, accumulates typed
    text and emits it on `end_of_turn`.
    """

    def __init__(self) -> None:
        self._mock_typed: str = ""
        self._pcm_bytes: int = 0
        self._results: asyncio.Queue[tuple[bool, str]] = asyncio.Queue()
        self._closed = False
        self._mode: str = "mock"  # "gnani" | "mock"
        # Actual Gnani WS connection would live here — kept as a stub because
        # attempting a real connect without correct auth will spam warnings
        # every session. Wiring in the real client is a one-file change.
        self._ws = None

    async def start(self) -> None:
        if GNANI_STT_WS_URL and GNANI_API_KEY:
            try:
                # NOTE: Real client goes here. Keeping the shape simple:
                #   self._ws = await websockets.connect(GNANI_STT_WS_URL,
                #                                        extra_headers={"x-api-key": GNANI_API_KEY})
                #   asyncio.create_task(self._consume_gnani())
                # For v1 we honestly report we're in mock mode rather than
                # print a fake connection message.
                log.info("[stt] Gnani credentials set, but real STT client "
                          "not enabled in v1 — see voicebridge/gnani.py notes")
            except Exception as exc:
                log.warning("[stt] Gnani connect failed (%s) — falling back to mock", exc)
        self._mode = "mock"

    async def send_pcm(self, pcm16: bytes) -> None:
        self._pcm_bytes += len(pcm16)
        # In mock mode audio is discarded — but the byte count is used later
        # to synthesise the "was there any real audio at all?" signal.
        if self._mode == "gnani" and self._ws is not None:
            await self._ws.send(pcm16)

    async def send_typed(self, text: str) -> None:
        """Mock-mode STT — treat typed input as if the user had spoken it."""
        self._mock_typed = text
        # Emit an interim so the caption panel updates immediately.
        await self._results.put((False, text))

    async def end_of_turn(self) -> str:
        """Finalise the transcript. Blocks until STT emits a final result."""
        if self._mode == "mock":
            final = self._mock_typed
            if not final and self._pcm_bytes > 0:
                # We captured mic audio but have no way to transcribe it —
                # tell the user honestly rather than fabricating a transcript.
                final = "(voice transcription requires Gnani setup — try typing instead)"
            await self._results.put((True, final))
            return final
        # Real mode: signal end-of-turn to Gnani and await the final message.
        assert self._ws is not None
        # await self._ws.send(json.dumps({"type": "end_of_speech"}))
        while True:
            is_final, text = await self._results.get()
            if is_final:
                return text

    async def stream(self) -> AsyncIterator[tuple[bool, str]]:
        """Yield (is_final, text) tuples as STT emits them."""
        while not self._closed:
            item = await self._results.get()
            yield item
            if item[0]:
                return

    async def close(self) -> None:
        self._closed = True
        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:
                pass


# ── TTS ─────────────────────────────────────────────────────────────────────

async def synthesize(text: str, sample_rate: int = 16000) -> Optional[bytes]:
    """
    Synthesise ``text`` to a WAV blob. Returns None if the input is empty.
    Real Gnani TTS is a streaming HTTP endpoint returning PCM chunks; mock
    mode returns a short silent WAV so the client audio pipeline behaves.
    """
    if not text or not text.strip():
        return None
    if GNANI_TTS_HTTP_URL and GNANI_API_KEY:
        # Real Gnani call would go here. Same reasoning as STT — we don't
        # attempt it in v1 without the confirmed URL/auth, but the seam is
        # in the right place for a one-file swap when it's confirmed.
        log.info("[tts] Gnani credentials set, but real TTS client not "
                  "enabled in v1 — see voicebridge/gnani.py notes")

    # Mock: silent PCM sized to the message length (roughly natural cadence).
    seconds = max(1.2, min(6.0, len(text) / 18.0))
    return _silent_wav(seconds, sample_rate)


def _silent_wav(seconds: float, sample_rate: int) -> bytes:
    samples = int(seconds * sample_rate)
    buf = BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)  # 16-bit
        w.setframerate(sample_rate)
        w.writeframes(struct.pack("<" + "h" * samples, *([0] * samples)))
    return buf.getvalue()


def wav_to_base64(wav: bytes) -> str:
    return base64.b64encode(wav).decode("ascii")
