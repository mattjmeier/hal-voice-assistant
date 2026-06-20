import argparse
from dataclasses import replace
from pathlib import Path
import time
import wave

import _bootstrap  # noqa: F401

from hal.audio import _pyaudio, _resolve_device
from hal.config import Config


def main() -> None:
    parser = argparse.ArgumentParser(description="Record a fixed-duration microphone test")
    parser.add_argument("--seconds", type=float, default=5.0)
    parser.add_argument("--output", default="/tmp/hal_test.wav")
    args = parser.parse_args()
    if args.seconds <= 0:
        parser.error("--seconds must be greater than zero")

    output = Path(args.output)
    if not output.is_absolute():
        output = _bootstrap.ROOT / output
    config = replace(Config.load(), output_wav_path=output)
    pyaudio = _pyaudio()
    audio = pyaudio.PyAudio()
    stream = None
    frames = []
    try:
        index = _resolve_device(config, for_input=True, audio=audio)
        stream = audio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=config.record_sample_rate,
            input=True,
            input_device_index=index,
            frames_per_buffer=config.record_frame_size,
        )
        print(f"Recording {args.seconds:g}s from device {index}...")
        deadline = time.monotonic() + args.seconds
        while time.monotonic() < deadline:
            frames.append(stream.read(config.record_frame_size, exception_on_overflow=False))
    finally:
        if stream is not None:
            stream.stop_stream()
            stream.close()
        sample_width = audio.get_sample_size(pyaudio.paInt16)
        audio.terminate()

    output = config.output_wav_path.expanduser()
    output.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(output), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(sample_width)
        wav_file.setframerate(config.record_sample_rate)
        wav_file.writeframes(b"".join(frames))
    print(f"Saved {output}")


if __name__ == "__main__":
    main()
