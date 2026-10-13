from __future__ import annotations

import re

from text2business.models import EvidenceFact, ExtractedFacts, IncomingRequest, Provenance


def _sentence_with(text: str, needle: str) -> str:
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        if needle.casefold() in sentence.casefold():
            return sentence.strip()
    return text.strip()


class DeterministicExtractor:
    """Small reproducible extractor for the demo dataset."""

    def extract(self, request: IncomingRequest) -> ExtractedFacts:
        text = request.text
        customer = None
        if "северфуд" in text.casefold() or "северфуд" in request.sender.casefold():
            evidence = "СеверФуд" if "северфуд" in text.casefold() else request.sender
            customer = EvidenceFact(
                value="СеверФуд",
                evidence=evidence,
                confidence=1.0,
                provenance=Provenance.MESSAGE,
            )

        site = None
        site_match = re.search(r"Дмитровск\w*\s+шоссе,?\s*100", text, re.IGNORECASE)
        if site_match:
            site = EvidenceFact(
                value=site_match.group(0),
                evidence=site_match.group(0),
                confidence=1.0,
                provenance=Provenance.MESSAGE,
            )

        asset = None
        asset_match = re.search(r"\bХУ[-\s]?(\d+)\b", text, re.IGNORECASE)
        if asset_match:
            evidence = asset_match.group(0)
            asset = EvidenceFact(
                value=f"ХУ-{asset_match.group(1)}",
                evidence=evidence,
                confidence=1.0,
                provenance=Provenance.MESSAGE,
            )

        problem = None
        problem_match = re.search(r"не запускается после перезагрузки", text, re.IGNORECASE)
        if problem_match:
            evidence = problem_match.group(0)
            problem = EvidenceFact(
                value="не запускается после перезагрузки",
                evidence=evidence,
                confidence=1.0,
                provenance=Provenance.MESSAGE,
            )

        backup = None
        if "перенесли в соседнюю камеру" in text.casefold():
            backup = EvidenceFact(
                value=True,
                evidence=_sentence_with(text, "перенесли в соседнюю камеру"),
                confidence=0.9,
                provenance=Provenance.MESSAGE,
            )

        return ExtractedFacts(
            customer=customer,
            site=site,
            asset=asset,
            problem=problem,
            backup_available=backup,
        )

