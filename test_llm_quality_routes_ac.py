#!/usr/bin/env python3
"""
LLM Quality Gate — Routes A & C (Azure GPT-4o via Groq proxy)
Tests whether the Route A/C system prompt correctly scores candidates.
Uses Groq Llama 3.3 70B as LLM proxy (same capability tier as GPT-4o).
"""
import json, os, time, re
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from groq import Groq

load_dotenv()
MODEL       = "llama-3.3-70b-versatile"
REPORTS_DIR = Path("reports")

# Route A/C system prompt (formal HR screening — Hindi/Kannada)
EVAL_PROMPT = (
    "You are an HR executive at Supernan evaluating a nanny candidate. "
    "You have just completed a phone screening. Score the candidate.\n\n"
    "Scoring criteria:\n"
    "  - Experience: 2+ years with young children (0–6 yrs) preferred\n"
    "  - Location: Must be in or near Bangalore\n"
    "  - Availability: Daytime hours (8am–7pm) minimum\n"
    "  - Salary expectation: ₹8,000–₹20,000/month reasonable\n"
    "  - Attitude: Polite, clear, professional\n\n"
    "Respond ONLY with JSON:\n"
    "{\"score\": <1-10>, \"verdict\": \"GOOD\" or \"BAD\", \"reason\": \"<one sentence>\"}\n"
    "No other text."
)

CANDIDATES = [
    {"id":1,"expected":"GOOD","label":"Experienced, Bangalore, reasonable salary",
     "conversation":"""
Kavitha: Namaste, main Kavitha, Supernan se bol rahi hoon. Aapka naam?
Candidate: Sunita Sharma hoon ji.
Kavitha: Aap Bangalore mein kahan rehti hain?
Candidate: Marathahalli, Bangalore.
Kavitha: Baby care ka kitna experience hai?
Candidate: 5 saal ka hai, 0 se 4 saal ke bacchon ke saath.
Kavitha: Kab se available hain?
Candidate: Abhi se, full-time.
Kavitha: Salary expectation?
Candidate: 14,000 se 16,000 per month."""},
    {"id":2,"expected":"GOOD","label":"Certified, infant experience",
     "conversation":"""
Kavitha: Aapka naam bata dijiye.
Candidate: Priya Nair hoon, 32 saal ki.
Kavitha: Area?
Candidate: Koramangala, Bangalore.
Kavitha: Experience?
Candidate: 4 saal, mainly infants. First aid certificate bhi hai.
Kavitha: Availability?
Candidate: Poore hafte, 8am to 8pm.
Kavitha: Salary?
Candidate: 12,000 se 15,000."""},
    {"id":3,"expected":"GOOD","label":"7 years, very professional",
     "conversation":"""
Kavitha: Naam?
Candidate: Kavitha Reddy, 35 saal.
Kavitha: Area?
Candidate: HSR Layout, Bangalore.
Kavitha: Experience?
Candidate: 7 saal, 1 se 6 saal ke bacchon ke saath. References bhi hain.
Kavitha: Availability aur salary?
Candidate: 8am to 6pm. 18,000 chahiye."""},
    {"id":4,"expected":"GOOD","label":"Twins experience, honest",
     "conversation":"""
Kavitha: Parichay dijiye.
Candidate: Fatima Begum, 30 saal. 4 saal kaam kiya, twins ke saath bhi.
Kavitha: Location?
Candidate: Indiranagar, Bangalore.
Kavitha: Salary?
Candidate: 13,000 to 15,000.
Kavitha: Availability?
Candidate: Monday to Saturday, 8am to 6pm."""},
    {"id":5,"expected":"GOOD","label":"Young but certified, Bangalore",
     "conversation":"""
Kavitha: Naam aur experience?
Candidate: Deepa S, 25 saal. 2 saal ka experience, certification bhi hai.
Kavitha: Availability?
Candidate: Full week, 7am to 7pm.
Kavitha: Salary?
Candidate: 10,000 to 12,000."""},
    {"id":6,"expected":"BAD","label":"No experience, Mysore, ₹35k",
     "conversation":"""
Kavitha: Naam?
Candidate: Ritu, 19 saal.
Kavitha: Area?
Candidate: Mysore mein rehti hoon, Bangalore shift ka plan hai shayad.
Kavitha: Experience?
Candidate: Koi experience nahi, pehli job hogi.
Kavitha: Salary?
Candidate: 30,000 to 35,000 chahiye.
Kavitha: Availability?
Candidate: Weekends nahi, shaam 4 ke baad bhi nahi."""},
    {"id":7,"expected":"BAD","label":"Rude, no childcare experience",
     "conversation":"""
Kavitha: Experience?
Candidate: Cooking kiya hai. Bacchon ke saath nahi — kya fark padta hai.
Kavitha: Salary?
Candidate: 22,000 se kam nahi.
Kavitha: Background check?
Candidate: Yeh sab kyun? Trust nahi hai kya?"""},
    {"id":8,"expected":"BAD","label":"Only older kids, Hosur, ₹25k",
     "conversation":"""
Kavitha: Experience?
Candidate: 6 mahine, school mein 10-12 saal ke bacchon ko padhaya.
Kavitha: Chote bacchon ke saath?
Candidate: Nahi, sirf bade bacche.
Kavitha: Location?
Candidate: Hosur mein rehti hoon.
Kavitha: Salary?
Candidate: 25,000 minimum."""},
    {"id":9,"expected":"BAD","label":"Evasive, no references",
     "conversation":"""
Kavitha: Pichli jobs?
Candidate: Kuch families ke saath kiya, theek nahi raha.
Kavitha: References?
Candidate: Woh log busy hain.
Kavitha: Salary?
Candidate: 20,000 chahiye.
Kavitha: Availability?
Candidate: Dekhte hain."""},
    {"id":10,"expected":"BAD","label":"Distracted, no professional exp",
     "conversation":"""
Kavitha: Naam aur experience?
Candidate: Haan... sorry, main doosra kaam kar rahi thi. Shobha hoon.
Kavitha: Experience?
Candidate: Padosiyon ke bacche dekhe hain kabhi kabhi.
Kavitha: Professionally?
Candidate: Nahi exactly, seekh jaaungi.
Kavitha: Location?
Candidate: Tumkur mein rehti hoon, travel kar sakti hoon shayad."""},
]

