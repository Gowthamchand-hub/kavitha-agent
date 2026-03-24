"""
Custom LiveKit TTS plugin for Sarvam AI (bulbul:v1, Hindi)
Compatible with livekit-agents >= 1.5
"""

from __future__ import annotations

import base64
import io
import os
import wave

import aiohttp

from livekit.agents import tts, APIConnectOptions
from livekit.agents.tts import ChunkedStream
from livekit.agents.tts.tts import AudioEmitter

SARVAM_TTS_URL = "https://api.sarvam.ai/text-to-speech"


class SarvamTTS(tts.TTS):
    def __init__(
        self,
        *,
        api_key: str | None = None,
        language: str = "hi-IN",
        speaker: str = "anushka",
        model: str = "bulbul:v2",
        pace: float = 0.9,
        loudness: float = 1.5,
    ) -> None:
        super().__init__(
            capabilities=tts.TTSCapabilities(streaming=False),
            sample_rate=22050,
            num_channels=1,
        )
        self._api_key  = api_key or os.getenv("SARVAM_API_KEY", "")
        self._language = language
        self._speaker  = speaker
        self._model    = model
        self._pace     = pace
        self._loudness = loudness

    def synthesize(
        self,
        text: str,
        *,
        conn_options: APIConnectOptions = APIConnectOptions(),
    ) -> ChunkedStream:
        return SarvamChunkedStream(
            tts=self,
            input_text=text,
            conn_options=conn_options,
        )


class SarvamChunkedStream(ChunkedStream):
    def __init__(self, *, tts: SarvamTTS, input_text: str, conn_options: APIConnectOptions) -> None:
        super().__init__(tts=tts, input_text=input_text, conn_options=conn_options)
        self._sarvam: SarvamTTS = tts

    async def _run(self, output_emitter: AudioEmitter) -> None:
        import uuid
        payload = {
            "inputs":               [self._input_text],
            "target_language_code": self._sarvam._language,
            "speaker":              self._sarvam._speaker,
            "model":                self._sarvam._model,
            "pitch":                0,
            "pace":                 self._sarvam._pace,
            "loudness":             self._sarvam._loudness,
            "speech_sample_rate":   22050,
            "enable_preprocessing": True,
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                SARVAM_TTS_URL,
                headers={
                    "api-subscription-key": self._sarvam._api_key,
                    "Content-Type":         "application/json",
                },
                json=payload,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                resp.raise_for_status()
                data      = await resp.json()
                wav_bytes = base64.b64decode(data["audios"][0])

        # Strip WAV header, emit raw PCM
        with wave.open(io.BytesIO(wav_bytes)) as wf:
            sample_rate = wf.getframerate()
            raw_pcm     = wf.readframes(wf.getnframes())

        output_emitter.initialize(
            request_id=str(uuid.uuid4()),
            sample_rate=sample_rate,
            num_channels=1,
            mime_type="audio/pcm",
        )
        output_emitter.push(raw_pcm)
        output_emitter.flush()
