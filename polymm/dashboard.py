"""Self-contained HTML dashboard generator for polymm.

Renders a single dependency-free page from a ``BacktestResult`` (and a toxicity
sweep). The same data contract is produced by the live/paper ``RunnerStats``, so
the identical page can front a live session -- point it at a snapshot instead of
a backtest.

Charts are inline SVG drawn in vanilla JS from JSON baked into the page, so it
obeys a strict CSP (no external scripts, fonts, or requests) and opens straight
from disk. Output is body-only (a leading ``<style>`` + markup + ``<script>``),
which both renders standalone in a browser and satisfies the Artifact skeleton.
"""

from __future__ import annotations

import datetime as _dt
import json

from .config import StrategyConfig
from .backtest import BacktestResult, BacktestConfig

__all__ = ["build_dashboard", "build_data"]


def _downsample(curve: list[float], target: int = 360) -> list[list[float]]:
    n = len(curve)
    if n <= target:
        return [[i, round(v, 2)] for i, v in enumerate(curve)]
    step = n / target
    out: list[list[float]] = []
    i = 0.0
    while int(i) < n:
        idx = int(i)
        out.append([idx, round(curve[idx], 2)])
        i += step
    if out[-1][0] != n - 1:
        out.append([n - 1, round(curve[-1], 2)])
    return out


def _histogram(values: list[float], bins: int = 23) -> list[dict]:
    graded = [v for v in values if abs(v) > 1e-9]
    if not graded:
        return []
    lo, hi = min(graded), max(graded)
    if lo == hi:
        lo -= 1.0
        hi += 1.0
    width = (hi - lo) / bins
    counts = [0] * bins
    for v in graded:
        k = int((v - lo) / width)
        k = min(bins - 1, max(0, k))
        counts[k] += 1
    return [
        {"x0": round(lo + i * width, 2), "x1": round(lo + (i + 1) * width, 2),
         "c": counts[i]}
        for i in range(bins)
    ]


def build_data(result: BacktestResult, sweep: list[tuple[float, BacktestResult]],
               cfg: StrategyConfig, bt: BacktestConfig,
               live: dict | None = None) -> dict:
    """Assemble the JSON data contract the page renders from.

    ``live`` is an optional captured market snapshot:
    ``{"ts": str, "source": str, "markets": [{asset,last,vol_pct,fair,bid,ask,delta}]}``
    """
    daily_loss_used = max(0.0, -result.realized_pnl)
    return {
        "live": live,
        "mode": "BACKTEST · synthetic",
        "generated": _dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "params": {
            "steps": bt.steps, "window_len_s": bt.window_len_s,
            "stagger_s": bt.stagger_s, "true_sigma": bt.true_sigma,
            "toxicity": bt.toxicity, "fee_bps": cfg.fee_bps,
        },
        "stats": {
            "realized_pnl": round(result.realized_pnl, 2),
            "win_rate": round(result.win_rate, 4),
            "sharpe": round(result.sharpe, 2),
            "max_drawdown": round(result.max_drawdown, 2),
            "n_fills": result.n_fills,
            "n_windows": result.n_windows,
            "fees_paid": round(result.fees_paid, 2),
            "halted": result.halted,
            "halt_reason": result.halt_reason,
        },
        "equity": _downsample(result.equity_curve),
        "hist": _histogram(result.per_window_pnl),
        "recent": [round(p, 2) for p in result.per_window_pnl[-14:]],
        "sweep": [
            {"toxicity": tox, "pnl": round(r.realized_pnl, 2),
             "win_rate": round(r.win_rate, 4), "sharpe": round(r.sharpe, 2),
             "halted": r.halted}
            for tox, r in sweep
        ],
        "risk": [
            {"label": "Daily loss", "used": round(daily_loss_used, 2),
             "limit": cfg.max_daily_loss},
            {"label": "Max drawdown", "used": round(result.max_drawdown, 2),
             "limit": cfg.max_drawdown},
        ],
        "limits": {
            "max_position_per_market": cfg.max_position_per_market,
            "max_gross_exposure": cfg.max_gross_exposure,
            "max_daily_loss": cfg.max_daily_loss,
            "max_drawdown": cfg.max_drawdown,
        },
    }