def score(client, candidate):
    t0 = time.monotonic()
    r = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": EVAL_PROMPT},
            {"role": "user", "content": f"Screening conversation:\n{candidate['conversation'].strip()}"},
        ],
        temperature=0.1, max_tokens=150,
    )
    latency = int((time.monotonic() - t0) * 1000)
    raw = r.choices[0].message.content.strip()
    try:
        result = json.loads(raw)
    except:
        m = re.search(r'\{.*\}', raw, re.DOTALL)
        result = json.loads(m.group()) if m else {"score":0,"verdict":"ERROR","reason":raw}
    return {
        "candidate_id": candidate["id"], "label": candidate["label"],
        "expected": candidate["expected"],
        "llm_verdict": result.get("verdict","ERROR"),
        "llm_score": result.get("score",0),
        "llm_reason": result.get("reason",""),
        "correct": result.get("verdict","") == candidate["expected"],
        "latency_ms": latency,
    }

def main():
    REPORTS_DIR.mkdir(exist_ok=True)
    client = Groq(api_key=os.getenv("GROQ_API_KEY",""))

    for route in ["A/C"]:
        print(f"\n{'='*55}")
        print(f"  LLM Quality Gate — Route {route} (GPT-4o tier)")
        print(f"  Model proxy: {MODEL}")
        print(f"{'='*55}")

        results, correct = [], 0
        for c in CANDIDATES:
            tag = "GOOD" if c["expected"]=="GOOD" else " BAD"
            print(f"\n  [{tag}] #{c['id']} — {c['label']}")
            r = score(client, c)
            results.append(r)
            tick = "✓" if r["correct"] else "✗"
            flag = "" if r["correct"] else "  ← WRONG"
            print(f"         LLM: {r['llm_verdict']} (score={r['llm_score']})  {tick}{flag}")
            print(f"         Reason: {r['llm_reason']}")
            if r["correct"]: correct += 1

        accuracy = correct / len(CANDIDATES) * 100
        good_ok = sum(1 for r in results if r["expected"]=="GOOD" and r["correct"])
        bad_ok  = sum(1 for r in results if r["expected"]=="BAD"  and r["correct"])

        print(f"\n{'='*55}")
        print(f"  Accuracy      : {correct}/{len(CANDIDATES)} ({accuracy:.0f}%)")
        print(f"  Good detected : {good_ok}/5")
        print(f"  Bad detected  : {bad_ok}/5")
        verdict = "PROCEED" if accuracy >= 80 else "DEPRIORITIZE"
        print(f"  Verdict       : {verdict}")
        print(f"{'='*55}")

        report = {
            "test_run": datetime.now().isoformat(), "route": "A_C_proxy",
            "model": MODEL, "total": len(CANDIDATES),
            "correct": correct, "accuracy_pct": accuracy,
            "good_correct": good_ok, "bad_correct": bad_ok,
            "verdict": verdict, "results": results,
        }
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out = REPORTS_DIR / f"llm_quality_routes_ac_{stamp}.json"
        out.write_text(json.dumps(report, indent=2, ensure_ascii=False))
        print(f"  Report: {out}\n")

if __name__ == "__main__":
    main()
