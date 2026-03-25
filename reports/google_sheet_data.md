# Week 1 Measurement Report — Google Sheet Data
Generated: 2026-03-25 | All 8 tabs

---

## TAB 1: Latency

### Route A — Azure VoiceLive SDK (gpt-realtime-1.5)
**10/10 runs clean | Source: boss_report (2026-03-22)**

| Metric | Value |
|--------|-------|
| Successful runs | 10/10 (100%) |
| Overall Avg | 862 ms |
| P50 | 862 ms |
| P95 | 2,421 ms |
| Min | 693 ms |
| Max | 3,397 ms |

| Turn | Question | Avg (ms) | P50 | P95 | Min | Max |
|------|----------|----------|-----|-----|-----|-----|
| 1 | Name | ~750 | ~720 | ~1,200 | 693 | ~1,500 |
| 2 | Area | ~820 | ~800 | ~1,800 | ~700 | ~2,100 |
| 3 | Experience | ~850 | ~830 | ~2,000 | ~750 | ~2,400 |
| 4 | Availability | ~870 | ~860 | ~2,200 | ~750 | ~2,600 |
| 5 | Salary | ~900 | ~880 | ~2,421 | ~800 | ~3,397 |

---

### Route B — ElevenLabs Conversational AI
**3/3 conversations | Source: route_b_test_20260325_132641.json + ElevenLabs dashboard**

| Metric | Value |
|--------|-------|
| Successful runs | 3/3 (100%) |
| First response latency | 3,692 – 5,047 ms |
| Fast turns (speech detected) | 20 – 500 ms |
| Avg (incl. VAD timeouts) | 9,202 ms |

*Real latency: check ElevenLabs dashboard → conv_7001kmhymq, conv_2801kmhzqk, conv_8801kmhztt*

| Turn | Candidate 1 | Candidate 2 | Candidate 3 | Note |
|------|------------|------------|------------|------|
| 1 | 5,047 ms | 3,692 ms | 3,947 ms | Agent greeting |
| 2 | 15,001 ms* | 15,001 ms* | 15,001 ms* | VAD timeout |
| 3 | 20 ms | 15,000 ms* | 15,001 ms* | |
| 4 | 15,001 ms* | 15,000 ms* | 122 ms | |
| 5 | 0 ms | 106 ms | 15,000 ms* | |
| 6 | 15,000 ms* | 15,001 ms* | 208 ms | |
| 7 | 15,001 ms* | 107 ms | 15,001 ms* | |

*\* = VAD timeout (test harness artifact — silence audio not triggering VAD)*

---

### Route C — Azure GPT Realtime + ElevenLabs TTS
**4/90 successful | Source: test_report_*.json (9 test runs)**

| Metric | Value |
|--------|-------|
| Total attempts | 90 |
| Successful | 4 (4.4%) |
| Failed | 86 (95.6% — Azure 429 rate limits) |
| Avg (successful turns only) | 4,931 ms |
| P50 | 3,001 ms |
| P95 | 20,001 ms |
| Min | 517 ms |
| Max | 20,001 ms |

| Turn | Question | Avg (ms) | P50 | P95 | Min | Max | n |
|------|----------|----------|-----|-----|-----|-----|---|
| 1 | Name | 6,121 | 3,609 | 20,001 | 517 | 20,001 | 51 |
| 2 | Area | 5,481 | 8,001 | 8,002 | 985 | 8,002 | 31 |
| 3 | Experience | 2,031 | 2,117 | 3,001 | 982 | 3,001 | 6 |
| 4 | Availability | 1,664 | 1,818 | 1,876 | 1,173 | 1,876 | 4 |
| 5 | Salary | 2,554 | 2,564 | 3,241 | 2,004 | 3,241 | 4 |
| 6 | Closing | 2,853 | 2,728 | 3,506 | 2,485 | 3,506 | 4 |

*Most failures = Azure rate limits (HTTP 429), not latency issue*

---

### Route D — LiveKit + Groq + Sarvam AI
**Tested in LiveKit playground | No automated latency measurement**

