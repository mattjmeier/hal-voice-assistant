from hal.config import Config
from hal.lights.base import LightController
from hal.lights.gpio import GpioLights
from hal.lights.null import NullLights


def create_lights(config: Config) -> LightController:
    if config.light_backend == "null":
        return NullLights()
    if config.light_backend == "gpio":
        return GpioLights(config)
    raise ValueError(f"Unsupported light backend: {config.light_backend}")


__all__ = ["LightController", "GpioLights", "NullLights", "create_lights"]
