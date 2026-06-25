from __future__ import annotations

import unittest
import wave
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from hal.tts import PiperClient, PiperError


class PiperClientTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = SimpleNamespace(
            piper_url="http://piper.local:5000",
            network_timeout_seconds=5,
        )

    def test_get_info_calls_info_endpoint(self) -> None:
        response = MagicMock()
        response.json.return_value = {"voice": "test"}

        with patch("hal.tts.requests.get", return_value=response) as get:
            info = PiperClient(self.config).get_info()

        self.assertEqual(info, {"voice": "test"})
        get.assert_called_once_with("http://piper.local:5000/info", timeout=5)
        response.raise_for_status.assert_called_once()

    def test_synthesize_posts_json_and_returns_wav_pcm(self) -> None:
        response = MagicMock()
        response.content = self._wav_bytes(sample_rate=24000, pcm=b"\x01\x00\x02\x00")

        with patch("hal.tts.requests.post", return_value=response) as post:
            audio = PiperClient(self.config).synthesize("Open the pod bay doors.")

        post.assert_called_once_with(
            "http://piper.local:5000/synthesize",
            json={"text": "Open the pod bay doors."},
            timeout=5,
        )
        response.raise_for_status.assert_called_once()
        self.assertEqual(audio.sample_rate, 24000)
        self.assertEqual(b"".join(audio.chunks), b"\x01\x00\x02\x00")

    def test_synthesize_rejects_invalid_wav(self) -> None:
        response = MagicMock()
        response.content = b"not wav"

        with (
            patch("hal.tts.requests.post", return_value=response),
            self.assertRaises(PiperError),
        ):
            PiperClient(self.config).synthesize("hello")

    @staticmethod
    def _wav_bytes(*, sample_rate: int, pcm: bytes) -> bytes:
        output = BytesIO()
        with wave.open(output, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(pcm)
        return output.getvalue()


if __name__ == "__main__":
    unittest.main()