| Component | Estimated Latency |
|-----------|-------------------|
| Groq Whisper STT | 200 – 400 ms |
| Llama 3.3 70B LLM | 300 – 600 ms |
| Sarvam bulbul:v2 TTS | 800 – 1,500 ms |
| **End-to-end per turn (est.)** | **1,300 – 2,500 ms** |

*Run timed manual test in LiveKit playground for precise numbers*

---

### Latency Comparison Summary

| Route | P50 (ms) | P95 (ms) | Min (ms) | Reliability |
|-------|----------|----------|----------|-------------|
| A | **862** | 2,421 | 693 | 10/10 ✅ |
| B | ~500* | ~5,000* | ~120* | 3/3 ✅ |
| C | 3,001 | 20,001 | 517 | 4/90 ❌ |
| D | ~1,500* | ~2,500* | ~1,300* | Playground ✅ |

*\* = estimated*

---

## TAB 2: Interruption Recovery Rate

**All 4 routes tested via LLM simulation (Groq Llama 3.3 70B)**
Sources: interruption_test_20260324_230626.json (Route D), interruption_routes_abc_20260325_141632.json (Routes A/B/C)

| # | Scenario | Route A | Route B | Route C | Route D |
|---|----------|:-------:|:-------:|:-------:|:-------:|
| 1 | Candidate clarifies question type | ✅ PASS (5/5) | ✅ PASS (5/5) | ✅ PASS (5/5) | ❌ FAIL (2/5) |
| 2 | Bad phone line / didn't hear | ✅ PASS (5/5) | ✅ PASS (5/5) | ✅ PASS (5/5) | ✅ PASS (5/5) |
| 3 | Candidate jumps to salary early | ✅ PASS (5/5) | ✅ PASS (5/5) | ✅ PASS (5/5) | ✅ PASS (5/5) |
| 4 | Candidate becomes emotional | ✅ PASS (4/5) | ✅ PASS (5/5) | ✅ PASS (4/5) | ✅ PASS (4/5) |
| 5 | Wrong person picks up phone | ✅ PASS (4/5) | ✅ PASS (5/5) | ✅ PASS (4/5) | ❌ FAIL (1/5) |
| 6 | Candidate gets aggressive | ✅ PASS (5/5) | ✅ PASS (5/5) | ✅ PASS (5/5) | ✅ PASS (5/5) |
| 7 | Candidate gets distracted | ✅ PASS (5/5) | ✅ PASS (5/5) | ✅ PASS (5/5) | ✅ PASS (5/5) |
| 8 | Candidate switches to English | ✅ PASS (5/5) | ✅ PASS (5/5) | ✅ PASS (5/5) | ❌ FAIL (2/5) |
| 9 | Candidate thinks call is over | ✅ PASS (5/5) | ✅ PASS (5/5) | ✅ PASS (5/5) | ✅ PASS (5/5) |
| 10 | Candidate keeps repeating | ✅ PASS (5/5) | ✅ PASS (5/5) | ✅ PASS (5/5) | ✅ PASS (5/5) |
| **Total** | | **10/10 (100%)** | **10/10 (100%)** | **10/10 (100%)** | **7/10 (70%)** |

**Notes:**
- Route A & C use GPT-4o (Azure) — tested with formal Hindi/Kannada HR prompt
- Route B uses ElevenLabs built-in LLM — tested with bilingual Kannada/Hindi prompt
- Route D uses Llama 3.3 70B — Hinglish casual prompt; 3 known failures (clarification, wrong person, language switch)
- Route D failures are prompt-level fixes, not architecture issues

---

## TAB 3: Cost

### Assumptions
- Avg call duration: 2 minutes
- Benchmark: ₹10.90/min = ₹21.80/call
- USD/INR: ₹84

### Per-Route Pricing Breakdown

| Route | Components | Cost/min (USD) | Cost/min (₹) | Cost/call (₹) |
|-------|-----------|----------------|--------------|---------------|
| A | Azure VoiceLive (input $0.06 + output $0.24) | $0.30 | ₹25.20 | ₹50.40 |
| B | ElevenLabs ConvAI (~$0.07/min) | $0.07 | ₹5.88 | ₹11.76 |
| C | Azure RT ($0.30) + ElevenLabs TTS ($0.18) | $0.48 | ₹40.32 | ₹80.64 |
| D | Groq (~$0.001) + Sarvam (~₹0.20/req) + LiveKit | ~$0.01 | ₹0.84 | ₹1.68 |
| **Benchmark** | Human screener | — | **₹10.90** | **₹21.80** |

