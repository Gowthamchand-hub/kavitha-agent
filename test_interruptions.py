#!/usr/bin/env python3
"""
Interruption Scenario Test — All Routes (LLM Simulation)
=========================================================
Simulates 10 interruption scenarios through Groq Llama 3.3 70B.
Scores each PASS/FAIL based on whether Kavitha recovers correctly.
"""

import json
import os
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq

load_dotenv()

MODEL       = "llama-3.3-70b-versatile"
REPORTS_DIR = Path("reports")

SYSTEM_PROMPT = (
    "You are Kavitha, a female SuperNanny recruitment agent doing a phone screening. "
    "Speak in Hinglish — Hindi with English words like 'experience', 'available', 'salary', 'live-in'. "
    "Use feminine Hindi forms only: 'kar rahi hoon', 'samajh rahi hoon', 'bol rahi hoon'. "
    "Ask ONE question at a time in this order: name, age, location, experience, availability, salary, live-in. "
    "When interrupted mid-sentence, stop gracefully, acknowledge the interruption, address it briefly, "
    "then return to screening naturally. "
    "Do NOT use emotion tags like [warm] or [excited]. "
    "Respond in 1-3 sentences max."
)

# 10 interruption scenarios
SCENARIOS = [
    {
        "id": 1,
        "type": "clarification_interrupt",
        "label": "Candidate interrupts to clarify a question",
        "context": "Kavitha is asking about experience. Candidate interrupts mid-question.",
        "kavitha_was_saying": "Aapko bacchon ke saath kitna...",
        "interruption": "Sorry, aap kis type ke bacchon ki baat kar rahi hain — infant ya school age?",
        "expected_behavior": "Acknowledge, clarify (0-6 years preferred), then re-ask experience question",
    },
    {
        "id": 2,
        "type": "phone_noise_interrupt",
        "label": "Background noise / bad line",
        "context": "Kavitha is asking about salary. Candidate says they couldn't hear.",
        "kavitha_was_saying": "Aapki expected salary kya hai per month?",
        "interruption": "Sorry, line cut gayi thi — aapne kya kaha?",
        "expected_behavior": "Repeat the salary question clearly without frustration",
    },
    {
        "id": 3,
        "type": "topic_jump_interrupt",
        "label": "Candidate jumps ahead to salary before being asked",
        "context": "Kavitha is still asking about location.",
        "kavitha_was_saying": "Aap Bangalore mein kahan rehti hain?",
        "interruption": "Waise mujhe 18,000 chahiye salary mein.",
        "expected_behavior": "Note the salary, gently redirect back to location question",
    },
    {
        "id": 4,
        "type": "emotional_interrupt",
        "label": "Candidate becomes emotional / starts crying",
        "context": "Kavitha asks about previous job. Candidate gets upset.",
        "kavitha_was_saying": "Pichli job chhodni kyon padi?",
        "interruption": "Woh family bahut buri thi... unhone mujhe bina notice ke nikaal diya...",
        "expected_behavior": "Empathize briefly, then gently move forward with screening",
    },
    {
        "id": 5,
        "type": "wrong_person_interrupt",
        "label": "Someone else picks up the phone mid-call",
        "context": "Kavitha is mid-screening. A third person speaks.",
        "kavitha_was_saying": "Aapki availability kya hai subah ke time?",
        "interruption": "Hello? Yeh meri behen ka phone hai, woh abhi free nahi hain.",
        "expected_behavior": "Politely ask to reschedule or wait for the candidate to return",
    },
    {
        "id": 6,
        "type": "aggressive_interrupt",
        "label": "Candidate gets aggressive about too many questions",
        "context": "Kavitha is asking about live-in.",
        "kavitha_was_saying": "Kya aap live-in ke liye consider kar sakti hain?",
        "interruption": "Itne sawal kyun pooch rahi hain? Yeh toh harassment hai!",
        "expected_behavior": "Stay calm, explain purpose of screening, de-escalate professionally",
    },
    {
        "id": 7,
        "type": "distraction_interrupt",
        "label": "Candidate gets distracted by something in background",
        "context": "Kavitha is mid-question.",
        "kavitha_was_saying": "Aapko kitne saal ka experience hai chote bacchon ke saath?",
        "interruption": "Ek second... [to someone else] Haan haan aa rahi hoon! ...Sorry aap bol rahi thin?",
        "expected_behavior": "Repeat the question patiently without irritation",
    },
    {
        "id": 8,
        "type": "language_switch_interrupt",
        "label": "Candidate suddenly switches to English",
        "context": "Conversation has been in Hindi. Candidate switches.",
        "kavitha_was_saying": "Aap kab se available hain?",
        "interruption": "Actually I'm more comfortable in English. Can we continue in English?",
        "expected_behavior": "Acknowledge, continue in Hinglish (not full English), keep tone warm",
    },
    {
        "id": 9,
        "type": "false_end_interrupt",
        "label": "Candidate thinks the call is over and says bye",
        "context": "Kavitha still has 2 questions left.",
        "kavitha_was_saying": "Theek hai, ek aur cheez poochhni thi—",
        "interruption": "Achha, theek hai, dhanyawad! Namaste!",
        "expected_behavior": "Quickly and warmly stop them, say there are just 2 more quick questions",
    },
    {
        "id": 10,
        "type": "repeat_answer_interrupt",
        "label": "Candidate keeps repeating the same answer",
        "context": "Kavitha has moved on but candidate loops back.",
        "kavitha_was_saying": "Aur aapki salary expectation kya hai?",
        "interruption": "Main phir se bolna chahti hoon — mujhe 5 saal ka experience hai, 5 saal. Bahut experience hai mujhe.",
        "expected_behavior": "Acknowledge the experience again briefly, then redirect to salary question",
    },
]


