#!/usr/bin/env node
import 'dotenv/config';
import { listTemplates } from './templates/index.js';
import { forgeProduct } from './marketplace/forge.js';
import { loadCatalog } from './marketplace/catalog.js';
import { exportProduct } from './marketplace/export.js';
import { startServer } from './store/server.js';

const [, , cmd, ...rest] = process.argv;

// Minimal flag parser: positional args + --key value / --flag.
function parseArgs(argv) {
  const pos = [];
  const opts = {};
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a.startsWith('--')) {
      const key = a.slice(2);
      const next = argv[i + 1];
      if (next === undefined || next.startsWith('--')) opts[key] = true;
      else opts[key] = next, i++;
    } else pos.push(a);
  }
  return { pos, opts };
}

const SEED_BRIEFS = [
  { templateId: 'weekly-planner', brief: 'cozy autumn budget and habit planner' },
  { templateId: 'invoice', brief: 'clean modern freelance designer invoice' },
  { templateId: 'resume', brief: 'minimal professional resume for tech roles' },
  { templateId: 'certificate', brief: 'elegant course completion certificate' },
];

async function main() {
  switch (cmd) {
    case 'templates': {
      console.log('\nAvailable template kinds:\n');
      for (const t of listTemplates()) {
        console.log(`  ${t.id.padEnd(16)} ${t.name}  ($${t.basePrice}, ${t.category})`);
      }
      console.log('\nForge one:  node src/cli.js generate <id> --brief "your niche"\n');
      break;
    }

    case 'generate': {
      const { pos, opts } = parseArgs(rest);
      const templateId = pos[0];
      if (!templateId) return die('Usage: generate <templateId> [--brief "..."] [--theme name] [--price 7.5]');
      const p = await forgeProduct({
        templateId,
        brief: opts.brief === true ? '' : opts.brief || '',
        theme: typeof opts.theme === 'string' ? opts.theme : undefined,
        price: opts.price != null && opts.price !== true ? Number(opts.price) : undefined,
      });
      console.log(`\n✓ Forged "${p.title}"  [${p.engine} engine]`);
      console.log(`  slug:    ${p.slug}`);
      console.log(`  price:   $${p.price}`);
      console.log(`  pdf:     ${p.files.pdf}`);
      console.log(`  preview: ${p.files.preview}`);
      console.log(`  tags:    ${p.tags.join(', ')}\n`);
      break;
    }

    case 'seed': {
      console.log('\nForging a starter catalog...\n');
      for (const s of SEED_BRIEFS) {
        const p = await forgeProduct(s);
        console.log(`  ✓ ${p.slug.padEnd(40)} $${p.price}  [${p.engine}]`);
      }
      console.log('\nDone. Run "node src/cli.js serve" to open the shop.\n');
      break;
    }

    case 'list': {
      const { products } = loadCatalog();
      if (!products.length) return console.log('\nNo products yet. Run "node src/cli.js seed".\n');
      console.log(`\n${products.length} product(s):\n`);
      for (const p of products) {
        console.log(`  ${p.slug.padEnd(40)} $${String(p.price).padStart(6)}  ${p.title}`);
      }
      console.log('');
      break;
    }

    case 'export': {
      const { pos } = parseArgs(rest);
      const slug = pos[0];
      if (!slug) return die('Usage: export <slug>   (see "list" for slugs)');
      const { zipPath } = await exportProduct(slug);
      console.log(`\n✓ Export package ready: ${zipPath}`);
      console.log('  Contains template.pdf, preview.svg, listing.txt, listing.json\n');
      break;
    }

    case 'serve': {
      const { opts } = parseArgs(rest);
      startServer(opts.port && opts.port !== true ? Number(opts.port) : undefined);
      break;
    }

    default:
      console.log(`
PDF Forge — generate PDF templates and put them up for sale.

Commands:
  templates                       List the template kinds available
  generate <id> [--brief "..."]   Forge one product (AI content + PDF + preview + listing)
                 [--theme name] [--price n]
  seed                            Forge a starter catalog (one of each kind)
  list                            List forged products
  export <slug>                   Package a product as a .zip for Etsy/Gumroad
  serve [--port 4000]             Launch the storefront (Stripe or demo checkout)

Environment:
  ANTHROPIC_API_KEY   Use Claude to design content + listing copy (optional)
  FORGE_MODEL         Model id (default claude-sonnet-5)
  STRIPE_SECRET_KEY   Enable real Stripe checkout (optional; demo mode otherwise)
  PORT                Storefront port (default 4000)
`);
  }
}

function die(msg) {
  console.error(msg);
  process.exitCode = 1;
}

main().catch((err) => {
  console.error(`\n✗ ${err.message}\n`);
  process.exitCode = 1;
});
