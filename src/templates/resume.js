import { rect, line, text, theme as getTheme } from '../pdf/spec.js';

export const meta = {
  id: 'resume',
  name: 'Resume Template',
  category: 'Business Documents',
  basePrice: 9.0,
  defaultTheme: 'ink',
  content: {
    name: 'string — the candidate name placeholder, e.g. "Your Name"',
    role: 'string — target role/headline',
    sidebarSections: 'string[] — left-column section titles (e.g. Contact, Skills, Education)',
    mainSections: 'string[] — right-column section titles (e.g. Summary, Experience)',
    tagline: 'string — one-line professional summary placeholder',
  },
};

export function fallbackContent() {
  return {
    name: 'Your Name',
    role: 'Your Professional Title',
    sidebarSections: ['Contact', 'Skills', 'Education', 'Certifications'],
    mainSections: ['Summary', 'Experience', 'Projects'],
    tagline: 'A concise, results-focused summary of who you are and the value you bring.',
  };
}

export function build(content = {}, themeName) {
  const c = { ...fallbackContent(), ...content };
  const t = getTheme(themeName || meta.defaultTheme);
  const W = 612;
  const H = 792;
  const els = [];
  const sidebarW = 196;

  // Sidebar
  els.push(rect({ x: 0, y: 0, w: sidebarW, h: H, fill: t.panel }));

  // Header name block
  els.push(text({ x: sidebarW + 32, y: 56, w: W - sidebarW - 64, text: c.name, size: 28, bold: true, color: t.accent }));
  els.push(text({ x: sidebarW + 32, y: 92, w: W - sidebarW - 64, text: (c.role || '').toUpperCase(), size: 11, color: t.soft, tracking: 2 }));
  els.push(line({ x1: sidebarW + 32, y1: 116, x2: W - 40, y2: 116, stroke: t.accent, lineWidth: 1.5 }));

  // Sidebar sections
  let sy = 60;
  c.sidebarSections.forEach((title) => {
    els.push(text({ x: 24, y: sy, w: sidebarW - 40, text: title.toUpperCase(), size: 10, bold: true, color: t.accent, tracking: 1.2 }));
    els.push(line({ x1: 24, y1: sy + 16, x2: sidebarW - 24, y2: sy + 16, stroke: t.hair, lineWidth: 1 }));
    for (let i = 0; i < 4; i++) {
      els.push(line({ x1: 24, y1: sy + 34 + i * 16, x2: sidebarW - 24, y2: sy + 34 + i * 16, stroke: t.hair, lineWidth: 0.6, dash: 2 }));
    }
    sy += 128;
  });

  // Main sections
  let my = 140;
  c.mainSections.forEach((title, idx) => {
    els.push(text({ x: sidebarW + 32, y: my, w: 300, text: title.toUpperCase(), size: 12, bold: true, color: t.accent, tracking: 1.2 }));
    els.push(line({ x1: sidebarW + 32, y1: my + 18, x2: W - 40, y2: my + 18, stroke: t.hair, lineWidth: 1 }));
    if (idx === 0) {
      els.push(text({ x: sidebarW + 32, y: my + 28, w: W - sidebarW - 72, text: c.tagline, size: 10, color: t.soft, lineGap: 4 }));
      my += 92;
    } else {
      for (let i = 0; i < 5; i++) {
        els.push(line({ x1: sidebarW + 32, y1: my + 34 + i * 18, x2: W - 40, y2: my + 34 + i * 18, stroke: t.hair, lineWidth: 0.6, dash: 2 }));
      }
      my += 150;
    }
  });

  return { meta: { pageSize: 'letter', title: `${c.name} — Resume`, category: meta.category, tags: [] }, pages: [{ elements: els }] };
}
