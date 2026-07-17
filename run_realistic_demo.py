#!/usr/bin/env python3
"""Quantify optimistic vs realistic paper fills on an identical book replay.

Live Polymarket/Bybit are CDN-blocked from this sandbox, so instead of a live
paper session this drives BOTH execution clients over the *same* simulated ask
path and reports how much the optimistic model over-fills — the whole reason the
realistic client exists.

    python3 run_realistic_demo.py
"""

from __future__ import annotations

import math
import random

from polymm.live.clob import PaperExecutionClient, RealisticPaperExecutionClient


class ReplayBook:
    """A one-token book whose best ask is driven from a pre-generated path."""
    def __init__(self):
        self.ask = 0.50

    def best_ask(self, token_id: str) -> float:
        return self.ask


def ask_path(n: int, seed: int) -> list[float]:
    """Ask price wandering around 0.50 so it repeatedly touches/through a
    maker bid at 0.495 — a realistic stream of fill opportunities."""
    rng = random.Random(seed)
    p, out = 0.50, []
    for _ in range(n):
        p += rng.gauss(0, 0.0018)
        p = min(0.60, max(0.40, p))
        out.append(round(p, 4))
    return out


def run(client_factory, path, bid=0.495, size=100.0, dt=0.25):
    book = ReplayBook()
    t = [0.0]
    ex = client_factory(book, t)
    fills, filled_qty, first_fill_t = 0, 0.0, None
    touches = throughs = 0
    for i, a in enumerate(path):
        t[0] = i * dt
        book.ask = a
        if a <= bid - 0.001 + 1e-12:
            throughs += 1
        elif a <= bid + 1e-12:
            touches += 1
        if not ex.open_orders():
            ex.submit("TOK", bid, size)
        for f in ex.poll_fills():
            fills += 1
            filled_qty += f.size
            if first_fill_t is None:
                first_fill_t = t[0]
    return {
        "fills": fills, "filled_qty": filled_qty,
        "first_fill_t": first_fill_t, "touches": touches, "throughs": throughs,
    }


def main() -> None:
    N, SEED = 4000, 11
    path = ask_path(N, SEED)
    opps = sum(1 for a in path if a <= 0.495 + 1e-12)

    opt = run(lambda b, t: PaperExecutionClient(book=b), path)
    real = run(lambda b, t: RealisticPaperExecutionClient(
        book=b, clock=lambda: t[0], latency_s=0.4, fill_prob=0.55,
        touch_fill_prob=0.08, seed=SEED), path)

    print(f"replay: {N} polls, {opps} cycles with ask at/below the 0.495 bid "
          f"({real['throughs']} through, {real['touches']} touch)\n")
    hdr = f"{'model':<12}{'fills':>8}{'filled qty':>13}{'first fill':>12}"
    print(hdr); print("-" * len(hdr))
    for name, r in (("optimistic", opt), ("realistic", real)):
        ff = f"{r['first_fill_t']:.2f}s" if r["first_fill_t"] is not None else "—"
        print(f"{name:<12}{r['fills']:>8}{r['filled_qty']:>13,.0f}{ff:>12}")

    ratio = real["filled_qty"] / opt["filled_qty"] if opt["filled_qty"] else 0
    print(f"\nrealistic filled {ratio*100:.0f}% of the optimistic volume — the rest is")
    print("latency, queue position, and partial fills the optimistic model ignores.")
    print("Assume your live fill rate is closer to the realistic line, not the optimistic one.")


if __name__ == "__main__":
    main()
