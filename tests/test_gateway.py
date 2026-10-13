from __future__ import annotations

import json

import pytest

from text2business.extractor import GatewayExtractor
from text2business.gateway import GatewayConfig, GatewayError
from text2business.models import ExtractedFacts
from text2business.scenarios import SCENARIOS


class FakeGatewayClient:
    """Deterministic structured response queue used without network access."""

    def __init__(self, responses: list[str]) -> None:
        self.responses = responses
        self.calls: list[dict[str, object]] = []

    def complete_json(self, **kwargs: object) -> str:
        self.calls.append(kwargs)
        return self.responses.pop(0)


def _valid_facts() -> str:
    return ExtractedFacts(
        asset_reference={
            "value": "ХУ-18",
            "evidence": "ХУ-18",
            "confidence": 1.0,
            "provenance": "message",
        }
    ).model_dump_json()


def test_gateway_extractor_validates_schema_and_exact_evidence() -> None:
    calls: list[str] = []
    extractor = GatewayExtractor(FakeGatewayClient([_valid_facts()]))  # type: ignore[arg-type]
    result = extractor.extract(SCENARIOS["full"], on_model_call=calls.append)
    assert result.asset_reference and result.asset_reference.value == "ХУ-18"
    assert calls == ["structured_extraction"]


def test_gateway_extractor_repairs_once_then_stops() -> None:
    invalid = json.dumps(
        {
            "asset_reference": {
                "value": "ХУ-18",
                "evidence": "not in source",
                "confidence": 1,
                "provenance": "message",
            }
        }
    )
    calls: list[str] = []
    extractor = GatewayExtractor(FakeGatewayClient([invalid, _valid_facts()]))  # type: ignore[arg-type]
    extractor.extract(SCENARIOS["full"], on_model_call=calls.append)
    assert calls == ["structured_extraction", "structured_extraction_repair"]

    extractor = GatewayExtractor(FakeGatewayClient([invalid, invalid]))  # type: ignore[arg-type]
    with pytest.raises(GatewayError, match="failed validation"):
        extractor.extract(SCENARIOS["full"])


def test_gateway_extractor_accepts_a_reviewable_prompt_override() -> None:
    client = FakeGatewayClient([_valid_facts()])
    extractor = GatewayExtractor(  # type: ignore[arg-type]
        client,
        system_prompt="case-specific extraction prompt",
    )

    extractor.extract(SCENARIOS["full"])

    assert client.calls[0]["system_prompt"] == "case-specific extraction prompt"


def test_gateway_config_rejects_public_openrouter(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_GATEWAY_BASE_URL", "https://openrouter.ai/api/v1")
    monkeypatch.setenv("AI_GATEWAY_API_KEY", "secret")
    monkeypatch.setenv("AI_GATEWAY_MODEL", "model")
    with pytest.raises(GatewayError, match="forbidden"):
        GatewayConfig.from_env()
