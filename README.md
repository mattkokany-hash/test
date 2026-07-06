# 📄 PDF Forge

An AI-driven engine that **designs sellable PDF templates and lists them for sale** —
either through a self-hosted Stripe storefront or as export-ready packages you upload
to Etsy, Gumroad, or Creative Market.

Give it a niche ("cozy autumn budget planner"); it writes the content, designs the
layout, renders a print-ready PDF, generates a matching preview, writes the
marketplace listing copy (title, description, tags, price), and puts it up for sale.

```
brief ──▶ AI content + listing ──▶ PDF + SVG preview ──▶ shop / export .zip
```

## Why it's built this way

Every template is a **declarative spec** rendered by two backends:

- `src/pdf/render.js` → the real, sellable **PDF** (pdfkit)
- `src/marketplace/preview.js` → the storefront **SVG** thumbnail

One spec, two renderers — so the preview a buyer sees always matches the file they
download. Adding a new product type is just a module exporting `{ meta, build,
fallbackContent }` registered in `src/templates/index.js`.

## Runs with zero setup

No API keys required. With none configured it uses a deterministic offline generator
and a **demo checkout** (simulated purchase, free download) so you can drive the whole
flow. Add keys to level up:

| Env var | Effect |
|---|---|
| `ANTHROPIC_API_KEY` | Use Claude to design content + write listing copy |
| `FORGE_MODEL` | Model id (default `claude-sonnet-5`) |
| `STRIPE_SECRET_KEY` | Take real payments via Stripe Checkout |
| `PORT` | Storefront port (default `4000`) |

## Quick start

```bash
npm install
cp .env.example .env          # optional — fill in any keys you have

npm run seed                  # forge a starter catalog (one of each kind)
npm run serve                 # open the shop at http://localhost:4000
```

## Template kinds

| id | product | category |
|---|---|---|
| `weekly-planner` | Weekly planner + habit tracker | Planners & Journals |
| `invoice` | Freelance / business invoice | Business Documents |
| `resume` | Two-column resume | Business Documents |
| `certificate` | Landscape certificate of achievement | Business Documents |

## CLI

```bash
node src/cli.js templates                                  # list template kinds
node src/cli.js generate weekly-planner --brief "cozy autumn budget planner"
node src/cli.js generate invoice --theme slate --price 12
node src/cli.js list                                       # forged products
node src/cli.js export <slug>                              # .zip for Etsy/Gumroad
node src/cli.js serve --port 4000                          # storefront
```

Each `generate` writes to `output/<slug>/`:

- `template.pdf` — the deliverable buyers download
- `preview.svg` — listing thumbnail (faithful to the PDF)
- `product.json` — catalog metadata

`export <slug>` bundles `template.pdf`, `preview.svg`, and a copy/paste
`listing.txt` (+ `listing.json`) into `output/_packages/<slug>.zip`.

## Storefront

- Grid catalog with live SVG previews
- Product pages with description, tags, price
- **Stripe Checkout** when `STRIPE_SECRET_KEY` is set; **demo mode** otherwise
- Downloads are **token-gated** — a link is only minted after a completed purchase

## Tests

```bash
npm test
```

Covers spec/SVG generation for every template, the offline listing generator
(including theme steering), and real PDF output.

## Project layout

```
src/
  ai/generator.js          Claude API + deterministic offline fallback
  templates/               weekly-planner · invoice · resume · certificate
  pdf/spec.js  render.js   declarative primitives + PDF backend
  marketplace/
    preview.js             SVG backend (storefront thumbnails)
    forge.js               brief → product pipeline
    catalog.js  export.js  JSON catalog + marketplace .zip packaging
  store/                   Express storefront (Stripe / demo checkout)
  cli.js                   command-line entry point
```

## Roadmap

- Multi-page planners (monthly + weekly spreads)
- Bundle products (e.g. "full planner kit")
- Direct Etsy/Gumroad API publishing
- PNG mockups (framed product shots) alongside the SVG preview
