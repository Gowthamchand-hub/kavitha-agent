#!/usr/bin/env python3
"""
Route D — LLM Quality Gate
===========================
Feeds 10 simulated nanny screening conversations (5 good, 5 bad candidates)
through Llama 3.3 70B via Groq and checks whether the model correctly
scores them. If it can't distinguish good from bad, deprioritize Route D.
"""

import json
import os
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
MODEL        = "llama-3.3-70b-versatile"
REPORTS_DIR  = Path("reports")

# ── Screening system prompt (same as Route C) ─────────────────────────────────
SYSTEM_PROMPT = (
    "You are a SuperNanny recruitment agent evaluating a nanny candidate "
    "for a family in Bangalore. You have just completed a phone screening "
    "interview. Based on the conversation below, score the candidate.\n\n"
    "Scoring criteria:\n"
    "  - Experience: 2+ years with young children (0–6 yrs) preferred\n"
    "  - Location: Must be in or near Bangalore\n"
    "  - Availability: Daytime hours (8am–7pm) minimum\n"
    "  - Salary expectation: ₹8,000–₹20,000/month reasonable\n"
    "  - Attitude: Polite, clear, professional\n"
    "  - Live-in: Bonus but not required\n\n"
    "Respond ONLY with a JSON object in this exact format:\n"
    "{\n"
    '  "score": <integer 1-10>,\n'
    '  "verdict": "GOOD" or "BAD",\n'
    '  "reason": "<one sentence explanation>"\n'
    "}\n"
    "No other text. Just the JSON."
)

