import asyncio, base64, logging, os, sys, re, struct, random
from dotenv import load_dotenv
load_dotenv()

ENDPOINT = os.getenv("AZURE_VOICELIVE_ENDPOINT", "https://seerfish-resource.services.ai.azure.com")
API_KEY = os.getenv("AZURE_VOICELIVE_API_KEY", "")
MODEL = os.getenv("AZURE_VOICELIVE_MODEL", "gpt-realtime-1.5")

AUDIO_TOKEN_RE = re.compile(r'<\|[^|]*\|>')
def clean(text):
    return AUDIO_TOKEN_RE.sub('', text)

SCREENING_PROMPT = """You are an HR executive at Supernan, a professional childcare company in Bangalore. Your name is Kavitha. You are conducting a screening call for a nanny position.

YOUR TONE AND MANNER:
- Sound like a real human HR person on a phone call â natural, slightly imperfect, not robotic. Use small fillers like "haan", "achha", "hmm", "okay" naturally between responses.
- NEVER repeat the same acknowledgement twice in a row. Vary it naturally based on the language:
  Hindi: "haan", "achha", "okay samjhi", "theek hai", "haan haan", sometimes nothing â just move on.
  Kannada: "sari", "achha", "okay", "haan sari", "gothaaytu", sometimes nothing â just move on.
- When speaking Hindi or Kannada, use a natural Indian accent and cadence. Sound like a professional woman from Bangalore on a work call.
- CRITICAL: Use SPOKEN colloquial Kannada, NOT written/textual Kannada. Say "hegidira" not "hege iddiri". Say "yenu beku" not "yenu beku ennuva". Say "kelsa" not "kaarya". Say "hogbeku" not "hoagabeku". Use the shortened everyday forms that people actually say on phone calls in Bangalore.
- Mix Kannada with English naturally the way Bangaloreans actually talk: "area yavdu?", "experience eshtu years?", "salary expectation eshtu?". Do not speak pure Kannada. Real Bangalore phone calls are 60% Kannada 40% English.
- Same for Hindi: use natural spoken Hindi, not Doordarshan Hindi. "Kitne saal ka experience hai" not "aapka anubhav kitne varshon ka hai".
- Professional, confident, brisk. You sound like a busy HR person at a real company. Not rude, but clearly in charge.
- You set the pace. You ask questions, she answers. Not the other way around.
- Use "aap" (respectful) but never "akka", never "didi". Address her by name once she gives it naturally in conversation.
- Rephrase questions naturally each time â don't read from a script. Keep the intent but vary the wording slightly like a real person would.
- If she rambles, politely cut: Hindi: "Haan haan, samajh gayi. Aage chalte hain." / Kannada: "Sari sari, gothaaytu. Mundhe hogona."
- If she asks questions back, answer briefly and redirect: Hindi: "Wo baad mein batate hain. Pehle aap bataiye..." / Kannada: "Adu mundhe heltivi. Modalu neevu heli..."
- The opening is always in Hindi. After the candidate replies, detect their language and LOCK into it for the ENTIRE call â every single question, acknowledgement, nudge, and the closing message must be in that same language. If they reply in Hindi, speak ONLY Hindi from that point till the end. If they reply in Kannada, speak ONLY Kannada from that point till the end. Never switch or mix languages after this point, not even for the closing.

SCREENING QUESTIONS (ask exactly in this order, one at a time):

1. OPENING (always in Hindi): "Namaste, main Kavitha, Supernan company se bol rahi hoon. Aapne nanny kaam ke liye apply kiya tha. Kuch basic sawaal hain, 2 minute lagenge. Aapka poora naam bata dijiye."

2. AREA:
   Hindi: "Aap Bangalore mein kahan rehti hain? Konsa area?"
   Kannada: "Neevu Bangalore alli elli irtira? Yaava area?"
   (If she names a very far area, note it but move on.)

3. EXPERIENCE:
   Hindi: "Baby care ka kitne saal ka experience hai? Aur jo sabse chota baccha tha, uski age kitni thi?"
   Kannada: "Baby care alli eshtu years experience ide? Neevu nodikondidda chikka magu eshtu tingalu itthu?"
   (Both parts in one question. If she only answers one, ask the other.)

4. AVAILABILITY:
   Hindi: "Kab se kaam shuru kar sakti hain? Full-time ya part-time chahiye?"
   Kannada: "Yaavaga kelsa shuru madabahudu? Full-time beku ya part-time?"
   (Get specific date or timeline. If vague â Hindi: "Exact bataiye." / Kannada: "Exact heli.")

5. SALARY:
   Hindi: "Mahine ka kitna expect karti hain?"
   Kannada: "Tingalige eshtu expect madtira?"
   (If she says "you tell me" â Hindi: "Hamari range 12 se 25 hazaar hai. Aapki expectation kya hai?" / Kannada: "Namma range 12 rinda 25 thousand. Nimma expectation eshtu?")

AFTER ALL 5 QUESTIONS:
   Hindi: "Theek hai, aapki details note kar li hain. Agar aap shortlist hoti hain to hamaari team 1-2 din mein call karegi interview ke liye. Thank you."
   Kannada: "Sari, nimma details note madiddeevi. Shortlist aadre namma team 1-2 dina alli call madutare. Dhanyavada."
   Hang up tone. Do not linger.

CRITICAL RULES:
- ONE question at a time. Wait for answer. Then next.
- Do NOT be warm, encouraging, or chatty. Be polite but efficient. She should feel this is a real company call.
- Do NOT say things like "bahut achha!", "wonderful!", "great answer!". Just acknowledge briefly in the detected language and move to next.
- Do NOT ask how she is feeling or if she is comfortable. This is a screening call, not therapy.
- If she gives vague answers, press once firmly.
- If she cannot answer basic questions, still complete the call professionally but note it.
- Total call should be under 2 minutes. You are busy. She should feel that.
- NEVER repeat the full opening/welcome message again after it has been said once. If the candidate says something unclear like "hello", just repeat ONLY the last question you asked."""