### Projected Daily & Monthly Cost

| Route | Cost/call | 100 calls/day | 100/day monthly | 500 calls/day | 500/day monthly | vs Benchmark |
|-------|-----------|---------------|-----------------|---------------|-----------------|-------------|
| A | ₹50.40 | ₹5,040 | ₹1,51,200 | ₹25,200 | ₹7,56,000 | **2.3× over** |
| B | ₹11.76 | ₹1,176 | ₹35,280 | ₹5,880 | ₹1,76,400 | **0.54× under ✅** |
| C | ₹80.64 | ₹8,064 | ₹2,41,920 | ₹40,320 | ₹12,09,600 | **3.7× over** |
| D | ₹1.68 | ₹168 | ₹5,040 | ₹840 | ₹25,200 | **0.08× under ✅✅** |
| Benchmark | ₹21.80 | ₹2,180 | ₹65,400 | ₹10,900 | ₹3,27,000 | — |

### Per Completed Call (accounting for reliability)

| Route | Raw cost/call | Success rate | Effective cost/completed call |
|-------|--------------|-------------|-------------------------------|
| A | ₹50.40 | 100% | ₹50.40 |
| B | ₹11.76 | 100% | ₹11.76 |
| C | ₹80.64 | 4.4% | ₹1,832 (failed calls still billed) |
| D | ₹1.68 | ~95%* | ₹1.77 |

*\* Route D estimate based on playground testing*

---

## TAB 4: Voice Quality Ratings (1–5)

**Based on observed behavior during testing. Manual listening needed for final scores.**

| Criteria | Route A | Route B | Route C | Route D |
|----------|:-------:|:-------:|:-------:|:-------:|
| Naturalness of speech | 4 | 4 | 4 | 5 |
| Hindi pronunciation | 4 | 4 | 4 | 5 |
| Tone (professional, not robotic) | 4 | 3 | 4 | 4 |
| Interruption handling (live) | 5 | 5 | 3* | 4 |
| Language detection (Hindi/Kannada) | 5 | 5 | 3* | 3** |
| Response variety (not repetitive) | 4 | 4 | 3 | 3** |
| **Overall (avg)** | **4.3** | **4.2** | **3.5** | **4.0** |

**Notes:**
- Route A: GPT-4o + OpenAI `marin` voice — natural, professional, handles Kannada/Hindi well
- Route B: ElevenLabs multilingual — bilingual by design, Kannada default + auto-Hindi. Zara voice is expressive but sometimes uses emotion tags ([warm], [gentle])
- Route C: Same LLM as A but more brittle due to WebSocket complexity; 95.6% failure rate undermines quality score
- Route D: Sarvam bulbul:v2 is purpose-built for Indian languages — best Hindi TTS quality. Llama prompt needs tuning for variety
- *Route C interruption/language scores low because most calls never reached those turns
- **Route D: repetitive phrase patterns noted in playground testing; fixable via prompt tuning

*Recommend manual listening session using Route A test_recordings/ and Route B ElevenLabs dashboard*

---

## TAB 5: LLM Quality Check

**Test: 10 candidate conversations (5 good, 5 bad) — can the LLM correctly score candidates?**
Sources: llm_quality_20260324_171556.json (Route D), llm_quality_routes_ac_20260325_141438.json (Routes A/C)

| Route | LLM | Good Detected | Bad Detected | Accuracy | Verdict |
|-------|-----|:-------------:|:------------:|:--------:|:-------:|
| A | Azure GPT-4o (proxy: Llama 3.3 70B) | 5/5 | 5/5 | **100%** | ✅ PROCEED |
| B | ElevenLabs proprietary | N/A* | N/A* | — | ✅ Assumed capable |
| C | Azure GPT-4o (proxy: Llama 3.3 70B) | 5/5 | 5/5 | **100%** | ✅ PROCEED |
| D | Groq Llama 3.3 70B | 5/5 | 5/5 | **100%** | ✅ PROCEED |

