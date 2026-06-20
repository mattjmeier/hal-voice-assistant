from __future__ import annotations

import logging
import threading
from pathlib import Path

from hal.audio import _pyaudio, _resolve_device
from hal.config import Config

LOGGER = logging.getLogger(__name__)
FRAME_SAMPLES = 1280  # openWakeWord's preferred 80 ms frame at 16 kHz.
RUNTIME_MODEL_DIR = Path(__file__).resolve().parent.parent / "models" / "openwakeword"


class WakeWordListener:
    def __init__(self, config: Config):
        self.config = config
        self._model = None

    def wait_for_wake_word(self, stop_requested: threading.Event | None = None) -> bool:
        if stop_requested is not None and stop_requested.is_set():
            return False
        if self.config.wakeword_disabled:
            try:
                input("Press Enter to simulate wake word...")
                return True
            except EOFError:
                return False

        model_path = Path(self.config.openwakeword_model_path)
        if not model_path.is_file():
            raise RuntimeError(
                f"openWakeWord model not found at {model_path}. "
                "Provide an ONNX model with OPENWAKEWORD_MODEL_PATH."
            )
        melspec_model_path = RUNTIME_MODEL_DIR / "melspectrogram.onnx"
        embedding_model_path = RUNTIME_MODEL_DIR / "embedding_model.onnx"
        for runtime_model_path in (melspec_model_path, embedding_model_path):
            if not runtime_model_path.is_file():
                raise RuntimeError(f"openWakeWord runtime model not found at {runtime_model_path}")
        try:
            import numpy as np
            from openwakeword.model import Model
        except ImportError as exc:
            raise RuntimeError(
                "openwakeword and numpy are required when wake-word detection is enabled"
            ) from exc

        audio = None
        stream = None
        try:
            if self._model is None:
                self._model = Model(
                    wakeword_models=[str(model_path)],
                    inference_framework="onnx",
                    melspec_model_path=str(melspec_model_path),
                    embedding_model_path=str(embedding_model_path),
                )
            else:
                self._model.reset()
            model = self._model
            pyaudio = _pyaudio()
            audio = pyaudio.PyAudio()
            device_index = _resolve_device(self.config, for_input=True, audio=audio)
            stream = audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.config.wake_sample_rate,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=FRAME_SAMPLES,
            )
            LOGGER.info(
                "Listening for wake word on audio device %s with model %s",
                device_index,
                model_path.name,
            )
            while stop_requested is None or not stop_requested.is_set():
                raw = stream.read(FRAME_SAMPLES, exception_on_overflow=False)
                scores = model.predict(np.frombuffer(raw, dtype=np.int16))
                score = max(scores.values(), default=0.0)
                if score >= self.config.openwakeword_threshold:
                    LOGGER.info("Wake word detected (score %.3f)", score)
                    return True
            return False
        finally:
            if stream is not None:
                if stream.is_active():
                    stream.stop_stream()
                stream.close()
            if audio is not None:
                audio.terminate()
