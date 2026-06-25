from __future__ import annotations

import logging
import math
import subprocess
import time
import wave
from array import array
from pathlib import Path

from hal.config import Config

LOGGER = logging.getLogger(__name__)
SAMPLE_WIDTH_BYTES = 2


def _pyaudio():
    try:
        import pyaudio
    except ImportError as exc:
        raise RuntimeError("PyAudio is required for audio. Install requirements.txt.") from exc
    return pyaudio


def _default_indexes(audio) -> tuple[int | None, int | None]:
    input_index = output_index = None
    try:
        input_index = int(audio.get_default_input_device_info()["index"])
    except (IOError, KeyError, TypeError):
        pass
    try:
        output_index = int(audio.get_default_output_device_info()["index"])
    except (IOError, KeyError, TypeError):
        pass
    return input_index, output_index


def list_audio_devices() -> None:
    pyaudio = _pyaudio()
    audio = pyaudio.PyAudio()
    try:
        default_input, default_output = _default_indexes(audio)
        print(f"{'Index':<7}{'Name':<40}{'In':>4}{'Out':>5}{'Default Hz':>13}  Default")
        for index in range(audio.get_device_count()):
            info = audio.get_device_info_by_index(index)
            flags = []
            if index == default_input:
                flags.append("input")
            if index == default_output:
                flags.append("output")
            print(
                f"{index:<7}{str(info.get('name', ''))[:38]:<40}"
                f"{int(info.get('maxInputChannels', 0)):>4}"
                f"{int(info.get('maxOutputChannels', 0)):>5}"
                f"{int(float(info.get('defaultSampleRate', 0))):>13}  {'/'.join(flags)}"
            )
    finally:
        audio.terminate()


def log_audio_devices() -> None:
    pyaudio = _pyaudio()
    audio = pyaudio.PyAudio()
    try:
        default_input, default_output = _default_indexes(audio)
        for index in range(audio.get_device_count()):
            info = audio.get_device_info_by_index(index)
            flags = []
            if index == default_input:
                flags.append("default-input")
            if index == default_output:
                flags.append("default-output")
            LOGGER.info(
                "Audio device %d: name=%r input_channels=%d output_channels=%d "
                "default_sample_rate=%d%s",
                index,
                info.get("name", ""),
                int(info.get("maxInputChannels", 0)),
                int(info.get("maxOutputChannels", 0)),
                int(float(info.get("defaultSampleRate", 0) or 0)),
                f" ({', '.join(flags)})" if flags else "",
            )
    finally:
        audio.terminate()


def _resolve_device(config: Config, *, for_input: bool, audio) -> int | None:
    exact = (
        config.audio_input_device_index if for_input else config.audio_output_device_index
    )
    hint = (
        config.audio_input_device_name_hint
        if for_input
        else config.audio_output_device_name_hint
    )
    channel_key = "maxInputChannels" if for_input else "maxOutputChannels"
    kind = "input" if for_input else "output"

    if exact is not None:
        if exact < 0 or exact >= audio.get_device_count():
            raise ValueError(f"Configured audio {kind} device index {exact} does not exist")
        info = audio.get_device_info_by_index(exact)
        if int(info.get(channel_key, 0)) < 1:
            raise ValueError(f"Audio device {exact} has no {kind} channels")
        return exact

    if hint:
        lowered = hint.casefold()
        for index in range(audio.get_device_count()):
            info = audio.get_device_info_by_index(index)
            name_matches = lowered in str(info.get("name", "")).casefold()
            if name_matches and int(info.get(channel_key, 0)) > 0:
                LOGGER.info("Selected %s audio device %d: %s", kind, index, info.get("name"))
                return index
        raise ValueError(f"No {kind} audio device matched name hint {hint!r}")

    try:
        info = (
            audio.get_default_input_device_info()
            if for_input
            else audio.get_default_output_device_info()
        )
        return int(info["index"])
    except (IOError, KeyError, TypeError) as exc:
        raise RuntimeError(f"No default audio {kind} device is available") from exc


def _candidate_sample_rates(audio, device_index: int | None, requested_rate: int) -> list[int]:
    rates = [requested_rate]
    if device_index is not None:
        try:
            info = audio.get_device_info_by_index(device_index)
            default_rate = int(float(info.get("defaultSampleRate", 0) or 0))
            if default_rate:
                rates.append(default_rate)
        except (IOError, KeyError, TypeError, ValueError):
            pass
    rates.extend([48000, 44100, 32000, 16000])
    return list(dict.fromkeys(rate for rate in rates if rate > 0))


def _supports_input_rate(audio, pyaudio, device_index: int | None, rate: int) -> bool:
    try:
        return bool(
            audio.is_format_supported(
                rate,
                input_device=device_index,
                input_channels=1,
                input_format=pyaudio.paInt16,
            )
        )
    except (ValueError, IOError):
        return False


