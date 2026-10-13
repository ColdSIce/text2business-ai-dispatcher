from __future__ import annotations

import re
from importlib.resources import files

from text2business.models import (
    AssetMatch,
    CorporateData,
    FindAssetsInput,
    FindAssetsOutput,
    FindOpenTicketsInput,
    FindOpenTicketsOutput,
    FindSiteInput,
    FindSiteOutput,
    GetContractInput,
    GetContractOutput,
    SiteMatch,
    TicketMutationInput,
    TicketMutationOutput,
)


def _normalize(value: str) -> str:
    return " ".join(re.findall(r"[a-zа-яё0-9]+", value.casefold()))


class MockCorporateTools:
    def __init__(self) -> None:
        path = files("text2business").joinpath("data/corporate.json")
        self.data = CorporateData.model_validate_json(path.read_text(encoding="utf-8"))

    def find_customer_or_site(self, payload: FindSiteInput) -> FindSiteOutput:
        query = _normalize(payload.query)
        matches: list[SiteMatch] = []
        for site in self.data.sites:
            score = 0
            reasons: list[str] = []
            if _normalize(site.customer_name) in query:
                score += 2
                reasons.append("customer_name_exact")

            address = _normalize(site.address)
            address_tokens = {
                token
                for token in address.split()
                if token not in {"москва", "екатеринбург", "улица", "шоссе"}
            }
            query_tokens = set(query.split())
            descriptive_tokens = {token for token in address_tokens if not token.isdigit()}
            descriptive_match = any(
                any(
                    candidate == token
                    or (
                        len(token) >= 8
                        and len(candidate) >= 8
                        and candidate[:8] == token[:8]
                    )
                    for candidate in query_tokens
                )
                for token in descriptive_tokens
            )
            if descriptive_match:
                score += 3
                reasons.append("address_street_match")
            numeric_tokens = {token for token in address_tokens if token.isdigit()}
            if numeric_tokens.intersection(query_tokens):
                score += 1
                reasons.append("address_number_match")

            if score:
                matches.append(SiteMatch(site=site, score=score, matched_by=reasons))
        matches.sort(key=lambda item: (-item.score, item.site.site_id))
        return FindSiteOutput(matches=matches)

    def find_assets(self, payload: FindAssetsInput) -> FindAssetsOutput:
        query = _normalize(payload.query).replace(" ", "")
        matches = []
        for asset in self.data.assets:
            code = _normalize(asset.local_code).replace(" ", "")
            if asset.site_id == payload.site_id and code in query:
                matches.append(AssetMatch(asset=asset, matched_by=["local_code_exact"]))
        return FindAssetsOutput(matches=matches)

    def get_contract(self, payload: GetContractInput) -> GetContractOutput:
        contract = next(
            (item for item in self.data.contracts if item.site_id == payload.site_id),
            None,
        )
        return GetContractOutput(contract=contract)

    def find_open_tickets(self, payload: FindOpenTicketsInput) -> FindOpenTicketsOutput:
        tickets = [
            ticket
            for ticket in self.data.open_tickets
            if ticket.asset_id == payload.asset_id
            and ticket.status not in {"closed", "cancelled", "resolved"}
        ]
        return FindOpenTicketsOutput(tickets=tickets)

    def create_or_update_ticket(
        self, payload: TicketMutationInput
    ) -> TicketMutationOutput:
        return TicketMutationOutput(
            accepted=True,
            proposal=payload,
            warnings=["DRY RUN: corporate data was not changed"],
        )
