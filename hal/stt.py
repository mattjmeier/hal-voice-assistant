from __future__ import annotations

import json
import logging
from pathlib import Path
import wave

from websocket import create_connection

from hal.config import Config

LOGGER = logging.getLogger(__name__)


class VoskClient:
    def __init__(self, config: Config):
        self.config = config

    def transcribe_wav(self, wav_path: Path) -> str:
        websocket = None
        final_transcripts: list[str] = []
        latest_partial = ""
        try:
            websocket = create_connection(
                self.config.vosk_url,
                timeout=self.config.network_timeout_seconds,
            )
            with wave.open(str(wav_path), "rb") as wav_file:
                websocket.send(json.dumps({"config": {"sample_rate": wav_file.getframerate()}}))
                frames_per_chunk = max(1, int(wav_file.getframerate() * 0.2))
                while data := wav_file.readframes(frames_per_chunk):
                    websocket.send_binary(data)
                    latest_partial = self._read_response(
                        websocket.recv(), final_transcripts, latest_partial
                    )
                websocket.send(json.dumps({"eof": 1}))
                latest_partial = self._read_response(
                    websocket.recv(), final_transcripts, latest_partial
                )
        except Exception as exc:
            LOGGER.exception("Vosk transcription failed")
            raise RuntimeError(f"Vosk transcription failed: {exc}") from exc
        finally:
            if websocket is not None:
                websocket.close()

        transcript = " ".join(final_transcripts).strip() or latest_partial.strip()
        LOGGER.info("Vosk transcript: %s", transcript or "<empty>")
        return transcript

    @staticmethod
    def _read_response(raw, finals: list[str], current_partial: str) -> str:
        try:
            data = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            LOGGER.debug("Ignoring invalid Vosk response: %r", raw)
            return current_partial
        text = str(data.get("text", "")).strip()
        if text:
            finals.append(text)
        partial = str(data.get("partial", "")).strip()
        return partial or current_partial
