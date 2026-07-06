import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { listTemplates, getTemplate } from '../src/templates/index.js';
import { renderSvgPreview } from '../src/marketplace/preview.js';
import { renderPdf } from '../src/pdf/render.js';
import { generate } from '../src/ai/generator.js';

test('every template builds a valid spec and non-trivial SVG', () => {
  for (const t of listTemplates()) {
    const tpl = getTemplate(t.id);
    const spec = tpl.build(tpl.fallbackContent(), tpl.meta.defaultTheme);
    assert.ok(spec.pages.length >= 1, `${t.id} has pages`);
    assert.ok(spec.pages[0].elements.length > 5, `${t.id} has elements`);
    const svg = renderSvgPreview(spec);
    assert.match(svg, /^<svg/, `${t.id} renders svg`);
    assert.ok(svg.includes('</svg>'), `${t.id} svg closes`);
  }
});

test('offline generator produces a complete listing without an API key', async () => {
  const saved = process.env.ANTHROPIC_API_KEY;
  delete process.env.ANTHROPIC_API_KEY;
  try {
    const g = await generate({ templateId: 'weekly-planner', brief: 'cozy autumn budget planner' });
    assert.equal(g.engine, 'offline');
    assert.ok(g.listing.title.length > 0);
    assert.ok(g.listing.tags.length >= 5);
    assert.ok(g.listing.price > 0);
    // "autumn/cozy" brief should steer the theme to ember.
    assert.equal(g.themeName, 'ember');
  } finally {
    if (saved !== undefined) process.env.ANTHROPIC_API_KEY = saved;
  }
});

test('renderPdf writes a real PDF file', async () => {
  const tpl = getTemplate('invoice');
  const spec = tpl.build(tpl.fallbackContent(), 'slate');
  const out = `${process.env.TMPDIR || '/tmp'}/forge-test-${Date.now()}.pdf`;
  await renderPdf(spec, out);
  const buf = fs.readFileSync(out);
  assert.ok(buf.length > 800, 'pdf has content');
  assert.equal(buf.subarray(0, 5).toString(), '%PDF-', 'pdf magic bytes');
  fs.unlinkSync(out);
});
