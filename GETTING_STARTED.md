# Getting started (no account, no money, no risk)

This guide runs the whole `polymm` engine **in simulation** on your own computer.
It never connects to a real exchange and never spends a cent — so it's the right
way to learn how this works. (Real trading on Bybit/Polymarket requires you to be
18+ and involves leverage that can lose more than you put in. The simulator below
teaches you the same ideas with zero risk.)

Everything here uses only Python's standard library — nothing to install but
Python itself.

---

## Step 1 — Install Python (once)

- **Windows:** go to <https://www.python.org/downloads/>, click the big yellow
  "Download Python" button, run the installer, and **tick "Add Python to PATH"**
  before clicking Install.
- **Mac:** it's usually already there. Open the **Terminal** app and type
  `python3 --version`. If it says a number like `3.11.x`, you're set. If not,
  install from the same link above.

Check it worked — open Terminal (Mac) or Command Prompt (Windows) and type:

```bash
python3 --version
```

You want to see something like `Python 3.11.x` (any 3.10 or higher is fine).

## Step 2 — Get the code

If you have `git`:

```bash
git clone <your repo URL>
cd test
```

No git? On the GitHub page click the green **Code** button → **Download ZIP**,
unzip it, then in the terminal `cd` into that folder.

## Step 3 — See it work (the fun part)

Run the backtest — this simulates thousands of trades and prints a scorecard:

```bash
python3 run_backtest.py
```

You'll see profit/loss, win rate, and a "toxicity sweep." Read the sweep
carefully: it shows the strategy **losing money** once the other traders get
smart. That's the single most important lesson in trading — the edge is thin and
fragile. The numbers are from a *pretend* market, not proof of real profit.

## Step 4 — Open the dashboard

```bash
python3 run_dashboard.py
```

That writes a file at `polymm/dashboard/dashboard.html`. Double-click it to open
it in your web browser. You get charts: the equity curve, the win/loss spread,
and the risk panel. (There's also a live version already published here:
<https://claude.ai/code/artifact/9ed55179-f899-4ff7-a4f3-60d88ab5b3e0>)

## Step 5 — Watch the fill simulator

```bash
python3 run_realistic_demo.py
```

This shows the difference between a *lazy* fill model (which lies and says you'd
get filled easily) and a *realistic* one (latency, queue position, partial
fills). The realistic one fills about **10%** as much. Lesson: assume the market
is harder than it looks.

---

## What each file is (so you can poke around)

| File | What it does |
|---|---|
| `polymm/fairvalue.py` | the math that guesses if a market goes up or down |
| `polymm/quoting.py` | decides the buy/sell prices to post |
| `polymm/risk.py` | the "stop-loss" brain — halts trading if losses pile up |
| `polymm/backtest.py` | the pretend market you're testing against |
| `run_backtest.py` | run the whole simulation |
| `run_dashboard.py` | build the charts |

Try changing a number in `polymm/config.py` (like `base_edge`) and re-run
`python3 run_backtest.py` to see what happens. Breaking things and re-running is
exactly how you learn this.

## Good next steps for learning (free, no account)

- Read about **market making** and **bid/ask spread** — that's the core idea here.
- Learn what **adverse selection** means (the toxicity sweep is showing you it).
- If you want to keep coding: try adding a new stat to the dashboard, or a new
  chart. Ask and I'll walk you through it.

## What you can't do yet (and why)

Connecting a real exchange — Bybit, Polymarket — needs an account you must be 18+
to open, and leveraged trading can lose more than your whole balance. When you're
older and want to try it for real, do it with tiny amounts you can afford to lose
and paper-trade first. Until then, the simulator above is the real classroom.
