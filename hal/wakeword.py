from __future__ import annotations

import logging
import threading
from array import array

from hal.audio import _pyaudio, _resolve_device
from hal.config import Config

LOGGER = logging.getLogger(__name__)


class WakeWordListener:
    def __init__(self, config: Config):
        self.config = config

    def wait_for_wake_word(self, stop_requested: threading.Event | None = None) -> bool:
        if self.config.wakeword_disabled:
            try:
                input("Press Enter to simulate wake word...")
                return True
            except EOFError:
                return False

        if not self.config.picovoice_key or not self.config.picovoice_model_path:
            raise RuntimeError("PICOVOICE_KEY and PICOVOICE_MODEL_PATH are required")
        try:
            import pvporcupine
        except ImportError as exc:
            raise RuntimeError(
                "pvporcupine is required when wake-word detection is enabled"
            ) from exc

        porcupine = None
        audio = None
        stream = None
        try:
            porcupine = pvporcupine.create(
                access_key=self.config.picovoice_key,
                keyword_paths=[self.config.picovoice_model_path],
            )
            pyaudio = _pyaudio()
            audio = pyaudio.PyAudio()
            device_index = _resolve_device(self.config, for_input=True, audio=audio)
            stream = audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=porcupine.sample_rate,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=porcupine.frame_length,
            )
            LOGGER.info("Listening for wake word on audio device %s", device_index)
            while stop_requested is None or not stop_requested.is_set():
                raw = stream.read(porcupine.frame_length, exception_on_overflow=False)
                pcm = array("h")
                pcm.frombytes(raw)
                if porcupine.process(pcm) >= 0:
                    LOGGER.info("Wake word detected")
                    return True
            return False
        finally:
            if stream is not None:
                if stream.is_active():
                    stream.stop_stream()
                stream.close()
            if audio is not None:
                audio.terminate()
            if porcupine is not None:
                porcupine.delete()
