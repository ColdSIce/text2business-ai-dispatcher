from __future__ import annotations

import inspect

from pydantic import BaseModel

import text2business.models as models
from text2business.models import CorporateData
from text2business.repository import JsonCorporateRepository


def test_every_application_model_has_a_semantic_docstring() -> None:
    undocumented = []
    for name, candidate in vars(models).items():
        if (
            inspect.isclass(candidate)
            and issubclass(candidate, BaseModel)
            and candidate.__module__ == models.__name__
            and not inspect.getdoc(candidate)
        ):
            undocumented.append(name)
    assert undocumented == []


def test_fixture_is_fully_typed() -> None:
    repository = JsonCorporateRepository()
    assert isinstance(repository.data, CorporateData)
    assert len(repository.data.customers) == 2
    assert len(repository.data.tickets) == 3