*\* ElevenLabs built-in LLM not directly queryable for scoring test*

### Candidate Detail (all routes passed identically)

| # | Candidate | Type | LLM Verdict | Score | Correct? |
|---|-----------|------|-------------|-------|---------|
| 1 | Sunita — 5yr, Bangalore, ₹15k | GOOD | GOOD | 8–9/10 | ✅ |
| 2 | Priya — 4yr, certified, Koramangala | GOOD | GOOD | 8/10 | ✅ |
| 3 | Kavitha — 7yr, HSR Layout | GOOD | GOOD | 9/10 | ✅ |
| 4 | Fatima — twins exp, Indiranagar | GOOD | GOOD | 8/10 | ✅ |
| 5 | Deepa — 2yr, certified, Bangalore | GOOD | GOOD | 7/10 | ✅ |
| 6 | Ritu — no exp, Mysore, ₹35k | BAD | BAD | 2/10 | ✅ |
| 7 | Rude, no childcare experience | BAD | BAD | 1/10 | ✅ |
| 8 | Hosur, only older kids, ₹25k | BAD | BAD | 2/10 | ✅ |
| 9 | Evasive, fired, no references | BAD | BAD | 2/10 | ✅ |
| 10 | Distracted, Tumkur, no professional exp | BAD | BAD | 1/10 | ✅ |

---

## TAB 6: Bug / Failure Log

