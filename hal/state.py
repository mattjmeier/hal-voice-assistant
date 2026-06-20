from enum import Enum


class AssistantState(str, Enum):
    STARTING = "starting"
    IDLE = "idle"
    WAKE_DETECTED = "wake_detected"
    LISTENING = "listening"
    RECORDING = "recording"
    TRANSCRIBING = "transcribing"
    THINKING = "thinking"
    SPEAKING = "speaking"
    ERROR = "error"
    OFFLINE = "offline"
    STOPPING = "stopping"