# ── 10 candidate conversations ─────────────────────────────────────────────────
# Each is a condensed transcript of the key Q&A from the screening call.
CANDIDATES = [
    # ── GOOD candidates ────────────────────────────────────────────────────────
    {
        "id": 1,
        "expected": "GOOD",
        "label": "Experienced, Bangalore, reasonable salary",
        "conversation": """
Agent: Namaste, main SuperNanny se bol rahi hoon. Kya aap Sunita hain?
Candidate: Haan ji, main Sunita hoon.
Agent: Aapka naam aur umar bata dijiye.
Candidate: Mera naam Sunita Sharma hai, meri umar 28 saal hai.
Agent: Aap kahaan rehti hain?
Candidate: Main Bangalore mein rehti hoon, Marathahalli ke paas.
Agent: Bacchon ki dekhbhal ka kitna anubhav hai?
Candidate: Mujhe 5 saal ka anubhav hai. Maine 0 se 4 saal ke bacchon ke saath kaam kiya hai.
Agent: Aap kab se kab tak available hain?
Candidate: Main subah 7 baje se sham 7 baje tak available hoon, week mein 6 din.
Agent: Expected salary kya hai?
Candidate: Mujhe 14,000 se 16,000 chahiye mahine mein.
Agent: Kya aap live-in kar sakti hain?
Candidate: Haan ji, agar zaroorat ho toh main live-in bhi kar sakti hoon.
""",
    },
    {
        "id": 2,
        "expected": "GOOD",
        "label": "Certified, infant experience, flexible",
        "conversation": """
Agent: Aapka naam aur umar?
Candidate: Main Priya Nair hoon, 32 saal ki hoon.
Agent: Aap kahaan rehti hain?
Candidate: Koramangala, Bangalore mein.
Agent: Experience?
Candidate: 4 saal ka anubhav hai. Mainly newborns aur infants ke saath kaam kiya hai. Mere paas basic first aid ka certificate bhi hai.
Agent: Availability?
Candidate: Poore hafte available hoon, subah 8 se raat 8 baje tak.
Agent: Salary expectation?
Candidate: 12,000 se 15,000 per month theek rahega.
Agent: Live-in?
Candidate: Haan, main live-in ke liye bilkul tayyar hoon.
""",
    },
    {
        "id": 3,
        "expected": "GOOD",
        "label": "7 years experience, very professional",
        "conversation": """
Agent: Aapka naam aur background?
Candidate: Main Kavitha Reddy hoon, 35 saal ki. Mujhe 7 saal ka experience hai bacchon ki dekhbhal mein — 1 se 6 saal tak ke bacchon ke saath.
Agent: Bangalore mein rehti hain?
Candidate: Haan, HSR Layout mein.
Agent: Availability aur salary?
Candidate: Subah 8 baje se sham 6 baje tak. Salary meri expectation 18,000 hai — experience ke hisaab se.
Agent: References hain?
Candidate: Haan, 2 pichli families ke references hain jo main de sakti hoon.
Agent: Live-in?
Candidate: Live-in nahi kar sakti, lekin time par aana-jaana bilkul kar sakti hoon.
""",
    },
    {
        "id": 4,
        "expected": "GOOD",
        "label": "Good experience, twins background, honest",
        "conversation": """
Agent: Apna parichay dijiye.
Candidate: Main Fatima Begum hoon, 30 saal ki. 4 saal kaam kiya hai, including ek family mein twins ke saath.
Agent: Location?
Candidate: Main Indiranagar, Bangalore mein rehti hoon.
Agent: Salary?
Candidate: 13,000 to 15,000 per month.
Agent: Availability?
Candidate: Monday se Saturday, 8am se 6pm.
Agent: Live-in?
Candidate: Prefer nahi karti, lekin agar family ki zaroorat ho toh soch sakti hoon.
Agent: Koi bhi concern?
Candidate: Nahi, main interviews ke liye tayyar hoon aur background check bhi de sakti hoon.
""",
    },
    {
        "id": 5,
        "expected": "GOOD",
        "label": "Young but certified, eager, Bangalore",
        "conversation": """
Agent: Aapka naam aur experience?
Candidate: Main Deepa S hoon, 25 saal ki. Experience 2 saal ka hai — ek family ke saath Bangalore mein hi. Mere paas childcare certification bhi hai government se.
Agent: Availability?
Candidate: Poori week available hoon, subah 7 se sham 7 baje tak.
Agent: Salary?
Candidate: 10,000 se 12,000 per month kaafi hai mujhe abhi.
Agent: Live-in?
Candidate: Haan ji, main live-in ke liye tayyar hoon.
Agent: Koi question?
Candidate: Sirf yeh jaanna tha ki bacche kitne saal ke hain — main chote bacchon mein zyada comfortable hoon.
""",
    },

    # ── BAD candidates ─────────────────────────────────────────────────────────
    {
        "id": 6,
        "expected": "BAD",
        "label": "No experience, wrong city, unrealistic salary",
        "conversation": """
Agent: Aapka naam aur background?
Candidate: Main Ritu hoon, 19 saal ki. Maine abhi tak koi kaam nahi kiya — yeh meri pehli job hogi.
Agent: Aap kahaan rehti hain?
Candidate: Main Mysore mein rehti hoon abhi, Bangalore shift hone ka plan hai shaayad.
Agent: Salary expectation?
Candidate: 30,000 se 35,000 chahiye.
Agent: Availability?
Candidate: Weekends nahi kar sakti, aur weekdays mein bhi shaam 4 baje ke baad nahi.
Agent: Live-in?
Candidate: Bilkul nahi.
""",
    },
    {
        "id": 7,
        "expected": "BAD",
        "label": "Rude, no real childcare experience",
        "conversation": """
Agent: Aapka anubhav bacchon ke saath?
Candidate: Maine cooking ka kaam kiya hai ghar mein. Bacchon ke saath nahi — lekin kya fark padta hai, bacche toh bacche hote hain.
Agent: Bangalore mein rehti hain?
Candidate: Haan.
Agent: Salary?
Candidate: 22,000 se kam nahi luungi.
Agent: Availability?
Candidate: Subah 10 se pehle nahi aa sakti.
Agent: Koi background check?
Candidate: Yeh sab kyun poochhte hain, trust nahi hai kya? Mujhe yeh sab pasand nahi.
""",
    },
    {
        "id": 8,
        "expected": "BAD",
        "label": "Only older children experience, far location, high salary",
        "conversation": """
Agent: Experience batayein.
Candidate: 6 mahine ka anubhav hai — ek school mein 10-12 saal ke bacchon ko padhaya hai.
Agent: Chote bacchon ke saath?
Candidate: Nahi, sirf bade bacche sambhale hain.
Agent: Location?
Candidate: Main Hosur mein rehti hoon — kaafi door hai Bangalore se.
Agent: Salary?
Candidate: 25,000 per month minimum.
Agent: Availability?
Candidate: Weekdays sirf, aur Fridays bhi nahi.
""",
    },
    {
        "id": 9,
        "expected": "BAD",
        "label": "Fired from previous jobs, no references, evasive",
        "conversation": """
Agent: Pichli jobs ke baare mein batayein.
Candidate: Kuch families ke saath kaam kiya tha... theek nahi raha, chhod diya.
Agent: References de sakti hain?
Candidate: References... woh log busy hain, nahi milenge.
Agent: Kyun chhodan pad pichli jobs?
Candidate: Personal reasons the. Aage poochhiye.
Agent: Salary?
Candidate: 20,000 chahiye.
Agent: Availability?
Candidate: Dekhte hain, schedule ke hisaab se.
""",
    },
    {
        "id": 10,
        "expected": "BAD",
        "label": "Distracted, unreliable, unclear experience",
        "conversation": """
Agent: Aapka naam aur experience?
Candidate: Haan... kya? Sorry, main doosra kaam kar rahi thi. Mera naam Shobha hai.
Agent: Experience?
Candidate: Experience... haan kuch kiya hai. Ek-do bacche dekhe hain kabhi kabhi padosiyon ke.
Agent: Professionally kaam kiya hai?
Candidate: Nahi exactly, lekin main seekh jaaungi jaldi.
Agent: Salary?
Candidate: Jo bhi milega theek hai... matlab 20,000 chahiye.
Agent: Bangalore mein rehti hain?
Candidate: Haan... actually Tumkur mein rehti hoon, travel kar sakti hoon shayad.
""",
    },
]


