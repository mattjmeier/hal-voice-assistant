from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from hal.audio import _resolve_device, _resolve_input_stream, resample_pcm


class AudioDeviceTests(unittest.TestCase):
    def test_resolve_device_honors_explicit_index(self) -> None:
        audio = self._audio()
        config = SimpleNamespace(
            audio_input_device_index=1,
            audio_output_device_index=None,
            audio_input_device_name_hint="",
            audio_output_device_name_hint="",
        )

        self.assertEqual(_resolve_device(config, for_input=True, audio=audio), 1)

    def test_resolve_device_honors_name_hint(self) -> None:
        audio = self._audio()
        config = SimpleNamespace(
            audio_input_device_index=None,
            audio_output_device_index=None,
            audio_input_device_name_hint="usb mic",
            audio_output_device_name_hint="",
        )

        self.assertEqual(_resolve_device(config, for_input=True, audio=audio), 1)

    def test_input_stream_falls_back_to_48khz_when_16khz_unsupported(self) -> None:
        audio = self._audio()
        audio.is_format_supported.side_effect = lambda rate, **_kwargs: rate == 48000
        stream = MagicMock()
        audio.open.return_value = stream
        config = SimpleNamespace(
            audio_input_device_index=1,
            audio_output_device_index=None,
            audio_input_device_name_hint="",
            audio_output_device_name_hint="",
        )
        pyaudio = SimpleNamespace(paInt16=8)

        resolved = _resolve_input_stream(
            config,
            audio=audio,
            pyaudio=pyaudio,
            target_rate=16000,
            target_frame_size=1280,
        )

        self.assertEqual(resolved, (stream, 1, 48000, 3840))
        audio.open.assert_called_once_with(
            format=8,
            channels=1,
            rate=48000,
            input=True,
            input_device_index=1,
            frames_per_buffer=3840,
        )

    def test_resample_pcm_converts_48khz_to_16khz(self) -> None:
        data = b"\x00\x00" * 480

        converted, state = resample_pcm(data, 48000, 16000, None)

        self.assertIsNotNone(state)
        self.assertEqual(len(converted), 320)

    @staticmethod
    def _audio() -> MagicMock:
        devices = [
            {
                "index": 0,
                "name": "Built-in Output",
                "maxInputChannels": 0,
                "maxOutputChannels": 2,
                "defaultSampleRate": 44100,
            },
            {
                "index": 1,
                "name": "USB Mic",
                "maxInputChannels": 1,
                "maxOutputChannels": 0,
                "defaultSampleRate": 48000,
            },
        ]
        audio = MagicMock()
        audio.get_device_count.return_value = len(devices)
        audio.get_device_info_by_index.side_effect = lambda index: devices[index]
        audio.get_default_input_device_info.return_value = devices[1]
        return audio


if __name__ == "__main__":
    unittest.main()
