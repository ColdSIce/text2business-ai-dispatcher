from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel


class GatewayError(RuntimeError):
    """Controlled model-gateway failure safe to expose as a degraded result."""


@dataclass(frozen=True)
class GatewayConfig:
    """Validated OpenAI-compatible private gateway configuration."""

    base_url: str
    api_key: str
    model: str
    timeout_seconds: float = 15.0

    @classmethod
    def from_env(cls) -> GatewayConfig:
        """Load gateway settings without accepting public OpenRouter endpoints."""

        base_url = os.environ.get("AI_GATEWAY_BASE_URL", "").strip()
        api_key = os.environ.get("AI_GATEWAY_API_KEY", "").strip()
        model = os.environ.get("AI_GATEWAY_MODEL", "").strip()
        if not base_url or not api_key or not model:
            raise GatewayError(
                "AI_GATEWAY_BASE_URL, AI_GATEWAY_API_KEY and AI_GATEWAY_MODEL are required"
            )
        parsed = urlparse(base_url)
        host = (parsed.hostname or "").casefold()
        if "openrouter" in host or host == "openrouter.ai":
            raise GatewayError("public OpenRouter endpoints are forbidden")
        if parsed.scheme not in {"http", "https"} or not host:
            raise GatewayError("AI_GATEWAY_BASE_URL must be an absolute HTTP(S) URL")
        timeout = float(os.environ.get("AI_GATEWAY_TIMEOUT_SECONDS", "15"))
        if timeout <= 0:
            raise GatewayError("AI_GATEWAY_TIMEOUT_SECONDS must be positive")
        return cls(base_url=base_url.rstrip("/"), api_key=api_key, model=model, timeout_seconds=timeout)


class StructuredGatewayClient:
    """Small JSON-schema client for a private OpenAI-compatible gateway."""

    def __init__(self, config: GatewayConfig) -> None:
        self.config = config

    def complete_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[BaseModel],
    ) -> str:
        """Return raw structured JSON content for validation by the caller."""

        payload = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": response_model.__name__,
                    "strict": True,
                    "schema": response_model.model_json_schema(),
                },
            },
        }
        request = urllib.request.Request(
            f"{self.config.base_url}/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode(),
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
                body: dict[str, Any] = json.loads(response.read())
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise GatewayError(f"gateway request failed: {type(exc).__name__}") from exc
        try:
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise GatewayError("gateway response does not contain message content") from exc
        if not isinstance(content, str):
            raise GatewayError("gateway message content must be a JSON string")
        return content
