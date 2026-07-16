# polymm — a principled market-making engine for crypto "Up / Down" binaries

A cleaner, more defensible take on the high-frequency market-making approach
people run on short crypto **Up / Down** prediction markets (e.g. Polymarket's
hourly BTC/ETH up-or-down windows).

> **Read this first.** The viral "25,448 trades, 56% win rate, $2,224/day"
> screenshots are survivorship-biased marketing. A ~56% hit rate on near-50/50
> binaries is a *razor-thin* edge that fees, latency, and adverse selection
> erase with ease. This repo does **not** promise profit. Its real product is
> the **backtester and risk engine** — the machinery that tells you whether an
> edge exists *before* you risk a cent, and that caps the damage when a regime
> turns against you. If the backtest can't show positive risk-adjusted edge on
> **your own recorded data with realistic fees**, don't run it live.

Everything here is **pure Python standard library** — no dependencies, no keys,
no live order routing. The live venue adapter is a documented stub on purpose.

---

## Why this is a "better version"

The described bot is essentially order-book pattern matching plus manual hedging.
This engine replaces the guesswork with a model and wraps it in real controls:

| Piece | The described bot | This engine |
|---|---|---|
| Fair value | implied from the book | **driftless-GBM terminal-price model** from live spot, strike, time-to-resolve, and EWMA realized vol (`fairvalue.py`, `vol.py`) |
| "Temporal arbitrage" | vibes | a probability that **updates continuously** as spot drifts and the clock runs — compared against the quoted book to find dislocations |
| Quoting | fixed spreads | **inventory-skewed** Avellaneda–Stoikov reservation price, EV-gated after fees, fractional-Kelly sizing (`quoting.py`) |
| Hedging | manual, leg-by-leg | **delta-based netting** across overlapping/adjacent windows — hedge the aggregate, not each leg (`hedge.py`) |
| Adverse selection | — | spreads **widen into resolution** and quotes are **pulled** inside the toxic cutoff (`quoting.py`) |
| Risk | — | per-market caps, gross-exposure cap, **daily-loss + drawdown kill switches** (`risk.py`) |
| Validation | a screenshot | a **backtester** with an adjustable adverse-selection knob (`backtest.py`) |

---

## The core idea in one equation

A window resolves **Up** (pays \$1) if spot at close `S_T` ≥ the window's
reference price `K`. Modelling log-price as driftless GBM over the short
remaining horizon `τ` with per-√second vol `σ`:

```
P(Up) = Φ( ( ln(S_t/K) − ½σ²τ ) / (σ·√τ) )
```

That single expression is the whole "temporal arbitrage" edge: it moves the
instant spot moves and as `τ` shrinks, usually faster than the book reprices.
We quote around it, skew for inventory, size by edge, hedge the net delta, and
let the risk engine pull the plug when things go wrong.

All time is in **seconds** and vol is **per-√second**, so `σ·√τ` is
dimensionless everywhere — no annualization constants to get wrong.

---

## Layout

```
polymm/
  fairvalue.py   GBM 'Up' probability Φ(...) and its underlying-delta
  vol.py         EWMA realized-vol estimator (per-√second)
  quoting.py     inventory-skewed, EV-gated, Kelly-sized two-sided quotes
  inventory.py   positions, average cost, realized/unrealized PnL, settlement
  risk.py        pre-trade caps + daily-loss / drawdown kill switches
  hedge.py       delta netting + partial-hedge recommendations
  strategy.py    per-tick orchestrator (venue-agnostic)
  backtest.py    synthetic overlapping-window world with an adverse-selection knob
  datafeed.py    generic feed/discovery interfaces (live adapter lives in live/)
  live/          real Polymarket adapter: gamma, spot, clob, runner
tests/           45 stdlib tests (also runnable under pytest)
run_tests.py     zero-dependency test runner
run_backtest.py  demo: baseline run + toxicity sweep + kill-switch check
run_paper.py     paper-trade the engine against LIVE books (no orders, no keys)
```

## Run it

```bash
python3 run_tests.py       # 34 tests, no dependencies
python3 run_backtest.py    # backtest summary + adverse-selection sweep
```

