#!/usr/bin/env python3
"""
Interruption Scenario Test — Routes A, B, C
Uses the Route A/C system prompt (formal HR, Hindi/Kannada)
and Groq Llama 3.3 70B as proxy for GPT-4o (Routes A & C).
Route B uses ElevenLabs built-in LLM — tested with same prompt as proxy.
"""
import json, os, time, re
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from groq import Groq

load_dotenv()
MODEL       = "llama-3.3-70b-versatile"
REPORTS_DIR = Path("reports")

# Route A/C persona — formal HR, Hindi/Kannada
SYSTEM_PROMPT_AC = (
    "You are Kavitha, an HR executive at Supernan childcare company in Bangalore. "
    "You are conducting a phone screening call for a nanny position. "
    "Speak in Hindi (natural spoken, not formal). After candidate replies, detect and lock to their language. "
    "Be professional, efficient, brisk. ONE question at a time. "
    "When interrupted, handle gracefully and return to screening. "
    "Do NOT use emotion tags like [warm] or [excited]. "
    "Respond in 1-3 sentences max."
)

# Route B persona — ElevenLabs built-in (Kannada default, auto-Hindi)
SYSTEM_PROMPT_B = (
    "You are Kavitha, an HR executive at Supernan childcare company in Bangalore. "
    "You are conducting a phone screening call for a nanny position. "
    "Default to Kannada but switch to Hindi if candidate speaks Hindi. "
    "Be professional, efficient. ONE question at a time. "
    "When interrupted, handle gracefully and return to screening. "
    "Respond in 1-3 sentences max."
)

SCENARIOS = [
    {"id":1,"type":"clarification_interrupt","label":"Candidate clarifies question type",
     "context":"Kavitha is asking about experience. Candidate interrupts.",
     "kavitha_was_saying":"Aapko bacchon ke saath kitna...",
     "interruption":"Sorry, aap kis type ke bacchon ki baat kar rahi hain — infant ya school age?",
     "expected":"Acknowledge, clarify 0-6 years preferred, then re-ask experience question"},
    {"id":2,"type":"phone_noise_interrupt","label":"Bad phone line",
     "context":"Kavitha asked about salary. Candidate didn't hear.",
     "kavitha_was_saying":"Mahine ka kitna expect karti hain?",
     "interruption":"Sorry, line cut gayi thi — aapne kya kaha?",
     "expected":"Repeat salary question clearly without frustration"},
    {"id":3,"type":"topic_jump_interrupt","label":"Candidate jumps to salary early",
     "context":"Kavitha is asking about location.",
     "kavitha_was_saying":"Aap Bangalore mein kahan rehti hain?",
     "interruption":"Waise mujhe 18,000 chahiye salary mein.",
     "expected":"Note salary, gently redirect back to location question"},
    {"id":4,"type":"emotional_interrupt","label":"Candidate becomes emotional",
     "context":"Kavitha asks about previous job.",
     "kavitha_was_saying":"Pichli job chhodni kyon padi?",
     "interruption":"Woh family bahut buri thi... unhone mujhe bina notice ke nikaal diya...",
     "expected":"Empathize briefly, then move forward with screening"},
    {"id":5,"type":"wrong_person_interrupt","label":"Wrong person picks up phone",
     "context":"Kavitha is mid-screening.",
     "kavitha_was_saying":"Aapki availability kya hai subah ke time?",
     "interruption":"Hello? Yeh meri behen ka phone hai, woh abhi free nahi hain.",
     "expected":"Politely ask to reschedule or wait for candidate to return"},
    {"id":6,"type":"aggressive_interrupt","label":"Candidate gets aggressive",
     "context":"Kavitha asks about live-in.",
     "kavitha_was_saying":"Kya aap live-in consider kar sakti hain?",
     "interruption":"Itne sawal kyun? Yeh toh harassment hai!",
     "expected":"Stay calm, explain purpose, de-escalate professionally"},
    {"id":7,"type":"distraction_interrupt","label":"Candidate gets distracted",
     "context":"Kavitha is mid-question.",
     "kavitha_was_saying":"Aapko kitne saal ka experience hai?",
     "interruption":"Ek second... [noise] ...sorry aap bol rahi thin?",
     "expected":"Repeat question patiently without irritation"},
    {"id":8,"type":"language_switch_interrupt","label":"Candidate switches to English",
     "context":"Conversation has been in Hindi.",
     "kavitha_was_saying":"Aap kab se available hain?",
     "interruption":"Actually I'm more comfortable in English. Can we continue in English?",
     "expected":"Acknowledge, continue in Hinglish or candidate's preferred language, stay warm"},
    {"id":9,"type":"false_end_interrupt","label":"Candidate thinks call is over",
     "context":"Kavitha still has 2 questions left.",
     "kavitha_was_saying":"Theek hai, ek aur cheez poochhni thi—",
     "interruption":"Achha, theek hai, dhanyawad! Namaste!",
     "expected":"Quickly and warmly stop them, say just 2 more quick questions"},
    {"id":10,"type":"repeat_answer_interrupt","label":"Candidate keeps repeating same answer",
     "context":"Kavitha moved on but candidate loops back.",
     "kavitha_was_saying":"Aur aapki salary expectation kya hai?",
     "interruption":"Main phir se bolna chahti hoon — mujhe 5 saal ka experience hai, 5 saal.",
     "expected":"Acknowledge briefly, redirect to salary question"},
]

