# Route B — ElevenLabs Conversational AI
**Status:** Planned / Not Yet Built ⏳

## Architecture
```
Phone/Browser → ElevenLabs Conversational AI Agent → Speaker
```

| Component | Detail |
|-----------|--------|
| Platform | ElevenLabs Conversational AI |
| Voice | Zara (`OtEfb2LVzIE45wdYe54M`) |
| Model | ElevenLabs built-in LLM |
| STT | ElevenLabs built-in |
| VAD | ElevenLabs built-in |

## What's Different from Route C
Route C uses ElevenLabs only for TTS (text-to-speech). Route B uses ElevenLabs end-to-end — their full conversational AI platform handles STT, LLM, and TTS together, with no external API calls needed.

## Tests Run

### 3-Conversation Test (`test_agent_elevenlabs.py`)
Uses ElevenLabs TTS to generate candidate audio, streams to ConvAI WebSocket.
Full transcripts and call analytics available in **ElevenLabs dashboard**.

**Results: 3/3 conversations completed**

| Metric | Value |
|--------|-------|
| Successful runs | 3/3 (100%) |
| Agent avg latency | ~3.5–5s per turn (fast turns) |
| Measured avg (incl. timeouts) | ~9.2s |
| Dashboard | Full transcripts + latency in ElevenLabs portal |

**Conversations tested:**
- Good candidate (experienced, Bangalore)
- Bad candidate (no experience, wrong city)
- Interruption scenario (jumps to salary early)

## Status
- Agent ID: `agent_5101kmcq15wbfwzsz8vg95p448hb`
- Language: Kannada default, auto-switches to Hindi when candidate speaks Hindi ✅
- Test harness: `test_agent_elevenlabs.py` ✅

## Notes
- Simplest to deploy — no custom code for STT/LLM/TTS pipeline
- Less control over LLM behavior vs Groq/Azure
- May have limitations with Hindi/Hinglish screening prompts
