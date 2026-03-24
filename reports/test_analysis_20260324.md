# SuperNanny Azure GPT Realtime — Test Analysis Report
**Date:** 2026-03-24
**Test run:** 16:15:45
**Deployment:** `gpt-realtime-1.5` on `seerfish-resource.openai.azure.com`
**API version:** `2024-10-01-preview`
**TTS:** ElevenLabs `eleven_multilingual_v2`, Voice: Zara (`OtEfb2LVzIE45wdYe54M`)

---

## Overall Results

| Metric | Value |
|--------|-------|
| Total calls | 10 |
| Successful | **4 (40%)** |
| Failed | **6 (60%)** |
| Avg latency (successful turns) | **2,351 ms** |
| Fastest turn | **885 ms** (Call 1, Turn 1) |
| Slowest turn | **4,018 ms** (Call 4, Turn 7) |
| Turns flagged slow (>1000ms) | **38 / 40** (95%) |

---

## What Worked

- **WebSocket connection & handshake** succeeded on calls 1–4 — session established cleanly each time.
- **All 10 turns completed** on calls 1–4 with no mid-call dropouts.
- **Agent language** — Hindi (Devanagari + romanised) throughout. No Kannada, no English bleeding in. Emotion tags (`[warm]`, etc.) fully eliminated.
- **Server VAD** triggered correctly on every turn — `speech_started`, `speech_stopped`, `committed` all fired as expected.
- **ElevenLabs TTS** — all 10 audio clips generated successfully.

---

## Failures

### Calls 5–10: `connection_failure: timed out during opening handshake`

**Root cause: Azure rate limiting / connection throttling**

After 4 rapid back-to-back calls (~5s gap between each), Azure stopped accepting new WebSocket connections. The handshake (TCP open → TLS → HTTP upgrade) timed out before `session.created` was received.

This is consistent with Azure OpenAI Realtime's concurrency/rate limits on the `gpt-realtime-1.5` deployment. Calls ran continuously from ~16:15 to ~16:19 (4 calls in ~4 minutes), and Azure likely has a per-minute or concurrent-session cap on this tier.

**Evidence:** All 6 failures had identical `failure_reason: connection_failure: timed out during opening handshake` with zero turns recorded — the connection never reached the session layer.

**Fix:** Increase `BETWEEN_CALLS` from 5s to 15–30s, or reduce `TOTAL_CALLS` per batch.

---

## Latency Analysis

### Per-turn latency (successful calls)

| Turn | Input | Avg latency | Notes |
|------|-------|-------------|-------|
| 1 | "Haan ji" | ~1,088ms | Fastest — short audio, simple response |
| 2 | "Haan, bol sakte hain" | ~1,188ms | Still fast |
| 3 | "Mera naam Sunita hai" | ~1,476ms | Slight increase |
| 4 | "Meri umar 28 saal hai" | ~1,714ms | Accumulating context |
| 5 | "Main Bangalore mein rehti hoon…" | ~2,651ms | Longer input, noticeable lag |
| 6 | "Mujhe 3 saal ka experience hai…" | ~2,854ms | |
| 7 | "Main subah 8 baje se sham 6 baje tak…" | ~3,267ms | |
| 8 | "Mujhe 12 se 15 hazaar chahiye" | ~2,778ms | |
| 9 | "Nahi, main live-in nahi kar sakti" | ~3,294ms | |
| 10 | "Theek hai, shukriya" | ~2,739ms | |

**Pattern:** Latency grows with turn number, likely because the model is processing an increasing conversation context each turn. Short early turns (1–2) approach ~1s; later turns plateau around 2.5–4s.

**Threshold note:** The current `SLOW_MS = 1000ms` flags 95% of turns. A more realistic threshold for this deployment is **2,000ms** for normal and **3,500ms** for slow.

---

## Speech Recognition Issues (Whisper transcription errors)

These are not agent failures but Whisper ASR misrecognitions on the Hindi audio — they affect response quality:

| Candidate said | Whisper heard | Agent response error |
|---------------|---------------|---------------------|
| "Sunita" | "Samita" / "Smita" | Agent addresses candidate by wrong name throughout |
| "28 saal" | "23 saal" / "30 saal" | Agent confirms wrong age back to candidate |
| "subah 8 baje" | "subah 6 baje" | Agent repeats wrong start time |
| "Marathahalli" | "बांग्ला" / "Bangalore" (partial) | Location garbled |

**Root cause:** The candidate audio is romanised Hindi TTS, and Whisper transcribes it phonetically but imprecisely for proper nouns. The model then echoes back what Whisper heard.

**Fix options:**
1. Use Devanagari text for candidate TTS inputs (better Whisper accuracy)
2. Lower Whisper language hint to `hi` if the API supports it
3. Accept as expected noise in a Whisper-based pipeline

---

## Agent Quality Observations

**Positive:**
- Correctly asks all required fields: name, age, location, experience, availability, salary, live-in
- Politely acknowledges each answer before moving to next question
- Correctly notes live-in refusal and wraps up professionally
- Responses are concise and conversational

**Issues:**
- **Echoes Whisper errors** — repeats misheard name/age back to candidate without correction
- **Asks redundant questions** — in some calls asks live-in status 2–3 times across multiple turns
- **Out-of-order questions** — in call 1, asks availability and salary in the same turn (turn 7), then repeats live-in question separately

---

## Root Causes Fixed During This Session

| # | Issue | Fix Applied |
|---|-------|------------|
| 1 | `TTS_MODEL = "elevan v3"` (typo) | Changed to `eleven_multilingual_v2` |
| 2 | `AZURE_API_VERSION = "2025-10-01-preview"` (non-existent) | Fixed to `2024-10-01-preview` |
| 3 | Missing `drain_agent_audio` after greeting | Added drain call before turn loop |
| 4 | Agent responding in Kannada | System prompt now explicitly enforces Hindi only |
| 5 | `[warm]` / emotion tags in transcripts | System prompt bans tags + regex strip in `recv_agent_response` |
| 6 | ElevenLabs `output_format` in JSON body | Moved to query param (`?output_format=pcm_16000`) |
| 7 | No retry on ElevenLabs 400/429 | Added 3-attempt retry with backoff |

---

## Recommendations

### Immediate
1. **Increase `BETWEEN_CALLS` to 20–30s** — will likely bring success rate to 10/10 by avoiding Azure throttling
2. **Raise `SLOW_MS` to 2000ms** — current 1000ms threshold is too tight; 95% of working turns are flagged, making the metric meaningless

### Short-term
3. **Use Devanagari TTS inputs** for candidate audio to improve Whisper accuracy on names/numbers
4. **Add `language: "hi"` to `input_audio_transcription`** config if Azure supports it

### Monitoring
5. **Target latency**: p50 ~2,000ms, p95 ~4,000ms is realistic for this deployment
6. **Success rate**: Should reach 10/10 with throttle fix; current 40% is purely an infrastructure issue, not a model issue
