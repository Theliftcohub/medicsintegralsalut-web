// @ts-check
import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';
import fs from 'node:fs';
import path from 'node:path';

// Rutas noindex fuera del sitemap: se leen de los JSON/MD de contenido.
function rutasNoindex() {
  const out = new Set();
  const walk = (dir) => {
    if (!fs.existsSync(dir)) return;
    for (const f of fs.readdirSync(dir, { withFileTypes: true })) {
      const p = path.join(dir, f.name);
      if (f.isDirectory()) walk(p);
      else if (f.name.endsWith('.json')) {
        const j = JSON.parse(fs.readFileSync(p, 'utf8'));
        if ((j.seo?.robots || '').includes('noindex')) out.add(j.path);
      }
    }
  };
  walk('src/content/pages');
  return out;
}
const NOINDEX = rutasNoindex();
const SITE = 'https://www.medicsintegralsalut.com';

export default defineConfig({
  site: SITE,
  trailingSlash: 'always',
  output: 'static',
  build: { format: 'directory' },
  integrations: [
    sitemap({
      filter: (page) => {
        const p = new URL(page).pathname;
        return !NOINDEX.has(p) && p !== '/404/' && p !== '/410/';
      },
    }),
  ],
});
