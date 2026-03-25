#!/usr/bin/env python3
"""
Route B — ElevenLabs Conversational AI Test Harness
=====================================================
Uses ElevenLabs TTS to generate candidate audio, then streams it
to the Kavitha ConvAI agent WebSocket. Measures response latency.
Full transcripts + analytics also appear in ElevenLabs dashboard.

Run:
    python test_agent_elevenlabs.py
"""

import asyncio
import base64
import json
import os
import time
from datetime import datetime
from pathlib import Path

import aiohttp
import websockets
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

AGENT_ID   = "agent_5101kmcq15wbfwzsz8vg95p448hb"
API_KEY    = os.getenv("ELEVENLABS_API_KEY", "")
VOICE_ID   = os.getenv("TTS_VOICE_ID", "OtEfb2LVzIE45wdYe54M")
WS_URL     = f"wss://api.elevenlabs.io/v1/convai/conversation?agent_id={AGENT_ID}"
TTS_URL    = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}"
REPORTS_DIR = Path(__file__).parent.parent / "reports"

CANDIDATES = [
    {
        "id": 1,
        "label": "Good candidate — experienced, Bangalore",
        "turns": [
            "Haan ji, main baat kar sakti hoon.",
            "Mera naam Sunita Sharma hai, main 28 saal ki hoon.",
            "Main Bangalore mein rehti hoon, Marathahalli ke paas.",
            "Mujhe 5 saal ka experience hai, chote bacchon ke saath.",
            "Main subah 7 baje se sham 7 baje tak available hoon.",
            "Mujhe 14000 se 16000 chahiye per month.",
            "Haan ji, live-in bhi kar sakti hoon.",
        ],
    },
    {
        "id": 2,
        "label": "Bad candidate — no experience, wrong city",
        "turns": [
            "Haan bolo.",
            "Ritu hoon, 19 saal ki.",
            "Main Mysore mein rehti hoon.",
            "Koi experience nahi hai, yeh meri pehli job hogi.",
            "Weekends nahi, aur shaam 4 ke baad bhi nahi.",
            "30000 se 35000 chahiye.",
            "Live-in bilkul nahi.",
        ],
    },
    {
        "id": 3,
        "label": "Interruption — jumps to salary early",
        "turns": [
            "Haan ji.",
            "Main Fatima hoon.",
            "Waise mujhe 18000 chahiye salary mein.",
            "Indiranagar, Bangalore.",
            "4 saal ka experience hai.",
            "Monday se Saturday, 8 to 6.",
            "Live-in nahi prefer karti.",
        ],
    },
]


async def tts_to_pcm(text: str, session: aiohttp.ClientSession) -> bytes:
    """Convert text to PCM 16kHz mono using ElevenLabs TTS."""
    async with session.post(
        TTS_URL + "?output_format=pcm_16000",
        headers={
            "xi-api-key": API_KEY,
            "Content-Type": "application/json",
        },
        json={
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
        },
        timeout=aiohttp.ClientTimeout(total=15),
    ) as resp:
        if resp.status != 200:
            body = await resp.text()
            raise Exception(f"TTS failed {resp.status}: {body[:200]}")
        return await resp.read()


async def drain_until_turn_end(ws, timeout: float = 15.0) -> str:
    """Drain WebSocket until turn_end. Returns agent response text."""
    text = ""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=deadline - time.monotonic())
        except asyncio.TimeoutError:
            break
        msg = json.loads(raw)
        t = msg.get("type", "")
        if t == "agent_response":
            text = (msg.get("agent_response_event") or {}).get("agent_response", text)
        elif t in ("turn_end", "agent_response_correction"):
            break
    return text


