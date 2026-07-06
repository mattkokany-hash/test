// Declarative page-spec primitives shared by every template.
//
// A template produces a `Spec`:
//   { meta: {...}, pages: [ { elements: [ ...Element ] } ] }
//
// The same Spec is consumed by two backends:
//   - render.js   -> a real, sellable PDF (via pdfkit)
//   - ../marketplace/preview.js -> an SVG thumbnail for the storefront
//
// Keeping one spec and two renderers means a preview always matches the
// product a customer downloads. Coordinates are in PostScript points
// (72 per inch); Letter is 612 x 792.

export const PAGE = {
  letter: { w: 612, h: 792 },
  a4: { w: 595.28, h: 841.89 },
};

// A small, deliberately restrained palette so generated products look
// like a coherent brand rather than clip-art.
export const THEMES = {
  ink: { accent: '#1f2937', soft: '#6b7280', hair: '#d1d5db', panel: '#f3f4f6', paper: '#ffffff' },
  sage: { accent: '#3f6212', soft: '#65803a', hair: '#d9e2c4', panel: '#f2f6ea', paper: '#ffffff' },
  plum: { accent: '#6d28d9', soft: '#8b5cf6', hair: '#ddd6fe', panel: '#f5f3ff', paper: '#ffffff' },
  ember: { accent: '#b45309', soft: '#d97706', hair: '#fde3c3', panel: '#fff7ed', paper: '#ffffff' },
  slate: { accent: '#0f172a', soft: '#475569', hair: '#cbd5e1', panel: '#f1f5f9', paper: '#ffffff' },
};

export function theme(name) {
  return THEMES[name] || THEMES.ink;
}

// Element factories — keep templates readable.
export const rect = (o) => ({ type: 'rect', ...o });
export const line = (o) => ({ type: 'line', ...o });
export const text = (o) => ({ type: 'text', ...o });
export const circle = (o) => ({ type: 'circle', ...o });

// Evenly spaced horizontal ruled lines, e.g. for note/planner areas.
export function ruled({ x, y, w, count, gap, stroke, lineWidth = 0.75, dash }) {
  const els = [];
  for (let i = 0; i < count; i++) {
    els.push(line({ x1: x, y1: y + i * gap, x2: x + w, y2: y + i * gap, stroke, lineWidth, dash }));
  }
  return els;
}

// A grid of dots, the classic bullet-journal surface.
export function dotGrid({ x, y, w, h, gap = 18, r = 0.8, fill }) {
  const els = [];
  for (let gy = y; gy <= y + h + 0.01; gy += gap) {
    for (let gx = x; gx <= x + w + 0.01; gx += gap) {
      els.push(circle({ x: gx, y: gy, r, fill }));
    }
  }
  return els;
}
