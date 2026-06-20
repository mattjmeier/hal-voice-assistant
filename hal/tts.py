from __future__ import annotations

import logging
from collections.abc import Iterable

import requests

from hal.config import Config

LOGGER = logging.getLogger(__name__)


class PiperClient:
    def __init__(self, config: Config):
        self.config = config

    def stream_tts(self, text: str) -> Iterable[bytes]:
        def chunks() -> Iterable[bytes]:
            try:
                with requests.get(
                    self.config.piper_url,
                    params={"text": text},
                    stream=True,
                    timeout=self.config.network_timeout_seconds,
                ) as response:
                    response.raise_for_status()
                    yield from (chunk for chunk in response.iter_content(4096) if chunk)
            except requests.RequestException as exc:
                LOGGER.error("Piper request failed: %s", exc)
                raise RuntimeError(f"Piper request failed: {exc}") from exc

        return chunks()
