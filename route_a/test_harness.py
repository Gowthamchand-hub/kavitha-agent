import asyncio, base64, os, sys, re, wave, json, shutil, statistics
from collections import Counter
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

ENDPOINT = os.getenv("AZURE_VOICELIVE_ENDPOINT", "https://seerfish-resource.services.ai.azure.com")
API_KEY  = os.getenv("AZURE_VOICELIVE_API_KEY", "")
MODEL    = os.getenv("AZURE_VOICELIVE_MODEL", "gpt-realtime-1.5")

AUDIO_DIR      = Path("test_audio")
RECORDINGS_DIR = Path("test_recordings")
RATE, CHUNK    = 24000, 1024
TOTAL_RUNS     = 10

AGENT_START_TIMEOUT = 15.0
TURN_DONE_TIMEOUT   = 30.0
CALL_END_TIMEOUT    = 15.0
RUN_TIMEOUT         = 180.0

AUDIO_TOKEN_RE   = re.compile(r'<\|[^|]*\|>')
CLOSING_KEYWORDS = ["shortlist", "dhanyavada", "call karegi interview", "1-2 din", "1-2 dina", "dhanyavada"]

def clean(text):
    return AUDIO_TOKEN_RE.sub('', text)

def percentile(data, p):
    if not data: return None
    s = sorted(data)
    idx = (len(s) - 1) * p / 100
    lo, hi = int(idx), min(int(idx) + 1, len(s) - 1)
    return round(s[lo] + (s[hi] - s[lo]) * (idx - lo), 1)

def load_wav_pcm(path):
    with wave.open(str(path), 'rb') as wf:
        assert wf.getnchannels() == 1,    f"{path}: must be mono"
        assert wf.getsampwidth() == 2,    f"{path}: must be 16-bit"
        assert wf.getframerate() == RATE, f"{path}: must be {RATE}Hz"
        return wf.readframes(wf.getnframes())

def save_wav(path, data):
    with wave.open(str(path), 'wb') as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(RATE)
        wf.writeframes(data)

SCREENING_PROMPT = """You are an HR executive at Supernan, a professional childcare company in Bangalore. Your name is Kavitha. You are conducting a screening call for a nanny position.

YOUR TONE AND MANNER:
- Sound like a real human HR person on a phone call - natural, slightly imperfect, not robotic.
- NEVER repeat the same acknowledgement twice in a row.
- Use SPOKEN colloquial Kannada, NOT written/textual Kannada.
- Mix Kannada with English naturally the way Bangaloreans actually talk.
- Same for Hindi: use natural spoken Hindi, not Doordarshan Hindi.
- Professional, confident, brisk.
- The opening is always in Hindi. After the candidate replies, detect their language and LOCK into it for the ENTIRE call.

SCREENING QUESTIONS (ask exactly in this order, one at a time):

1. OPENING (always in Hindi): "Namaste, main Kavitha, Supernan company se bol rahi hoon. Aapne nanny kaam ke liye apply kiya tha. Kuch basic sawaal hain, 2 minute lagenge. Aapka poora naam bata dijiye."

2. AREA:
   Hindi: "Aap Bangalore mein kahan rehti hain? Konsa area?"
   Kannada: "Neevu Bangalore alli elli irtira? Yaava area?"

3. EXPERIENCE:
   Hindi: "Baby care ka kitne saal ka experience hai? Aur jo sabse chota baccha tha, uski age kitni thi?"
   Kannada: "Baby care alli eshtu years experience ide? Neevu nodikondidda chikka magu eshtu tingalu itthu?"

4. AVAILABILITY:
   Hindi: "Kab se kaam shuru kar sakti hain? Full-time ya part-time chahiye?"
   Kannada: "Yaavaga kelsa shuru madabahudu? Full-time beku ya part-time?"

5. SALARY:
   Hindi: "Mahine ka kitna expect karti hain?"
   Kannada: "Tingalige eshtu expect madtira?"

AFTER ALL 5 QUESTIONS:
   Hindi: "Theek hai, aapki details note kar li hain. Agar aap shortlist hoti hain to hamaari team 1-2 din mein call karegi interview ke liye. Thank you."
   Kannada: "Sari, nimma details note madiddeevi. Shortlist aadre namma team 1-2 dina alli call madutare. Dhanyavada."

CRITICAL RULES:
- ONE question at a time.
- NEVER repeat the full opening/welcome message again after it has been said once."""


