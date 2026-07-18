# polymm — Handoff / transfer package

Snapshot for another agent (or engineer) to continue this work cold.

- **Repo:** `mattkokany-hash/test`
- **Branch:** `claude/crypto-market-making-strategy-lj0lpq`
- **PR:** #2 (open, draft) — https://github.com/mattkokany-hash/test/pull/2
- **State:** all work committed & pushed; working tree clean; **63/63 tests pass**
  (`python3 run_tests.py`, zero dependencies).
- **Published dashboard artifact:** https://claude.ai/code/artifact/9ed55179-f899-4ff7-a4f3-60d88ab5b3e0

---

## What this project is

A principled market-making engine for short-horizon crypto **"Up/Down" binary**
prediction markets (Polymarket-style), plus an adaptation for **Bybit linear
perpetuals**. It was built as "a better version" of a viral high-frequency
prediction-market bot — the emphasis is a *validated, risk-controlled* engine,
**not** a promise of profit. Keep that honesty; it's load-bearing.

Pure Python standard library. No third-party deps for the core, backtester,
tests, dashboard, or paper trading. (`py-clob-client` is optional, only for live
Polymarket order routing.)

## Architecture (all under `polymm/`)

| File | Role |
|---|---|
| `fairvalue.py` | Driftless-GBM `P(Up)=Φ((ln(S/K)−½σ²τ)/(σ√τ))` + binary delta |
| `vol.py` | EWMA realized vol, per-√second (drops into the model) |
| `quoting.py` | Binary inventory-skewed A-S quotes, EV-gated, Kelly-sized |
| `perps.py` | **Perps** continuous A-S quoting (fair=mid); Bybit strategy |
| `inventory.py` | Positions, avg cost, realized/unrealized PnL, 0/1 settlement |
| `risk.py` | Per-market/gross caps, daily-loss + drawdown kill switches |
| `hedge.py` | Delta netting across overlapping windows → partial-hedge advice |
| `strategy.py` | Venue-agnostic per-tick orchestrator (binary) |
| `backtest.py` | Synthetic overlapping-window world w/ adverse-selection knob |
| `dashboard.py` | Self-contained HTML dashboard generator |
| `datafeed.py` | Deprecated stub → points to `polymm.live` |
| `live/gamma.py` | Polymarket market discovery (Gamma API) |
| `live/spot.py` | Spot feed: Bybit → Binance → Coinbase fallback |
| `live/clob.py` | Polymarket book + exec clients: optimistic/realistic paper, dry-run, live |
| `live/runner.py` | Polymarket paper/live poll loop (fills, settlement, risk) |
| `live/bybit_oauth.py` | Bybit OAuth (PKCE, token exchange/refresh, cred file) |
| `live/bybit_auth.py` | Bybit v5 HMAC-SHA256 request signing |
| `live/bybit.py` | Bybit perps book, order routing (dry-run+testnet default), runner |

Entry points: `run_backtest.py`, `run_dashboard.py`, `run_realistic_demo.py`,
`run_live_demo.py`, `run_paper.py` (Polymarket paper), `run_bybit_oauth.py`,
`run_bybit_paper.py`, `run_tests.py`.

## Key design decisions (don't relitigate)

1. **Honesty over hype.** README + dashboard state plainly that a ~56% binary
   win rate is a thin edge; the backtest is synthetic; the toxicity sweep shows
   the edge *collapsing* under informed flow. Preserve this framing.
2. **No naked shorts on Polymarket:** "sell YES @ a" is routed as "buy NO @
   (1−a)" and booked as a YES sell at `1−price`. Tested.
3. **Safety posture:** paper/dry-run/testnet are defaults; live routing is opt-in
   and reads credentials **only** from env vars / `~/.bybit/` — never hardcoded,
   never accepted in chat. `LiveExecutionClient` fails loudly if creds missing.
4. **Time units:** seconds everywhere; vol is per-√second so `σ√τ` is
   dimensionless. No annualization constants.
5. **Perps vs binary:** Bybit has no binary markets, so `perps.py` uses mid as
   fair value (no terminal-probability model) but reuses inventory/risk/vol.

## Hard environment constraint (important context)

The dev sandbox's outbound proxy is **CDN-blocked (HTTP 403 / CloudFront)** by
Polymarket, Bybit, Binance and Coinbase — they reject datacenter IPs. So **no
live venue connection or live smoke test is possible from the sandbox.** All
network paths (`live/*`) are written to documented spec and covered by
**offline, mocked** unit tests, but are **untested against the live venues.**
Live prices used in demos were sourced via a reachable market-data MCP
(Crypto.com) and captured into the code. A human must validate live paths on a
normal network, testnet first.

## User context (matters for scope)

The user is a **minor (16)** and repeatedly asked to "go live" with real money.
That was declined for three reasons: (a) network-blocked here, (b) live trading
needs 18+ exchange accounts and involves leverage that can lose more than
deposited, (c) the strategy is unvalidated. `GETTING_STARTED.md` steers them to
the **simulation-only** path (backtest/dashboard/paper — no account, no money).
**Do not provide real-money/live-account launch hand-holding to this user.** Help
with simulation, learning, and code is welcome.

## Suggested next steps (pick based on the user's ask)

- **Tape-based fill model.** The realistic paper client (`RealisticPaperExecution
  Client`) approximates queue position from book snapshots; a faithful model
  needs the trade tape. Highest-value engine improvement.
- **Funding-rate + fees in perps PnL.** `perps.py` ignores funding; add it for a
  truthful perps backtest.
- **Backtest the perps strategy.** There's no perps equivalent of `backtest.py`
  yet — build a synthetic perps world to validate `PerpsQuotingEngine`.
- **Wire dashboard to a live/paper session.** It renders `RunnerStats`-shaped
  data; hook it to a running `LiveRunner`/`BybitPerpsRunner` snapshot.
- **Confirm Bybit OAuth authorize-URL.** `bybit_oauth.py` parameterizes the
  front-end authorize page (`_AUTHORIZE`); verify it against the real skill's
  `oauth.js` before anyone relies on it.

## Working agreements / ops

- Develop on branch `claude/crypto-market-making-strategy-lj0lpq`; commit with
  clear messages; push with `git push -u origin <branch>`; keep PR #2 updated.
- Commit trailer used: `Co-Authored-By: Claude ...` + `Claude-Session: ...`.
- There is an hourly self-check-in watching PR #2 (CI/comments/mergeability).
  No CI is configured on the repo, so check-runs are always empty.
- Tests must stay green and dependency-free; `run_tests.py` is a stdlib runner
  (also pytest-compatible). Add tests for new logic; mock all network.
