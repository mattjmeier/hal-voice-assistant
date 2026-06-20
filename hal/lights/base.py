from hal.state import AssistantState


class LightController:
    def set_state(self, state: AssistantState) -> None:
        raise NotImplementedError

    def off(self) -> None:
        raise NotImplementedError

    def close(self) -> None:
        pass
