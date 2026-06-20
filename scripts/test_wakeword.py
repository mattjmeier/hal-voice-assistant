import _bootstrap  # noqa: F401

from hal.config import Config
from hal.logging_config import configure_logging
from hal.wakeword import WakeWordListener


def main() -> None:
    config = Config.load()
    configure_logging(config.log_level)
    if WakeWordListener(config).wait_for_wake_word():
        print("Wake word detected")


if __name__ == "__main__":
    main()
