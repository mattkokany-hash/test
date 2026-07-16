"""Offline tests for the live adapter. Everything network-facing is faked, so
these run with no connectivity and no credentials."""

from polymm.config import StrategyConfig
from polymm.live import gamma as gamma_mod
from polymm.live.gamma import (
    GammaClient, PolyMarket, parse_iso8601, _up_index, _is_up_down, _detect_asset,
    _load_json_field,
)
from polymm.live.spot import SpotSource, MultiSourceSpot
from polymm.live.clob import PaperExecutionClient, Fill, ExecutionClient
from polymm.live.runner import LiveRunner


# --- gamma parsing --------------------------------------------------------

def test_iso8601_parsing_utc():
    t = parse_iso8601("2026-07-16T19:00:00Z")
    assert isinstance(t, float) and t > 0


def test_up_index_and_asset_detection():
    assert _up_index(["Up", "Down"]) == 0
    assert _up_index(["Down", "Up"]) == 1
    assert _up_index(["Yes", "No"]) == 0
    assert _detect_asset("Bitcoin Up or Down - 3PM ET") == "BTC"
    assert _detect_asset("Will Ethereum go up?") == "ETH"
    assert _is_up_down("Bitcoin Up or Down?")
    assert not _is_up_down("Will BTC hit 100k?")


def test_load_json_field_handles_string_and_list():
    assert _load_json_field('["a","b"]', []) == ["a", "b"]
    assert _load_json_field(["a", "b"], []) == ["a", "b"]
    assert _load_json_field("not json", ["d"]) == ["d"]


def test_gamma_active_up_down_parses_markets(monkeypatch):
    fake_rows = [
        {
            "conditionId": "0xabc", "slug": "bitcoin-up-or-down-3pm",
            "question": "Bitcoin Up or Down - July 16 3PM ET",
            "clobTokenIds": '["111","222"]', "outcomes": '["Up","Down"]',
            "startDate": "2026-07-16T18:00:00Z", "endDate": "2026-07-16T19:00:00Z",
            "active": True, "closed": False,
        },
        {  # not an up/down market -> filtered out
            "conditionId": "0xdef", "slug": "btc-100k",
            "question": "Will BTC hit 100k in 2026?",
            "clobTokenIds": '["333","444"]', "outcomes": '["Yes","No"]',
            "endDate": "2026-12-31T00:00:00Z", "active": True, "closed": False,
        },
    ]
    monkeypatch.setattr(gamma_mod, "get_json", lambda *a, **k: fake_rows)
    out = GammaClient().active_up_down(assets={"BTC"})
    assert len(out) == 1
    m = out[0]
    assert m.asset == "BTC"
    assert m.yes_token_id == "111" and m.no_token_id == "222"
    assert m.resolve_at > m.start_at


# --- spot fallback --------------------------------------------------------

class _FailSpot(SpotSource):
    def price(self, asset):
        raise ValueError("down")


class _OkSpot(SpotSource):
    def __init__(self, px):
        self.px = px

    def price(self, asset):
        return self.px


def test_multisource_spot_falls_back():
    src = MultiSourceSpot(sources=[_FailSpot(), _OkSpot(60000.0)])
    assert src.price("BTC") == 60000.0


# --- paper execution against a fake book ----------------------------------

class _FakeBook:
    def __init__(self, ask):
        self.ask = ask

    def best_ask(self, token_id):
        return self.ask


def test_paper_fill_when_ask_crosses():
    book = _FakeBook(ask=0.55)
    ex = PaperExecutionClient(book=book)
    oid = ex.submit("tok", price=0.50, size=100.0)
    assert ex.poll_fills() == []          # ask 0.55 > our 0.50 -> no fill
    book.ask = 0.49                        # ask drops to/below our bid
    fills = ex.poll_fills()
    assert len(fills) == 1 and fills[0].order_id == oid
    assert ex.open_orders() == []          # consumed


# --- runner wiring --------------------------------------------------------

