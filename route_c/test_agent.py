#!/usr/bin/env python3
"""
SuperNanny ElevenLabs Conversational AI — Audio-Based Test Harness

Flow per turn
─────────────
1. Convert candidate Hindi text → PCM audio via ElevenLabs TTS
2. Stream audio chunks to the agent (simulates candidate speaking)
3. Stream silence so the server's VAD detects end-of-speech
4. START latency timer (candidate has "stopped speaking")
5. Wait for {"type": "agent_response"} from server
6. STOP timer — record latency_ms

Audio pre-generation
────────────────────
All 10 candidate audios are generated once at startup to avoid
TTS delays during the timed call loop.

Failure categories
──────────────────
  connection_failure       – WebSocket could not be established
  timeout                  – no agent_response within TURN_TIMEOUT seconds
  no_response              – connection dropped before agent replied
  unexpected_disconnection – connection closed mid-session
"""

import asyncio
import base64
import json
import os
import time
from datetime import datetime
from pathlib import Path

import requests
import websockets
from dotenv import load_dotenv

load_dotenv()

# ── Configuration ──────────────────────────────────────────────────────────────
AGENT_ID      = "agent_5101kmcq15wbfwzsz8vg95p448hb"
API_KEY       = "sk_5dbe90b49a97eb0582de79bd9ccf458b75c96723faf8f9a4"
WS_URL        = f"wss://api.elevenlabs.io/v1/convai/conversation?agent_id={AGENT_ID}"
TTS_VOICE_ID  = "21m00Tcm4TlvDq8ikWAM"   # Rachel — change to any ElevenLabs voice
TTS_MODEL     = "eleven_turbo_v2_5"        # multilingual, supports Hindi romanisation

DEBUG          = True   # set False to silence raw-message logs
TOTAL_CALLS    = 10
TURN_TIMEOUT   = 20.0   # seconds — give agent plenty of time to respond
SLOW_MS        = 1000   # ms  — flag slow turns in report
BETWEEN_TURNS  = 0.3    # seconds — extra gap after agent finishes (post-drain)
BETWEEN_CALLS  = 5.0    # seconds — gap between calls (avoid DNS throttling)
HANDSHAKE_WAIT = 10.0   # seconds — timeout for conversation_initiation_metadata
GREETING_WAIT  = 10.0   # seconds — timeout for agent's opening statement

SAMPLE_RATE  = 16_000   # Hz  (ElevenLabs ConvAI expects 16 kHz 16-bit PCM)
SAMPLE_WIDTH = 2        # bytes per sample
SILENCE_SECS = 1.5      # seconds of silence appended to trigger server VAD
CHUNK_BYTES  = 4_000    # ~125 ms per chunk at 16 kHz 16-bit
CHUNK_SLEEP  = 0.05     # seconds between chunks

REPORTS_DIR = Path("reports")

# ── Candidate responses (Hindi) ────────────────────────────────────────────────
CANDIDATE_RESPONSES = [
    "Haan ji",
    "Haan, bol sakte hain",
    "Mera naam Sunita hai",
    "Meri umar 28 saal hai",
    "Main Bangalore mein rehti hoon, Marathahalli ke paas",
    "Mujhe 3 saal ka experience hai, chote bachon ke saath",
    "Main subah 8 baje se sham 6 baje tak available hoon",
    "Mujhe 12 se 15 hazaar chahiye",
    "Nahi, main live-in nahi kar sakti",
    "Theek hai, shukriya",
]


# ── TTS & audio helpers ────────────────────────────────────────────────────────