# ── Scoring logic ──────────────────────────────────────────────────────────────

def score_candidate(client: Groq, candidate: dict) -> dict:
    """Send a candidate conversation to Llama 3.3 70B and parse the score."""
    user_message = f"Screening conversation:\n{candidate['conversation'].strip()}"

    t_start = time.monotonic()
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_message},
        ],
        temperature=0.1,
        max_tokens=200,
    )
    latency_ms = int((time.monotonic() - t_start) * 1000)

    raw = response.choices[0].message.content.strip()

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        # Try to extract JSON if model added extra text
        import re
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        result = json.loads(match.group()) if match else {"score": 0, "verdict": "ERROR", "reason": raw}

    return {
        "candidate_id":    candidate["id"],
        "label":           candidate["label"],
        "expected":        candidate["expected"],
        "llm_verdict":     result.get("verdict", "ERROR"),
        "llm_score":       result.get("score", 0),
        "llm_reason":      result.get("reason", ""),
        "correct":         result.get("verdict", "") == candidate["expected"],
        "latency_ms":      latency_ms,
        "raw_response":    raw,
    }


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    REPORTS_DIR.mkdir(exist_ok=True)
    client = Groq(api_key=GROQ_API_KEY)

    print("=" * 60)
    print("  Route D — LLM Quality Gate")
    print(f"  Model  : {MODEL}")
    print(f"  Cases  : {len(CANDIDATES)} (5 good, 5 bad)")
    print("=" * 60)

    results = []
    correct = 0

    for c in CANDIDATES:
        tag = "GOOD" if c["expected"] == "GOOD" else " BAD"
        print(f"\n  [{tag}] #{c['id']} — {c['label']}")
        r = score_candidate(client, c)
        results.append(r)

        tick = "✓" if r["correct"] else "✗"
        flag = "" if r["correct"] else "  ← WRONG"
        print(f"         LLM: {r['llm_verdict']} (score={r['llm_score']})  {tick}{flag}")
        print(f"         Reason: {r['llm_reason']}")
        print(f"         Latency: {r['latency_ms']}ms")
        if r["correct"]:
            correct += 1

    accuracy = correct / len(CANDIDATES) * 100
    good_correct = sum(1 for r in results if r["expected"] == "GOOD" and r["correct"])
    bad_correct  = sum(1 for r in results if r["expected"] == "BAD"  and r["correct"])

    print("\n" + "=" * 60)
    print("  RESULTS")
    print(f"  Accuracy      : {correct}/{len(CANDIDATES)} ({accuracy:.0f}%)")
    print(f"  Good detected : {good_correct}/5")
    print(f"  Bad detected  : {bad_correct}/5")

    if accuracy >= 80:
        verdict = "PROCEED"
        print(f"\n  ✓ VERDICT: PROCEED WITH ROUTE D")
        print(f"    LLM distinguishes good from bad caregivers reliably.")
    else:
        verdict = "DEPRIORITIZE"
        print(f"\n  ✗ VERDICT: DEPRIORITIZE ROUTE D")
        print(f"    LLM accuracy too low ({accuracy:.0f}%) to trust scoring.")
    print("=" * 60)

    # Save report
    report = {
        "test_run":    datetime.now().isoformat(),
        "model":       MODEL,
        "total":       len(CANDIDATES),
        "correct":     correct,
        "accuracy_pct": accuracy,
        "good_correct": good_correct,
        "bad_correct":  bad_correct,
        "verdict":     verdict,
        "results":     results,
    }

    stamp   = datetime.now().strftime("%Y%m%d_%H%M%S")
    outpath = REPORTS_DIR / f"llm_quality_{stamp}.json"
    outpath.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"\n  Report: {outpath.resolve()}\n")


if __name__ == "__main__":
    main()
