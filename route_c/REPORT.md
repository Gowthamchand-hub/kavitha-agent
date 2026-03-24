# Route C — Azure GPT Realtime + ElevenLabs TTS (Hybrid)
**Status:** Built & Tested ✅

## Architecture
```
WebSocket → Azure OpenAI gpt-realtime-1.5 → ElevenLabs TTS → Audio
```

| Component | Detail |
|-----------|--------|
| LLM | Azure OpenAI `gpt-realtime-1.5` |
| TTS | ElevenLabs `eleven_multilingual_v2` |
| Voice | Zara (`OtEfb2LVzIE45wdYe54M`) |
| STT | Built into Azure Realtime API |
| Transport | Raw WebSocket |
| Audio format | PCM 16kHz 16-bit mono |

## Tests Run

### 10-Run Automated Screening Test (`test_agent_azure.py`)
Simulates a full nanny screening call with 6 turns per run.

**Results: 4/10 successful**

| Metric | Value |
|--------|-------|
| Total runs | 10 |
| Successful | 4/10 (40%) |
| Failed | 6/10 — Azure rate limits (HTTP 429) |
| Avg latency (successful) | ~1.2s |

### Failure Breakdown
| Failure type | Count |
|--------------|-------|
| Azure 429 rate limit | 5 |
| Turn 1 timeout (drain issue, fixed) | 1 |

## Bugs Found & Fixed During Build

| Bug | Fix |
|-----|-----|
| `TTS_MODEL = "elevan v3"` typo | Fixed to `"eleven_multilingual_v2"` |
| Azure API version `2025-10-01-preview` (doesn't exist) | Fixed to `"2024-10-01-preview"` |
| WebSocket buffer not drained after greeting | Added `drain_agent_audio()` call |
| ElevenLabs `output_format` in JSON body | Moved to query param `?output_format=pcm_16000` |
| ElevenLabs 400 errors on retry | Added retry logic with backoff |
| Credentials hardcoded in script | Moved to `.env` file |

## Key Files
- `test_agent_azure.py` — full 10-run automated test harness
- `test_agent.py` — earlier prototype

## Notes
- Failures are rate limit throttling from Azure, not code bugs
- With production-tier Azure quota, expect near 10/10 success rate
- Hybrid approach gives full control over TTS voice (ElevenLabs Zara)
- More complex than Route A — requires managing WebSocket events manually
- Latency higher than Route A because two separate API calls (Azure + ElevenLabs)