async def run_single_call(run_num, candidate_files, run_dir):
    from azure.core.credentials import AzureKeyCredential
    from azure.ai.voicelive.aio import connect

    loop         = asyncio.get_event_loop()
    running      = True
    turns        = []
    conv_trans   = []
    failures     = []

    cur_kav_text  = [""]
    cur_kav_audio = [b""]
    cur_stop_ms   = [None]
    cur_start_ms  = [None]

    kavitha_done  = asyncio.Event()
    agent_started = asyncio.Event()
    call_ended    = asyncio.Event()

    def fail(kind, detail="", turn=None):
        entry = {"kind": kind, "turn": turn, "detail": str(detail),
                 "timestamp_ms": round(loop.time() * 1000, 1)}
        failures.append(entry)
        print(f"  \033[91m[Run {run_num}] FAILURE {kind} turn={turn}: {str(detail)[:80]}\033[0m")

    async with connect(
        endpoint=ENDPOINT,
        credential=AzureKeyCredential(API_KEY),
        model=MODEL,
    ) as conn:

        await conn.send({
            "type": "session.update",
            "session": {
                "instructions":              SCREENING_PROMPT,
                "voice":                     {"name": "marin", "type": "openai"},
                "input_audio_format":        "pcm16",
                "output_audio_format":       "pcm16",
                "input_audio_transcription": {"model": "whisper-1"},
                "turn_detection":            None,
            },
        })

        while True:
            evt = await asyncio.wait_for(conn.recv(), timeout=10.0)
            if evt.get("type") == "session.updated":
                await conn.send({
                    "type": "response.create",
                    "response": {
                        "instructions": (
                            "Say ONLY these exact words, nothing else, no additions: "
                            "Namaste, main Kavitha, Supernan company se bol rahi hoon. "
                            "Aapne nanny kaam ke liye apply kiya tha. "
                            "Kuch basic sawaal hain, 2 minute lagenge. "
                            "Aapka poora naam bata dijiye."
                        )
                    },
                })
                break
            if evt.get("type") == "error":
                msg = evt.get("error", {}).get("message", "")
                fail("api_error", msg)
                return turns, conv_trans, failures

        async def recv_events():
            nonlocal running
            while running:
                try:
                    evt = await asyncio.wait_for(conn.recv(), timeout=20.0)
                    if evt is None:
                        running = False; call_ended.set(); break

                    t   = evt.get("type", "")
                    now = loop.time() * 1000

                    if t == "response.audio.delta":
                        cur_kav_audio[0] += base64.b64decode(evt.get("delta", ""))
                        if not agent_started.is_set():
                            cur_start_ms[0] = now
                            agent_started.set()

                    elif t == "response.audio_transcript.delta":
                        text = clean(evt.get("delta", ""))
                        if text:
                            cur_kav_text[0] += text
                            print(f"\033[94m  K: {text}\033[0m", end="", flush=True)

                    elif t == "response.audio_transcript.done":
                        print()
                        is_closing = any(kw in cur_kav_text[0].lower() for kw in CLOSING_KEYWORDS)
                        kavitha_done.set()
                        if is_closing:
                            await asyncio.sleep(2.0)
                            running = False; call_ended.set()

                    elif t == "conversation.item.input_audio_transcription.completed":
                        text = clean(evt.get("transcript", ""))
                        if text:
                            print(f"\033[92m  C: {text}\033[0m")
                            conv_trans.append({"speaker": "Candidate", "text": text})

                    elif t == "error":
                        msg = evt.get("error", {}).get("message", "")
                        fail("api_error", msg)
                        if "closed" in msg.lower():
                            running = False; call_ended.set()

                except asyncio.TimeoutError:
                    fail("recv_timeout", "no event received within 20s")
                    running = False; call_ended.set(); break
                except Exception as e:
                    fail("connection_drop", e)
                    running = False; call_ended.set(); break

        async def run_turns():
            nonlocal running

            try:
                await asyncio.wait_for(kavitha_done.wait(), timeout=TURN_DONE_TIMEOUT)
            except asyncio.TimeoutError:
                fail("timeout_turn0", "opening never completed", turn=0)
                running = False; call_ended.set(); return

            kav_path = run_dir / "kavitha_turn_0.wav"
            save_wav(kav_path, cur_kav_audio[0])
            conv_trans.append({"speaker": "Kavitha", "turn": 0, "text": cur_kav_text[0]})
            turns.append({
                "turn": 0, "label": "Opening",
                "kavitha_text": cur_kav_text[0],
                "kavitha_audio_file": str(kav_path),
                "candidate_file": None, "latency_ms": None, "status": "ok",
            })

            for i, wav_file in enumerate(candidate_files, start=1):
                if not running: break

                cur_kav_text[0]  = ""; cur_kav_audio[0] = b""
                cur_stop_ms[0]   = None; cur_start_ms[0] = None
                agent_started.clear(); kavitha_done.clear()

                cand_rec = run_dir / f"candidate_turn_{i}.wav"
                shutil.copy(wav_file, cand_rec)
                print(f"  \033[90m[Run {run_num}] Turn {i} -> {wav_file.name}\033[0m")
                conv_trans.append({"speaker": "Candidate", "turn": i, "audio_file": str(cand_rec)})

                pcm = load_wav_pcm(wav_file)
                chunks_sent = 0
                for offset in range(0, len(pcm), CHUNK * 2):
                    if not running: break
                    chunk = pcm[offset: offset + CHUNK * 2]
                    await conn.input_audio_buffer.append(audio=base64.b64encode(chunk).decode())
                    await asyncio.sleep(CHUNK / RATE / 4)
                    chunks_sent += 1

                if not running: break
                if chunks_sent == 0:
                    fail("empty_audio", f"no chunks sent for {wav_file.name}", turn=i); break

                cur_stop_ms[0] = loop.time() * 1000
                await conn.input_audio_buffer.commit()
                await conn.response.create()

                try:
                    await asyncio.wait_for(agent_started.wait(), timeout=AGENT_START_TIMEOUT)
                    latency = round(cur_start_ms[0] - cur_stop_ms[0], 1)
                    if latency < 0:
                        fail("negative_latency", f"{latency}ms", turn=i)
                    print(f"  \033[93m[Run {run_num}] Latency turn {i}: {latency}ms\033[0m")
                except asyncio.TimeoutError:
                    fail("timeout_agent_started", f"no response within {AGENT_START_TIMEOUT}s", turn=i)
                    latency = None
                    running = False; call_ended.set()

                try:
                    await asyncio.wait_for(kavitha_done.wait(), timeout=TURN_DONE_TIMEOUT)
                    turn_status = "ok"
                except asyncio.TimeoutError:
                    fail("timeout_kavitha_done", f"transcript never completed within {TURN_DONE_TIMEOUT}s", turn=i)
                    turn_status = "timeout"
                    running = False; call_ended.set()

                kav_path = run_dir / f"kavitha_turn_{i}.wav"
                save_wav(kav_path, cur_kav_audio[0])
                conv_trans.append({"speaker": "Kavitha", "turn": i, "text": cur_kav_text[0]})
                turns.append({
                    "turn": i, "label": f"Turn {i}",
                    "kavitha_text": cur_kav_text[0],
                    "kavitha_audio_file": str(kav_path),
                    "candidate_file": str(wav_file),
                    "latency_ms": latency, "status": turn_status,
                })

                if not running: break

            try:
                await asyncio.wait_for(call_ended.wait(), timeout=CALL_END_TIMEOUT)
            except asyncio.TimeoutError:
                fail("timeout_call_ended", "call_ended never fired")

        await asyncio.gather(
            asyncio.create_task(recv_events()),
            asyncio.create_task(run_turns()),
        )

    return turns, conv_trans, failures


