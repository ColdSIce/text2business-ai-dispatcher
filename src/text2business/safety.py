from __future__ import annotations

import re

from text2business.models import EvidenceFact, IncomingRequest, Provenance


_INSTRUCTION_PATTERNS = (
    re.compile(
        r"(?:игнорир|забуд|отмен|обойд|наруш)[а-яё\w\s-]{0,50}"
        r"(?:правил|инструкц|ограничен|системн|предыдущ)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:вызов|вызови|запуст|используй|выполни)[а-яё\w\s-]{0,40}"
        r"(?:tool|function|create|update|propose|инструмент|функци)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:покажи|раскрой|выведи|пришли)[а-яё\w\s-]{0,40}"
        r"(?:system prompt|системн\w* промпт|секрет|api.?key|токен)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:ignore|forget|override|bypass)\s+(?:all\s+)?(?:previous|system|safety|rules|instructions)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:call|invoke|execute|run)\s+(?:the\s+)?(?:tool|function|create|update|propose)",
        re.IGNORECASE,
    ),
)


def scan_untrusted_instructions(request: IncomingRequest) -> EvidenceFact | None:
    """Detect instruction-like payloads in both message and attachment before any model/tool call."""

    sources = (
        (request.text, Provenance.MESSAGE),
        (request.attachment_text or "", Provenance.ATTACHMENT),
    )
    for source, provenance in sources:
        for pattern in _INSTRUCTION_PATTERNS:
            match = pattern.search(source)
            if match:
                start = max(0, match.start() - 30)
                end = min(len(source), match.end() + 60)
                evidence = source[start:end].strip()
                return EvidenceFact(
                    value=True,
                    evidence=evidence,
                    confidence=1.0,
                    provenance=provenance,
                )
    return None
