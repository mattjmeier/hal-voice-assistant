from __future__ import annotations

import logging
import time

import requests

from hal.config import Config

LOGGER = logging.getLogger(__name__)


class OllamaClient:
    def __init__(self, config: Config):
        self.config = config

    def generate(self, prompt: str) -> str:
        started = time.monotonic()
        payload = {
            "model": self.config.ollama_model,
            "prompt": prompt,
            "system": self.config.ollama_system,
            "stream": False,
        }
        try:
            response = requests.post(
                self.config.ollama_url,
                json=payload,
                timeout=self.config.network_timeout_seconds,
            )
            response.raise_for_status()
            text = str(response.json().get("response", "")).strip()
            if not text:
                raise RuntimeError("Ollama returned an empty response")
            return text
        except (requests.RequestException, ValueError) as exc:
            raise RuntimeError(f"Ollama request failed: {exc}") from exc
        finally:
            LOGGER.info("Ollama request completed in %.2fs", time.monotonic() - started)
