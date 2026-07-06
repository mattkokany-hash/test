import { rect, line, text, theme as getTheme } from '../pdf/spec.js';

export const meta = {
  id: 'certificate',
  name: 'Certificate of Achievement',
  category: 'Business Documents',
  basePrice: 5.0,
  defaultTheme: 'plum',
  pageSize: 'letter',
  content: {
    title: 'string — certificate heading, e.g. "Certificate of Achievement"',
    presentedTo: 'string — the "presented to" line label',
    body: 'string — the recognition sentence (may contain a blank for a name)',
    signatureLabels: 'string[2] — two signature-line captions',
  },
};

export function fallbackContent() {
  return {
    title: 'Certificate of Achievement',
    presentedTo: 'This certificate is proudly presented to',
    body: 'in recognition of outstanding dedication, effort, and accomplishment.',
    signatureLabels: ['Signature', 'Date'],
  };
}

export function build(content = {}, themeName) {
  const c = { ...fallbackContent(), ...content };
  const t = getTheme(themeName || meta.defaultTheme);
  // Landscape letter
  const W = 792;
  const H = 612;
  const els = [];

  // Double decorative border
  els.push(rect({ x: 28, y: 28, w: W - 56, h: H - 56, stroke: t.accent, lineWidth: 3 }));
  els.push(rect({ x: 40, y: 40, w: W - 80, h: H - 80, stroke: t.hair, lineWidth: 1 }));

  // Corner flourishes
  for (const [cx, cy] of [[40, 40], [W - 40, 40], [40, H - 40], [W - 40, H - 40]]) {
    els.push(rect({ x: cx - 6, y: cy - 6, w: 12, h: 12, fill: t.soft }));
  }

  els.push(text({ x: 0, y: 96, w: W, text: (c.title || '').toUpperCase(), size: 34, bold: true, color: t.accent, align: 'center', tracking: 3 }));
  els.push(line({ x1: W / 2 - 70, y1: 148, x2: W / 2 + 70, y2: 148, stroke: t.soft, lineWidth: 2 }));

  els.push(text({ x: 0, y: 190, w: W, text: c.presentedTo, size: 13, color: t.soft, align: 'center' }));

  // Recipient name line
  els.push(line({ x1: W / 2 - 200, y1: 268, x2: W / 2 + 200, y2: 268, stroke: t.accent, lineWidth: 1 }));
  els.push(text({ x: 0, y: 274, w: W, text: 'Recipient Name', size: 9, color: t.hair, align: 'center' }));

  els.push(text({ x: W / 2 - 240, y: 300, w: 480, text: c.body, size: 12, color: t.soft, align: 'center', lineGap: 4 }));

  // Signatures
  const sy = 470;
  const labels = c.signatureLabels || [];
  els.push(line({ x1: 150, y1: sy, x2: 330, y2: sy, stroke: t.accent, lineWidth: 1 }));
  els.push(text({ x: 150, y: sy + 8, w: 180, text: labels[0] || 'Signature', size: 10, color: t.soft, align: 'center' }));
  els.push(line({ x1: W - 330, y1: sy, x2: W - 150, y2: sy, stroke: t.accent, lineWidth: 1 }));
  els.push(text({ x: W - 330, y: sy + 8, w: 180, text: labels[1] || 'Date', size: 10, color: t.soft, align: 'center' }));

  // Seal
  els.push({ type: 'circle', x: W / 2, y: sy + 6, r: 34, stroke: t.accent, lineWidth: 2 });
  els.push({ type: 'circle', x: W / 2, y: sy + 6, r: 26, stroke: t.soft, lineWidth: 1 });
  els.push(text({ x: W / 2 - 34, y: sy - 2, w: 68, text: 'SEAL', size: 9, bold: true, color: t.accent, align: 'center', tracking: 1 }));

  return { meta: { pageSize: 'letter-landscape', title: c.title, category: meta.category, tags: [], _size: { w: W, h: H } }, pages: [{ elements: els }] };
}