class _FakeExec(ExecutionClient):
    def __init__(self):
        self.submitted = []      # (token_id, price, size, order_id)
        self.cancelled = []
        self._queued = []
        self._n = 0

    def submit(self, token_id, price, size):
        self._n += 1
        oid = f"o{self._n}"
        self.submitted.append((token_id, price, size, oid))
        return oid

    def cancel(self, order_id):
        self.cancelled.append(order_id)

    def open_orders(self):
        return [s[3] for s in self.submitted]

    def queue_fill(self, order_id, token_id, price, size):
        self._queued.append(Fill(order_id, token_id, price, size))

    def poll_fills(self):
        out, self._queued = self._queued, []
        return out


def _btc_market():
    return PolyMarket(
        market_id="0xabc", slug="btc-updown", question="Bitcoin Up or Down",
        asset="BTC", yes_token_id="YES", no_token_id="NO",
        start_at=0.0, resolve_at=300.0, closed=False,
    )


class _StaticGamma:
    def __init__(self, markets):
        self._m = markets

    def active_up_down(self, assets=None):
        return self._m

    def market_by_condition(self, cid):
        return None


def _runner(clock_holder, exec_client, spot_px=60000.0):
    gamma = _StaticGamma([_btc_market()])
    return LiveRunner(
        StrategyConfig(),
        execution=exec_client,
        spot=_OkSpot(spot_px),
        gamma=gamma,
        assets={"BTC"},
        discovery_interval_s=0.0,
        clock=lambda: clock_holder[0],
    )


def test_runner_captures_strike_and_quotes():
    t = [10.0]                      # 10s into the window (tau ~ 290s)
    ex = _FakeExec()
    r = _runner(t, ex)
    r.poll()
    tm = r.tracked["0xabc"]
    assert tm.strike == 60000.0     # captured from spot at window open
    # Flat + far from resolution => a two-sided quote => two BUY orders:
    #   YES token (buy YES) and NO token (sell YES == buy NO).
    tokens = {s[0] for s in ex.submitted}
    assert "YES" in tokens and "NO" in tokens


def test_sell_side_routed_as_buy_no_at_complement():
    t = [10.0]
    ex = _FakeExec()
    r = _runner(t, ex)
    r.poll()
    yes_orders = [s for s in ex.submitted if s[0] == "YES"]
    no_orders = [s for s in ex.submitted if s[0] == "NO"]
    assert yes_orders and no_orders
    # The NO order price is the complement of the YES ask (both near 0.5 here),
    # and must be a valid probability.
    no_price = no_orders[0][1]
    assert 0.0 < no_price < 1.0


def test_fill_on_no_token_books_a_yes_sell():
    t = [10.0]
    ex = _FakeExec()
    r = _runner(t, ex)
    r.poll()
    no_order = next(s for s in ex.submitted if s[0] == "NO")
    token_id, price, size, oid = no_order
    # Simulate the NO order filling; next poll should reconcile it.
    ex.queue_fill(oid, token_id, price, size)
    r.poll()
    pos = r.inv.position("0xabc")
    assert pos.qty < 0.0            # buying NO == short YES
    assert r.stats.fills >= 1


def test_settlement_at_resolution():
    t = [10.0]
    ex = _FakeExec()
    r = _runner(t, ex)
    r.poll()                        # opens/quotes, strike = 60000
    # Take a long YES position via a YES-token fill.
    yes_order = next(s for s in ex.submitted if s[0] == "YES")
    ex.queue_fill(yes_order[3], "YES", yes_order[1], yes_order[2])
    r.poll()
    # Advance past resolution with spot above strike => YES wins.
    t[0] = 301.0
    r.poll()
    tm = r.tracked["0xabc"]
    assert tm.resolved
    assert r.stats.settled == 1
    assert r.inv.realized_pnl > 0.0  # long YES, resolved UP


def test_halt_pulls_quotes():
    t = [10.0]
    ex = _FakeExec()
    r = _runner(t, ex)
    r.risk._halt("manual")
    snap = r.poll()
    assert snap["halted"]
    # No new orders while halted (cancels may fire, submits must not).
    assert ex.submitted == []