def tts_to_pcm(text: str) -> bytes:
    """Call ElevenLabs TTS and return raw 16 kHz 16-bit PCM bytes."""
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{TTS_VOICE_ID}"
    resp = requests.post(
        url,
        headers={"xi-api-key": API_KEY, "Content-Type": "application/json"},
        json={
            "text": text,
            "model_id": TTS_MODEL,
            "output_format": "pcm_16000",
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.content


def silence_pcm(duration_secs: float) -> bytes:
    """Return silent (all-zero) PCM for the given duration."""
    return bytes(int(SAMPLE_RATE * duration_secs) * SAMPLE_WIDTH)


async def stream_pcm(ws, pcm: bytes) -> None:
    """Send PCM bytes as base64 user_audio_chunk messages."""
    for offset in range(0, len(pcm), CHUNK_BYTES):
        chunk = pcm[offset: offset + CHUNK_BYTES]
        await ws.send(json.dumps({
            "user_audio_chunk": base64.b64encode(chunk).decode()
        }))
        await asyncio.sleep(CHUNK_SLEEP)


# ── WebSocket helpers ──────────────────────────────────────────────────────────

def ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


async def drain_agent_audio(ws, quiet_for: float = 3.0) -> None:
    """
    After agent_response is received, the server keeps streaming audio chunks.
    Drain them until no message arrives for `quiet_for` seconds — that means
    the agent has finished speaking and is ready for the next user turn.
    """
    while True:
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=quiet_for)
            msg = json.loads(raw)
            if msg.get("type") == "ping":
                await ws.send(json.dumps({
                    "type":     "pong",
                    "event_id": msg.get("ping_event", {}).get("event_id"),
                }))
            # audio / user_transcript / interruption → just discard, keep draining
        except asyncio.TimeoutError:
            break   # quiet for quiet_for seconds → agent done speaking
        except websockets.exceptions.ConnectionClosed:
            break


async def recv_agent_response(ws, timeout: float) -> tuple[str | None, str | None]:
    """
    Drain server messages until agent_response arrives or timeout/close.
    Returns (response_text, None) on success, (None, error_str) on failure.
    """
    deadline = time.monotonic() + timeout
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return None, f"Timeout ({timeout}s) — no agent_response received"
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=remaining)
        except asyncio.TimeoutError:
            return None, f"Timeout ({timeout}s) — no agent_response received"
        except websockets.exceptions.ConnectionClosed as exc:
            return None, f"Connection closed: {exc}"

        msg   = json.loads(raw)
        mtype = msg.get("type", "")

        if mtype == "agent_response":
            text = msg.get("agent_response_event", {}).get("agent_response", "")
            return text, None

        if mtype == "ping":
            ping_ms = msg.get("ping_event", {}).get("ping_ms") or 0
            await asyncio.sleep(ping_ms / 1000)
            await ws.send(json.dumps({
                "type":     "pong",
                "event_id": msg.get("ping_event", {}).get("event_id"),
            }))

        if mtype == "conversation_end":
            return None, "Server ended conversation unexpectedly"


# ── Single call ────────────────────────────────────────────────────────────────

async def run_call(call_number: int, audio_clips: list[bytes]) -> dict:
    call_result: dict = {
        "call_number":    call_number,
        "status":         "success",
        "failure_reason": None,
        "turns":          [],
    }

    print(f"\n{'─'*56}")
    print(f"  Call {call_number}/{TOTAL_CALLS}  —  connecting…")

    try:
        headers = {"xi-api-key": API_KEY}

        async with websockets.connect(
            WS_URL,
            additional_headers=headers,
            ping_interval=None,
            open_timeout=10.0,
        ) as ws:

            # ── Handshake ──────────────────────────────────────────────────────
            try:
                raw_init = await asyncio.wait_for(ws.recv(), timeout=HANDSHAKE_WAIT)
            except asyncio.TimeoutError:
                call_result["status"]         = "failed"
                call_result["failure_reason"] = "connection_failure: handshake timeout"
                print(f"  [FAIL] Handshake timeout")
                return call_result

            init_msg = json.loads(raw_init)
            if init_msg.get("type") != "conversation_initiation_metadata":
                call_result["status"]         = "failed"
                call_result["failure_reason"] = (
                    f"connection_failure: unexpected first message "
                    f"type={init_msg.get('type')!r}"
                )
                print(f"  [FAIL] Bad handshake")
                return call_result

            conv_id = (
                init_msg
                .get("conversation_initiation_metadata_event", {})
                .get("conversation_id", "?")
            )

            # Send initiation confirmation (required per ElevenLabs WebSocket spec)
            await ws.send(json.dumps({"type": "conversation_initiation_client_data"}))
            print(f"  Connected  conversation_id={conv_id}")

            # ── Drain agent opening statement ──────────────────────────────────
            print(f"  Waiting for agent opening…")
            opening, open_err = await recv_agent_response(ws, GREETING_WAIT)
            if open_err:
                print(f"  [WARN] No opening: {open_err}")
            else:
                preview = (opening[:70] + "…") if len(opening or "") > 70 else opening
                print(f"  Agent: \"{preview}\"")

            # ── Ten turns ──────────────────────────────────────────────────────
            silence = silence_pcm(SILENCE_SECS)

            for turn_idx, candidate_text in enumerate(CANDIDATE_RESPONSES):
                turn_num  = turn_idx + 1
                turn_time = ts()

                print(f"  Turn {turn_num:2d} ▶  \"{candidate_text}\"")

                # Stream candidate voice + silence (VAD trigger)
                await stream_pcm(ws, audio_clips[turn_idx])
                await stream_pcm(ws, silence)

                # ── START timer (candidate finished speaking) ──────────────────
                t_start = time.monotonic()

                agent_text, err = await recv_agent_response(ws, TURN_TIMEOUT)
                latency_ms = int((time.monotonic() - t_start) * 1000)

                if err:
                    label = "no_response" if "closed" in err.lower() else "timeout"
                    call_result["turns"].append({
                        "turn":            turn_num,
                        "candidate_input": candidate_text,
                        "agent_response":  None,
                        "latency_ms":      latency_ms,
                        "flagged_slow":    True,
                        "timestamp":       turn_time,
                        "error":           err,
                    })
                    call_result["status"]         = "failed"
                    call_result["failure_reason"] = f"{label} on turn {turn_num}: {err}"
                    print(f"         ✗  [{label}] {err}")
                    break

                flagged  = latency_ms > SLOW_MS
                slow_tag = "  ⚠ SLOW" if flagged else ""
                preview  = (agent_text[:67] + "…") if len(agent_text) > 70 else agent_text
                print(f"         ◀  \"{preview}\"")
                print(f"            latency={latency_ms}ms{slow_tag}")

                call_result["turns"].append({
                    "turn":            turn_num,
                    "candidate_input": candidate_text,
                    "agent_response":  agent_text,
                    "latency_ms":      latency_ms,
                    "flagged_slow":    flagged,
                    "timestamp":       turn_time,
                })

                if turn_idx < len(CANDIDATE_RESPONSES) - 1:
                    # Wait for agent to finish streaming its audio before next turn
                    await drain_agent_audio(ws)
                    await asyncio.sleep(BETWEEN_TURNS)

    except (websockets.exceptions.InvalidHandshake,
            websockets.exceptions.InvalidURI, OSError) as exc:
        call_result["status"]         = "failed"
        call_result["failure_reason"] = f"connection_failure: {exc}"
        print(f"  [FAIL] {exc}")

    except asyncio.TimeoutError:
        call_result["status"]         = "failed"
        call_result["failure_reason"] = "connection_failure: connect timed out"
        print(f"  [FAIL] Connection timed out")

    except websockets.exceptions.ConnectionClosed as exc:
        call_result["status"]         = "failed"
        call_result["failure_reason"] = f"unexpected_disconnection: {exc}"
        print(f"  [FAIL] Unexpected disconnection: {exc}")

    except Exception as exc:
        call_result["status"]         = "failed"
        call_result["failure_reason"] = f"{type(exc).__name__}: {exc}"
        print(f"  [FAIL] {type(exc).__name__}: {exc}")

    icon = "✓" if call_result["status"] == "success" else "✗"
    print(f"  {icon}  Call {call_number} — {call_result['status']}")
    return call_result


