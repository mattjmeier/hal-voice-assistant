import argparse

import _bootstrap  # noqa: F401

from hal.config import Config
from hal.home_assistant import HomeAssistantConversationClient
from hal.logging_config import configure_logging


def main() -> None:
    parser = argparse.ArgumentParser(description="Test Home Assistant conversation processing")
    parser.add_argument("text")
    args = parser.parse_args()
    config = Config.load()
    configure_logging(config.log_level)
    print(HomeAssistantConversationClient(config).process_text(args.text))


if __name__ == "__main__":
    main()
