import express from 'express';
import Stripe from 'stripe';
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { loadCatalog, getProduct } from '../marketplace/catalog.js';
import { page, catalogView, productView, successView } from './views.js';

// In-memory download grants: token -> slug. A grant is minted only after a
// completed purchase (real Stripe payment, or the keyless demo checkout).
const grants = new Map();

export function createServer() {
  const app = express();
  app.use(express.urlencoded({ extended: true }));

  const stripe = getStripe();
  const money = (n) => `$${Number(n).toFixed(2)}`;

  app.get('/', (req, res) => {
    const { products } = loadCatalog();
    res.send(page('PDF Forge — Shop', catalogView(products, money, !!stripe)));
  });

  // Serve the SVG preview generated at forge time.
  app.get('/preview/:slug.svg', (req, res) => {
    const p = getProduct(req.params.slug);
    if (!p) return res.status(404).end();
    const svg = path.resolve(p.files.preview);
    if (!fs.existsSync(svg)) return res.status(404).end();
    res.type('image/svg+xml').send(fs.readFileSync(svg));
  });

  app.get('/p/:slug', (req, res) => {
    const p = getProduct(req.params.slug);
    if (!p) return res.status(404).send(page('Not found', '<p>Product not found.</p>'));
    res.send(page(p.title, productView(p, money, !!stripe)));
  });

  // Start a purchase.
  app.post('/buy/:slug', async (req, res) => {
    const p = getProduct(req.params.slug);
    if (!p) return res.status(404).end();

    if (stripe) {
      try {
        const base = `${req.protocol}://${req.get('host')}`;
        const session = await stripe.checkout.sessions.create({
          mode: 'payment',
          line_items: [
            {
              quantity: 1,
              price_data: {
                currency: 'usd',
                unit_amount: Math.round(Number(p.price) * 100),
                product_data: { name: p.title, description: p.description?.slice(0, 300) },
              },
            },
          ],
          success_url: `${base}/success?slug=${p.slug}&session_id={CHECKOUT_SESSION_ID}`,
          cancel_url: `${base}/p/${p.slug}`,
        });
        return res.redirect(303, session.url);
      } catch (err) {
        return res.status(500).send(page('Checkout error', `<p>Stripe error: ${escapeHtml(err.message)}</p>`));
      }
    }

    // Keyless demo mode: simulate an instant, free "purchase".
    const token = mintGrant(p.slug);
    res.redirect(303, `/success?slug=${p.slug}&demo=1&token=${token}`);
  });

  app.get('/success', async (req, res) => {
    const p = getProduct(req.query.slug);
    if (!p) return res.status(404).send(page('Not found', '<p>Unknown product.</p>'));

    let token = req.query.token;
    if (stripe && req.query.session_id) {
      try {
        const session = await stripe.checkout.sessions.retrieve(req.query.session_id);
        if (session.payment_status === 'paid') token = mintGrant(p.slug);
      } catch {
        /* fall through to no-token state */
      }
    }

    const ok = token && grants.get(token) === p.slug;
    res.send(page('Thank you', successView(p, ok ? token : null, !!req.query.demo)));
  });

  // Token-gated download of the actual PDF.
  app.get('/download/:slug', (req, res) => {
    const token = req.query.token;
    if (!token || grants.get(token) !== req.params.slug) {
      return res.status(403).send(page('Access denied', '<p>Invalid or expired download link.</p>'));
    }
    const p = getProduct(req.params.slug);
    const pdf = path.resolve(p.files.pdf);
    if (!fs.existsSync(pdf)) return res.status(404).end();
    res.download(pdf, `${p.slug}.pdf`);
  });

  return app;
}

export function startServer(port = process.env.PORT || 4000) {
  const app = createServer();
  return app.listen(port, () => {
    const mode = getStripe() ? 'Stripe live checkout' : 'DEMO checkout (no Stripe key set)';
    console.log(`\n  PDF Forge storefront  →  http://localhost:${port}`);
    console.log(`  Payment mode: ${mode}\n`);
  });
}

let _stripe = null;
function getStripe() {
  const key = process.env.STRIPE_SECRET_KEY;
  if (!key) return null;
  if (!_stripe) _stripe = new Stripe(key);
  return _stripe;
}

function mintGrant(slug) {
  const token = crypto.randomBytes(18).toString('hex');
  grants.set(token, slug);
  return token;
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
}
