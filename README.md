# Newcastle Pricing Superagent

A Claude Code **superagent** that produces complete, client-ready quotes for
**pressure-cleaning and protective / pressure-coatings** work, priced on the
**current average Newcastle market rates at the moment of the request** — never
on stale or invented numbers.

Every quote it generates includes, in order:

1. **Title**
2. **Heading block** (quote no., dates, customer, business, region)
3. **Description of the work**
4. **Itemised costs** — a full internal cost breakdown (labour, materials,
   equipment, access, waste, travel, overhead, margin, contingency)
5. **Summarised line items** — the clean, customer-facing quote table
6. **Pricing basis** — the average Newcastle rates used, with sources + dates
7. **Terms & conditions**
8. **Covering email** (with subject line)
9. **Upsell / optional extras**

## How it works

On each request the agent:

1. **Researches live prices** — web-searches current Newcastle rates for every
   cost driver relevant to the job (labour, coatings/products, equipment hire,
   waste disposal, access) and records the source + date for each figure.
2. **Builds the itemised internal breakdown** — every cost, grouped and summed,
   with a stated overhead, margin and contingency.
3. **Summarises the rates used** so the quote is transparent and auditable.
4. **Assembles the client-ready quote** — title, heading, scope, line items,
   assumptions/exclusions, T&Cs, optional extras and a covering email.
5. **Saves** the finished quote to `examples/` as a dated Markdown file.

The internal cost breakdown and the client-facing quote are clearly separated —
the owner sends the client-facing part only.

## Region

Defaults to **Newcastle, NSW, Australia** (AUD, GST 10%, Australian Consumer
Law). To price for **Newcastle upon Tyne, UK** (£, VAT 20%, UK Consumer Rights
Act) or elsewhere, just say so in the request — the agent's *Region
configuration* block flips currency, tax and consumer-law basis in one step.

## Usage

In Claude Code, invoke the agent and describe the job:

```
Use the newcastle-pricing-superagent to quote:
"300 m² warehouse floor, oil-stained, wants an anti-slip epoxy coating."
```

Give it as much or as little detail as you have — it makes clearly-stated
assumptions for anything missing (area, substrate, condition, access, coats) and
lists them so the customer can correct them. It only stops to ask when a missing
fact would swing the price and cannot be reasonably assumed.

## Files

| Path | Purpose |
|------|---------|
| `.claude/agents/newcastle-pricing-superagent.md` | The superagent definition (research + pricing + output rules). |
| `pricing/newcastle-rate-card.md` | Checklist of cost drivers to research and search queries that work. **Not** a price list — prices are always fetched live. |
| `templates/quote-template.md` | The two-part (internal + client-facing) quote skeleton the agent fills. |
| `examples/quote-warehouse-epoxy-floor-20260711.md` | A fully worked example grounded in live Newcastle rates (11/07/2026). |

## Notes

- Figures in the example are illustrative of the method; a live run refreshes
  every rate at request time.
- Every adopted rate is cited with its source and the date it was seen. Where a
  Newcastle-specific figure can't be found, the nearest regional/national average
  is used and flagged `[assumption]` for the owner to sanity-check.