def _resolve_input_stream(
    config: Config,
    *,
    audio,
    pyaudio,
    target_rate: int,
    target_frame_size: int,
):
    device_index = _resolve_device(config, for_input=True, audio=audio)
    for hardware_rate in _candidate_sample_rates(audio, device_index, target_rate):
        if _supports_input_rate(audio, pyaudio, device_index, hardware_rate):
            hardware_frame_size = max(1, round(target_frame_size * hardware_rate / target_rate))
            stream = audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=hardware_rate,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=hardware_frame_size,
            )
            LOGGER.info(
                "Opened input device %s at %d Hz for %d Hz processing",
                device_index,
                hardware_rate,
                target_rate,
            )
            return stream, device_index, hardware_rate, hardware_frame_size

    raise RuntimeError(
        f"Audio input device {device_index} does not support a usable mono 16-bit rate. "
        f"Tried: {_candidate_sample_rates(audio, device_index, target_rate)}"
    )


def resample_pcm(data: bytes, from_rate: int, to_rate: int, state):
    if from_rate == to_rate:
        return data, state
    samples = array("h")
    samples.frombytes(data[: len(data) - (len(data) % SAMPLE_WIDTH_BYTES)])
    if not samples:
        return b"", state

    previous_samples, next_position = state or (array("h"), 0.0)
    source = array("h", previous_samples)
    source.extend(samples)
    step = from_rate / to_rate
    output = array("h")

    while next_position < len(source) - 1:
        left_index = int(next_position)
        fraction = next_position - left_index
        left = source[left_index]
        right = source[left_index + 1]
        value = round(left + ((right - left) * fraction))
        output.append(max(-32768, min(32767, value)))
        next_position += step

    drop_count = max(0, int(next_position) - 1)
    if drop_count:
        source = source[drop_count:]
        next_position -= drop_count

    return output.tobytes(), (source, next_position)


def resolve_input_device(config: Config) -> int | None:
    pyaudio = _pyaudio()
    audio = pyaudio.PyAudio()
    try:
        return _resolve_device(config, for_input=True, audio=audio)
    finally:
        audio.terminate()


def resolve_output_device(config: Config) -> int | None:
    pyaudio = _pyaudio()
    audio = pyaudio.PyAudio()
    try:
        return _resolve_device(config, for_input=False, audio=audio)
    finally:
        audio.terminate()


def pcm_rms(data: bytes) -> int:
    if len(data) < 2:
        return 0
    samples = array("h")
    samples.frombytes(data[: len(data) - (len(data) % 2)])
    if not samples:
        return 0
    return int(math.sqrt(sum(sample * sample for sample in samples) / len(samples)))


def record_until_silence(config: Config) -> Path:
    pyaudio = _pyaudio()
    audio = pyaudio.PyAudio()
    stream = None
    frames: list[bytes] = []
    started = time.monotonic()
    silence_started: float | None = None
    try:
        stream, device_index, hardware_rate, hardware_frame_size = _resolve_input_stream(
            config,
            audio=audio,
            pyaudio=pyaudio,
            target_rate=config.record_sample_rate,
            target_frame_size=config.record_frame_size,
        )
        LOGGER.info("Recording from audio device %s", device_index)
        resample_state = None
        while True:
            raw = stream.read(hardware_frame_size, exception_on_overflow=False)
            data, resample_state = resample_pcm(
                raw, hardware_rate, config.record_sample_rate, resample_state
            )
            frames.append(data)
            now = time.monotonic()
            elapsed = now - started
            rms = pcm_rms(data)
            silent = rms < config.silence_rms_threshold
            LOGGER.debug("Microphone RMS=%d silent=%s elapsed=%.2fs", rms, silent, elapsed)

            if elapsed >= config.min_record_seconds and silent:
                if silence_started is None:
                    silence_started = now
                    LOGGER.debug("Silence interval started")
                elif now - silence_started >= config.silence_duration_seconds:
                    LOGGER.info("Silence detected; recording complete")
                    break
            elif not silent and silence_started is not None:
                LOGGER.debug("Silence interval ended")
                silence_started = None

            if elapsed >= config.max_record_seconds:
                LOGGER.info("Maximum recording duration reached")
                break
    finally:
        if stream is not None:
            if stream.is_active():
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
    LOGGER.info("Recording saved to %s", output)
    return output


def play_pcm_stream(chunks, sample_rate: int, config: Config) -> None:
    pyaudio = _pyaudio()
    audio = pyaudio.PyAudio()
    stream = None
    try:
        device_index = _resolve_device(config, for_input=False, audio=audio)
        stream = audio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=sample_rate,
            output=True,
            output_device_index=device_index,
            frames_per_buffer=1024,
        )
        LOGGER.info("Playing audio through device %s", device_index)
        for chunk in chunks:
            if chunk:
                stream.write(bytes(chunk))
    finally:
        if stream is not None:
            if stream.is_active():
                stream.stop_stream()
            stream.close()
        audio.terminate()


def set_alsa_volume(config: Config) -> None:
    if config.alsa_card_index is None:
        return
    try:
        result = subprocess.run(
            [
                "amixer",
                "-c",
                str(config.alsa_card_index),
                "sset",
                config.alsa_speaker_control,
                config.alsa_speaker_volume,
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            LOGGER.warning("Could not set ALSA volume: %s", result.stderr.strip())
    except OSError as exc:
        LOGGER.warning("Could not run amixer: %s", exc)
