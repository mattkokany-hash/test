// Server-rendered HTML for the storefront. No client framework — just a
// small, clean, theme-aware shop. All styles are inline in the shell.

export function page(title, body) {
  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>${esc(title)}</title>
<style>
:root{--bg:#f7f7f5;--card:#fff;--ink:#1f2937;--soft:#6b7280;--line:#e5e7eb;--accent:#3f6212;--accent2:#6d28d9}
*{box-sizing:border-box}
body{margin:0;font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;background:var(--bg);color:var(--ink)}
a{color:inherit}
header.top{padding:22px 24px;border-bottom:1px solid var(--line);background:var(--card);display:flex;align-items:center;gap:12px}
header.top .logo{font-weight:800;letter-spacing:-.02em;font-size:20px}
header.top .tag{color:var(--soft);font-size:13px}
.wrap{max-width:1080px;margin:0 auto;padding:28px 24px 60px}
h1{font-size:26px;margin:.2em 0 .1em;letter-spacing:-.02em}
.muted{color:var(--soft)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:20px;margin-top:24px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;overflow:hidden;transition:box-shadow .15s,transform .15s;display:flex;flex-direction:column}
.card:hover{box-shadow:0 10px 30px rgba(0,0,0,.08);transform:translateY(-2px)}
.thumb{aspect-ratio:8.5/11;background:#fafafa;border-bottom:1px solid var(--line);overflow:hidden;display:flex;align-items:center;justify-content:center}
.thumb img{width:100%;height:100%;object-fit:contain}
.card .body{padding:12px 14px 14px;display:flex;flex-direction:column;gap:6px;flex:1}
.card h3{margin:0;font-size:15px;line-height:1.3}
.pill{display:inline-block;font-size:11px;color:var(--soft);background:#f3f4f6;border-radius:999px;padding:2px 9px;width:fit-content}
.price{font-weight:700;font-size:16px}
.row{display:flex;align-items:center;justify-content:space-between;margin-top:auto;padding-top:6px}
.btn{display:inline-block;background:var(--accent);color:#fff;border:0;border-radius:9px;padding:10px 16px;font-size:14px;font-weight:600;cursor:pointer;text-decoration:none}
.btn.alt{background:var(--accent2)}
.btn.ghost{background:transparent;color:var(--accent);border:1px solid var(--line)}
.detail{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:36px;margin-top:24px}
@media(max-width:760px){.detail{grid-template-columns:1fr}}
.preview{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px}
.preview img{width:100%;height:auto;display:block;border:1px solid var(--line);border-radius:6px}
.tags{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}
.tags span{font-size:12px;color:var(--soft);background:#f3f4f6;border-radius:6px;padding:3px 8px}
.banner{background:#fff7ed;border:1px solid #fde3c3;color:#9a3412;padding:10px 14px;border-radius:10px;font-size:13px;margin-top:16px}
.ok{background:#f0fdf4;border:1px solid #bbf7d0;color:#166534}
footer{color:var(--soft);font-size:12px;text-align:center;padding:24px}
</style>
</head>
<body>
<header class="top">
  <a href="/" style="text-decoration:none;display:flex;align-items:center;gap:10px">
    <span class="logo">📄 PDF Forge</span>
  </a>
  <span class="tag">AI-generated printable templates</span>
</header>
<div class="wrap">${body}</div>
<footer>Built with PDF Forge · templates render live from a shared spec</footer>
</body></html>`;
}

export function catalogView(products, money, stripeOn) {
  const banner = stripeOn
    ? ''
    : `<div class="banner">Demo mode — no Stripe key configured, so checkout is simulated and downloads are free. Set <code>STRIPE_SECRET_KEY</code> to take real payments.</div>`;
  if (!products.length) {
    return `<h1>Your shop is empty</h1><p class="muted">Forge your first product:</p>
    <pre style="background:#fff;border:1px solid var(--line);padding:14px;border-radius:10px">npm run seed
# or
node src/cli.js generate weekly-planner --brief "cozy autumn budget planner"</pre>${banner}`;
  }
  const cards = products
    .map(
      (p) => `<a class="card" href="/p/${esc(p.slug)}" style="text-decoration:none">
    <div class="thumb"><img loading="lazy" src="/preview/${esc(p.slug)}.svg" alt="${esc(p.title)}"/></div>
    <div class="body">
      <span class="pill">${esc(p.category)}</span>
      <h3>${esc(p.title)}</h3>
      <div class="row"><span class="price">${money(p.price)}</span><span class="btn ghost">View</span></div>
    </div>
  </a>`
    )
    .join('\n');
  return `<h1>Printable Template Shop</h1>
  <p class="muted">${products.length} product${products.length === 1 ? '' : 's'} · instant-download PDFs</p>
  ${banner}
  <div class="grid">${cards}</div>`;
}

export function productView(p, money, stripeOn) {
  const tags = (p.tags || []).map((t) => `<span>${esc(t)}</span>`).join('');
  const cta = stripeOn ? 'Buy & Download' : 'Get it (demo)';
  return `<p><a href="/" class="muted">← Back to shop</a></p>
  <div class="detail">
    <div class="preview"><img src="/preview/${esc(p.slug)}.svg" alt="${esc(p.title)}"/></div>
    <div>
      <span class="pill">${esc(p.category)}</span>
      <h1>${esc(p.title)}</h1>
      <p class="price" style="font-size:22px">${money(p.price)}</p>
      <p>${esc(p.description || '')}</p>
      <form method="post" action="/buy/${esc(p.slug)}">
        <button class="btn" type="submit">${cta}</button>
      </form>
      <p class="muted" style="margin-top:14px;font-size:13px">Print-ready PDF · US Letter · instant download</p>
      <div class="tags">${tags}</div>
    </div>
  </div>`;
}

export function successView(p, token, demo) {
  if (!token) {
    return `<h1>Payment not confirmed</h1>
    <p class="muted">We couldn't confirm a completed purchase for <strong>${esc(p.title)}</strong>.</p>
    <p><a class="btn ghost" href="/p/${esc(p.slug)}">Try again</a></p>`;
  }
  return `<div class="banner ok">${demo ? 'Demo purchase complete.' : 'Payment received — thank you!'}</div>
  <h1>Your download is ready</h1>
  <p class="muted">${esc(p.title)}</p>
  <p><a class="btn" href="/download/${esc(p.slug)}?token=${esc(token)}">⬇ Download PDF</a></p>
  <p style="margin-top:18px"><a class="muted" href="/">← Back to shop</a></p>`;
}

function esc(s) {
  return String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
}
