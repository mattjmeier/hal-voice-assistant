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

    def _url(self, path: str) -> str:
        normalized = path if path.startswith("/") else f"/{path}"
        return f"{self.config.piper_url}{normalized}"

    def get_info(self) -> dict:
        path = getattr(self.config, "piper_info_path", "/voices")
        try:
            response = requests.get(
                self._url(path),
                timeout=self.config.network_timeout_seconds,
            )
            response.raise_for_status()
            data = response.json()
        except (ValueError, requests.RequestException) as exc:
            raise PiperError(f"Piper probe request failed: {exc}") from exc
        if isinstance(data, dict):
            return data
        if isinstance(data, list):
            return {"voices": data}
        raise PiperError("Piper probe response was not a JSON object or array")

    def synthesize(self, text: str) -> PcmAudio:
        path = getattr(self.config, "piper_synthesize_path", "/")
        try:
            response = requests.post(
                self._url(path),
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
