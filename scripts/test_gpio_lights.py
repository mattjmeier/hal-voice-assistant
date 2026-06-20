import time

import _bootstrap  # noqa: F401

from hal.config import Config
from hal.lights import create_lights
from hal.logging_config import configure_logging
from hal.state import AssistantState


def main() -> None:
    config = Config.load()
    configure_logging(config.log_level)
    lights = create_lights(config)
    states = [
        AssistantState.STARTING,
        AssistantState.IDLE,
        AssistantState.WAKE_DETECTED,
        AssistantState.LISTENING,
        AssistantState.RECORDING,
        AssistantState.TRANSCRIBING,
        AssistantState.THINKING,
        AssistantState.SPEAKING,
        AssistantState.ERROR,
    ]
    try:
        for state in states:
            print(state.value.upper())
            lights.set_state(state)
            time.sleep(2)
        print("OFF")
        lights.off()
    finally:
        lights.close()


if __name__ == "__main__":
    main()
