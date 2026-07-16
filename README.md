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
  datafeed.py    feed/discovery interfaces + a Polymarket adapter STUB
tests/           34 stdlib tests (also runnable under pytest)
run_tests.py     zero-dependency test runner
run_backtest.py  demo: baseline run + toxicity sweep + kill-switch check
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

## Wiring it to a real venue

`strategy.MarketMaker` is deliberately venue-agnostic — it consumes
`(spot, now, [MarketState])` and emits desired quotes + a hedge recommendation.
`backtest.py` is one adapter over a synthetic world. A live Polymarket adapter
(`datafeed.PolymarketAdapter`, currently a stub) would supply:

1. **Market discovery** — active up/down windows, their strikes, resolve times
   (Gamma API).
2. **A spot feed** — a low-latency price for the underlying (CEX websocket or a
   Pyth/Chainlink oracle) to drive the model.
3. **Order routing** — translate quotes into post-only CLOB orders and reconcile
   fills back through `record_fill` / `settle`.

That layer needs credentials, rate-limit handling, and careful fill
reconciliation, so it belongs in a separately reviewed deployment — not bundled
with the modelling core.

## Before you even think about going live

- Re-run the backtest against **your own recorded ticks and real fee/slippage**,
  not the synthetic path.
- Start in **paper / tiny size**. Confirm your measured fill-time edge survives
  latency.
- Keep the kill switches **tight**. The screenshots never show the accounts that
  blew up; the whole point of `risk.py` is to not become one.
- This is not financial advice, and prediction-market trading may be restricted
  where you live — that's on you to check.