async def main():
    if not API_KEY:
        print("ERROR: Set AZURE_VOICELIVE_API_KEY in .env"); sys.exit(1)

    candidate_files = sorted(AUDIO_DIR.glob("turn_*.wav"))
    if not candidate_files:
        print(f"ERROR: No WAV files in {AUDIO_DIR}/"); sys.exit(1)

    RECORDINGS_DIR.mkdir(exist_ok=True)

    print(f"\n{'='*60}")
    print(f"  SUPERNAN Test Harness - {TOTAL_RUNS} automated runs")
    print(f"  Candidate turns per call : {len(candidate_files)}")
    print(f"  Model                    : {MODEL}")
    print(f"  VAD mode                 : manual commit (no server VAD)")
    print(f"  Run timeout              : {RUN_TIMEOUT}s")
    print(f"{'='*60}\n")

    all_runs = []

    for run_num in range(1, TOTAL_RUNS + 1):
        print(f"\n{'─'*60}")
        print(f"  RUN {run_num} / {TOTAL_RUNS}")
        print(f"{'─'*60}")

        run_dir = RECORDINGS_DIR / f"run_{run_num:02d}"
        run_dir.mkdir(exist_ok=True)

        turns, transcript, failures, run_status = [], [], [], "ok"

        try:
            turns, transcript, failures = await asyncio.wait_for(
                run_single_call(run_num, candidate_files, run_dir),
                timeout=RUN_TIMEOUT,
            )
        except asyncio.TimeoutError:
            run_status = "run_timeout"
            failures = [{"kind": "run_timeout", "turn": None,
                         "detail": f"entire run exceeded {RUN_TIMEOUT}s", "timestamp_ms": None}]
        except Exception as e:
            run_status = "failed"
            failures = [{"kind": "exception", "turn": None, "detail": str(e), "timestamp_ms": None}]

        valid_lats = [t["latency_ms"] for t in turns
                      if t["latency_ms"] is not None and t["latency_ms"] > 0]

        if failures and run_status == "ok":
            run_status = "partial" if valid_lats else "failed"

        run_summary = {
            "avg_latency_ms":  round(sum(valid_lats) / len(valid_lats), 1) if valid_lats else None,
            "min_latency_ms":  round(min(valid_lats), 1) if valid_lats else None,
            "max_latency_ms":  round(max(valid_lats), 1) if valid_lats else None,
            "turns_completed": len([t for t in turns if t.get("status") == "ok"]),
            "failure_count":   len(failures),
        }

        run_data = {
            "run": run_num, "timestamp": datetime.now().isoformat(),
            "status": run_status, "turns": turns,
            "transcript": transcript, "failures": failures, "summary": run_summary,
        }
        all_runs.append(run_data)

        with open(run_dir / "report.json", "w", encoding="utf-8") as f:
            json.dump(run_data, f, ensure_ascii=False, indent=2)

        print(f"  Run {run_num} done - status: {run_status} | "
              f"avg latency: {run_summary['avg_latency_ms']}ms | "
              f"failures: {run_summary['failure_count']}")

        if run_num < TOTAL_RUNS:
            await asyncio.sleep(2.0)

    all_valid_lats = [
        t["latency_ms"] for run in all_runs for t in run["turns"]
        if t["latency_ms"] is not None and t["latency_ms"] > 0
    ]

    per_turn_stats = []
    for i in range(1, len(candidate_files) + 1):
        lats = [t["latency_ms"] for run in all_runs for t in run["turns"]
                if t["turn"] == i and t["latency_ms"] is not None and t["latency_ms"] > 0]
        per_turn_stats.append({
            "turn": i, "samples": len(lats),
            "avg_ms": round(sum(lats)/len(lats), 1) if lats else None,
            "p50_ms": percentile(lats, 50), "p95_ms": percentile(lats, 95),
            "min_ms": round(min(lats), 1) if lats else None,
            "max_ms": round(max(lats), 1) if lats else None,
        })

    all_failures = [f for run in all_runs for f in run["failures"]]
    failure_kinds = dict(Counter(f["kind"] for f in all_failures))

    outlier_threshold = None
    outlier_count = 0
    if len(all_valid_lats) >= 3:
        mean_lat = statistics.mean(all_valid_lats)
        stdev_lat = statistics.stdev(all_valid_lats)
        outlier_threshold = round(mean_lat + 3 * stdev_lat, 1)
        outlier_count = sum(1 for x in all_valid_lats if x > outlier_threshold)

    overall_summary = {
        "total_runs":           TOTAL_RUNS,
        "runs_clean":           sum(1 for r in all_runs if r["status"] == "ok"),
        "runs_partial":         sum(1 for r in all_runs if r["status"] == "partial"),
        "runs_failed":          sum(1 for r in all_runs if r["status"] in ("failed","run_timeout")),
        "total_failures":       len(all_failures),
        "failure_kinds":        failure_kinds,
        "total_turns_measured": len(all_valid_lats),
        "overall_avg_ms":       round(sum(all_valid_lats)/len(all_valid_lats), 1) if all_valid_lats else None,
        "overall_p50_ms":       percentile(all_valid_lats, 50),
        "overall_p95_ms":       percentile(all_valid_lats, 95),
        "overall_min_ms":       round(min(all_valid_lats), 1) if all_valid_lats else None,
        "overall_max_ms":       round(max(all_valid_lats), 1) if all_valid_lats else None,
        "outlier_threshold_ms": outlier_threshold,
        "outlier_count":        outlier_count,
        "per_run_avg_ms":       [r["summary"]["avg_latency_ms"] for r in all_runs],
        "per_turn_stats":       per_turn_stats,
    }

    final_report = {
        "generated": datetime.now().isoformat(), "model": MODEL,
        "vad_mode": "manual_commit", "runs": all_runs,
        "overall_summary": overall_summary,
    }

    with open("test_report.json", "w", encoding="utf-8") as f:
        json.dump(final_report, f, ensure_ascii=False, indent=2)

    o = overall_summary
    print(f"\n{'='*60}")
    print(f"  ALL {TOTAL_RUNS} RUNS COMPLETE")
    print(f"  Clean: {o['runs_clean']}  Partial: {o['runs_partial']}  Failed: {o['runs_failed']}")
    print(f"  Total failures : {o['total_failures']}  {o['failure_kinds']}")
    print(f"  Overall avg    : {o['overall_avg_ms']} ms")
    print(f"  Overall P50    : {o['overall_p50_ms']} ms")
    print(f"  Overall P95    : {o['overall_p95_ms']} ms")
    print(f"  Overall min    : {o['overall_min_ms']} ms")
    print(f"  Overall max    : {o['overall_max_ms']} ms")
    if o["outlier_threshold_ms"]:
        print(f"  Outliers       : {o['outlier_count']} (>{o['outlier_threshold_ms']}ms)")
    print(f"  Report         : test_report.json")
    print(f"{'='*60}\n")


asyncio.run(main())
