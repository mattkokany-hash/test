import PDFDocument from 'pdfkit';
import fs from 'node:fs';
import { PAGE } from './spec.js';

// Render a Spec to a PDF file on disk. Returns a promise that resolves to
// the output path once the file is fully flushed.
export function renderPdf(spec, outPath) {
  const size = spec.meta._size || PAGE[spec.meta.pageSize] || PAGE.letter;
  const doc = new PDFDocument({
    size: [size.w, size.h],
    margin: 0,
    info: {
      Title: spec.meta.title,
      Author: spec.meta.author || 'PDF Forge',
      Subject: spec.meta.category,
      Keywords: (spec.meta.tags || []).join(', '),
    },
  });

  const stream = fs.createWriteStream(outPath);
  doc.pipe(stream);

  spec.pages.forEach((page, i) => {
    if (i > 0) doc.addPage({ size: [size.w, size.h], margin: 0 });
    for (const el of page.elements) drawElement(doc, el);
  });

  doc.end();
  return new Promise((resolve, reject) => {
    stream.on('finish', () => resolve(outPath));
    stream.on('error', reject);
  });
}

function drawElement(doc, el) {
  switch (el.type) {
    case 'rect': {
      if (el.radius) doc.roundedRect(el.x, el.y, el.w, el.h, el.radius);
      else doc.rect(el.x, el.y, el.w, el.h);
      applyPaint(doc, el);
      break;
    }
    case 'circle': {
      doc.circle(el.x, el.y, el.r);
      applyPaint(doc, el);
      break;
    }
    case 'line': {
      doc.moveTo(el.x1, el.y1).lineTo(el.x2, el.y2);
      if (el.dash) doc.dash(el.dash, { space: el.dash });
      else doc.undash();
      doc.lineWidth(el.lineWidth || 1).strokeColor(el.stroke || '#000').stroke();
      doc.undash();
      break;
    }
    case 'text': {
      const font = el.bold ? 'Helvetica-Bold' : el.font || 'Helvetica';
      doc.font(font)
        .fontSize(el.size || 11)
        .fillColor(el.color || '#111827')
        .text(el.text ?? '', el.x, el.y, {
          width: el.w,
          align: el.align || 'left',
          lineGap: el.lineGap || 2,
          characterSpacing: el.tracking || 0,
        });
      break;
    }
    default:
      break;
  }
}

function applyPaint(doc, el) {
  if (el.fill && el.stroke) {
    doc.lineWidth(el.lineWidth || 1).fillAndStroke(el.fill, el.stroke);
  } else if (el.fill) {
    doc.fill(el.fill);
  } else if (el.stroke) {
    doc.lineWidth(el.lineWidth || 1).stroke(el.stroke);
  }
}
