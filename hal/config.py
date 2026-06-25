from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


def _optional_int(name: str) -> int | None:
    value = os.getenv(name, "").strip()
    return int(value) if value else None


def _float(name: str, default: float) -> float:
    return float(os.getenv(name, str(default)))


def _int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be true or false, got {value!r}")


@dataclass(frozen=True)
class Config:
    mode: str
    name: str
    log_level: str
    wakeword_disabled: bool
    openwakeword_model_path: Path
    openwakeword_threshold: float
    audio_backend: str
    audio_input_device_index: int | None
    audio_output_device_index: int | None
    audio_input_device_name_hint: str
    audio_output_device_name_hint: str
    wake_sample_rate: int
    record_sample_rate: int
    tts_sample_rate: int
    audio_channels: int
    record_frame_size: int
    output_wav_path: Path
    silence_rms_threshold: int
    silence_duration_seconds: float
    max_record_seconds: float
    min_record_seconds: float
    alsa_card_index: int | None
    alsa_speaker_control: str
    alsa_speaker_volume: str
    vosk_url: str
    ollama_url: str
    ollama_model: str
    ollama_system: str
    network_timeout_seconds: float
    piper_url: str
    ha_url: str
    ha_token: str
    ha_language: str
    ha_agent_id: str
    ha_conversation_id: str
    light_backend: str
    gpio_active_high: bool
    gpio_red_led_pin: int | None
    gpio_white_led_pin: int | None
    gpio_enable_pwm: bool
    gpio_pwm_frequency: int
    gpio_idle_red_brightness: float
    gpio_active_red_brightness: float
    gpio_white_brightness: float
    gpio_red_led_inverted: bool
    gpio_white_led_inverted: bool

    @classmethod
    def load(cls, env_file: str | Path | None = None) -> "Config":
        load_dotenv(dotenv_path=env_file)
        config = cls(
            mode=os.getenv("HAL_MODE", "direct").strip().lower(),
            name=os.getenv("HAL_NAME", "hal-office").strip(),
            log_level=os.getenv("HAL_LOG_LEVEL", "INFO").strip().upper(),
            wakeword_disabled=_bool("WAKEWORD_DISABLED", False),
            openwakeword_model_path=Path(
                os.getenv(
                    "OPENWAKEWORD_MODEL_PATH", "models/openwakeword/hey_hal.onnx"
                ).strip()
            ),
            openwakeword_threshold=_float("OPENWAKEWORD_THRESHOLD", 0.5),
            audio_backend=os.getenv("AUDIO_BACKEND", "pyaudio").strip().lower(),
            audio_input_device_index=_optional_int("AUDIO_INPUT_DEVICE_INDEX"),
            audio_output_device_index=_optional_int("AUDIO_OUTPUT_DEVICE_INDEX"),
            audio_input_device_name_hint=os.getenv("AUDIO_INPUT_DEVICE_NAME_HINT", "").strip(),
            audio_output_device_name_hint=os.getenv("AUDIO_OUTPUT_DEVICE_NAME_HINT", "").strip(),
            wake_sample_rate=_int("WAKE_SAMPLE_RATE", 16000),
            record_sample_rate=_int("RECORD_SAMPLE_RATE", 16000),
            tts_sample_rate=_int("TTS_SAMPLE_RATE", 22050),
            audio_channels=_int("AUDIO_CHANNELS", 1),
            record_frame_size=_int("RECORD_FRAME_SIZE", 1024),
            output_wav_path=Path(os.getenv("OUTPUT_WAV_PATH", "/tmp/hal_prompt.wav")),
            silence_rms_threshold=_int("SILENCE_RMS_THRESHOLD", 25000),
            silence_duration_seconds=_float("SILENCE_DURATION_SECONDS", 2.0),
            max_record_seconds=_float("MAX_RECORD_SECONDS", 15.0),
            min_record_seconds=_float("MIN_RECORD_SECONDS", 0.5),
            alsa_card_index=_optional_int("ALSA_CARD_INDEX"),
            alsa_speaker_control=os.getenv("ALSA_SPEAKER_CONTROL", "Speaker"),
            alsa_speaker_volume=os.getenv("ALSA_SPEAKER_VOLUME", "100%"),
            vosk_url=os.getenv("VOSK_URL", "ws://localhost:2700").rstrip("/"),
            ollama_url=os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate"),
            ollama_model=os.getenv("OLLAMA_MODEL", "llama3:latest"),
            ollama_system=os.getenv(
                "OLLAMA_SYSTEM",
                "Limit your responses to three sentences. You are a voice assistant.",
            ),
            network_timeout_seconds=_float("NETWORK_TIMEOUT_SECONDS", 30.0),
            piper_url=os.getenv("PIPER_URL", "http://localhost:5000").rstrip("/"),
            ha_url=os.getenv("HA_URL", "http://homeassistant.local:8123").rstrip("/"),
            ha_token=os.getenv("HA_TOKEN", "").strip(),
            ha_language=os.getenv("HA_LANGUAGE", "en").strip(),
            ha_agent_id=os.getenv("HA_AGENT_ID", "").strip(),
            ha_conversation_id=os.getenv("HA_CONVERSATION_ID", "hal-office").strip(),
            light_backend=os.getenv("LIGHT_BACKEND", "gpio").strip().lower(),
            gpio_active_high=_bool("GPIO_ACTIVE_HIGH", True),
            gpio_red_led_pin=_optional_int("GPIO_RED_LED_PIN"),
            gpio_white_led_pin=_optional_int("GPIO_WHITE_LED_PIN"),
            gpio_enable_pwm=_bool("GPIO_ENABLE_PWM", True),
            gpio_pwm_frequency=_int("GPIO_PWM_FREQUENCY", 200),
            gpio_idle_red_brightness=_float("GPIO_IDLE_RED_BRIGHTNESS", 0.20),
            gpio_active_red_brightness=_float("GPIO_ACTIVE_RED_BRIGHTNESS", 1.0),
            gpio_white_brightness=_float("GPIO_WHITE_BRIGHTNESS", 1.0),
            gpio_red_led_inverted=_bool("GPIO_RED_LED_INVERTED", False),
            gpio_white_led_inverted=_bool("GPIO_WHITE_LED_INVERTED", False),
        )
        config.validate()
        return config

    def validate(self) -> None:
        if self.mode not in {"direct", "home_assistant_conversation"}:
            raise ValueError("HAL_MODE must be direct or home_assistant_conversation")
        if self.light_backend not in {"gpio", "null"}:
            raise ValueError("LIGHT_BACKEND must be gpio or null")
        if self.audio_backend != "pyaudio":
            raise ValueError("AUDIO_BACKEND currently supports only pyaudio")
        if self.audio_channels != 1:
            raise ValueError("AUDIO_CHANNELS must be 1; HAL currently uses mono PCM")
        if self.wake_sample_rate != 16000:
            raise ValueError("WAKE_SAMPLE_RATE must be 16000 for openWakeWord")
        if not 0 <= self.openwakeword_threshold <= 1:
            raise ValueError("OPENWAKEWORD_THRESHOLD must be between 0 and 1")
        if self.min_record_seconds > self.max_record_seconds:
            raise ValueError("MIN_RECORD_SECONDS cannot exceed MAX_RECORD_SECONDS")
        for name, value in (
            ("GPIO_IDLE_RED_BRIGHTNESS", self.gpio_idle_red_brightness),
            ("GPIO_ACTIVE_RED_BRIGHTNESS", self.gpio_active_red_brightness),
            ("GPIO_WHITE_BRIGHTNESS", self.gpio_white_brightness),
        ):
            if not 0 <= value <= 1:
                raise ValueError(f"{name} must be between 0 and 1")
