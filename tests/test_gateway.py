from __future__ import annotations

import json

import pytest

from text2business.extractor import GatewayExtractor
from text2business.drafting import GatewayResponseDrafter
from text2business.gateway import GatewayConfig, GatewayError
from text2business.models import ExtractedFacts
from text2business.prompts import DEFAULT_DRAFTING_PROMPT, DEFAULT_EXTRACTION_PROMPT
from text2business.scenarios import SCENARIOS
from text2business.workflow import run_case


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
    assert "Предыдущий ответ не прошёл валидацию" in extractor.client.calls[1]["user_prompt"]

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
    monkeypatch.setenv("AI_GATEWAY_ALLOWED_HOSTS", "openrouter.ai")
    with pytest.raises(GatewayError, match="forbidden"):
        GatewayConfig.from_env()


@pytest.mark.parametrize(
    "base_url,error",
    [
        ("https://api.openai.com/v1", "forbidden"),
        ("http://gateway.company.test/v1", "HTTPS"),
        ("https://other.company.test/v1", "not allowlisted"),
    ],
)
def test_gateway_config_rejects_untrusted_endpoints(
    monkeypatch: pytest.MonkeyPatch,
    base_url: str,
    error: str,
) -> None:
    monkeypatch.setenv("AI_GATEWAY_BASE_URL", base_url)
    monkeypatch.setenv("AI_GATEWAY_API_KEY", "secret")
    monkeypatch.setenv("AI_GATEWAY_MODEL", "model")
    monkeypatch.setenv("AI_GATEWAY_ALLOWED_HOSTS", "gateway.company.test")

    with pytest.raises(GatewayError, match=error):
        GatewayConfig.from_env()


def test_gateway_config_accepts_allowlisted_private_https_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AI_GATEWAY_BASE_URL", "https://gateway.company.test/v1")
    monkeypatch.setenv("AI_GATEWAY_API_KEY", "secret")
    monkeypatch.setenv("AI_GATEWAY_MODEL", "model")
    monkeypatch.setenv("AI_GATEWAY_ALLOWED_HOSTS", "company.test")

    config = GatewayConfig.from_env()

    assert config.allowed_hosts == ("company.test",)


def test_unsafe_model_draft_is_replaced_by_safe_template() -> None:
    unsafe = json.dumps(
        {
            "subject": "Заявка принята",
            "body": "Инженер гарантированно приедет сегодня в 18:00.",
            "warnings": [],
        },
        ensure_ascii=False,
    )
    drafter = GatewayResponseDrafter(FakeGatewayClient([unsafe]))  # type: ignore[arg-type]

    result = run_case(SCENARIOS["full"], drafter=drafter)

    assert "гарантированно приедет" not in result.draft_response.body
    assert "UNSAFE_MODEL_DRAFT_BLOCKED" in result.draft_response.warnings


def test_default_prompts_are_reviewable_russian_text() -> None:
    assert "извлекаешь факты" in DEFAULT_EXTRACTION_PROMPT
    assert "Верни только валидный JSON" in DEFAULT_EXTRACTION_PROMPT
    assert "Напиши краткий, спокойный" in DEFAULT_DRAFTING_PROMPT
    assert "Не обещай выезд" in DEFAULT_DRAFTING_PROMPT