async def main():
    if not API_KEY:
        print("ERROR: Set AZURE_VOICELIVE_API_KEY in .env"); sys.exit(1)

    import pyaudio
    from azure.core.credentials import AzureKeyCredential
    from azure.ai.voicelive.aio import connect

    pa = pyaudio.PyAudio()
    RATE, CHUNK = 24000, 1024
    mic = pa.open(format=pyaudio.paInt16, channels=1, rate=RATE, input=True, frames_per_buffer=CHUNK)
    spk = pa.open(format=pyaudio.paInt16, channels=1, rate=RATE, output=True, frames_per_buffer=CHUNK)

    print(f"\n{'='*60}")
    print(f"  SUPERNAN Nanny Screening Agent")
    print(f"  Agent: Kavitha (HR Executive)")
    print(f"  Model: {MODEL}  |  WEAR HEADPHONES")
    print(f"  Ctrl+C to stop.")
    print(f"{'='*60}\n")

    running = True
    audio_queue = asyncio.Queue()
    muted = False
    last_kavitha_done = [None]
    candidate_spoke = [False]
    last_nudge_time = [None]
    kavitha_speaking = [False]
    current_transcript = [""]
    SILENCE_TIMEOUT = 8.0
    NUDGE_COOLDOWN = 12.0
    CLOSING_KEYWORDS = ["shortlist", "dhanyavada", "call karegi interview", "1-2 din", "1-2 dina"]

    async with connect(
        endpoint=ENDPOINT,
        credential=AzureKeyCredential(API_KEY),
        model=MODEL,
    ) as conn:
        await conn.send({
            "type": "session.update",
            "session": {
                "instructions": SCREENING_PROMPT,
                "voice": {"name": "marin", "type": "openai"},
                "input_audio_format": "pcm16",
                "output_audio_format": "pcm16",
                "input_audio_transcription": {"model": "whisper-1"},
                "turn_detection": {
                    "type": "server_vad",
                    "threshold": 0.8,
                    "prefix_padding_ms": 500,
                    "silence_duration_ms": 500,
                    "interrupt_response": True,
                },
            },
        })

        while True:
            evt = await asyncio.wait_for(conn.recv(), timeout=10.0)
            if evt.get("type") == "session.updated":
                print("  Kavitha is ready. Starting screening call.\n")
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
                print(f"  [Error] {evt.get('error',{}).get('message')}"); return

        async def send_audio():
            nonlocal running
            while running:
                try:
                    data = await asyncio.to_thread(mic.read, CHUNK, False)
                    await conn.input_audio_buffer.append(audio=base64.b64encode(data).decode())
                    await asyncio.sleep(0.01)
                except Exception:
                    running = False; break

        NOISE_LEVEL = 60
        SILENCE_CHUNK = CHUNK * 2

        def mix_noise(chunk):
            samples = struct.unpack_from(f'{len(chunk)//2}h', chunk)
            noisy = [max(-32768, min(32767, s + random.randint(-NOISE_LEVEL, NOISE_LEVEL))) for s in samples]
            return struct.pack(f'{len(noisy)}h', *noisy)

        def make_noise(size):
            samples = [random.randint(-NOISE_LEVEL, NOISE_LEVEL) for _ in range(size // 2)]
            return struct.pack(f'{len(samples)}h', *samples)

        async def play_audio():
            nonlocal muted
            while running:
                try:
                    chunk = await asyncio.wait_for(audio_queue.get(), timeout=0.05)
                    if muted:
                        await asyncio.to_thread(spk.write, make_noise(len(chunk)))
                    else:
                        await asyncio.to_thread(spk.write, mix_noise(chunk))
                except asyncio.TimeoutError:
                    await asyncio.to_thread(spk.write, make_noise(SILENCE_CHUNK))

        async def recv_events():
            nonlocal running, muted
            while running:
                try:
                    evt = await conn.recv()
                    if evt is None:
                        print("\n  [Session ended]"); running = False; break
                    t = evt.get("type", "")

                    if t == "response.audio.delta":
                        if not muted:
                            audio_queue.put_nowait(base64.b64decode(evt.get("delta", "")))

                    elif t == "response.audio_transcript.delta":
                        text = clean(evt.get("delta", ""))
                        if text:
                            current_transcript[0] += text
                            print(f"\033[94mKavitha: {text}\033[0m", end="", flush=True)

                    elif t == "response.audio_transcript.done":
                        print()
                        kavitha_speaking[0] = False
                        if any(kw in current_transcript[0].lower() for kw in CLOSING_KEYWORDS):
                            while not audio_queue.empty():
                                await asyncio.sleep(0.2)
                            await asyncio.sleep(3.0)
                            running = False; break
                        current_transcript[0] = ""
                        if candidate_spoke[0]:
                            last_kavitha_done[0] = asyncio.get_event_loop().time()

                    elif t == "conversation.item.input_audio_transcription.completed":
                        text = clean(evt.get("transcript", ""))
                        if text:
                            print(f"\033[92mCandidate: {text}\033[0m")

                    elif t == "input_audio_buffer.speech_started":
                        candidate_spoke[0] = True
                        last_kavitha_done[0] = None
                        muted = True
                        while not audio_queue.empty():
                            try: audio_queue.get_nowait()
                            except: break
                        print(f"\n\033[93m  [interrupted]\033[0m")

                    elif t == "response.created":
                        kavitha_speaking[0] = True
                        muted = False

                    elif t == "error":
                        msg = evt.get('error',{}).get('message','')
                        print(f"\n[Error] {msg}")
                        if "closed" in msg.lower():
                            running = False; break

                except Exception:
                    running = False; break

        async def silence_watchdog():
            while running:
                await asyncio.sleep(1.0)
                t0 = last_kavitha_done[0]
                if t0 is not None and candidate_spoke[0] and not kavitha_speaking[0]:
                    now = asyncio.get_event_loop().time()
                    if last_nudge_time[0] is not None and now - last_nudge_time[0] < NUDGE_COOLDOWN:
                        continue
                    elapsed = now - t0
                    if elapsed > SILENCE_TIMEOUT:
                        last_kavitha_done[0] = None
                        last_nudge_time[0] = now
                        try:
                            await conn.send({
                                "type": "response.create",
                                "response": {
                                    "instructions": (
                                        "The candidate has been silent. "
                                        "In whichever language you have been using, say briefly: "
                                        "Hindi: 'Sorry, mujhe sunai nahi diya. Dobara boliye please.' "
                                        "Kannada: 'Sorry, nanage kelisuttilla. Ondu sari heli please.' "
                                        "Do NOT repeat the full welcome. Just say this one line and wait."
                                    )
                                },
                            })
                        except Exception:
                            pass

        try:
            await asyncio.gather(
                asyncio.create_task(send_audio()),
                asyncio.create_task(play_audio()),
                asyncio.create_task(recv_events()),
                asyncio.create_task(silence_watchdog()),
            )
        except KeyboardInterrupt:
            pass
        finally:
            running = False
            try: mic.stop_stream(); mic.close()
            except: pass
            try: spk.stop_stream(); spk.close()
            except: pass
            pa.terminate()
            print("\nScreening session ended.")

asyncio.run(main())
