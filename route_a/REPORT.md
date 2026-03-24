# Route A — Azure VoiceLive SDK
**Status:** Built & Tested ✅

## Architecture
```
Mic → Azure VoiceLive SDK → gpt-realtime-1.5 → Speaker
```

| Component | Detail |
|-----------|--------|
| SDK | `azure-ai-voicelive` |
| Model | `gpt-realtime-1.5` |
| Endpoint | `https://seerfish-resource.services.ai.azure.com` |
| Voice | `marin` (OpenAI built-in) |
| STT | Whisper-1 (built into realtime API) |
| VAD | Manual commit mode |

## Tests Run

### 10-Run Automated Test Harness (`test_harness.py`)
- Streams pre-recorded candidate audio at 4x speed
- Manual VAD commit after each candidate turn
- Measures latency per turn

**Results: 10/10 runs clean**

| Metric | Value |
|--------|-------|
| Total runs | 10 |
| Successful | 10/10 (100%) |
| Avg latency (P50) | 862ms |
| P95 latency | 2421ms |
| Min latency | 693ms |
| Max latency | 3397ms |

## Key Files
- `voice_agent.py` — live mic/speaker agent, server VAD, silence watchdog, Hindi/Kannada language lock
- `test_harness.py` — 10-run automated test with latency measurement
- `test_connection.py` — connection tester for SDK and raw WebSocket
- `record_candidate.py` — tool to record candidate WAV files

## Notes
- Most reliable route — 100% success rate
- Lowest median latency (862ms P50)
- Uses Azure VoiceLive SDK which handles audio I/O, VAD, and turn management natively
- No custom TTS needed — voice is built into the realtime model
- Requires `AZURE_VOICELIVE_API_KEY` (separate from Route C's `AZURE_API_KEY`)
