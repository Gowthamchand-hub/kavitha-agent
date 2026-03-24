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

## Tests Planned
- 10-run automated screening test
- Interruption scenario test (same 10 scenarios as Route D)
- Latency comparison vs Routes A, C, D

## Status
- Agent ID not yet configured
- No test harness built yet
- Awaiting ElevenLabs Conversational AI agent setup

## Notes
- Simplest to deploy — no custom code for STT/LLM/TTS pipeline
- Less control over LLM behavior vs Groq/Azure
- May have limitations with Hindi/Hinglish screening prompts
