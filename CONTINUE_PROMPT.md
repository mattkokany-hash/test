# Continuation prompt (paste this to the next agent)

> You are picking up an existing project. **Read `HANDOFF.md` at the repo root
> first — it is the source of truth for state, decisions, and constraints.**
>
> **Project:** `polymm` — a dependency-free Python market-making engine for
> crypto "Up/Down" binary prediction markets (Polymarket), plus a Bybit linear-
> perpetuals adaptation. Repo `mattkokany-hash/test`, branch
> `claude/crypto-market-making-strategy-lj0lpq`, open draft PR #2. All work is
> committed and pushed; `python3 run_tests.py` shows 63/63 passing, zero deps.
>
> **Ground rules (do not violate):**
> 1. Keep the honest framing — this is a validated, risk-controlled engine, NOT a
>    profit promise. The backtest is synthetic; the toxicity sweep shows the edge
>    collapsing under informed flow. Never oversell returns.
> 2. Safety defaults stay: paper / dry-run / testnet by default; live routing is
>    opt-in and reads credentials only from env vars / `~/.bybit/` — never
>    hardcode secrets, never accept them in chat.
> 3. The user is a 16-year-old. Do NOT hand-hold them into real-money or live-
>    exchange account setup (18+ required; leverage risk). Help freely with
>    simulation, learning, and code. See `GETTING_STARTED.md`.
> 4. The dev sandbox is CDN-blocked from Polymarket/Bybit/Binance/Coinbase (HTTP
>    403) — you cannot do a live venue smoke test here. Keep new network code
>    behind offline, mocked tests; a human validates live paths on a real network.
> 5. Tests stay green and dependency-free; add tests for new logic and mock all
>    network. Develop on the branch above, commit clearly, push, keep PR #2 current.
>
> **Your task:** <STATE THE SPECIFIC NEXT TASK HERE>. If unspecified, propose
> from the "Suggested next steps" in `HANDOFF.md` (top candidate: a trade-tape-
> based fill model, or a synthetic perps backtest to validate `PerpsQuotingEngine`)
> and confirm with the user before large changes.
>
> Start by running `python3 run_tests.py` to confirm a green baseline, then read
> the files named in `HANDOFF.md` relevant to your task.
