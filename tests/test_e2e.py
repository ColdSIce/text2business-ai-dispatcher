from datetime import datetime

from text2business.models import Action, IncomingRequest
from text2business.workflow import run_case


def test_full_request_produces_explainable_create_dry_run() -> None:
    request = IncomingRequest(
        channel="email",
        sender='Андрей, «СеверФуд»',
        received_at=datetime.fromisoformat("2026-08-13T16:40:00+03:00"),
        text=(
            "СеверФуд, склад на Дмитровском шоссе, 100. "
            "ХУ-18 не запускается после перезагрузки. "
            "Продукцию пока перенесли в соседнюю камеру. "
            "Нужен выезд специалиста."
        ),
    )

    result = run_case(request)

    assert result.resolved_site is not None
    assert result.resolved_site.site_id == "S-MSK-01"
    assert result.resolved_asset is not None
    assert result.resolved_asset.asset_id == "A-1003"
    assert result.decision.action == Action.CREATE_NEW
    assert result.priority is not None and result.priority.priority == "P3"
    assert result.sla is not None
    assert result.sla.deadline.isoformat() == "2026-08-13T17:40:00+03:00"
    assert result.mutation is not None
    assert result.mutation.dry_run is True
    assert result.mutation.proposal.expected_version == 0
    assert result.mutation.proposal.requires_human_confirmation is True
    assert len(result.mutation.proposal.idempotency_key) == 64
    assert [event.name for event in result.trace] == [
        "deterministic_extraction",
        "find_customer_or_site",
        "find_assets",
        "get_contract",
        "find_open_tickets",
        "business_rules",
        "create_or_update_ticket",
    ]

