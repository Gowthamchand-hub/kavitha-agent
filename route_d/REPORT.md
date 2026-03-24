# Route D — LiveKit + Groq + Sarvam AI
**Status:** Built & Deployed ✅

## Architecture
```
Phone (Exotel SIP) → LiveKit Room → Groq Whisper STT → Llama 3.3 70B → Sarvam TTS → Audio
```

| Component | Detail |
|-----------|--------|
| Transport | LiveKit (WebRTC) |
| STT | Groq Whisper Large v3 (Hindi) |
| LLM | Groq `llama-3.3-70b-versatile` |
| TTS | Sarvam AI `bulbul:v2`, `anushka` speaker |
| Language | hi-IN (22050Hz WAV) |
| VAD | Silero |
| Framework | `livekit-agents` v1.5+ |

## Persona — Kavitha
- Female SuperNanny recruitment agent
- Speaks Hinglish — Hindi with English words like "experience", "salary", "available"
- Feminine Hindi forms only: `kar rahi hoon`, `samajh rahi hoon`, `bol rahi hoon`
- Natural fillers: `Hmm...`, `Achha...`, `Haan ji...`, `Theek hai...`
- Greets first after connecting
- Asks ONE question at a time: name → age → location → experience → availability → salary → live-in

## Tests Run

### LLM Quality Gate (`test_llm_quality.py`)
Fed 10 candidate conversations (5 good, 5 bad) through Llama 3.3 70B to check if it can correctly score candidates.

**Result: 10/10 (100%) — PROCEED ✅**

| Category | Result |
|----------|--------|
| Good candidates detected | 5/5 |
| Bad candidates detected | 5/5 |

### Interruption Scenario Test (`test_interruptions.py`)
Simulated 10 real-world interruption types via LLM.

**Result: 7/10 (70%) — GOOD ✅**

| # | Scenario | Result |
|---|----------|--------|
| 1 | Candidate clarifies question type | ✗ FAIL |
| 2 | Bad phone line, didn't hear | ✓ PASS |
| 3 | Candidate jumps to salary early | ✓ PASS |
| 4 | Candidate becomes emotional | ✓ PASS |
| 5 | Wrong person picks up phone | ✗ FAIL |
| 6 | Candidate gets aggressive | ✓ PASS |
| 7 | Candidate gets distracted | ✓ PASS |
| 8 | Candidate switches to English | ✗ FAIL |
| 9 | Candidate thinks call is over | ✓ PASS |
| 10 | Candidate keeps repeating answer | ✓ PASS |

**3 Failures — all prompt-level fixes:**
- Clarification: needs to explain "0–6 years" before re-asking
- Wrong person: should ask to reschedule, not continue
- Language switch: should stay in Hinglish, not switch to full Hindi

## Custom Work
Built `sarvam_tts.py` — a custom LiveKit TTS plugin for Sarvam AI since no official plugin exists.
- Uses `ChunkedStream` + `AudioEmitter` pattern (livekit-agents v1.5 API)
- Fetches WAV from Sarvam API, strips header, emits raw PCM

## Key Files
- `agent.py` — LiveKit agent entrypoint
- `sarvam_tts.py` — custom Sarvam AI TTS plugin

## Deployment
- LiveKit Cloud: `wss://route-d-w4n7gs4o.livekit.cloud`
- Run: `python agent.py start`
- Dev mode (browser mic): `python agent.py dev`
- Agent name in playground: `supernanny`

## Notes
- Only fully open-source stack (Groq + Sarvam — no Azure dependency)
- Best Hindi TTS quality — Sarvam bulbul:v2 is purpose-built for Indian languages
- Exotel SIP integration pending (needs Bangalore number setup)
