import fs from 'node:fs';
import path from 'node:path';

// A tiny JSON-file catalog. Products the engine forges are appended here;
// the storefront reads from it. Good enough for a single-seller shop and
// trivial to swap for a real DB later.
const DATA_DIR = path.resolve('data');
const CATALOG = path.join(DATA_DIR, 'products.json');

export function loadCatalog() {
  if (!fs.existsSync(CATALOG)) return { products: [] };
  try {
    return JSON.parse(fs.readFileSync(CATALOG, 'utf8'));
  } catch {
    return { products: [] };
  }
}

export function saveCatalog(cat) {
  fs.mkdirSync(DATA_DIR, { recursive: true });
  fs.writeFileSync(CATALOG, JSON.stringify(cat, null, 2));
}

export function upsertProduct(product) {
  const cat = loadCatalog();
  const idx = cat.products.findIndex((p) => p.slug === product.slug);
  if (idx >= 0) cat.products[idx] = product;
  else cat.products.push(product);
  saveCatalog(cat);
  return product;
}

export function getProduct(slug) {
  return loadCatalog().products.find((p) => p.slug === slug);
}

export function slugify(s) {
  return s
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 60);
}

// Ensure slug uniqueness within the existing catalog.
export function uniqueSlug(base) {
  const cat = loadCatalog();
  const taken = new Set(cat.products.map((p) => p.slug));
  let slug = base || 'product';
  let n = 2;
  while (taken.has(slug)) slug = `${base}-${n++}`;
  return slug;
}
