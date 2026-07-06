import { rect, line, text, ruled, theme as getTheme } from '../pdf/spec.js';

export const meta = {
  id: 'weekly-planner',
  name: 'Weekly Planner',
  category: 'Planners & Journals',
  basePrice: 6.0,
  defaultTheme: 'sage',
  // Schema handed to the AI content generator so it knows what to fill.
  content: {
    title: 'string — the planner name, e.g. "Weekly Reset Planner"',
    subtitle: 'string — a short tagline under the title',
    days: 'string[7] — day labels, usually Monday..Sunday',
    focusLabel: 'string — heading for the weekly focus box',
    habits: 'string[] — 4 to 6 habit names to track',
    quote: 'string — a short motivational line for the footer',
  },
};

export function fallbackContent() {
  return {
    title: 'Weekly Reset Planner',
    subtitle: 'Plan the week, protect your focus, track what matters.',
    days: ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'],
    focusLabel: 'This Week I Will Focus On',
    habits: ['Move 30 min', 'Read', 'Water', 'Sleep by 11', 'No phone AM'],
    quote: 'Small steps, repeated, become the path.',
  };
}

export function build(content = {}, themeName) {
  const c = { ...fallbackContent(), ...content };
  const t = getTheme(themeName || meta.defaultTheme);
  const M = 40; // margin
  const W = 612;
  const els = [];

  // Header band
  els.push(rect({ x: 0, y: 0, w: W, h: 96, fill: t.panel }));
  els.push(text({ x: M, y: 26, w: W - 2 * M, text: c.title, size: 26, bold: true, color: t.accent }));
  els.push(text({ x: M, y: 60, w: W - 2 * M, text: c.subtitle, size: 11, color: t.soft }));
  els.push(line({ x1: M, y1: 96, x2: W - M, y2: 96, stroke: t.accent, lineWidth: 2 }));

  // Weekly focus box
  const focusY = 118;
  els.push(text({ x: M, y: focusY, w: W - 2 * M, text: (c.focusLabel || '').toUpperCase(), size: 9, bold: true, color: t.soft, tracking: 1.5 }));
  els.push(rect({ x: M, y: focusY + 16, w: W - 2 * M, h: 54, stroke: t.hair, lineWidth: 1, radius: 6 }));
  els.push(...ruled({ x: M + 12, y: focusY + 34, w: W - 2 * M - 24, count: 2, gap: 18, stroke: t.hair, dash: 2 }));

  // Day blocks — two columns
  const gridTop = focusY + 92;
  const colW = (W - 2 * M - 16) / 2;
  const blockH = 74;
  const blockGap = 8;
  c.days.forEach((day, i) => {
    const col = i % 2;
    const row = Math.floor(i / 2);
    const x = M + col * (colW + 16);
    const y = gridTop + row * (blockH + blockGap);
    els.push(rect({ x, y, w: colW, h: blockH, stroke: t.hair, lineWidth: 1, radius: 6 }));
    els.push(rect({ x, y, w: 92, h: blockH, fill: t.panel, radius: 6 }));
    els.push(text({ x: x + 12, y: y + 12, w: 72, text: day, size: 12, bold: true, color: t.accent }));
    els.push(text({ x: x + 12, y: y + 30, w: 72, text: '__ / __', size: 9, color: t.soft }));
    els.push(...ruled({ x: x + 104, y: y + 16, w: colW - 116, count: 3, gap: 18, stroke: t.hair, dash: 2 }));
  });

  // Habit tracker footer
  const habits = c.habits.slice(0, 6);
  const habY = gridTop + 4 * (blockH + blockGap) + 6;
  els.push(text({ x: M, y: habY, w: W - 2 * M, text: 'HABIT TRACKER', size: 9, bold: true, color: t.soft, tracking: 1.5 }));
  const cell = 20;
  habits.forEach((h, i) => {
    const y = habY + 18 + i * (cell + 2);
    els.push(text({ x: M, y: y + 4, w: 150, text: h, size: 10, color: t.accent }));
    for (let d = 0; d < 7; d++) {
      els.push(rect({ x: M + 160 + d * (cell + 6), y, w: cell, h: cell, stroke: t.hair, lineWidth: 1, radius: 3 }));
    }
  });

  els.push(text({ x: M, y: 760, w: W - 2 * M, text: c.quote, size: 10, color: t.soft, align: 'center' }));

  return { meta: { pageSize: 'letter', title: c.title, category: meta.category, tags: [] }, pages: [{ elements: els }] };
}
