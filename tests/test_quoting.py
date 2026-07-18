from polymm.config import StrategyConfig
from polymm.quoting import QuotingEngine


def make(**kw):
    return QuotingEngine(StrategyConfig(**kw))


def test_two_sided_when_flat_and_far_from_resolution():
    q = make().quote("M", fair=0.50, inventory=0.0, tau=300.0)
    assert q.bid is not None and q.ask is not None
    assert q.bid < q.fair < q.ask


def test_quotes_pulled_near_resolution():
    q = make(resolution_cutoff_s=15.0).quote("M", 0.50, 0.0, tau=10.0)
    assert q.is_empty()


def test_inventory_skews_reservation_down_when_long():
    eng = make()
    flat = eng.quote("M", 0.50, 0.0, 300.0)
    long = eng.quote("M", 0.50, 1500.0, 300.0)
    # Long inventory should push the reservation price (and thus quotes) lower,
    # making us keener to sell than to buy.
    assert long.reservation < flat.reservation


def test_spread_widens_as_resolution_approaches():
    eng = make()
    far = eng.quote("M", 0.50, 0.0, 300.0)
    near = eng.quote("M", 0.50, 0.0, 30.0)
    far_spread = (far.ask - far.bid)
    near_spread = (near.ask - near.bid)
    assert near_spread > far_spread


def test_no_negative_or_supra_unit_quotes():
    eng = make()
    for fair in (0.02, 0.5, 0.98):
        q = eng.quote("M", fair, 0.0, 300.0)
        if q.bid is not None:
            assert q.bid > 0.0
        if q.ask is not None:
            assert q.ask < 1.0


def test_ev_gate_blocks_when_edge_below_threshold():
    # Huge required edge => nothing should quote.
    eng = make(base_edge=0.9)
    q = eng.quote("M", 0.50, 0.0, 300.0)
    assert q.is_empty()


def test_sizes_nonnegative():
    q = make().quote("M", 0.55, 0.0, 300.0)
    assert q.bid_size >= 0.0 and q.ask_size >= 0.0
