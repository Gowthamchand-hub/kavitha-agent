#!/usr/bin/env python3
"""
Route D — LiveKit Agent (livekit-agents v1.5+)
================================================
Pipeline:  Groq Whisper (Hindi STT)  →  Groq Llama 3.3 70B  →  Sarvam TTS
Phone:     Exotel SIP trunk  →  LiveKit room  →  this agent

Run in dev mode (browser mic, no phone):
    python agent.py dev

Run as production worker:
    python agent.py start
"""

import os
import sys

from dotenv import load_dotenv
from livekit.agents import WorkerOptions, cli
from livekit.agents.voice import Agent, AgentSession
from livekit.plugins import groq, silero

load_dotenv()

# Add route_d to path so sarvam_tts can be imported
sys.path.insert(0, os.path.dirname(__file__))


# ── Screening system prompt ────────────────────────────────────────────────────
SYSTEM_PROMPT = (
    "You are Kavitha, a female SuperNanny recruitment agent doing a phone screening interview with a nanny candidate. "
    "You are a woman — always use feminine Hindi forms: 'thi', 'kar rahi hoon', 'bol rahi hoon', 'samajh rahi hoon', 'chahti hoon'. "
    "Never use masculine forms like 'tha', 'karta hoon', 'bol raha hoon'. "

    "Speak in Hindi, but use English words naturally where Hindi speakers do — "
    "words like 'experience', 'available', 'salary', 'live-in', 'full-time', 'part-time', 'location', 'confirm'. "
    "Everything else in Hindi. Do NOT speak full English sentences. "

    "Sound like a real human on a phone call — vary your responses every time. "
    "Use natural fillers and reactions: 'Hmm...', 'Achha...', 'Haan ji...', 'Theek hai...', 'Bilkul...', 'Wah, achha hai...', 'Samajh gayi...'. "
    "Add short natural pauses with '...' mid-sentence when thinking. "
    "Sometimes react warmly: 'Oh, bahut achha!', 'Great, yeh toh bahut helpful hai.' "
    "NEVER start two consecutive responses with the same word or phrase. "
    "Vary your sentence structure — sometimes short, sometimes a little longer. "

    "Ask ONE question at a time. Cover in order: name, age, location, childcare experience, availability, expected salary, live-in. "
    "Do NOT use emotion tags like [warm] or [excited]. "
    "Do NOT repeat the same acknowledgment twice in a row."
)


# ── Build TTS engine ───────────────────────────────────────────────────────────
def get_tts():
    from sarvam_tts import SarvamTTS
    print("[Route D] TTS: Sarvam AI bulbul:v2 (anushka, hi-IN)")
    return SarvamTTS(language="hi-IN", speaker="anushka")


# ── Agent entrypoint ───────────────────────────────────────────────────────────
async def entrypoint(ctx):
    session = AgentSession(
        vad=silero.VAD.load(),
        stt=groq.STT(model="whisper-large-v3", language="hi"),
        llm=groq.LLM(model="llama-3.3-70b-versatile"),
        tts=get_tts(),
        allow_interruptions=True,
        min_endpointing_delay=0.5,
        max_endpointing_delay=3.0,
    )

    agent = Agent(instructions=SYSTEM_PROMPT)

    await ctx.connect()
    await session.start(agent, room=ctx.room)

    await session.say(
        "Namaste! Main Kavitha bol rahi hoon, SuperNanny ki taraf se. "
        "Kya aap abhi baat kar sakti hain?",
        allow_interruptions=True,
    )


# ── Worker entry ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            agent_name="supernanny",
            api_key=os.getenv("LIVEKIT_API_KEY"),
            api_secret=os.getenv("LIVEKIT_API_SECRET"),
            ws_url=os.getenv("LIVEKIT_URL"),
        )
    )
