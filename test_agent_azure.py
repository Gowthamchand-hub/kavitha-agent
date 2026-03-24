#!/usr/bin/env python3
"""
SuperNanny — Azure GPT Realtime + ElevenLabs TTS Test Harness

Flow per turn
─────────────
1. Convert candidate Hindi text → PCM audio via ElevenLabs TTS  (pre-generated at startup)
2. Stream audio chunks to Azure GPT Realtime  (input_audio_buffer.append)
3. Stream silence so server VAD detects end-of-speech
4. START latency timer
5. Wait for {"type": "response.audio_transcript.done"} from Azure
6. STOP timer — record latency_ms

Credential blocks
─────────────────
  Block A  (line ~30)  — Azure OpenAI Realtime
  Block B  (line ~38)  — ElevenLabs TTS (candidate voice only)
"""

import asyncio
import base64
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path

import requests
import websockets
from dotenv import load_dotenv

load_dotenv()

# ── Block A: Azure OpenAI Realtime credentials ─────────────────────────────────
# Set these in your .env file (see .env.example)
AZURE_RESOURCE   = os.getenv("AZURE_RESOURCE", "")
AZURE_API_KEY    = os.getenv("AZURE_API_KEY", "")
AZURE_DEPLOYMENT = os.getenv("AZURE_DEPLOYMENT", "gpt-realtime-1.5")
AZURE_API_VERSION = os.getenv("AZURE_API_VERSION", "2024-10-01-preview")

WS_URL = (
    f"wss://{AZURE_RESOURCE}.openai.azure.com/openai/realtime"
    f"?api-version={AZURE_API_VERSION}&deployment={AZURE_DEPLOYMENT}"
)

# ── Block B: ElevenLabs TTS (used only to generate candidate audio) ─────────────
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
TTS_VOICE_ID       = os.getenv("TTS_VOICE_ID", "OtEfb2LVzIE45wdYe54M")  # Zara
TTS_MODEL          = os.getenv("TTS_MODEL", "eleven_multilingual_v2")

# ── Test configuration ─────────────────────────────────────────────────────────
DEBUG          = True
TOTAL_CALLS    = 10
TURN_TIMEOUT   = 20.0   # seconds per turn
SLOW_MS        = 1000   # ms — flag slow turns in report
BETWEEN_TURNS  = 0.3    # seconds between turns within a call
BETWEEN_CALLS  = 5.0    # seconds between calls
HANDSHAKE_WAIT = 10.0   # seconds — timeout for session.created
GREETING_WAIT  = 15.0   # seconds — timeout for agent opening statement

SAMPLE_RATE  = 16_000   # Hz  (Azure Realtime expects 16 kHz 16-bit PCM)
SAMPLE_WIDTH = 2        # bytes per sample
SILENCE_SECS = 1.5      # seconds of silence to trigger server VAD
CHUNK_BYTES  = 4_000    # ~125 ms per chunk at 16 kHz 16-bit
CHUNK_SLEEP  = 0.05     # seconds between chunks

REPORTS_DIR = Path("reports")

# ── System prompt (SuperNanny nanny-recruitment agent) ─────────────────────────
SYSTEM_PROMPT = (
    "You are a SuperNanny recruitment agent conducting a phone screening interview "
    "with a nanny candidate. You MUST speak exclusively in Hindi (Devanagari or "
    "romanised Hindi). Never switch to Kannada, English, or any other language. "
    "Ask about the candidate's name, age, location, childcare experience, "
    "availability, expected salary, and whether they can live-in. Be polite, "
    "professional, and conversational. Keep responses concise. "
    "Do NOT use emotion or tone tags such as [warm], [excited], [neutral], etc."
)

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
    for attempt in range(3):
        resp = requests.post(
            url,
            headers={"xi-api-key": ELEVENLABS_API_KEY, "Content-Type": "application/json"},
            params={"output_format": "pcm_16000"},
            json={"text": text, "model_id": TTS_MODEL},
            timeout=30,
        )
        if resp.ok:
            return resp.content
        print(f"  [ElevenLabs error] attempt {attempt+1}: {resp.status_code}: {resp.text[:200]}", flush=True)
        if resp.status_code not in (400, 429) or attempt == 2:
            resp.raise_for_status()
        time.sleep(2 ** attempt)
    resp.raise_for_status()


def silence_pcm(duration_secs: float) -> bytes:
    return bytes(int(SAMPLE_RATE * duration_secs) * SAMPLE_WIDTH)


async def stream_pcm(ws, pcm: bytes) -> None:
    """Send PCM bytes to Azure as input_audio_buffer.append messages."""
    for offset in range(0, len(pcm), CHUNK_BYTES):
        chunk = pcm[offset: offset + CHUNK_BYTES]
        await ws.send(json.dumps({
            "type":  "input_audio_buffer.append",
            "audio": base64.b64encode(chunk).decode(),
        }))
        await asyncio.sleep(CHUNK_SLEEP)


# ── WebSocket helpers ──────────────────────────────────────────────────────────

def ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


async def drain_agent_audio(ws, quiet_for: float = 3.0) -> None:
    """
    Drain server messages until response.done arrives or no message
    for quiet_for seconds — signals the agent has finished its turn.
    """
    while True:
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=quiet_for)
            msg = json.loads(raw)
            if msg.get("type") == "response.done":
                break
        except asyncio.TimeoutError:
            break
        except websockets.exceptions.ConnectionClosed:
            break