Example (numbers are from the *synthetic* world, not reality):

```
Baseline run
pnl=$1883.34  fees=$28.74  fills=14725  windows=334  win=57.2%  sharpe=3.68  maxDD=$709.75

Toxicity sweep (edge COLLAPSES once flow is informed enough)
toxicity=0.0   pnl=$ 243.25  win=51.8%  sharpe= 0.42
toxicity=0.6   pnl=$1883.34  win=57.2%  sharpe= 3.68
toxicity=1.0   pnl=$-1313.10 win=41.5%  sharpe=-2.49  HALTED[daily loss]
toxicity=1.5   pnl=$-1396.34 win=35.2%  sharpe=-3.59  HALTED[daily loss]
```

The sweep is the honest part: crank up `toxicity` (how informed the flow hitting
your quotes is) and the edge flips to a loss and the kill switch fires. **That is
what real adverse selection does to this style of strategy.**

## The live Polymarket adapter (`polymm/live/`)

The engine is venue-agnostic; `polymm/live/` is a working adapter that plugs it
into real Polymarket data. It is **dependency-free except for live order
routing**, and its default mode is **paper trading against the live book**.

| Module | Job |
|---|---|
| `live/gamma.py` | Discover active crypto Up/Down windows via the Gamma API — token ids, start/resolve times, asset |
| `live/spot.py` | Underlying spot feed (Binance primary, Coinbase fallback, same `price()` interface for a future websocket) |
| `live/clob.py` | Read the real CLOB book; `PaperExecutionClient` (simulated fills vs live depth) and `LiveExecutionClient` (real post-only orders via `py-clob-client`) |
| `live/runner.py` | `LiveRunner` poll loop: shared inventory + global kill switches, per-asset vol, strike capture at window open, fill reconciliation, settlement |

**Paper trade against live liquidity — no keys, no orders:**

```bash
python3 run_paper.py --cycles 50 --interval 3 --assets BTC,ETH
```

It discovers real markets, pulls the real book and real spot, quotes through the
risk engine, and simulates fills against actual depth.

**Two design points worth knowing:**

- **No naked shorts.** Polymarket won't let you sell a token you don't hold, so
  the runner expresses *"sell YES @ a"* as *"buy NO @ (1 − a)"*. A NO fill is
  booked as a YES sell at `1 − price`, so inventory/PnL math matches the backtest.
- **Strike capture.** The reference price for a window isn't a clean Gamma field,
  so the runner captures it from the spot feed at window open. Markets joined
  mid-window without a known strike are skipped rather than guessed.

### Going live (deliberate, opt-in)

Live order routing needs `py-clob-client` and credentials read **only** from the
environment (never source):

```bash
export POLY_PRIVATE_KEY=...        # wallet key (L1 signing)
export POLY_API_KEY=...            # CLOB API creds (L2)
export POLY_API_SECRET=...
export POLY_API_PASSPHRASE=...
export POLY_FUNDER=...             # optional proxy/funder address
```

```python
from polymm.config import StrategyConfig
from polymm.live import LiveRunner, LiveExecutionClient

runner = LiveRunner(StrategyConfig(), execution=LiveExecutionClient())
runner.run(interval_s=2.0)         # posts real post-only maker orders
```

`LiveExecutionClient` fails loudly if the library or any credential is missing,
so you can't accidentally go live half-configured.

> **Network note:** the public Gamma/CLOB/exchange endpoints sit behind
> Cloudflare and block many datacenter IPs (you'll see HTTP 403 / code 1010).
> Run from a network/region allowed to reach them; the adapter logs the block
> and keeps polling rather than crashing.

## Before you even think about going live

- Re-run the backtest against **your own recorded ticks and real fee/slippage**,
  not the synthetic path.
- Start in **paper / tiny size**. Confirm your measured fill-time edge survives
  latency.
- Keep the kill switches **tight**. The screenshots never show the accounts that
  blew up; the whole point of `risk.py` is to not become one.
- This is not financial advice, and prediction-market trading may be restricted
  where you live — that's on you to check.
