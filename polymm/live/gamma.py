"""Market discovery via Polymarket's Gamma API.

Gamma (``https://gamma-api.polymarket.com``) is the read-only metadata layer. We
use it to find the currently active short-horizon "Up / Down" crypto markets and
extract, for each one:

* the two CLOB token ids (the YES/"Up" outcome token and the NO/"Down" token),
* the resolution timestamp,
* the window start timestamp,
* the underlying asset (BTC/ETH/...) so we know which spot feed drives it.

The reference/strike price (spot at window open) is generally *not* a first-class
Gamma field for these markets -- it is defined by the resolution source at the
window's start instant. This adapter therefore captures the strike from the spot
feed at the moment a window opens (see ``runner.py``); markets we join mid-window
without a known strike are skipped rather than guessed. That is the honest,
safe default.
"""

from __future__ import annotations

import datetime as _dt
import json
from dataclasses import dataclass

from .http import get_json

__all__ = ["PolyMarket", "GammaClient", "parse_iso8601"]

GAMMA_BASE = "https://gamma-api.polymarket.com"

# Question-text hints that identify a short crypto up/down window and its asset.
_ASSET_HINTS = {
    "bitcoin": "BTC", "btc": "BTC",
    "ethereum": "ETH", "eth": "ETH",
    "solana": "SOL", "sol": "SOL",
}


def parse_iso8601(s: str) -> float:
    """Parse an ISO-8601 timestamp (e.g. '2026-07-16T19:00:00Z') to epoch secs."""
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return _dt.datetime.fromisoformat(s).timestamp()


@dataclass
class PolyMarket:
    market_id: str          # conditionId (stable id)
    slug: str
    question: str
    asset: str              # 'BTC' / 'ETH' / ...
    yes_token_id: str       # CLOB token id for the 'Up' outcome
    no_token_id: str        # CLOB token id for the 'Down' outcome
    start_at: float         # epoch seconds
    resolve_at: float       # epoch seconds
    closed: bool


def _detect_asset(text: str) -> str | None:
    low = text.lower()
    for hint, sym in _ASSET_HINTS.items():
        if hint in low:
            return sym
    return None


def _is_up_down(question: str) -> bool:
    q = question.lower()
    return ("up or down" in q) or ("up/down" in q) or (" up " in q and "down" in q)


def _load_json_field(value, default):
    """Gamma returns some array fields as JSON-encoded strings."""
    if isinstance(value, (list, dict)):
        return value
    if isinstance(value, str) and value:
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default
    return default


class GammaClient:
    def __init__(self, base: str = GAMMA_BASE, timeout: float = 10.0):
        self.base = base.rstrip("/")
        self.timeout = timeout

    def _markets(self, params: dict) -> list[dict]:
        data = get_json(f"{self.base}/markets", params, timeout=self.timeout)
        if isinstance(data, dict):  # some deployments wrap in {"data": [...]}
            data = data.get("data", [])
        return data if isinstance(data, list) else []

    def active_up_down(self, *, assets: set[str] | None = None,
                       limit: int = 200) -> list[PolyMarket]:
        """Return active, open, short-horizon up/down markets.

        ``assets`` optionally restricts to a set like ``{"BTC", "ETH"}``.
        """
        raw = self._markets({
            "active": "true",
            "closed": "false",
            "limit": str(limit),
            "order": "endDate",
            "ascending": "true",
        })
        out: list[PolyMarket] = []
        for m in raw:
            question = m.get("question") or m.get("title") or ""
            if not _is_up_down(question):
                continue
            asset = _detect_asset(question) or _detect_asset(m.get("slug", ""))
            if asset is None:
                continue
            if assets and asset not in assets:
                continue

            token_ids = _load_json_field(m.get("clobTokenIds"), [])
            if len(token_ids) < 2:
                continue
            outcomes = _load_json_field(m.get("outcomes"), ["Up", "Down"])
            yes_idx = _up_index(outcomes)

            start_s = m.get("startDate") or m.get("startTime")
            end_s = m.get("endDate") or m.get("endDateIso") or m.get("endTime")
            if not end_s:
                continue
            try:
                resolve_at = parse_iso8601(end_s)
                start_at = parse_iso8601(start_s) if start_s else resolve_at
            except (ValueError, TypeError):
                continue

            out.append(PolyMarket(
                market_id=str(m.get("conditionId") or m.get("id") or m.get("slug")),
                slug=str(m.get("slug", "")),
                question=question,
                asset=asset,
                yes_token_id=str(token_ids[yes_idx]),
                no_token_id=str(token_ids[1 - yes_idx]),
                start_at=start_at,
                resolve_at=resolve_at,
                closed=bool(m.get("closed", False)),
            ))
        return out

    def market_by_condition(self, condition_id: str) -> dict | None:
        raw = self._markets({"condition_ids": condition_id})
        return raw[0] if raw else None


def _up_index(outcomes: list) -> int:
    """Index of the 'Up'/'Yes' outcome among the two tokens."""
    for i, o in enumerate(outcomes):
        if str(o).strip().lower() in ("up", "yes"):
            return i
    return 0