EVAL_PROMPT = (
    "You are an evaluator checking if a voice agent responded correctly to an interruption.\n\n"
    "Scenario: {label}\nContext: {context}\n"
    "Kavitha was saying: \"{kavitha_was_saying}\"\n"
    "Interruption: \"{interruption}\"\n"
    "Expected behavior: {expected}\n\n"
    "Kavitha's actual response: \"{response}\"\n\n"
    "Respond ONLY with JSON: {{\"pass\": true/false, \"score\": 1-5, \"reason\": \"one sentence\"}}"
)

def simulate(client, prompt, scenario):
    msg = (f"[Context: {scenario['context']}]\n"
           f"You were saying: \"{scenario['kavitha_was_saying']}\"\n"
           f"Candidate interrupted: \"{scenario['interruption']}\"\nHow do you respond?")
    r = client.chat.completions.create(
        model=MODEL,
        messages=[{"role":"system","content":prompt},{"role":"user","content":msg}],
        temperature=0.3, max_tokens=150,
    )
    return r.choices[0].message.content.strip()

def evaluate(client, scenario, response):
    prompt = EVAL_PROMPT.format(**scenario, response=response)
    r = client.chat.completions.create(
        model=MODEL,
        messages=[{"role":"user","content":prompt}],
        temperature=0.1, max_tokens=100,
    )
    raw = r.choices[0].message.content.strip()
    try:
        return json.loads(raw)
    except:
        m = re.search(r'\{.*\}', raw, re.DOTALL)
        return json.loads(m.group()) if m else {"pass":False,"score":0,"reason":raw}

def run_route(client, route_name, prompt):
    print(f"\n{'='*55}")
    print(f"  Interruption Test — Route {route_name}")
    print(f"{'='*55}")

    results, passed = [], 0
    for s in SCENARIOS:
        print(f"\n  [{s['type']}] #{s['id']} — {s['label']}")
        t0 = time.monotonic()
        response = simulate(client, prompt, s)
        latency = int((time.monotonic() - t0) * 1000)
        ev = evaluate(client, s, response)
        ok = ev.get("pass", False)
        if ok: passed += 1
        tick = "✓ PASS" if ok else "✗ FAIL"
        print(f"    Response: {response[:100]}{'...' if len(response)>100 else ''}")
        print(f"    Eval: {tick}  score={ev.get('score','?')}/5  ({latency}ms)")
        print(f"    Reason: {ev.get('reason','')}")
        results.append({
            "id": s["id"], "type": s["type"], "label": s["label"],
            "interruption": s["interruption"],
            "expected": s["expected_behavior"] if "expected_behavior" in s else s["expected"],
            "response": response, "pass": ok,
            "score": ev.get("score",0), "reason": ev.get("reason",""), "latency_ms": latency,
        })

    accuracy = passed / len(SCENARIOS) * 100
    print(f"\n{'='*55}")
    print(f"  Route {route_name}: {passed}/10 ({accuracy:.0f}%)")
    print(f"{'='*55}")
    return results, passed, accuracy

def main():
    REPORTS_DIR.mkdir(exist_ok=True)
    client = Groq(api_key=os.getenv("GROQ_API_KEY",""))

    all_results = {}

    for route_name, prompt in [("A", SYSTEM_PROMPT_AC), ("B", SYSTEM_PROMPT_B), ("C", SYSTEM_PROMPT_AC)]:
        results, passed, accuracy = run_route(client, route_name, prompt)
        all_results[route_name] = {"results": results, "passed": passed, "accuracy": accuracy}

    print(f"\n{'='*55}")
    print("  SUMMARY")
    for r, d in all_results.items():
        print(f"  Route {r}: {d['passed']}/10 ({d['accuracy']:.0f}%)")
    print(f"{'='*55}")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = REPORTS_DIR / f"interruption_routes_abc_{stamp}.json"
    out.write_text(json.dumps({
        "test_run": datetime.now().isoformat(),
        "model_proxy": MODEL,
        "routes": all_results,
    }, indent=2, ensure_ascii=False))
    print(f"\n  Report: {out}\n")

if __name__ == "__main__":
    main()
