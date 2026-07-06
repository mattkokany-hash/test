import fs from 'node:fs';
import path from 'node:path';
import { getTemplate } from '../templates/index.js';
import { generate } from '../ai/generator.js';
import { renderPdf } from '../pdf/render.js';
import { renderSvgPreview } from './preview.js';
import { upsertProduct, slugify, uniqueSlug } from './catalog.js';

const OUT = path.resolve('output');

// The end-to-end "make one sellable product" pipeline:
//   brief -> AI content + listing -> PDF + SVG preview -> catalog entry.
export async function forgeProduct({ templateId, brief = '', theme, price } = {}) {
  const tpl = getTemplate(templateId);
  const gen = await generate({ templateId, brief, themeName: theme });

  // Build the spec, stamp final tags/title into PDF metadata.
  const spec = tpl.build(gen.content, gen.themeName);
  spec.meta.tags = gen.listing.tags;
  spec.meta.title = gen.listing.title;

  const slug = uniqueSlug(slugify(gen.listing.title || tpl.meta.name));
  const dir = path.join(OUT, slug);
  fs.mkdirSync(dir, { recursive: true });

  const pdfPath = path.join(dir, 'template.pdf');
  await renderPdf(spec, pdfPath);

  const svg = renderSvgPreview(spec);
  fs.writeFileSync(path.join(dir, 'preview.svg'), svg);

  const product = {
    slug,
    templateId,
    title: gen.listing.title,
    description: gen.listing.description,
    tags: gen.listing.tags,
    theme: gen.themeName,
    category: tpl.meta.category,
    brief,
    price: price != null ? Number(price) : gen.listing.price,
    engine: gen.engine,
    files: {
      pdf: path.relative(process.cwd(), pdfPath),
      preview: path.relative(process.cwd(), path.join(dir, 'preview.svg')),
    },
    createdAt: new Date().toISOString(),
  };

  fs.writeFileSync(path.join(dir, 'product.json'), JSON.stringify(product, null, 2));
  upsertProduct(product);
  return product;
}
