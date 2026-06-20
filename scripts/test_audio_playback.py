import argparse
from itertools import chain
import math
from pathlib import Path
import struct
import wave

import _bootstrap  # noqa: F401

from hal.audio import play_pcm_stream
from hal.config import Config


def tone(sample_rate: int, seconds: float = 1.0, frequency: float = 440.0):
    samples = int(sample_rate * seconds)
    pcm = bytearray()
    for index in range(samples):
        value = int(8000 * math.sin(2 * math.pi * frequency * index / sample_rate))
        pcm.extend(struct.pack("<h", value))
        if len(pcm) >= 4096:
            yield bytes(pcm)
            pcm.clear()
    if pcm:
        yield bytes(pcm)


def wav_chunks(path: Path):
    with wave.open(str(path), "rb") as wav_file:
        if wav_file.getnchannels() != 1 or wav_file.getsampwidth() != 2:
            raise ValueError("Test WAV must be mono 16-bit PCM")
        sample_rate = wav_file.getframerate()
        while chunk := wav_file.readframes(2048):
            yield sample_rate, chunk


def main() -> None:
    parser = argparse.ArgumentParser(description="Play a WAV file or a generated test tone")
    parser.add_argument("wav", nargs="?", type=Path)
    args = parser.parse_args()
    config = Config.load()
    if args.wav:
        items = wav_chunks(args.wav)
        try:
            first_rate, first_chunk = next(items)
        except StopIteration:
            raise ValueError("WAV file contains no audio") from None
        chunks = (chunk for _rate, chunk in items)
        play_pcm_stream(chain((first_chunk,), chunks), first_rate, config)
    else:
        play_pcm_stream(tone(config.tts_sample_rate), config.tts_sample_rate, config)


if __name__ == "__main__":
    main()
