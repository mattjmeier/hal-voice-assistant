from __future__ import annotations

import logging
import signal
import threading

from hal.audio import play_pcm_stream, record_until_silence, set_alsa_volume
from hal.config import Config
from hal.home_assistant import HomeAssistantConversationClient
from hal.lights import create_lights
from hal.llm import OllamaClient
from hal.logging_config import configure_logging
from hal.state import AssistantState
from hal.stt import VoskClient
from hal.tts import PiperClient
from hal.wakeword import WakeWordListener

LOGGER = logging.getLogger(__name__)


def main() -> None:
    config = Config.load()
    configure_logging(config.log_level)
    stop_requested = threading.Event()

    def request_stop(signum, _frame) -> None:
        LOGGER.info("Received signal %s; stopping", signum)
        stop_requested.set()

    if threading.current_thread() is threading.main_thread():
        signal.signal(signal.SIGINT, request_stop)
        signal.signal(signal.SIGTERM, request_stop)

    lights = create_lights(config)
    wakeword = WakeWordListener(config)
    stt = VoskClient(config)
    tts = PiperClient(config)
    conversation = (
        OllamaClient(config)
        if config.mode == "direct"
        else HomeAssistantConversationClient(config)
    )

    try:
        lights.set_state(AssistantState.STARTING)
        set_alsa_volume(config)
        LOGGER.info("Starting %s in %s mode", config.name, config.mode)
        lights.set_state(AssistantState.IDLE)

        while not stop_requested.is_set():
            try:
                if not wakeword.wait_for_wake_word(stop_requested):
                    if config.wakeword_disabled:
                        stop_requested.set()
                    continue
                lights.set_state(AssistantState.WAKE_DETECTED)
                lights.set_state(AssistantState.LISTENING)
                lights.set_state(AssistantState.RECORDING)
                wav_path = record_until_silence(config)

                lights.set_state(AssistantState.TRANSCRIBING)
                transcript = stt.transcribe_wav(wav_path)
                if not transcript:
                    LOGGER.warning("No speech was transcribed")
                    lights.set_state(AssistantState.IDLE)
                    continue

                lights.set_state(AssistantState.THINKING)
                if config.mode == "direct":
                    response_text = conversation.generate(transcript)
                else:
                    response_text = conversation.process_text(transcript)
                LOGGER.info("Assistant response: %s", response_text)

                lights.set_state(AssistantState.SPEAKING)
                play_pcm_stream(tts.stream_tts(response_text), config.tts_sample_rate, config)
                lights.set_state(AssistantState.IDLE)
            except KeyboardInterrupt:
                stop_requested.set()
            except Exception:
                LOGGER.exception("Recoverable interaction error")
                lights.set_state(AssistantState.ERROR)
                try:
                    error_text = "I'm sorry. I couldn't complete that request."
                    play_pcm_stream(tts.stream_tts(error_text), config.tts_sample_rate, config)
                except Exception:
                    LOGGER.debug("Could not play the error message", exc_info=True)
                stop_requested.wait(1.0)
                if not stop_requested.is_set():
                    lights.set_state(AssistantState.IDLE)
    finally:
        LOGGER.info("Shutting down")
        lights.set_state(AssistantState.STOPPING)
        stop_requested.wait(0.6)
        lights.off()
        lights.close()


# Future modes intentionally remain server-side: Home Assistant Assist pipeline WebSocket,
# Hermes/orchestration, camera snapshots/face recognition, and voice-level LED animation.
