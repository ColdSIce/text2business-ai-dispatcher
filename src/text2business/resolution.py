from __future__ import annotations

from text2business.models import Asset, AssetMatch, Site, SiteMatch


def resolve_unique_site(matches: list[SiteMatch]) -> Site | None:
    """Select a site only when the best deterministic score is unique."""

    if not matches:
        return None
    best = matches[0].score
    top = [match.site for match in matches if match.score == best]
    return top[0] if len(top) == 1 else None


def resolve_unique_asset(matches: list[AssetMatch]) -> Asset | None:
    """Select an asset only when the best deterministic score is unique."""

    if not matches:
        return None
    best = matches[0].score
    top = [match.asset for match in matches if match.score == best]
    return top[0] if len(top) == 1 else None
