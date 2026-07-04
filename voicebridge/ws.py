"""
WebSocket handler for the voice bridge. Mounted on the API gateway at
``/ws/voice``. One connection per browser session.

Per-turn flow:
  browser mic PCM / typed text → STTSession → transcript
  transcript → intent.classify() → maybe (action, ack, is_data_query)
                                   plus (optionally) copilot_query() answer
  ack + speakable answer → TTS → PCM bytes → base64 WAV → browser
  action → JSON `{kind:"action", action:...}` → browser action bus

Order matters for perceived latency: the ack is sent FIRST (so the user hears
"Here's Strait of Hormuz" instantly), then the action, then any longer
data-query answer.
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from voicebridge import gnani, speakable
from voicebridge.intent import classify

log = logging.getLogger(__name__)


async def _send(ws: WebSocket, payload: dict[str, Any]) -> None:
    try:
        await ws.send_text(json.dumps(payload))
    except Exception as exc:
        log.debug("[voice] send failed (probably client gone): %s", exc)


async def _speak(ws: WebSocket, text: str, sample_rate: int) -> None:
    if not text:
        return
    await _send(ws, {"kind": "reply", "text": text})
    await _send(ws, {"kind": "state", "state": "speaking"})
    wav = await gnani.synthesize(text, sample_rate=sample_rate)
    if wav is None:
        await _send(ws, {"kind": "state", "state": "idle"})
        return
    await _send(ws, {
        "kind": "audio",
        "format": "wav",
        "base64": gnani.wav_to_base64(wav),
    })
    # The client transitions back to "idle" when the <audio> tag's onended
    # fires; we don't need to push another state here.


async def _handle_transcript(ws: WebSocket, transcript: str, sample_rate: int) -> None:
    """Central per-turn logic — same code path for typed and spoken input."""
    if not transcript.strip():
        await _send(ws, {"kind": "state", "state": "idle"})
        return
    await _send(ws, {"kind": "state", "state": "thinking"})

    action, ack, is_data_query = classify(transcript)

    # 1) Dispatch the action to the UI FIRST — the visual response happens
    #    while the TTS is still synthesising, exactly the "diagrams pop up
    #    while SAGE is still talking" effect the design targets.
    if action is not None:
        await _send(ws, {"kind": "action", "action": action})

    # 2) Speak the short ack (if any) BEFORE the longer data answer. Short
    #    replies feel instant even when Gnani is slow to first-byte.
    if ack:
        await _speak(ws, ack, sample_rate)

    # 3) Fire copilot_query for data intents (open_wiki + open-ended).
    if is_data_query:
        try:
            from knowledge.api.read import copilot_query
            ans = await copilot_query(transcript)
            sources_by_idx = {s.index: s.entity for s in (ans.sources or [])}
            speech = speakable.to_speech(ans.answer, sources_by_idx)
            await _speak(ws, speech, sample_rate)
        except Exception as exc:
            log.warning("[voice] copilot_query failed: %s", exc)
            await _speak(ws, "I couldn't retrieve that just now.", sample_rate)

    # If neither ack nor data answer fired, the ack-less action already ran —
    # return the orb to idle so the user knows the turn is over.
    if not ack and not is_data_query:
        await _send(ws, {"kind": "state", "state": "idle"})


async def voice_ws_endpoint(ws: WebSocket) -> None:
    await ws.accept()
    sample_rate = 16000
    stt = gnani.STTSession()
    await stt.start()
    await _send(ws, {"kind": "state", "state": "idle"})

    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await _send(ws, {"kind": "error", "message": "invalid JSON"})
                continue

            kind = msg.get("kind")

            if kind == "hello":
                sample_rate = int(msg.get("sampleRate") or 16000)
                # Fresh STT session per connection is fine; nothing else to do.
                continue

            if kind == "audio":
                try:
                    pcm = base64.b64decode(msg["base64"])
                except Exception:
                    await _send(ws, {"kind": "error", "message": "bad audio chunk"})
                    continue
                await stt.send_pcm(pcm)
                continue

            if kind == "text":
                # The keyboard/mock path — mirrors the spoken flow so the UI
                # behaves identically. Send an interim so the caption panel
                # shows the input while we process.
                text = str(msg.get("text") or "")
                await _send(ws, {"kind": "transcript", "final": True, "text": text})
                await _handle_transcript(ws, text, sample_rate)
                continue

            if kind == "end_of_turn":
                # Close out the current utterance; finalise transcript.
                final = await stt.end_of_turn()
                await _send(ws, {"kind": "transcript", "final": True, "text": final})
                await _handle_transcript(ws, final, sample_rate)
                # Fresh session for the next turn.
                await stt.close()
                stt = gnani.STTSession()
                await stt.start()
                continue

            if kind == "stop":
                # Client-driven barge-in. Server-side we just acknowledge.
                await _send(ws, {"kind": "state", "state": "idle"})
                continue

            await _send(ws, {"kind": "error", "message": f"unknown kind: {kind}"})
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        log.warning("[voice] ws error: %s", exc)
        try:
            await _send(ws, {"kind": "error", "message": str(exc)})
        except Exception:
            pass
    finally:
        try:
            await stt.close()
        except Exception:
            pass
        # Best effort — client may have already gone.
        try:
            await ws.close()
        except Exception:
            pass
