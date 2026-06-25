from __future__ import annotations

import tempfile
import unittest
import wave
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

from hal.stt import VOSK_EOF_MESSAGE, VoskClient


class VoskClientTests(unittest.TestCase):
    def test_transcribe_sends_binary_audio_and_legacy_eof_message(self) -> None:
        websocket = MagicMock()
        websocket.recv.side_effect = [
            '{"partial": "open"}',
            '{"text": "open the pod bay doors"}',
        ]
        config = SimpleNamespace(
            vosk_url="ws://vosk.local:2700",
            network_timeout_seconds=5,
        )

        with (
            tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file,
            patch("hal.stt.create_connection", return_value=websocket) as create_connection,
        ):
            wav_path = Path(temp_file.name)
            self._write_wav(wav_path, b"\x01\x00\x02\x00")
            transcript = VoskClient(config).transcribe_wav(wav_path)

        try:
            self.assertEqual(transcript, "open the pod bay doors")
            create_connection.assert_called_once_with("ws://vosk.local:2700", timeout=5)
            websocket.send.assert_has_calls(
                [
                    call('{"config": {"sample_rate": 16000}}'),
                    call(VOSK_EOF_MESSAGE),
                ]
            )
            websocket.send_binary.assert_called_once_with(b"\x01\x00\x02\x00")
            websocket.close.assert_called_once()
        finally:
            wav_path.unlink(missing_ok=True)

    @staticmethod
    def _write_wav(path: Path, pcm: bytes) -> None:
        with wave.open(str(path), "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(16000)
            wav_file.writeframes(pcm)


if __name__ == "__main__":
    unittest.main()
