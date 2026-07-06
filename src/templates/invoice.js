import { rect, line, text, theme as getTheme } from '../pdf/spec.js';

export const meta = {
  id: 'invoice',
  name: 'Invoice Template',
  category: 'Business Documents',
  basePrice: 8.0,
  defaultTheme: 'slate',
  content: {
    businessName: 'string — the seller/business name',
    tagline: 'string — short business tagline',
    columns: 'string[] — line-item column headers (Description, Qty, Rate, Amount)',
    notesLabel: 'string — heading for the notes/terms block',
    notes: 'string — payment terms / thank-you note',
  },
};

export function fallbackContent() {
  return {
    businessName: 'Your Business Name',
    tagline: 'Professional services, done right.',
    columns: ['Description', 'Qty', 'Rate', 'Amount'],
    notesLabel: 'Notes & Terms',
    notes: 'Payment due within 14 days. Thank you for your business.',
  };
}

export function build(content = {}, themeName) {
  const c = { ...fallbackContent(), ...content };
  const t = getTheme(themeName || meta.defaultTheme);
  const M = 48;
  const W = 612;
  const els = [];

  // Masthead
  els.push(text({ x: M, y: 48, w: 300, text: c.businessName, size: 22, bold: true, color: t.accent }));
  els.push(text({ x: M, y: 76, w: 300, text: c.tagline, size: 10, color: t.soft }));
  els.push(text({ x: W - M - 200, y: 44, w: 200, text: 'INVOICE', size: 30, bold: true, color: t.hair, align: 'right' }));

  // Meta fields (billed-to + invoice details)
  const metaY = 128;
  els.push(text({ x: M, y: metaY, w: 120, text: 'BILL TO', size: 8, bold: true, color: t.soft, tracking: 1.2 }));
  els.push(...labeledLines(M, metaY + 14, 220, ['Client name', 'Company', 'Email / phone'], t));

  const rx = W - M - 220;
  els.push(...pairRows(rx, metaY, 220, [
    ['Invoice #', '________'],
    ['Date', '________'],
    ['Due date', '________'],
  ], t));

  // Line-item table
  const tableY = 236;
  const cols = c.columns.slice(0, 4);
  const colX = [M, W - M - 210, W - M - 140, W - M - 70];
  els.push(rect({ x: M, y: tableY, w: W - 2 * M, h: 26, fill: t.accent }));
  cols.forEach((h, i) => {
    els.push(text({ x: colX[i] + (i === 0 ? 10 : 0), y: tableY + 8, w: i === 0 ? 220 : 62, text: h, size: 9, bold: true, color: '#ffffff', align: i === 0 ? 'left' : 'right' }));
  });
  const rows = 10;
  for (let r = 0; r < rows; r++) {
    const y = tableY + 26 + r * 28;
    if (r % 2 === 1) els.push(rect({ x: M, y, w: W - 2 * M, h: 28, fill: t.panel }));
    els.push(line({ x1: M, y1: y + 28, x2: W - M, y2: y + 28, stroke: t.hair, lineWidth: 0.5 }));
  }

  // Totals
  const totY = tableY + 26 + rows * 28 + 14;
  els.push(...pairRows(W - M - 220, totY, 220, [
    ['Subtotal', '________'],
    ['Tax', '________'],
  ], t));
  els.push(rect({ x: W - M - 220, y: totY + 44, w: 220, h: 30, fill: t.panel, radius: 4 }));
  els.push(text({ x: W - M - 210, y: totY + 53, w: 100, text: 'TOTAL', size: 11, bold: true, color: t.accent }));
  els.push(text({ x: W - M - 120, y: totY + 53, w: 100, text: '$ ________', size: 11, bold: true, color: t.accent, align: 'right' }));

  // Notes
  els.push(text({ x: M, y: totY + 8, w: 260, text: (c.notesLabel || '').toUpperCase(), size: 8, bold: true, color: t.soft, tracking: 1.2 }));
  els.push(text({ x: M, y: totY + 24, w: 260, text: c.notes, size: 9, color: t.soft, lineGap: 4 }));

  els.push(line({ x1: M, y1: 748, x2: W - M, y2: 748, stroke: t.hair, lineWidth: 1 }));
  els.push(text({ x: M, y: 758, w: W - 2 * M, text: c.businessName, size: 8, color: t.soft, align: 'center' }));

  return { meta: { pageSize: 'letter', title: `${c.businessName} — Invoice`, category: meta.category, tags: [] }, pages: [{ elements: els }] };
}

function labeledLines(x, y, w, labels, t) {
  const els = [];
  labels.forEach((_, i) => {
    els.push(line({ x1: x, y1: y + 18 + i * 22, x2: x + w, y2: y + 18 + i * 22, stroke: t.hair, lineWidth: 0.75 }));
  });
  return els;
}

function pairRows(x, y, w, pairs, t) {
  const els = [];
  pairs.forEach(([k, v], i) => {
    const ry = y + i * 22;
    els.push(text({ x, y: ry, w: w - 90, text: k, size: 9, color: t.soft }));
    els.push(text({ x: x + w - 90, y: ry, w: 90, text: v, size: 9, color: t.accent, align: 'right' }));
  });
  return els;
}
