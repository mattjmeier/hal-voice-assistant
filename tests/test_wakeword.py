from __future__ import annotations

import sys
import threading
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np

from hal.wakeword import FRAME_SAMPLES, WakeWordListener


class WakeWordListenerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.model_file = Path(__file__).with_name("wakeword-test.onnx")
        self.model_file.touch()
        self.config = SimpleNamespace(
            wakeword_disabled=False,
            openwakeword_model_path=self.model_file,
            openwakeword_threshold=0.5,
            wake_sample_rate=16000,
        )

    def tearDown(self) -> None:
        self.model_file.unlink(missing_ok=True)

    def test_returns_false_without_opening_audio_when_stop_was_already_requested(self) -> None:
        stop_requested = threading.Event()
        stop_requested.set()
        model = self._install_model({"hey-hal": 0.0})
        _audio, _stream, pyaudio = self._audio()

        with (
            patch("hal.wakeword._pyaudio", return_value=pyaudio),
            patch("hal.wakeword._resolve_device", return_value=3),
        ):
            detected = WakeWordListener(self.config).wait_for_wake_word(stop_requested)

        self.assertFalse(detected)
        model.predict.assert_not_called()
        pyaudio.PyAudio.assert_not_called()

    def test_detects_score_at_configured_threshold_and_closes_audio(self) -> None:
        model = self._install_model({"hey-hal": 0.7})
        audio, stream, pyaudio = self._audio()
        stream.read.return_value = bytes(FRAME_SAMPLES * 2)

        with (
            patch("hal.wakeword._pyaudio", return_value=pyaudio),
            patch("hal.wakeword._resolve_device", return_value=3),
        ):
            detected = WakeWordListener(self.config).wait_for_wake_word()

        self.assertTrue(detected)
        model.predict.assert_called_once()
        samples = model.predict.call_args.args[0]
        self.assertEqual(samples.dtype, np.int16)
        self.assertEqual(len(samples), FRAME_SAMPLES)
        audio.open.assert_called_once_with(
            format=pyaudio.paInt16,
            channels=1,
            rate=16000,
            input=True,
            input_device_index=3,
            frames_per_buffer=FRAME_SAMPLES,
        )
        stream.stop_stream.assert_called_once()
        stream.close.assert_called_once()
        audio.terminate.assert_called_once()

    def _install_model(self, prediction: dict[str, float]) -> MagicMock:
        model = MagicMock()
        model.predict.return_value = prediction
        model_class = MagicMock(return_value=model)
        package = ModuleType("openwakeword")
        module = ModuleType("openwakeword.model")
        module.Model = model_class
        package.model = module
        self.addCleanup(sys.modules.pop, "openwakeword.model", None)
        self.addCleanup(sys.modules.pop, "openwakeword", None)
        sys.modules["openwakeword"] = package
        sys.modules["openwakeword.model"] = module
        return model

    @staticmethod
    def _audio() -> tuple[MagicMock, MagicMock, SimpleNamespace]:
        stream = MagicMock()
        stream.is_active.return_value = True
        audio = MagicMock()
        audio.open.return_value = stream
        pyaudio = SimpleNamespace(paInt16=8, PyAudio=MagicMock(return_value=audio))
        return audio, stream, pyaudio


if __name__ == "__main__":
    unittest.main()
