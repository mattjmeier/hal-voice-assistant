import logging

from hal.lights.base import LightController
from hal.state import AssistantState

LOGGER = logging.getLogger(__name__)


class NullLights(LightController):
    def set_state(self, state: AssistantState) -> None:
        LOGGER.info("Light state: %s", state.value)

    def off(self) -> None:
        LOGGER.info("Lights off")

    def close(self) -> None:
        self.off()
