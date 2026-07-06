import * as weeklyPlanner from './weekly-planner.js';
import * as invoice from './invoice.js';
import * as resume from './resume.js';
import * as certificate from './certificate.js';

// The catalog of template kinds the engine can produce. Adding a new
// product type is just: create a module exporting { meta, build,
// fallbackContent } and register it here.
const MODULES = [weeklyPlanner, invoice, resume, certificate];

export const templates = new Map(MODULES.map((m) => [m.meta.id, m]));

export function getTemplate(id) {
  const t = templates.get(id);
  if (!t) throw new Error(`Unknown template "${id}". Available: ${[...templates.keys()].join(', ')}`);
  return t;
}

export function listTemplates() {
  return [...templates.values()].map((m) => ({
    id: m.meta.id,
    name: m.meta.name,
    category: m.meta.category,
    basePrice: m.meta.basePrice,
    defaultTheme: m.meta.defaultTheme,
  }));
}