async def run_conversation(candidate: dict, http: aiohttp.ClientSession) -> dict:
    print(f"\n  #{candidate['id']} — {candidate['label']}", flush=True)

    # Pre-generate TTS for all turns
    print("    Generating candidate audio...", flush=True)
    turn_audio = []
    for turn_text in candidate["turns"]:
        try:
            pcm = await tts_to_pcm(turn_text, http)
            turn_audio.append((turn_text, pcm))
        except Exception as e:
            print(f"    TTS error: {e}", flush=True)
            turn_audio.append((turn_text, b"\x00" * 32000))  # 1s silence fallback

    turn_latencies = []
    conversation_id = "unknown"

    try:
        async with websockets.connect(
            WS_URL,
            additional_headers={"xi-api-key": API_KEY},
            open_timeout=10,
        ) as ws:
            print("    Connected", flush=True)

            raw = await asyncio.wait_for(ws.recv(), timeout=10)
            meta = json.loads(raw)
            cid = (meta.get("conversation_initiation_metadata_event") or {}).get("conversation_id", "")
            conversation_id = cid or "unknown"
            print(f"    ID: {conversation_id}", flush=True)

            # Wait for agent greeting to fully complete
            greeting = await drain_until_turn_end(ws, timeout=20)
            print(f"    Greeting: {greeting[:80]}", flush=True)
            await asyncio.sleep(1.5)  # let agent finish speaking before we send audio

            # 500ms silence trailer — signals end-of-speech to VAD
            silence_trail = base64.b64encode(b"\x00" * 16000).decode()  # 0.5s @ 16kHz

            # Send each turn as real speech audio
            for i, (turn_text, pcm) in enumerate(turn_audio):
                # Stream PCM in 4096-byte chunks
                chunk_size = 4096
                for offset in range(0, len(pcm), chunk_size):
                    chunk = pcm[offset:offset + chunk_size]
                    await ws.send(json.dumps({
                        "user_audio_chunk": base64.b64encode(chunk).decode()
                    }))
                    await asyncio.sleep(0.01)

                # Send silence trail so VAD commits end-of-turn
                await ws.send(json.dumps({"user_audio_chunk": silence_trail}))
                await asyncio.sleep(0.3)

                t0 = time.monotonic()
                response = await drain_until_turn_end(ws, timeout=15)
                latency_ms = int((time.monotonic() - t0) * 1000)
                turn_latencies.append(latency_ms)
                print(f"    Turn {i+1} ({latency_ms}ms): {response[:70]}", flush=True)
                await asyncio.sleep(1.0)  # pause between turns

            await ws.send(json.dumps({"type": "conversation_end"}))

    except Exception as e:
        print(f"    ERROR: {e}", flush=True)
        return {
            "candidate_id": candidate["id"],
            "label": candidate["label"],
            "conversation_id": conversation_id,
            "success": False,
            "error": str(e),
            "turn_latencies": turn_latencies,
        }

    avg = int(sum(turn_latencies) / len(turn_latencies)) if turn_latencies else 0
    print(f"    Avg latency: {avg}ms", flush=True)
    return {
        "candidate_id":    candidate["id"],
        "label":           candidate["label"],
        "conversation_id": conversation_id,
        "success":         True,
        "turn_latencies":  turn_latencies,
        "avg_latency_ms":  avg,
        "turns_completed": len(turn_latencies),
    }


async def main():
    REPORTS_DIR.mkdir(exist_ok=True)

    print("=" * 60, flush=True)
    print("  Route B — ElevenLabs Conversational AI", flush=True)
    print(f"  Agent  : {AGENT_ID}", flush=True)
    print(f"  Runs   : {len(CANDIDATES)}", flush=True)
    print("=" * 60, flush=True)
    print("  NOTE: Full transcripts also in ElevenLabs dashboard", flush=True)
    print("=" * 60, flush=True)

    results = []
    async with aiohttp.ClientSession() as http:
        for c in CANDIDATES:
            r = await run_conversation(c, http)
            results.append(r)
            await asyncio.sleep(2)

    successes = sum(1 for r in results if r["success"])
    all_lat   = [l for r in results if r["success"] for l in r.get("turn_latencies", [])]
    avg_lat   = int(sum(all_lat) / len(all_lat)) if all_lat else 0

    print("\n" + "=" * 60, flush=True)
    print("  RESULTS", flush=True)
    print(f"  Successful : {successes}/{len(CANDIDATES)}", flush=True)
    print(f"  Avg latency: {avg_lat}ms", flush=True)
    print("  Check ElevenLabs dashboard for transcripts & full metrics", flush=True)
    print("=" * 60, flush=True)

    report = {
        "test_run":       datetime.now().isoformat(),
        "route":          "B",
        "agent_id":       AGENT_ID,
        "total":          len(CANDIDATES),
        "successful":     successes,
        "avg_latency_ms": avg_lat,
        "results":        results,
    }
    stamp   = datetime.now().strftime("%Y%m%d_%H%M%S")
    outpath = REPORTS_DIR / f"route_b_test_{stamp}.json"
    outpath.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"\n  Report: {outpath}\n", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
