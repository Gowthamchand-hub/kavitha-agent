# SuperNanny Voice Agent — Boss Report
**Date:** 2026-03-24
**Project:** Kavitha — AI Phone Screening Agent
**Prepared by:** Claude Code + Gowthamchand

---

## Summary

We built and tested a multi-route AI voice screening agent ("Kavitha") that conducts nanny candidate phone interviews in Hinglish. Today we completed:

| Task | Status |
|------|--------|
| Route C: Azure GPT Realtime + ElevenLabs TTS | ✅ Built & tested |
| Route D: LiveKit + Groq + Sarvam TTS | ✅ Built & deployed |
| LLM quality gate (good vs bad candidates) | ✅ 10/10 (100%) |
| Interruption scenario test | ✅ 7/10 (70%) |
| GitHub repo | ✅ Live |

---

## Route C — Azure GPT Realtime + ElevenLabs (Hybrid)

**Architecture:** Azure OpenAI `gpt-realtime-1.5` WebSocket → ElevenLabs `eleven_multilingual_v2` TTS
**Test:** 10 automated screening calls
**Results:** 4/10 successful (6 failed due to Azure rate limits, not code)

| Metric | Value |
|--------|-------|
| Successful runs | 4/10 |
| Avg response latency | ~1.2s |
| TTS voice | ElevenLabs Zara (OtEfb2LVzIE45wdYe54M) |
| Failure cause | Azure Realtime API rate limits (429) |

**Bugs fixed during build:**
- TTS model typo (`"elevan v3"` → `"eleven_multilingual_v2"`)
- Azure API version wrong (`2025-10-01-preview` → `2024-10-01-preview`)
- WebSocket buffer drain missing after greeting (caused turn 1 timeouts)
- ElevenLabs `output_format` moved to query param (was in JSON body)
- Added retry logic for ElevenLabs 400 errors

---

## Route D — LiveKit + Groq + Sarvam AI

**Architecture:** LiveKit Agent → Groq Whisper STT → Llama 3.3 70B → Sarvam `bulbul:v2` TTS
**Status:** Deployed and working in LiveKit playground

| Component | Config |
|-----------|--------|
| STT | Groq Whisper Large v3 (Hindi) |
| LLM | Llama 3.3 70B Versatile |
| TTS | Sarvam bulbul:v2, anushka speaker, hi-IN |
| VAD | Silero |
| Interruptions | Enabled (min 0.5s, max 3.0s endpointing) |

**Custom work:** Built `sarvam_tts.py` — a LiveKit-compatible TTS plugin for Sarvam AI since no official plugin exists. Uses `ChunkedStream` + `AudioEmitter` pattern from livekit-agents v1.5.

**Persona:** Kavitha speaks natural Hinglish — Hindi with English words like "experience", "salary", "available". Uses feminine Hindi forms. Greets first after connecting.

---

## LLM Quality Gate — Can the LLM Score Candidates?

**Model:** Groq Llama 3.3 70B
**Test:** 10 candidate conversations (5 good, 5 bad)
**Result: 10/10 (100%) — PROCEED**

| Category | Correct |
|----------|---------|
| Good candidates detected | 5/5 |
| Bad candidates detected | 5/5 |

The LLM reliably distinguishes good caregivers (Bangalore-based, 2+ yrs experience, reasonable salary) from bad ones (no experience, wrong city, unrealistic demands, evasive).

---

## Interruption Scenario Test — Route D

**Test:** 10 interruption types simulated via LLM
**Result: 7/10 (70%) — GOOD**

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

**Failures (3):**
- **Clarification:** Didn't explain "0–6 years" before re-asking
- **Wrong person:** Continued screening instead of asking to reschedule
- **Language switch:** Responded in Hindi instead of Hinglish

These are prompt-level fixes, not architecture issues.

---

## What's Next

| Item | Priority |
|------|----------|
| Fix 3 failing interruption scenarios (prompt tuning) | High |
| Route A: Azure VoiceLive SDK integration | High |
| Route B: ElevenLabs Conversational AI | Medium |
| Exotel SIP + Bangalore number for Route D | Medium |
| Run interruption tests on Routes A, B, C | Medium |

---

## GitHub

**Repo:** https://github.com/Gowthamchand-hub/kavitha-agent

Files: `test_agent_azure.py`, `test_llm_quality.py`, `test_interruptions.py`, `route_d/agent.py`, `route_d/sarvam_tts.py`, `reports/`
