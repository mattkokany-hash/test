import { getTemplate } from '../templates/index.js';
import { THEMES } from '../pdf/spec.js';

const API_URL = 'https://api.anthropic.com/v1/messages';
const MODEL = process.env.FORGE_MODEL || 'claude-sonnet-5';

// Generate everything needed to produce and sell one template:
//   { content, themeName, listing: { title, description, tags, price } }
//
// If ANTHROPIC_API_KEY is set, ask Claude to design content + listing copy
// tailored to `brief` (a niche prompt like "cozy autumn budget planner").
// Otherwise fall back to a deterministic generator so the tool always runs.
export async function generate({ templateId, brief = '', themeName } = {}) {
  const tpl = getTemplate(templateId);
  const chosenTheme = themeName || pickTheme(brief, tpl.meta.defaultTheme);

  if (process.env.ANTHROPIC_API_KEY) {
    try {
      const ai = await callClaude(tpl, brief, chosenTheme);
      return {
        content: { ...tpl.fallbackContent(), ...ai.content },
        themeName: ai.theme && THEMES[ai.theme] ? ai.theme : chosenTheme,
        listing: normalizeListing(ai.listing, tpl, brief),
        engine: 'claude',
      };
    } catch (err) {
      // Never fail a generation just because the API hiccuped.
      console.warn(`[ai] Claude generation failed (${err.message}); using offline fallback.`);
    }
  }

  return {
    content: tpl.fallbackContent(),
    themeName: chosenTheme,
    listing: offlineListing(tpl, brief),
    engine: 'offline',
  };
}

async function callClaude(tpl, brief, chosenTheme) {
  const sys =
    'You are a product designer for a digital-printables shop. You fill in the ' +
    'text content of PDF templates and write marketplace listing copy that sells. ' +
    'Respond with ONLY a single JSON object, no prose, no markdown fences.';

  const prompt = [
    `Template type: ${tpl.meta.name} (${tpl.meta.category}).`,
    `Product brief / niche: ${brief || 'a clean, broadly appealing version'}.`,
    `Available color themes: ${Object.keys(THEMES).join(', ')}. Prefer: ${chosenTheme}.`,
    '',
    'Fill this content schema (keep array lengths as described, keep text short and print-ready):',
    JSON.stringify(tpl.meta.content, null, 2),
    '',
    'Return JSON shaped exactly like:',
    '{',
    '  "content": { ...matching the schema above... },',
    '  "theme": "<one of the theme names>",',
    '  "listing": {',
    '    "title": "SEO-friendly product title, <=70 chars",',
    '    "description": "2-4 sentence sales description",',
    '    "tags": ["13 lowercase marketplace search tags"],',
    '    "price": <number, USD, one decimal>',
    '  }',
    '}',
  ].join('\n');

  const res = await fetch(API_URL, {
    method: 'POST',
    headers: {
      'content-type': 'application/json',
      'x-api-key': process.env.ANTHROPIC_API_KEY,
      'anthropic-version': '2023-06-01',
    },
    body: JSON.stringify({
      model: MODEL,
      max_tokens: 1500,
      system: sys,
      messages: [{ role: 'user', content: prompt }],
    }),
  });

  if (!res.ok) throw new Error(`HTTP ${res.status}: ${(await res.text()).slice(0, 200)}`);
  const data = await res.json();
  const raw = (data.content || []).map((b) => b.text || '').join('').trim();
  return JSON.parse(stripFences(raw));
}

function stripFences(s) {
  const fenced = s.match(/```(?:json)?\s*([\s\S]*?)```/);
  if (fenced) return fenced[1].trim();
  const brace = s.indexOf('{');
  const end = s.lastIndexOf('}');
  return brace >= 0 && end > brace ? s.slice(brace, end + 1) : s;
}

// ---- Offline fallback -------------------------------------------------

const THEME_HINTS = {
  sage: ['calm', 'nature', 'green', 'garden', 'wellness', 'minimal', 'organic'],
  plum: ['creative', 'elegant', 'luxury', 'purple', 'bold', 'modern'],
  ember: ['warm', 'autumn', 'cozy', 'fall', 'orange', 'energy'],
  slate: ['professional', 'business', 'corporate', 'finance', 'clean'],
  ink: ['classic', 'monochrome', 'timeless', 'simple'],
};

function pickTheme(brief, fallback) {
  const b = brief.toLowerCase();
  for (const [name, words] of Object.entries(THEME_HINTS)) {
    if (words.some((w) => b.includes(w))) return name;
  }
  return fallback;
}

function keywords(brief) {
  return brief
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, ' ')
    .split(/\s+/)
    .filter((w) => w.length > 2);
}

function offlineListing(tpl, brief) {
  const nice = titleCase(brief);
  const base = nice ? `${nice} ${tpl.meta.name}` : tpl.meta.name;
  const kws = keywords(brief);
  const tags = dedupe([
    ...kws,
    tpl.meta.category.toLowerCase(),
    'printable',
    'pdf template',
    'instant download',
    'digital planner',
    tpl.meta.id.replace('-', ' '),
  ]).slice(0, 13);

  return {
    title: base.slice(0, 70),
    description:
      `A print-ready ${tpl.meta.name.toLowerCase()}${nice ? ` with a ${nice.toLowerCase()} feel` : ''}. ` +
      `Instant-download PDF, formatted for US Letter and ready to print at home or send to a print shop. ` +
      `Clean, editable-friendly layout you can use again and again.`,
    tags,
    price: tpl.meta.basePrice,
  };
}

function normalizeListing(listing = {}, tpl, brief) {
  const fallback = offlineListing(tpl, brief);
  const price = Number(listing.price);
  return {
    title: (listing.title || fallback.title).toString().slice(0, 70),
    description: listing.description || fallback.description,
    tags: Array.isArray(listing.tags) && listing.tags.length ? dedupe(listing.tags.map(String)).slice(0, 13) : fallback.tags,
    price: Number.isFinite(price) && price > 0 ? Math.round(price * 100) / 100 : fallback.price,
  };
}

function titleCase(s) {
  return (s || '').replace(/\w\S*/g, (w) => w[0].toUpperCase() + w.slice(1)).trim();
}
function dedupe(arr) {
  return [...new Set(arr.map((s) => s.trim()).filter(Boolean))];
}
