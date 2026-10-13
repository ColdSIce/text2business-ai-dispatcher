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
        site_match = re.search(
            r"Дмитровск\w*(?:\s+шоссе,?\s*100)?", text, re.IGNORECASE
        )
        if site_match:
            site = EvidenceFact(
                value=site_match.group(0),
                evidence=site_match.group(0),
                confidence=1.0,
                provenance=Provenance.MESSAGE,
            )

        asset = None
        asset_match = re.search(r"\bХУ[-\s]?(\d+)\b", text, re.IGNORECASE)
        if not asset_match:
            asset_match = re.search(r"\b(\d+)-я\b", text, re.IGNORECASE)
        if asset_match:
            evidence = asset_match.group(0)
            asset = EvidenceFact(
                value=f"ХУ-{asset_match.group(1)}",
                evidence=evidence,
                confidence=1.0,
                provenance=Provenance.MESSAGE,
            )
        elif re.search(r"семнадцат\w+\s+установ", text, re.IGNORECASE):
            evidence = re.search(
                r"семнадцат\w+\s+установ\w*", text, re.IGNORECASE
            )
            assert evidence is not None
            asset = EvidenceFact(
                value="ХУ-17",
                evidence=evidence.group(0),
                confidence=0.9,
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

        symptoms: list[EvidenceFact] = []
        temperature_match = re.search(
            r"температура\s+(?:уже\s+)?\+?(\d+(?:[,.]\d+)?)",
            text,
            re.IGNORECASE,
        )
        if temperature_match:
            value = float(temperature_match.group(1).replace(",", "."))
            symptoms.append(
                EvidenceFact(
                    value=value,
                    evidence=_sentence_with(text, temperature_match.group(0)),
                    confidence=0.95,
                    provenance=Provenance.MESSAGE,
                )
            )

        desired_deadline = None
        deadline_match = re.search(r"сегодня\s+до\s+\d{1,2}:\d{2}", text, re.IGNORECASE)
        if deadline_match:
            desired_deadline = EvidenceFact(
                value=deadline_match.group(0),
                evidence=deadline_match.group(0),
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
        elif "резервная камера вроде работает" in text.casefold():
            backup = EvidenceFact(
                value=True,
                evidence=_sentence_with(text, "резервная камера вроде работает"),
                confidence=0.6,
                provenance=Provenance.MESSAGE,
            )
        elif "резервная камера есть" in text.casefold():
            backup = EvidenceFact(
                value=True,
                evidence=_sentence_with(text, "резервная камера есть"),
                confidence=0.55 if "не уверены" in text.casefold() else 0.9,
                provenance=Provenance.MESSAGE,
            )

        previous_contact = None
        previous_patterns = (
            r"снова",
            r"вчера\s+.*?мастер",
            r"уже писал минут сорок назад",
        )
        for pattern in previous_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                previous_contact = EvidenceFact(
                    value=True,
                    evidence=_sentence_with(text, match.group(0)),
                    confidence=0.9,
                    provenance=Provenance.MESSAGE,
                )
                break

        suspicious_instruction = None
        injection_match = re.search(
            r"игнорируй\s+правил\w*|вызови\s+create_or_update_ticket",
            text,
            re.IGNORECASE,
        )
        if injection_match:
            suspicious_instruction = EvidenceFact(
                value=True,
                evidence=_sentence_with(text, injection_match.group(0)),
                confidence=1.0,
                provenance=Provenance.MESSAGE,
            )

        return ExtractedFacts(
            customer=customer,
            site=site,
            asset=asset,
            problem=problem,
            symptoms=symptoms,
            desired_deadline=desired_deadline,
            backup_available=backup,
            previous_contact=previous_contact,
            suspicious_instruction=suspicious_instruction,
        )
