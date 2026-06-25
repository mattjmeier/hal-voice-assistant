from __future__ import annotations

import logging
import wave
from collections.abc import Iterable
from dataclasses import dataclass
from io import BytesIO

import requests

from hal.config import Config

LOGGER = logging.getLogger(__name__)


class PiperError(RuntimeError):
    pass


@dataclass(frozen=True)
class PcmAudio:
    chunks: Iterable[bytes]
    sample_rate: int


class PiperClient:
    def __init__(self, config: Config):
        self.config = config

    def get_info(self) -> dict:
        try:
            response = requests.get(
                f"{self.config.piper_url}/info",
                timeout=self.config.network_timeout_seconds,
            )
            response.raise_for_status()
            data = response.json()
        except (ValueError, requests.RequestException) as exc:
            raise PiperError(f"Piper info request failed: {exc}") from exc
        if not isinstance(data, dict):
            raise PiperError("Piper info response was not a JSON object")
        return data

    def synthesize(self, text: str) -> PcmAudio:
        try:
            response = requests.post(
                f"{self.config.piper_url}/synthesize",
                json={"text": text},
                timeout=self.config.network_timeout_seconds,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            LOGGER.error("Piper synthesis failed: %s", exc)
            raise PiperError(f"Piper synthesis failed: {exc}") from exc

        try:
            with wave.open(BytesIO(response.content), "rb") as wav_file:
                if wav_file.getnchannels() != 1 or wav_file.getsampwidth() != 2:
                    raise PiperError(
                        "Piper returned unsupported WAV format: "
                        f"{wav_file.getnchannels()} channels, {wav_file.getsampwidth()} bytes"
                    )
                sample_rate = wav_file.getframerate()
                pcm = wav_file.readframes(wav_file.getnframes())
        except (EOFError, wave.Error) as exc:
            raise PiperError(f"Piper returned invalid WAV audio: {exc}") from exc

        def chunks() -> Iterable[bytes]:
            for offset in range(0, len(pcm), 4096):
                yield pcm[offset : offset + 4096]

        return PcmAudio(chunks=chunks(), sample_rate=sample_rate)