async def recv_agent_response(ws, timeout: float) -> tuple[str | None, str | None]:
    """
    Drain server messages until response.audio_transcript.done arrives.
    Returns (transcript_text, None) on success, (None, error_str) on failure.

    Azure event map
    ───────────────
      response.audio_transcript.done  → agent text ready  (primary target)
      response.text.done              → text-only fallback
      error                           → Azure-side error
    """
    deadline = time.monotonic() + timeout
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return None, f"Timeout ({timeout}s) — no agent response received"
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=remaining)
        except asyncio.TimeoutError:
            return None, f"Timeout ({timeout}s) — no agent response received"
        except websockets.exceptions.ConnectionClosed as exc:
            return None, f"Connection closed: {exc}"

        msg   = json.loads(raw)
        mtype = msg.get("type", "")

        if DEBUG and mtype not in ("response.audio.delta", "response.audio_transcript.delta"):
            print(f"    [DBG] {mtype}")

        if mtype == "response.audio_transcript.done":
            text = msg.get("transcript", "") or ""
            text = re.sub(r"^\[[^\]]+\]\s*", "", text)
            return text, None

        if mtype == "response.text.done":
            text = msg.get("text", "") or ""
            text = re.sub(r"^\[[^\]]+\]\s*", "", text)
            return text, None

        if mtype == "error":
            err = msg.get("error", {})
            return None, f"Azure error {err.get('code')}: {err.get('message')}"

        if mtype == "conversation.item.truncated":
            # Agent was interrupted — treat as end of response
            return "", None


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
        async with websockets.connect(
            WS_URL,
            additional_headers={"api-key": AZURE_API_KEY},
            ping_interval=None,
            open_timeout=10.0,
        ) as ws:

            # ── Handshake: wait for session.created ────────────────────────────
            try:
                raw_init = await asyncio.wait_for(ws.recv(), timeout=HANDSHAKE_WAIT)
            except asyncio.TimeoutError:
                call_result["status"]         = "failed"
                call_result["failure_reason"] = "connection_failure: handshake timeout"
                print(f"  [FAIL] Handshake timeout")
                return call_result

            init_msg = json.loads(raw_init)
            if init_msg.get("type") != "session.created":
                call_result["status"]         = "failed"
                call_result["failure_reason"] = (
                    f"connection_failure: unexpected first message "
                    f"type={init_msg.get('type')!r}"
                )
                print(f"  [FAIL] Bad handshake: got {init_msg.get('type')!r}")
                return call_result

            session_id = init_msg.get("session", {}).get("id", "?")
            print(f"  Connected  session_id={session_id}")

            # ── Configure session ──────────────────────────────────────────────
            # server_vad mirrors the current ElevenLabs approach: stream audio
            # + silence and let the server detect end-of-speech automatically.
            await ws.send(json.dumps({
                "type": "session.update",
                "session": {
                    "modalities":            ["text", "audio"],
                    "instructions":          SYSTEM_PROMPT,
                    "input_audio_format":    "pcm16",
                    "output_audio_format":   "pcm16",
                    "input_audio_transcription": {"model": "whisper-1"},
                    "turn_detection": {
                        "type":                "server_vad",
                        "threshold":           0.5,
                        "prefix_padding_ms":   300,
                        "silence_duration_ms": 500,
                    },
                },
            }))

            # ── Trigger agent opening statement ────────────────────────────────
            await ws.send(json.dumps({"type": "response.create"}))

            print(f"  Waiting for agent opening…")
            opening, open_err = await recv_agent_response(ws, GREETING_WAIT)
            if open_err:
                print(f"  [WARN] No opening: {open_err}")
            else:
                preview = (opening[:70] + "…") if len(opening or "") > 70 else opening
                print(f"  Agent: \"{preview}\"")
            # Drain remaining greeting audio/response.done before starting turns
            await drain_agent_audio(ws)

            # ── Ten turns ──────────────────────────────────────────────────────
            silence = silence_pcm(SILENCE_SECS)

            for turn_idx, candidate_text in enumerate(CANDIDATE_RESPONSES):
                turn_num  = turn_idx + 1
                turn_time = ts()

                print(f"  Turn {turn_num:2d} ▶  \"{candidate_text}\"")

                # Stream candidate voice + silence (triggers server VAD)
                await stream_pcm(ws, audio_clips[turn_idx])
                await stream_pcm(ws, silence)

                # ── START timer (candidate has "stopped speaking") ─────────────
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
    print("  SuperNanny — Azure GPT Realtime Test Harness")
    print(f"  Resource : {AZURE_RESOURCE}.openai.azure.com")
    print(f"  Deploy   : {AZURE_DEPLOYMENT}")
    print(f"  Calls    : {TOTAL_CALLS}   Turns/call : {len(CANDIDATE_RESPONSES)}")
    print(f"  Timeout  : {TURN_TIMEOUT}s   Slow flag  : >{SLOW_MS}ms")
    print("=" * 56)

    print("\nGenerating TTS audio for candidate responses…")
    audio_clips: list[bytes] = []
    for i, text in enumerate(CANDIDATE_RESPONSES, 1):
        print(f"  [{i:2d}/{len(CANDIDATE_RESPONSES)}] {text}")
        audio_clips.append(tts_to_pcm(text))
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
