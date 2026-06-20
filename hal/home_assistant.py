from __future__ import annotations

import logging

import requests

from hal.config import Config

LOGGER = logging.getLogger(__name__)
NO_SPEECH = "I processed the request, but Home Assistant did not return a spoken response."


class HomeAssistantConversationClient:
    def __init__(self, config: Config):
        self.config = config

    def process_text(self, text: str) -> str:
        if not self.config.ha_token:
            raise RuntimeError("HA_TOKEN is required for home_assistant_conversation mode")
        payload = {"text": text, "language": self.config.ha_language}
        if self.config.ha_agent_id:
            payload["agent_id"] = self.config.ha_agent_id
        if self.config.ha_conversation_id:
            payload["conversation_id"] = self.config.ha_conversation_id
        try:
            response = requests.post(
                f"{self.config.ha_url}/api/conversation/process",
                headers={"Authorization": f"Bearer {self.config.ha_token}"},
                json=payload,
                timeout=self.config.network_timeout_seconds,
            )
            response.raise_for_status()
            data = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise RuntimeError(f"Home Assistant conversation request failed: {exc}") from exc

        result = data.get("response", {})
        LOGGER.info(
            "Home Assistant response type=%s targets=%s",
            result.get("response_type", "unknown"),
            result.get("data", {}).get("targets", []),
        )
        speech = result.get("speech", {}).get("plain", {}).get("speech", "")
        return str(speech).strip() or NO_SPEECH
