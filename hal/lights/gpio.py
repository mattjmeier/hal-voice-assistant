from __future__ import annotations

import logging
import threading

from hal.config import Config
from hal.lights.base import LightController
from hal.state import AssistantState

LOGGER = logging.getLogger(__name__)

STATE_LIGHTS = {
    AssistantState.STARTING: {"red": "blink", "white": "off"},
    AssistantState.IDLE: {"red": "idle_dim", "white": "off"},
    AssistantState.WAKE_DETECTED: {"red": "flash", "white": "on"},
    AssistantState.LISTENING: {"red": "on", "white": "on"},
    AssistantState.RECORDING: {"red": "on", "white": "on"},
    AssistantState.TRANSCRIBING: {"red": "slow_pulse", "white": "on"},
    AssistantState.THINKING: {"red": "slow_pulse", "white": "on"},
    AssistantState.SPEAKING: {"red": "fast_pulse", "white": "on"},
    AssistantState.ERROR: {"red": "error_blink", "white": "off"},
    AssistantState.OFFLINE: {"red": "slow_blink", "white": "off"},
    AssistantState.STOPPING: {"red": "fade_out", "white": "off"},
}


class GpioLights(LightController):
    def __init__(self, config: Config):
        if config.gpio_red_led_pin is None and config.gpio_white_led_pin is None:
            raise ValueError(
                "LIGHT_BACKEND=gpio requires GPIO_RED_LED_PIN or GPIO_WHITE_LED_PIN"
            )
        try:
            from gpiozero import LED, PWMLED
            from gpiozero.pins.lgpio import LGPIOFactory
        except ImportError as exc:
            raise RuntimeError("gpiozero and lgpio are required for LIGHT_BACKEND=gpio") from exc

        self.config = config
        self._pin_factory = LGPIOFactory()
        led_type = PWMLED if config.gpio_enable_pwm else LED
        extra = {"pin_factory": self._pin_factory}
        if config.gpio_enable_pwm:
            extra["frequency"] = config.gpio_pwm_frequency
        self.red = self._create_led(
            led_type,
            config.gpio_red_led_pin,
            config.gpio_active_high != config.gpio_red_led_inverted,
            extra,
        )
        self.white = self._create_led(
            led_type,
            config.gpio_white_led_pin,
            config.gpio_active_high != config.gpio_white_led_inverted,
            extra,
        )
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._lock = threading.Lock()

    @staticmethod
    def _create_led(led_type, pin: int | None, active_high: bool, extra: dict):
        if pin is None:
            return None
        return led_type(pin, active_high=active_high, initial_value=False, **extra)

    def set_state(self, state: AssistantState) -> None:
        behavior = STATE_LIGHTS[state]
        with self._lock:
            self._stop_animation()
            self._set_white(behavior["white"] == "on")
            red_behavior = behavior["red"]
            if red_behavior == "off":
                self._set_red(0)
            elif red_behavior == "on":
                self._set_red(self.config.gpio_active_red_brightness)
            elif red_behavior == "idle_dim":
                self._set_red(self.config.gpio_idle_red_brightness)
            else:
                self._stop = threading.Event()
                self._thread = threading.Thread(
                    target=self._animate,
                    args=(red_behavior, self._stop),
                    name="hal-light-animation",
                    daemon=True,
                )
                self._thread.start()
        LOGGER.debug("GPIO light state: %s", state.value)

    def _animate(self, behavior: str, stop: threading.Event) -> None:
        if self.red is None:
            return
        if behavior == "flash":
            self._set_red(self.config.gpio_active_red_brightness)
            stop.wait(0.25)
            self._set_red(0)
            return
        if behavior == "fade_out":
            for step in range(10, -1, -1):
                if stop.wait(0.05):
                    return
                self._set_red(self.config.gpio_active_red_brightness * step / 10)
            return

        if behavior in {"slow_pulse", "fast_pulse"} and self.config.gpio_enable_pwm:
            delay = 0.09 if behavior == "slow_pulse" else 0.035
            while not stop.is_set():
                for steps in (range(0, 11), range(9, -1, -1)):
                    for step in steps:
                        self._set_red(self.config.gpio_active_red_brightness * step / 10)
                        if stop.wait(delay):
                            return
            return

        intervals = {
            "blink": 0.25,
            "slow_pulse": 0.6,
            "fast_pulse": 0.18,
            "error_blink": 0.12,
            "slow_blink": 1.0,
        }
        interval = intervals.get(behavior, 0.5)
        while not stop.is_set():
            self._set_red(self.config.gpio_active_red_brightness)
            if stop.wait(interval):
                return
            self._set_red(0)
            if stop.wait(interval):
                return

    def _set_red(self, value: float) -> None:
        self._set_led(self.red, value)

    def _set_white(self, enabled: bool) -> None:
        value = self.config.gpio_white_brightness if enabled else 0
        self._set_led(self.white, value)

    def _set_led(self, led, value: float) -> None:
        if led is None:
            return
        value = max(0.0, min(1.0, value))
        if self.config.gpio_enable_pwm:
            led.value = value
        elif value > 0:
            led.on()
        else:
            led.off()

    def _stop_animation(self) -> None:
        self._stop.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self._thread = None

    def off(self) -> None:
        with self._lock:
            self._stop_animation()
            self._set_red(0)
            self._set_white(False)

    def close(self) -> None:
        self.off()
        if self.red is not None:
            self.red.close()
        if self.white is not None:
            self.white.close()
        self._pin_factory.close()
