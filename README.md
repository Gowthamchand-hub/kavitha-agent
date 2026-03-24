# SuperNanny — ElevenLabs ConvAI Test Harness

Automated test runner for the SuperNanny nanny-recruitment agent.
Simulates **10 full candidate calls**, each with **10 Hindi responses**, and measures per-turn latency over WebSocket.

---

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Create .env
cp .env.example .env
# Edit .env and paste your ElevenLabs API key

# 3. Run
python test_agent.py
```

Report is written to `reports/test_report.json` (plus a timestamped copy).

---

## Candidate Script (Hindi)

| Turn | Candidate says |
|------|----------------|
| 1 | Haan ji |
| 2 | Haan, bol sakte hain |
| 3 | Mera naam Sunita hai |
| 4 | Meri umar 28 saal hai |
| 5 | Main Bangalore mein rehti hoon, Marathahalli ke paas |
| 6 | Mujhe 3 saal ka experience hai, chote bachon ke saath |
| 7 | Main subah 8 baje se sham 6 baje tak available hoon |
| 8 | Mujhe 12 se 15 hazaar chahiye |
| 9 | Nahi, main live-in nahi kar sakti |
| 10 | Theek hai, shukriya |

---

## How it Works

```
 Connect WebSocket
       │
       ▼
 Receive conversation_initiation_metadata  (handshake)
       │
       ▼
 Drain agent opening statement             (not timed)
       │
       ▼  ┌─────────────────────────────────────────────┐
 Turn N │  │  send {"type":"user_message","text":"..."}  │
       │  │  ┌─ START timer                              │
       │  │  │                                           │
       │  │  │  wait for {"type":"agent_response",...}   │
       │  │  │                                           │
       │  │  └─ STOP timer  →  latency_ms recorded       │
       │  └─────────────────────────────────────────────┘
       │        (repeat for turns 1–10)
       ▼
 Close connection, move to next call
```

### Latency definition

| Event | Clock |
|-------|-------|
| **Start** | `ws.send(user_message)` completes |
| **Stop** | First `agent_response` message received |

Turns with latency **> 1 000 ms** are flagged `"flagged_slow": true`.

### Failure categories

| Status | Meaning |
|--------|---------|
| `connection_failure` | WebSocket could not connect or handshake failed |
| `timeout` | No `agent_response` within 3 seconds of sending turn |
| `no_response` | Connection closed before agent replied |
| `unexpected_disconnection` | Connection dropped mid-session |

---

## Report Format

`reports/test_report.json`

```json
{
  "test_run": "2025-10-01T10:30:00",
  "total_calls": 10,
  "successful_calls": 9,
  "failed_calls": 1,
  "average_latency_ms": 340,
  "slowest_turn_ms": 1240,
  "fastest_turn_ms": 180,
  "calls": [
    {
      "call_number": 1,
      "status": "success",
      "failure_reason": null,
      "turns": [
        {
          "turn": 1,
          "candidate_input": "Haan ji",
          "agent_response": "Namaste! ...",
          "latency_ms": 280,
          "flagged_slow": false,
          "timestamp": "10:30:05"
        }
      ]
    }
  ]
}
```

A timestamped copy (`test_report_YYYYMMDD_HHMMSS.json`) is also saved alongside the canonical `test_report.json`.

---

## Agent Configuration

- **Agent ID:** `agent_7701kh84k2y6fba8jv2gq7jn4rrx`
- **Input mode:** Text (`{"type": "user_message", "text": "..."}`)

> **Important:** Your ElevenLabs agent must have **text input mode** enabled, or the
> WebSocket connection must accept text messages without an audio stream.
> This is configurable in the ElevenLabs dashboard under the agent's input settings.

### If your agent only accepts audio

Replace the `send` call in `test_agent.py` with a TTS-generated audio chunk:

```python
# pip install elevenlabs
from elevenlabs import ElevenLabs
client = ElevenLabs(api_key=API_KEY)

audio = b"".join(client.text_to_speech.convert(
    text=candidate_text,
    voice_id="your_voice_id",
    model_id="eleven_turbo_v2",
    output_format="pcm_16000",
))
# Send in 4 kB chunks as base64 user_audio_chunk messages
```

---

## Files

```
kavitha-agent/
├── test_agent.py        # Main test harness
├── requirements.txt     # Python dependencies
├── .env.example         # Environment variable template
├── .env                 # Your API key (git-ignored)
├── reports/
│   ├── test_report.json              # Latest run (overwritten each time)
│   └── test_report_20251001_103000.json  # Timestamped archive
└── README.md
```

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ELEVENLABS_API_KEY` | Yes | Your ElevenLabs API key |

---

## Tuning Constants

Edit the top of `test_agent.py`:

| Constant | Default | Description |
|----------|---------|-------------|
| `TURN_TIMEOUT` | `3.0 s` | Max wait for agent response per turn |
| `SLOW_MS` | `1000 ms` | Latency threshold for `flagged_slow` |
| `BETWEEN_TURNS` | `0.4 s` | Pause between turns within a call |
| `BETWEEN_CALLS` | `1.5 s` | Pause between consecutive calls |
| `GREETING_WAIT` | `8.0 s` | Max wait for agent's opening statement |