def build_dashboard(result: BacktestResult,
                    sweep: list[tuple[float, BacktestResult]],
                    cfg: StrategyConfig, bt: BacktestConfig,
                    live: dict | None = None) -> str:
    data = build_data(result, sweep, cfg, bt, live=live)
    return _TEMPLATE.replace("/*__DATA__*/null", json.dumps(data))


_TEMPLATE = r"""<style>
:root{
  --bg:#0d1117; --panel:#161b22; --panel-2:#1b222c; --border:#242c38;
  --ink:#e6edf3; --muted:#8b98a9; --faint:#5b6675;
  --accent:#e3b341; --accent-soft:rgba(227,179,65,.14);
  --pos:#3fb950; --neg:#f85149; --warn:#d29922;
  --grid:rgba(139,152,169,.16);
  --sans:-apple-system,BlinkMacSystemFont,"Segoe UI",Inter,system-ui,sans-serif;
  --mono:ui-monospace,"JetBrains Mono","SF Mono",Menlo,Consolas,monospace;
}
@media (prefers-color-scheme:light){
  :root{
    --bg:#f5f6f8; --panel:#ffffff; --panel-2:#f0f2f5; --border:#e0e4ea;
    --ink:#161b22; --muted:#5b6675; --faint:#8a94a3;
    --accent:#b7791f; --accent-soft:rgba(183,121,31,.12);
    --pos:#1a7f37; --neg:#cf222e; --warn:#9a6700; --grid:rgba(91,102,117,.16);
  }
}
:root[data-theme="dark"]{
  --bg:#0d1117; --panel:#161b22; --panel-2:#1b222c; --border:#242c38;
  --ink:#e6edf3; --muted:#8b98a9; --faint:#5b6675;
  --accent:#e3b341; --accent-soft:rgba(227,179,65,.14);
  --pos:#3fb950; --neg:#f85149; --warn:#d29922; --grid:rgba(139,152,169,.16);
}
:root[data-theme="light"]{
  --bg:#f5f6f8; --panel:#ffffff; --panel-2:#f0f2f5; --border:#e0e4ea;
  --ink:#161b22; --muted:#5b6675; --faint:#8a94a3;
  --accent:#b7791f; --accent-soft:rgba(183,121,31,.12);
  --pos:#1a7f37; --neg:#cf222e; --warn:#9a6700; --grid:rgba(91,102,117,.16);
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--sans);
  -webkit-font-smoothing:antialiased;line-height:1.45}
.wrap{max-width:1160px;margin:0 auto;padding:22px 20px 60px}
.num{font-family:var(--mono);font-variant-numeric:tabular-nums}

/* --- top bar --- */
.top{display:flex;flex-wrap:wrap;align-items:baseline;gap:10px 16px;
  padding-bottom:16px;border-bottom:1px solid var(--border)}
.brand{font-weight:700;font-size:18px;letter-spacing:-.01em}
.brand b{color:var(--accent)}
.sub{color:var(--muted);font-size:12.5px}
.chips{margin-left:auto;display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.chip{font-family:var(--mono);font-size:11px;letter-spacing:.04em;
  padding:4px 9px;border-radius:999px;border:1px solid var(--border);
  background:var(--panel-2);color:var(--muted);text-transform:uppercase}
.chip.mode{color:var(--accent);border-color:var(--accent);background:var(--accent-soft)}
.chip.ok{color:var(--pos);border-color:color-mix(in oklab,var(--pos) 45%,var(--border))}
.chip.halt{color:var(--neg);border-color:color-mix(in oklab,var(--neg) 50%,var(--border));
  background:color-mix(in oklab,var(--neg) 12%,transparent)}
.tbtn{cursor:pointer;font-family:var(--mono);font-size:11px;padding:4px 9px;
  border-radius:999px;border:1px solid var(--border);background:var(--panel-2);
  color:var(--muted)}
.tbtn:focus-visible{outline:2px solid var(--accent);outline-offset:2px}

/* --- kpi row --- */
.kpis{display:grid;grid-template-columns:repeat(6,1fr);gap:12px;margin:18px 0}
.kpi{background:var(--panel);border:1px solid var(--border);border-radius:10px;
  padding:12px 13px}
.kpi .lab{font-size:10.5px;letter-spacing:.07em;text-transform:uppercase;
  color:var(--muted)}
.kpi .val{font-family:var(--mono);font-size:22px;font-weight:600;margin-top:6px;
  letter-spacing:-.01em}
.kpi .foot{font-family:var(--mono);font-size:11px;color:var(--faint);margin-top:3px}
.pos{color:var(--pos)} .neg{color:var(--neg)} .warnc{color:var(--warn)}

/* --- panels --- */
.grid{display:grid;gap:14px}
.row2{grid-template-columns:1.35fr 1fr}
.row2b{grid-template-columns:1fr 1.25fr}
.panel{background:var(--panel);border:1px solid var(--border);border-radius:12px;
  padding:15px 16px}
.phead{display:flex;align-items:baseline;gap:10px;margin-bottom:4px}
.ptitle{font-size:13.5px;font-weight:650;letter-spacing:-.01em}
.phead .h{color:var(--muted);font-size:11.5px;margin-left:auto}
.pnote{color:var(--muted);font-size:11.5px;margin:0 0 10px}
svg{display:block;width:100%;overflow:visible}
.axis{fill:var(--faint);font-family:var(--mono);font-size:10px}
.gl{stroke:var(--grid);stroke-width:1}

/* --- risk bars --- */
.risk{display:flex;flex-direction:column;gap:14px;margin-top:4px}
.rrow .rlab{display:flex;justify-content:space-between;font-size:12px;
  color:var(--muted);margin-bottom:6px}
.rlab .rv{font-family:var(--mono);color:var(--ink)}
.track{height:9px;border-radius:6px;background:var(--panel-2);
  border:1px solid var(--border);overflow:hidden}
.fill{height:100%;border-radius:6px;background:var(--pos)}
.fill.warn{background:var(--warn)} .fill.crit{background:var(--neg)}
.kill{margin-top:16px;padding:11px 12px;border-radius:9px;font-size:12.5px;
  display:flex;gap:9px;align-items:center;border:1px solid var(--border);
  background:var(--panel-2)}
.dot{width:9px;height:9px;border-radius:50%;flex:none}
.dot.g{background:var(--pos)} .dot.r{background:var(--neg)}

/* --- table --- */
table{width:100%;border-collapse:collapse;font-size:12px}
th,td{text-align:right;padding:6px 8px;border-bottom:1px solid var(--border)}
th{color:var(--muted);font-weight:600;font-size:10.5px;letter-spacing:.05em;
  text-transform:uppercase}
td:first-child,th:first-child{text-align:left}
td.num{font-family:var(--mono)}
.tag{font-family:var(--mono);font-size:10.5px;padding:2px 7px;border-radius:5px}
.tag.w{color:var(--pos);background:color-mix(in oklab,var(--pos) 14%,transparent)}
.tag.l{color:var(--neg);background:color-mix(in oklab,var(--neg) 14%,transparent)}

/* --- tooltip --- */
.tip{position:fixed;pointer-events:none;z-index:20;opacity:0;transition:opacity .08s;
  background:var(--panel);border:1px solid var(--border);border-radius:8px;
  padding:7px 9px;font-family:var(--mono);font-size:11.5px;color:var(--ink);
  box-shadow:0 6px 22px rgba(0,0,0,.28);white-space:nowrap}
.tip b{color:var(--accent)}
.foot{color:var(--faint);font-size:11.5px;margin-top:22px;line-height:1.6;
  border-top:1px solid var(--border);padding-top:14px}
.foot b{color:var(--muted);font-weight:600}
@media (max-width:820px){
  .kpis{grid-template-columns:repeat(3,1fr)}
  .row2,.row2b{grid-template-columns:1fr}
}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
</style>

<div class="wrap">
  <div class="top">
    <div>
      <div class="brand"><b>polymm</b> · market-making monitor</div>
      <div class="sub" id="sub"></div>
    </div>
    <div class="chips">
      <span class="chip mode" id="modechip">BACKTEST</span>
      <span class="chip" id="statechip">—</span>
      <button class="tbtn" id="themebtn" type="button">theme</button>
    </div>
  </div>

  <div class="kpis" id="kpis"></div>

  <div class="grid" id="livewrap" style="margin-bottom:14px;display:none">
    <div class="panel">
      <div class="phead"><span class="ptitle">Live market snapshot</span>
        <span class="h" id="livemeta"></span></div>
      <p class="pnote">Real spot captured live; the engine's model fair value and the two-sided quote it would post right now for a fresh 5-minute Up/Down window (at the money, flat inventory).</p>
      <div style="overflow-x:auto">
        <table><thead><tr><th>Asset</th><th>Spot</th><th>Est. vol</th>
          <th>P(Up)</th><th>Δ / token</th><th>Bid</th><th>Ask</th><th>Edge</th></tr></thead>
        <tbody id="livebody"></tbody></table>
      </div>
    </div>
  </div>

  <div class="grid" style="margin-bottom:14px">
    <div class="panel">
      <div class="phead"><span class="ptitle">Equity curve</span>
        <span class="h">mark-to-model equity across the session</span></div>
      <p class="pnote">Cumulative PnL over backtest cycles. Endpoint marks final realized+unrealized.</p>
      <svg id="equity" viewBox="0 0 900 260" preserveAspectRatio="none"
        role="img" aria-label="Equity curve over the session"></svg>
    </div>
  </div>

  <div class="grid row2" style="margin-bottom:14px">
    <div class="panel">
      <div class="phead"><span class="ptitle">Per-window PnL</span>
        <span class="h">distribution across graded windows</span></div>
      <p class="pnote">Each settled window's realized PnL. Green right of zero (wins), red left (losses).</p>
      <svg id="hist" viewBox="0 0 560 240" role="img"
        aria-label="Histogram of per-window PnL"></svg>
    </div>
    <div class="panel">
      <div class="phead"><span class="ptitle">Adverse-selection sweep</span>
        <span class="h">edge vs informed flow</span></div>
      <p class="pnote">Session PnL as counterparty flow gets more informed. The edge collapses and the kill switch fires.</p>
      <svg id="sweep" viewBox="0 0 560 240" role="img"
        aria-label="Session PnL by toxicity level"></svg>
    </div>
  </div>

  <div class="grid row2b">
    <div class="panel">
      <div class="phead"><span class="ptitle">Risk &amp; kill switches</span></div>
      <p class="pnote">Live utilization against configured limits. Bars turn amber past 70%, red past 90%.</p>
      <div class="risk" id="risk"></div>
      <div class="kill" id="kill"></div>
    </div>
    <div class="panel">
      <div class="phead"><span class="ptitle">Recent windows</span>
        <span class="h">last 14 settled</span></div>
      <div style="overflow-x:auto">
        <table><thead><tr><th>#</th><th>Realized PnL</th><th>Outcome</th></tr></thead>
        <tbody id="recent"></tbody></table>
      </div>
    </div>
  </div>

  <div class="foot" id="foot"></div>
</div>
<div class="tip" id="tip"></div>

<script>
const DATA = /*__DATA__*/null;
const $=(s)=>document.querySelector(s);
const tip=$("#tip");
const money=(v)=>(v<0?"-$":"$")+Math.abs(v).toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2});
const money0=(v)=>(v<0?"-$":"$")+Math.abs(v).toLocaleString(undefined,{maximumFractionDigits:0});
function css(n){return getComputedStyle(document.documentElement).getPropertyValue(n).trim();}
function showTip(html,x,y){tip.innerHTML=html;tip.style.opacity=1;
  const r=tip.getBoundingClientRect();let nx=x+14,ny=y-r.height-10;
  if(nx+r.width>innerWidth-8)nx=x-r.width-14; if(ny<8)ny=y+16;
  tip.style.left=nx+"px";tip.style.top=ny+"px";}
function hideTip(){tip.style.opacity=0;}

/* ---- header + kpis ---- */
function header(){
  const p=DATA.params, s=DATA.stats;
  $("#sub").textContent=`${DATA.mode}  ·  ${p.steps.toLocaleString()} cycles · `+
    `${p.window_len_s}s windows / ${p.stagger_s}s stagger · toxicity ${p.toxicity} · fees ${p.fee_bps}bps · generated ${DATA.generated}`;
  const sc=$("#statechip");
  if(s.halted){sc.className="chip halt";sc.textContent="HALTED · "+s.halt_reason;}
  else{sc.className="chip ok";sc.textContent="ACTIVE · no breach";}
}
function kpis(){
  const s=DATA.stats;
  const items=[
    {lab:"Realized PnL",val:money(s.realized_pnl),cls:s.realized_pnl>=0?"pos":"neg",
      foot:money(s.fees_paid)+" fees"},
    {lab:"Win rate",val:(s.win_rate*100).toFixed(1)+"%",cls:"",
      foot:s.n_windows+" windows"},
    {lab:"Sharpe",val:s.sharpe.toFixed(2),cls:s.sharpe>=0?"pos":"neg",foot:"per-window"},
    {lab:"Max drawdown",val:money0(s.max_drawdown),cls:"warnc",foot:"peak-to-trough"},
    {lab:"Fills",val:s.n_fills.toLocaleString(),cls:"",foot:"maker fills"},
    {lab:"Net / window",val:money(s.realized_pnl/Math.max(1,s.n_windows)),
      cls:s.realized_pnl>=0?"pos":"neg",foot:"avg realized"},
  ];
  $("#kpis").innerHTML=items.map(i=>
    `<div class="kpi"><div class="lab">${i.lab}</div>`+
    `<div class="val ${i.cls}">${i.val}</div><div class="foot">${i.foot}</div></div>`).join("");
}

/* ---- live snapshot ---- */
function live(){
  const L=DATA.live; if(!L||!L.markets||!L.markets.length)return;
  $("#livewrap").style.display="grid";
  $("#livemeta").textContent=`${L.source} · ${L.ts}`;
  $("#livebody").innerHTML=L.markets.map(m=>{
    const spread=(m.ask!=null&&m.bid!=null)?(m.ask-m.bid):null;
    const bid=m.bid!=null?m.bid.toFixed(3):"—";
    const ask=m.ask!=null?m.ask.toFixed(3):"—";
    const edge=spread!=null?`${(spread*100).toFixed(1)}¢`:"pulled";
    return `<tr><td>${m.asset}</td><td class="num">$${m.last.toLocaleString(undefined,{maximumFractionDigits:2})}</td>`+
      `<td class="num">${m.vol_pct.toFixed(2)}%/d</td>`+
      `<td class="num">${m.fair.toFixed(3)}</td>`+
      `<td class="num">${m.delta.toFixed(1)}</td>`+
      `<td class="num pos">${bid}</td><td class="num neg">${ask}</td>`+
      `<td class="num">${edge}</td></tr>`;
  }).join("");
}

/* ---- equity area+line ---- */
function equity(){
  const el=$("#equity"), W=900,H=260,P={l:52,r:14,t:14,b:24};
  const pts=DATA.equity; const xs=pts.map(p=>p[0]), ys=pts.map(p=>p[1]);
  const xmin=xs[0],xmax=xs[xs.length-1];
  let ymin=Math.min(0,...ys),ymax=Math.max(0,...ys); if(ymin===ymax){ymax+=1;}
  const pad=(ymax-ymin)*0.08; ymin-=pad; ymax+=pad;
  const X=x=>P.l+(x-xmin)/(xmax-xmin)*(W-P.l-P.r);
  const Y=y=>P.t+(ymax-y)/(ymax-ymin)*(H-P.t-P.b);
  let g="";
  const ticks=4;
  for(let i=0;i<=ticks;i++){const v=ymin+(ymax-ymin)*i/ticks;const y=Y(v);
    g+=`<line class="gl" x1="${P.l}" y1="${y.toFixed(1)}" x2="${W-P.r}" y2="${y.toFixed(1)}"/>`+
       `<text class="axis" x="${P.l-8}" y="${(y+3).toFixed(1)}" text-anchor="end">${money0(v)}</text>`;}
  const y0=Y(0);
  g+=`<line x1="${P.l}" y1="${y0.toFixed(1)}" x2="${W-P.r}" y2="${y0.toFixed(1)}" stroke="var(--faint)" stroke-width="1" stroke-dasharray="3 3"/>`;
  let line=pts.map((p,i)=>(i?"L":"M")+X(p[0]).toFixed(1)+" "+Y(p[1]).toFixed(1)).join(" ");
  const area=`M${X(xs[0]).toFixed(1)} ${y0.toFixed(1)} `+
    pts.map(p=>"L"+X(p[0]).toFixed(1)+" "+Y(p[1]).toFixed(1)).join(" ")+
    ` L${X(xs[xs.length-1]).toFixed(1)} ${y0.toFixed(1)} Z`;
  const last=pts[pts.length-1];
  g+=`<path d="${area}" fill="var(--accent-soft)"/>`+
     `<path d="${line}" fill="none" stroke="var(--accent)" stroke-width="2" stroke-linejoin="round"/>`+
     `<circle cx="${X(last[0]).toFixed(1)}" cy="${Y(last[1]).toFixed(1)}" r="4" fill="var(--accent)"/>`;
  g+=`<line id="cx" x1="0" y1="${P.t}" x2="0" y2="${H-P.b}" stroke="var(--muted)" stroke-width="1" opacity="0"/>`+
     `<circle id="cd" r="4" fill="var(--accent)" stroke="var(--panel)" stroke-width="2" opacity="0"/>`;
  el.innerHTML=g;
  const cx=el.querySelector("#cx"),cd=el.querySelector("#cd");
  el.addEventListener("pointermove",e=>{
    const r=el.getBoundingClientRect();const sx=(e.clientX-r.left)/r.width*W;
    if(sx<P.l||sx>W-P.r){hideTip();cx.style.opacity=0;cd.style.opacity=0;return;}
    const xv=xmin+(sx-P.l)/(W-P.l-P.r)*(xmax-xmin);
    let best=pts[0],bd=1e18;for(const p of pts){const d=Math.abs(p[0]-xv);if(d<bd){bd=d;best=p;}}
    cx.setAttribute("x1",X(best[0]));cx.setAttribute("x2",X(best[0]));cx.style.opacity=.6;
    cd.setAttribute("cx",X(best[0]));cd.setAttribute("cy",Y(best[1]));cd.style.opacity=1;
    showTip(`cycle <b>${best[0].toLocaleString()}</b><br>equity ${money(best[1])}`,e.clientX,e.clientY);
  });
  el.addEventListener("pointerleave",()=>{hideTip();cx.style.opacity=0;cd.style.opacity=0;});
}

/* ---- histogram ---- */
function hist(){
  const el=$("#hist"),W=560,H=240,P={l:40,r:12,t:12,b:28};
  const bins=DATA.hist; if(!bins.length){el.innerHTML="";return;}
  const cmax=Math.max(...bins.map(b=>b.c));
  const bw=(W-P.l-P.r)/bins.length;
  const Y=c=>P.t+(1-c/cmax)*(H-P.t-P.b);
  let g="";
  for(let i=0;i<=3;i++){const c=cmax*i/3;const y=Y(c);
    g+=`<line class="gl" x1="${P.l}" y1="${y.toFixed(1)}" x2="${W-P.r}" y2="${y.toFixed(1)}"/>`+
       `<text class="axis" x="${P.l-7}" y="${(y+3).toFixed(1)}" text-anchor="end">${Math.round(c)}</text>`;}
  bins.forEach((b,i)=>{
    const x=P.l+i*bw, y=Y(b.c), h=(H-P.b)-y;
    const mid=(b.x0+b.x1)/2, col=mid>=0?"var(--pos)":"var(--neg)";
    g+=`<rect x="${(x+1).toFixed(1)}" y="${y.toFixed(1)}" width="${(bw-2).toFixed(1)}" height="${Math.max(0,h).toFixed(1)}" rx="2" fill="${col}" opacity=".85" data-i="${i}"/>`;
  });
  const yb=H-P.b;
  g+=`<line x1="${P.l}" y1="${yb}" x2="${W-P.r}" y2="${yb}" stroke="var(--border)" stroke-width="1"/>`+
     `<text class="axis" x="${P.l}" y="${H-8}" text-anchor="start">loss</text>`+
     `<text class="axis" x="${W-P.r}" y="${H-8}" text-anchor="end">profit</text>`;
  el.innerHTML=g;
  el.querySelectorAll("rect[data-i]").forEach(rc=>{
    const b=bins[+rc.dataset.i];
    rc.addEventListener("pointermove",e=>{rc.setAttribute("opacity","1");
      showTip(`${money(b.x0)} → ${money(b.x1)}<br><b>${b.c}</b> windows`,e.clientX,e.clientY);});
    rc.addEventListener("pointerleave",()=>{rc.setAttribute("opacity",".85");hideTip();});
  });
}

/* ---- toxicity sweep ---- */
function sweep(){
  const el=$("#sweep"),W=560,H=240,P={l:48,r:12,t:14,b:34};
  const rows=DATA.sweep; const vals=rows.map(r=>r.pnl);
  let ymin=Math.min(0,...vals),ymax=Math.max(0,...vals);
  const pad=(ymax-ymin)*0.1||1; ymin-=pad;ymax+=pad;
  const bw=(W-P.l-P.r)/rows.length;
  const Y=v=>P.t+(ymax-v)/(ymax-ymin)*(H-P.t-P.b);
  let g="";
  for(let i=0;i<=4;i++){const v=ymin+(ymax-ymin)*i/4;const y=Y(v);
    g+=`<line class="gl" x1="${P.l}" y1="${y.toFixed(1)}" x2="${W-P.r}" y2="${y.toFixed(1)}"/>`+
       `<text class="axis" x="${P.l-7}" y="${(y+3).toFixed(1)}" text-anchor="end">${money0(v)}</text>`;}
  const y0=Y(0);
  rows.forEach((r,i)=>{
    const cx=P.l+i*bw+bw/2, col=r.pnl>=0?"var(--pos)":"var(--neg)";
    const yv=Y(r.pnl), top=Math.min(yv,y0), h=Math.abs(yv-y0);
    g+=`<rect x="${(cx-bw*0.32).toFixed(1)}" y="${top.toFixed(1)}" width="${(bw*0.64).toFixed(1)}" height="${Math.max(1,h).toFixed(1)}" rx="3" fill="${col}" opacity=".88" data-i="${i}"/>`;
    if(r.halted) g+=`<text class="axis" x="${cx.toFixed(1)}" y="${(top-6).toFixed(1)}" text-anchor="middle" fill="var(--neg)">halt</text>`;
    g+=`<text class="axis" x="${cx.toFixed(1)}" y="${H-10}" text-anchor="middle">tox ${r.toxicity}</text>`;
  });
  g+=`<line x1="${P.l}" y1="${y0.toFixed(1)}" x2="${W-P.r}" y2="${y0.toFixed(1)}" stroke="var(--faint)" stroke-width="1"/>`;
  el.innerHTML=g;
  el.querySelectorAll("rect[data-i]").forEach(rc=>{
    const r=rows[+rc.dataset.i];
    rc.addEventListener("pointermove",e=>{rc.setAttribute("opacity","1");
      showTip(`toxicity <b>${r.toxicity}</b><br>PnL ${money(r.pnl)}<br>win ${(r.win_rate*100).toFixed(1)}% · sharpe ${r.sharpe.toFixed(2)}${r.halted?"<br><span style='color:var(--neg)'>kill switch fired</span>":""}`,e.clientX,e.clientY);});
    rc.addEventListener("pointerleave",()=>{rc.setAttribute("opacity",".88");hideTip();});
  });
}

/* ---- risk + table ---- */
function risk(){
  $("#risk").innerHTML=DATA.risk.map(r=>{
    const pct=Math.max(0,Math.min(1,r.used/r.limit));
    const cls=pct>=0.9?"crit":pct>=0.7?"warn":"";
    return `<div class="rrow"><div class="rlab"><span>${r.label}</span>`+
      `<span class="rv">${money0(r.used)} / ${money0(r.limit)} · ${(pct*100).toFixed(0)}%</span></div>`+
      `<div class="track"><div class="fill ${cls}" style="width:${(pct*100).toFixed(1)}%"></div></div></div>`;
  }).join("");
  const s=DATA.stats,k=$("#kill");
  if(s.halted){k.innerHTML=`<span class="dot r"></span><span>Kill switch <b>ENGAGED</b> — ${s.halt_reason}. Risk-increasing orders blocked; only reducing trades allowed.</span>`;}
  else{k.innerHTML=`<span class="dot g"></span><span>All kill switches nominal. Position, gross-exposure, daily-loss and drawdown limits within bounds.</span>`;}
}
function recent(){
  $("#recent").innerHTML=DATA.recent.map((p,i)=>{
    const w=p>1e-9,l=p<-1e-9;
    const tag=w?`<span class="tag w">WIN</span>`:l?`<span class="tag l">LOSS</span>`:`<span class="tag">FLAT</span>`;
    const cls=w?"pos":l?"neg":"";
    return `<tr><td>${DATA.stats.n_windows-DATA.recent.length+i+1}</td>`+
      `<td class="num ${cls}">${money(p)}</td><td>${tag}</td></tr>`;
  }).reverse().join("");
}
function foot(){
  const L=DATA.limits;
  $("#foot").innerHTML=
    `<b>Reading this:</b> data is a synthetic backtest, not live trading — the numbers prove the engine is internally sound, not that it prints money. `+
    `The adverse-selection sweep is the honest panel: a thin binary edge survives clean mispricing but collapses once counterparty flow is informed. `+
    `<br><b>Limits in force:</b> position ≤ ${money0(L.max_position_per_market)}/mkt · gross ≤ ${money0(L.max_gross_exposure)} · daily loss ≤ ${money0(L.max_daily_loss)} · drawdown ≤ ${money0(L.max_drawdown)}. `+
    `The same page renders a live/paper session — point it at a RunnerStats snapshot instead of a backtest.`;
}

/* ---- theme toggle ---- */
function initTheme(){
  const btn=$("#themebtn");
  const cur=()=>document.documentElement.getAttribute("data-theme")||
    (matchMedia("(prefers-color-scheme:dark)").matches?"dark":"light");
  const draw=()=>{header();kpis();live();equity();hist();sweep();risk();recent();foot();};
  btn.addEventListener("click",()=>{
    const next=cur()==="dark"?"light":"dark";
    document.documentElement.setAttribute("data-theme",next);
    btn.textContent=next==="dark"?"☀ light":"☾ dark";
    draw();
  });
  btn.textContent=cur()==="dark"?"☀ light":"☾ dark";
}

header();kpis();live();equity();hist();sweep();risk();recent();foot();initTheme();
addEventListener("resize",()=>{equity();hist();sweep();});
</script>
"""