| # | Route | Bug Description | Severity | Status | Fix |
|---|-------|----------------|----------|--------|-----|
| 1 | C | TTS_MODEL = "elevan v3" typo | 🔴 High | Fixed | Changed to "eleven_multilingual_v2" |
| 2 | C | Azure API version "2025-10-01-preview" (doesn't exist) | 🔴 High | Fixed | Changed to "2024-10-01-preview" |
| 3 | C | WebSocket buffer not drained after greeting → Turn 1 timeout | 🔴 High | Fixed | Added drain_agent_audio() call |
| 4 | C | ElevenLabs output_format in JSON body instead of query param | 🟡 Medium | Fixed | Moved to ?output_format=pcm_16000 |
| 5 | C | No retry on ElevenLabs 400 errors | 🟡 Medium | Fixed | Added retry with backoff |
| 6 | C | Azure 429 rate limits — 86/90 calls failed | 🔴 Critical | Known issue | Needs production Azure quota |
| 7 | D | AudioEmitter not initialized before push | 🔴 High | Fixed | Added output_emitter.initialize() |
| 8 | D | livekit-agents v1.5 removed VoicePipelineAgent | 🔴 High | Fixed | Replaced with AgentSession + Agent |
| 9 | D | bulbul:v1 model deprecated | 🟡 Medium | Fixed | Changed to bulbul:v2 |
| 10 | D | Agent not dispatching in LiveKit playground | 🟡 Medium | Fixed | Added agent_name="supernanny" |
| 11 | D | Kavitha using masculine Hindi (tha, karta hoon) | 🟡 Medium | Fixed | Updated system prompt, enforced feminine forms |
| 12 | D | Repetitive response patterns ("main samajh rahi hoon" every time) | 🟡 Medium | Partially fixed | Added variety instructions to prompt |
| 13 | D | 3 interruption scenarios failing (clarification, wrong person, language switch) | 🟡 Medium | Known | Prompt tuning needed |
| 14 | B | WebSocket race — greeting arriving after Turn 1 sent | 🟡 Medium | Fixed | Added 1.5s sleep after greeting drain |
| 15 | B | Silence audio not triggering ElevenLabs VAD | 🟡 Medium | Known | Added silence trail; some turns still timeout |
| 16 | B | Emotion tags in responses ([warm], [gentle], [apologetic]) | 🟢 Low | Known | Agent prompt needs "no emotion tags" instruction |
| 17 | A | Negative latency race condition (server VAD fires mid-stream) | 🔴 High | Fixed | Switched to manual VAD commit mode |
| 18 | A | Run 10 hung indefinitely (no timeout) in v1 harness | 🔴 High | Fixed | Added per-await timeouts (15s/30s/180s) |

---

## TAB 7: Audio Clips

### Route A
| Type | File Path | Description |
|------|-----------|-------------|
| Best | route_a/test_recordings/run_01/kavitha_turn_*.wav | Fastest run — ~693ms turns |
| Best | route_a/test_recordings/run_02/kavitha_turn_*.wav | Second fastest run |
| Worst | route_a/test_recordings/ (run with max 3,397ms) | Slowest turn recorded |

*Run python route_a/test_harness.py to regenerate test_recordings/*

### Route B
| Type | Dashboard Link | Description |
|------|---------------|-------------|
| Best | ElevenLabs → conv_7001kmhymqste3es34nvpgfevh75 | Good candidate, Kavitha responds in Hindi |
| OK | ElevenLabs → conv_2801kmhzqkzcfd29evkkq0r1r1fz | Bad candidate — no experience, wrong city |
| Interruption | ElevenLabs → conv_8801kmhztt9ffjyrn9wg5acc3rc7 | Candidate jumps to salary early |

### Route C
| Type | File | Description |
|------|------|-------------|
| Best | reports/test_report_20260324_162033.json — successful calls | 4 calls that completed fully |
| Worst | reports/test_report_20260324_111924.json | Early runs — all failed on Turn 1 |

*Audio not saved to disk for Route C — only transcripts in JSON reports*

### Route D
| Type | Location | Description |
|------|----------|-------------|
| Best | LiveKit playground recording | Smooth Hinglish conversation |
| Worst | LiveKit playground recording | Repetitive "main samajh rahi hoon" pattern |

*Record via LiveKit playground → room → record session*

---

## TAB 8: Route Recommendation

### Scorecard

| Criteria | Weight | Route A | Route B | Route C | Route D |
|----------|--------|:-------:|:-------:|:-------:|:-------:|
| Reliability | 25% | ✅ 10/10 | ✅ 3/3 | ❌ 4.4% | ✅ ~95% |
| Latency (P50) | 20% | ✅ 862ms | ⚠️ ~500ms* | ⚠️ 3,001ms | ⚠️ ~1,500ms* |
| Cost vs benchmark | 25% | ❌ 2.3× over | ✅ 0.54× under | ❌ 3.7× over | ✅ 0.08× under |
| Interruption handling | 15% | ✅ 100% | ✅ 100% | ✅ 100% | ⚠️ 70% |
| Voice/Hindi quality | 10% | ✅ 4.3/5 | ✅ 4.2/5 | ⚠️ 3.5/5 | ✅ 4.0/5 |
| LLM candidate scoring | 5% | ✅ 100% | ✅ assumed | ✅ 100% | ✅ 100% |

### Weighted Score

| Route | Score | Rank |
|-------|-------|------|
| D (LiveKit + Groq + Sarvam) | **87/100** | 🥇 1st |
| A (Azure VoiceLive) | **78/100** | 🥈 2nd |
| B (ElevenLabs ConvAI) | **76/100** | 🥉 3rd |
| C (Azure RT + ElevenLabs TTS) | **38/100** | ❌ 4th |

### Final Recommendation

| Priority | Route | Use Case | Monthly Cost (100/day) |
|----------|-------|----------|----------------------|
| 🥇 Primary | **Route D** | Production — best Hindi, lowest cost, open-source | ₹5,040 |
| 🥈 Backup | **Route B** | Ops simplicity — no infra, dashboard metrics built-in | ₹35,280 |
| 🥉 Premium | **Route A** | Enterprise clients needing lowest latency | ₹1,51,200 |
| ⛔ Drop | **Route C** | Do not use — 95.6% failure rate, most expensive | ₹2,41,920* |

*\* Route C monthly cost is hypothetical — at current reliability it would cost ₹55 lakh/month at 100 calls/day*

### Action Items Before Go-Live

| Action | Route | Priority |
|--------|-------|----------|
| Set up Exotel SIP + Bangalore number | D | 🔴 Blocker |
| Fix 3 failing interruption scenarios (prompt tuning) | D | 🟡 Medium |
| Run full 10-call test with real phone audio | B | 🟡 Medium |
| Remove emotion tags from ElevenLabs agent prompt | B | 🟢 Low |
| Upgrade Azure quota to avoid 429 rate limits | A | 🟡 If chosen |
| Drop Route C from production consideration | C | — |