EVAL_PROMPT = (
    "You are an evaluator checking if a voice agent responded correctly to an interruption.\n\n"
    "Scenario: {label}\n"
    "Context: {context}\n"
    "Kavitha was saying: \"{kavitha_was_saying}\"\n"
    "Interruption: \"{interruption}\"\n"
    "Expected behavior: {expected_behavior}\n\n"
    "Kavitha's actual response: \"{response}\"\n\n"
    "Did Kavitha handle this correctly? Respond ONLY with JSON:\n"
    "{{\"pass\": true/false, \"score\": 1-5, \"reason\": \"one sentence\"}}"
)


def simulate_response(client: Groq, scenario: dict) -> str:
    """Get Kavitha's response to an interruption scenario."""
    user_msg = (
        f"[Context: {scenario['context']}]\n"
        f"You (Kavitha) were saying: \"{scenario['kavitha_was_saying']}\"\n"
        f"The candidate just interrupted and said: \"{scenario['interruption']}\"\n"
        f"How do you respond?"
    )
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_msg},
        ],
        temperature=0.3,
        max_tokens=150,
    )
    return resp.choices[0].message.content.strip()


def evaluate_response(client: Groq, scenario: dict, response: str) -> dict:
    """Ask LLM to evaluate if the response was correct."""
    prompt = EVAL_PROMPT.format(
        label=scenario["label"],
        context=scenario["context"],
        kavitha_was_saying=scenario["kavitha_was_saying"],
        interruption=scenario["interruption"],
        expected_behavior=scenario["expected_behavior"],
        response=response,
    )
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=100,
    )
    raw = resp.choices[0].message.content.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        import re
        m = re.search(r'\{.*\}', raw, re.DOTALL)
        return json.loads(m.group()) if m else {"pass": False, "score": 0, "reason": raw}


def main():
    REPORTS_DIR.mkdir(exist_ok=True)
    client = Groq(api_key=os.getenv("GROQ_API_KEY", ""))

    print("=" * 65)
    print("  Interruption Scenario Test — Route D (Groq Llama 3.3 70B)")
    print(f"  Scenarios : {len(SCENARIOS)}")
    print(f"  Model     : {MODEL}")
    print("=" * 65)

    results = []
    passed  = 0

    for s in SCENARIOS:
        print(f"\n  [{s['type']}] #{s['id']} — {s['label']}")

        t0       = time.monotonic()
        response = simulate_response(client, s)
        t1       = time.monotonic()
        eval_r   = evaluate_response(client, s, response)
        latency  = int((t1 - t0) * 1000)

        ok   = eval_r.get("pass", False)
        tick = "✓ PASS" if ok else "✗ FAIL"
        if ok:
            passed += 1

        print(f"    Kavitha: {response[:120]}{'...' if len(response) > 120 else ''}")
        print(f"    Eval   : {tick}  score={eval_r.get('score', '?')}/5  latency={latency}ms")
        print(f"    Reason : {eval_r.get('reason', '')}")

        results.append({
            "id":           s["id"],
            "type":         s["type"],
            "label":        s["label"],
            "interruption": s["interruption"],
            "expected":     s["expected_behavior"],
            "response":     response,
            "pass":         ok,
            "score":        eval_r.get("score", 0),
            "reason":       eval_r.get("reason", ""),
            "latency_ms":   latency,
        })

    accuracy = passed / len(SCENARIOS) * 100

    print("\n" + "=" * 65)
    print("  RESULTS")
    print(f"  Passed   : {passed}/{len(SCENARIOS)} ({accuracy:.0f}%)")

    by_type = {}
    for r in results:
        by_type.setdefault(r["type"], []).append(r["pass"])
    print("\n  By category:")
    for t, vals in by_type.items():
        p = sum(vals)
        print(f"    {t:<30} {p}/{len(vals)}")

    if accuracy >= 70:
        verdict = "GOOD"
        print(f"\n  ✓ Route D handles interruptions well ({accuracy:.0f}%)")
    elif accuracy >= 50:
        verdict = "ACCEPTABLE"
        print(f"\n  ~ Route D interruption handling acceptable ({accuracy:.0f}%) — needs tuning")
    else:
        verdict = "POOR"
        print(f"\n  ✗ Route D interruption handling poor ({accuracy:.0f}%) — needs work")
    print("=" * 65)

    report = {
        "test_run":      datetime.now().isoformat(),
        "route":         "D",
        "model":         MODEL,
        "total":         len(SCENARIOS),
        "passed":        passed,
        "accuracy_pct":  accuracy,
        "verdict":       verdict,
        "results":       results,
    }

    stamp   = datetime.now().strftime("%Y%m%d_%H%M%S")
    outpath = REPORTS_DIR / f"interruption_test_{stamp}.json"
    outpath.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"\n  Report saved: {outpath.resolve()}\n")


if __name__ == "__main__":
    main()
