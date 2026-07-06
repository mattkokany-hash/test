import { PAGE } from '../pdf/spec.js';

// Render the first page of a Spec to an SVG string. Used for storefront
// thumbnails and export preview images. Because it reads the exact same
// Spec the PDF is built from, the preview is faithful to the product.
export function renderSvgPreview(spec, { scale = 1 } = {}) {
  const size = spec.meta._size || PAGE[spec.meta.pageSize] || PAGE.letter;
  const page = spec.pages[0];
  const parts = [];

  parts.push(
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${size.w} ${size.h}" ` +
      `width="${size.w * scale}" height="${size.h * scale}" font-family="Helvetica, Arial, sans-serif">`
  );
  // Paper + subtle drop shadow for a "printable" look.
  parts.push(
    `<rect x="0" y="0" width="${size.w}" height="${size.h}" fill="#ffffff" ` +
      `stroke="#e5e7eb" stroke-width="1"/>`
  );

  for (const el of page.elements) parts.push(svgElement(el));
  parts.push('</svg>');
  return parts.join('');
}

function esc(s) {
  return String(s ?? '').replace(/[<>&]/g, (c) => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;' }[c]));
}

function svgElement(el) {
  switch (el.type) {
    case 'rect': {
      const rx = el.radius ? ` rx="${el.radius}"` : '';
      return `<rect x="${el.x}" y="${el.y}" width="${el.w}" height="${el.h}"${rx} ` +
        `fill="${el.fill || 'none'}" stroke="${el.stroke || 'none'}" ` +
        `stroke-width="${el.lineWidth || 1}"/>`;
    }
    case 'circle':
      return `<circle cx="${el.x}" cy="${el.y}" r="${el.r}" ` +
        `fill="${el.fill || 'none'}" stroke="${el.stroke || 'none'}" ` +
        `stroke-width="${el.lineWidth || 1}"/>`;
    case 'line': {
      const dash = el.dash ? ` stroke-dasharray="${el.dash} ${el.dash}"` : '';
      return `<line x1="${el.x1}" y1="${el.y1}" x2="${el.x2}" y2="${el.y2}" ` +
        `stroke="${el.stroke || '#000'}" stroke-width="${el.lineWidth || 1}"${dash}/>`;
    }
    case 'text': {
      const anchor = el.align === 'center' ? 'middle' : el.align === 'right' ? 'end' : 'start';
      const tx = el.align === 'center' ? el.x + (el.w || 0) / 2 : el.align === 'right' ? el.x + (el.w || 0) : el.x;
      const weight = el.bold ? ' font-weight="bold"' : '';
      const spacing = el.tracking ? ` letter-spacing="${el.tracking}"` : '';
      // SVG text is baseline-anchored; pdfkit is top-anchored. Nudge down
      // by ~0.8em so preview text sits where the PDF renders it.
      const y = el.y + (el.size || 11) * 0.8;
      const lines = String(el.text ?? '').split('\n');
      if (lines.length === 1) {
        return `<text x="${tx}" y="${y}" font-size="${el.size || 11}" ` +
          `fill="${el.color || '#111827'}" text-anchor="${anchor}"${weight}${spacing}>${esc(el.text)}</text>`;
      }
      const gap = (el.size || 11) + (el.lineGap || 2);
      return lines
        .map(
          (ln, i) =>
            `<text x="${tx}" y="${y + i * gap}" font-size="${el.size || 11}" ` +
            `fill="${el.color || '#111827'}" text-anchor="${anchor}"${weight}${spacing}>${esc(ln)}</text>`
        )
        .join('');
    }
    default:
      return '';
  }
}
