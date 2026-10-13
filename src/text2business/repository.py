from __future__ import annotations

import hashlib
import re
from importlib.resources import files

from text2business.models import (
    Action,
    AssetMatch,
    CorporateData,
    CustomerMatch,
    FindAssetsInput,
    FindAssetsOutput,
    FindCustomersInput,
    FindCustomersOutput,
    FindSitesInput,
    FindSitesOutput,
    FindTicketsInput,
    FindTicketsOutput,
    GetCapacityInput,
    GetCapacityOutput,
    GetContractInput,
    GetContractOutput,
    GetCustomerInput,
    GetCustomerOutput,
    SiteMatch,
    TicketChangeProposal,
    TicketChangeProposalOutput,
)


def normalize_text(value: str) -> str:
    """Normalize Russian/Latin free text for deterministic fixture matching."""

    return " ".join(re.findall(r"[a-zа-яё0-9]+", value.casefold()))


def _token_matches(query_token: str, candidate_token: str) -> bool:
    """Match exact tokens or stable word stems without fuzzy external libraries."""

    if query_token == candidate_token:
        return True
    return (
        len(query_token) >= 8
        and len(candidate_token) >= 8
        and query_token[:8] == candidate_token[:8]
    )


class JsonCorporateRepository:
    """Read-only typed adapter over the packaged corporate JSON fixture."""

    def __init__(self) -> None:
        path = files("text2business").joinpath("data/corporate.json")
        raw = path.read_bytes()
        self.source_digest = hashlib.sha256(raw).hexdigest()
        self.data = CorporateData.model_validate_json(raw)

    def get_customer(self, payload: GetCustomerInput) -> GetCustomerOutput:
        """Return an exact customer for a trusted CRM identifier."""

        customer = next(
            (item for item in self.data.customers if item.customer_id == payload.customer_id),
            None,
        )
        return GetCustomerOutput(customer=customer)

    def find_customers(self, payload: FindCustomersInput) -> FindCustomersOutput:
        """Return deterministic customer candidates for untrusted display text."""

        query = normalize_text(payload.query)
        matches: list[CustomerMatch] = []
        for customer in self.data.customers:
            labels = [customer.name, *customer.aliases]
            normalized = [normalize_text(label) for label in labels]
            exact = [label for label in normalized if label and label in query]
            if exact:
                matches.append(
                    CustomerMatch(
                        customer=customer,
                        score=10,
                        matched_by=["customer_label_exact"],
                    )
                )
        matches.sort(key=lambda item: (-item.score, item.customer.customer_id))
        return FindCustomersOutput(matches=matches)

    def find_sites(self, payload: FindSitesInput) -> FindSitesOutput:
        """Rank sites only inside the confirmed customer scope."""

        query_tokens = set(normalize_text(payload.query).split())
        matches: list[SiteMatch] = []
        ignored = {
            "москва",
            "екатеринбург",
            "улица",
            "шоссе",
            "объект",
            "склад",
            "на",
        }
        for site in self.data.sites:
            if site.customer_id != payload.customer_id:
                continue
            address_tokens = set(normalize_text(site.address).split())
            score = 1
            reasons = ["customer_scope"]
            for candidate in address_tokens - ignored:
                if any(_token_matches(token, candidate) for token in query_tokens):
                    score += 3 if not candidate.isdigit() else 1
                    reasons.append("address_token_match")
            matches.append(SiteMatch(site=site, score=score, matched_by=sorted(set(reasons))))
        matches.sort(key=lambda item: (-item.score, item.site.site_id))
        return FindSitesOutput(matches=matches)

    def find_assets(self, payload: FindAssetsInput) -> FindAssetsOutput:
        """Rank assets only inside the resolved site scope."""

        query = normalize_text(payload.query).replace(" ", "")
        matches: list[AssetMatch] = []
        for asset in self.data.assets:
            if asset.site_id != payload.site_id:
                continue
            code = normalize_text(asset.local_code).replace(" ", "")
            score = 1
            reasons = ["site_scope"]
            if code and code in query:
                score = 10
                reasons.append("local_code_exact")
            matches.append(AssetMatch(asset=asset, score=score, matched_by=reasons))
        matches.sort(key=lambda item: (-item.score, item.asset.asset_id))
        return FindAssetsOutput(matches=matches)

    def get_contract(self, payload: GetContractInput) -> GetContractOutput:
        """Return the one fixture contract for a resolved site."""

        contract = next(
            (item for item in self.data.contracts if item.site_id == payload.site_id),
            None,
        )
        return GetContractOutput(contract=contract)

    def find_tickets(self, payload: FindTicketsInput) -> FindTicketsOutput:
        """Return exact scoped ticket history ordered newest first."""

        tickets = [
            ticket
            for ticket in self.data.tickets
            if ticket.customer_id == payload.customer_id
            and ticket.site_id == payload.site_id
            and ticket.asset_id == payload.asset_id
        ]
        tickets.sort(key=lambda item: (item.created_at, item.ticket_id), reverse=True)
        return FindTicketsOutput(tickets=tickets)

    def get_capacity(self, payload: GetCapacityInput) -> GetCapacityOutput:
        """Return informational capacity for one service group and region."""

        capacity = next(
            (
                item
                for item in self.data.capacities
                if item.service_group == payload.service_group
                and item.region == payload.region
            ),
            None,
        )
        return GetCapacityOutput(capacity=capacity)

    def propose_ticket_change(
        self, payload: TicketChangeProposal
    ) -> TicketChangeProposalOutput:
        """Validate a proposal and return it without opening any write path."""

        if payload.operation == Action.CREATE_NEW:
            if payload.expected_version != 0 or payload.target_ticket_id is not None:
                raise ValueError("create proposal requires version 0 and no target ticket")
        elif payload.operation == Action.UPDATE_EXISTING:
            if payload.expected_version < 1 or payload.target_ticket_id is None:
                raise ValueError("update proposal requires target ticket and current version")
        return TicketChangeProposalOutput(
            accepted=True,
            proposal=payload,
            warnings=["DRY RUN: corporate data was not changed"],
        )
