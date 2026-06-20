import time

import _bootstrap  # noqa: F401

from hal.audio import _pyaudio, _resolve_device, pcm_rms
from hal.config import Config


def main() -> None:
    config = Config.load()
    pyaudio = _pyaudio()
    audio = pyaudio.PyAudio()
    stream = None
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
        print(f"Reading device {index}; press Ctrl+C to stop")
        while True:
            rms = pcm_rms(stream.read(config.record_frame_size, exception_on_overflow=False))
            marker = "  speaking detected" if rms >= config.silence_rms_threshold else ""
            print(f"RMS: {rms:05d}{marker}")
            time.sleep(0.02)
    except KeyboardInterrupt:
        pass
    finally:
        if stream is not None:
            stream.stop_stream()
            stream.close()
        audio.terminate()


if __name__ == "__main__":
    main()