# ── Aggregate stats ────────────────────────────────────────────────────────────

def compute_summary(calls: list[dict]) -> dict:
    successful    = sum(1 for c in calls if c["status"] == "success")
    all_latencies = [
        t["latency_ms"]
        for c in calls
        for t in c["turns"]
        if t.get("agent_response") is not None and t.get("latency_ms") is not None
    ]
    return {
        "successful_calls":   successful,
        "failed_calls":       TOTAL_CALLS - successful,
        "average_latency_ms": round(sum(all_latencies) / len(all_latencies)) if all_latencies else 0,
        "slowest_turn_ms":    max(all_latencies, default=0),
        "fastest_turn_ms":    min(all_latencies, default=0),
    }


# ── Main ───────────────────────────────────────────────────────────────────────

async def main() -> None:
    REPORTS_DIR.mkdir(exist_ok=True)

    print("=" * 56)
    print("  SuperNanny — ElevenLabs ConvAI Test Harness")
    print(f"  Agent   : {AGENT_ID}")
    print(f"  Calls   : {TOTAL_CALLS}   Turns/call : {len(CANDIDATE_RESPONSES)}")
    print(f"  Timeout : {TURN_TIMEOUT}s   Slow flag  : >{SLOW_MS}ms")
    print("=" * 56)

    # Pre-generate TTS audio for all candidate lines
    print("\nGenerating TTS audio for candidate responses…")
    audio_clips: list[bytes] = []
    for i, text in enumerate(CANDIDATE_RESPONSES, 1):
        print(f"  [{i:2d}/{len(CANDIDATE_RESPONSES)}] {text}")
        pcm = tts_to_pcm(text)
        audio_clips.append(pcm)
    print(f"  Done — {len(audio_clips)} clips ready.\n")

    all_calls: list[dict] = []
    run_ts = datetime.now().isoformat()

    for call_num in range(1, TOTAL_CALLS + 1):
        result = await run_call(call_num, audio_clips)
        all_calls.append(result)
        if call_num < TOTAL_CALLS:
            await asyncio.sleep(BETWEEN_CALLS)

    summary = compute_summary(all_calls)

    report = {
        "test_run":    run_ts,
        "total_calls": TOTAL_CALLS,
        **summary,
        "calls": all_calls,
    }

    stamp       = datetime.now().strftime("%Y%m%d_%H%M%S")
    ts_path     = REPORTS_DIR / f"test_report_{stamp}.json"
    latest_path = REPORTS_DIR / "test_report.json"

    payload = json.dumps(report, indent=2, ensure_ascii=False)
    ts_path.write_text(payload)
    latest_path.write_text(payload)

    print("\n" + "=" * 56)
    print("  TEST COMPLETE")
    print(f"  Successful : {summary['successful_calls']}/{TOTAL_CALLS}")
    print(f"  Failed     : {summary['failed_calls']}/{TOTAL_CALLS}")
    if summary["average_latency_ms"]:
        print(f"  Avg latency: {summary['average_latency_ms']} ms")
        print(f"  Fastest    : {summary['fastest_turn_ms']} ms")
        print(f"  Slowest    : {summary['slowest_turn_ms']} ms")
    print(f"  Report     : {latest_path.resolve()}")
    print("=" * 56 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
