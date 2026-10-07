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
        const canon = j.seo?.canonical ? new URL(j.seo.canonical).pathname : null;
        if ((j.seo?.robots || '').includes('noindex') || (canon && decodeURI(canon) !== j.path)) out.add(j.path);
      } else if (f.name.endsWith('.md')) {
        // entradas: frontmatter con path/robots/canonical en JSON por línea
        const fm = fs.readFileSync(p, 'utf8').split('---')[1] || '';
        const get = (k) => { const m = fm.match(new RegExp('^' + k + ': (.*)$', 'm')); return m ? JSON.parse(m[1]) : null; };
        const pth = get('path'), rob = get('robots') || '', can = get('canonical');
        if (pth && (rob.includes('noindex') || (can && decodeURI(new URL(can).pathname) !== pth))) out.add(pth);
      }
    }
  };
  walk('src/content/pages');
  walk('src/content/posts');
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
        return !NOINDEX.has(decodeURI(p)) && p !== '/404/' && p !== '/410/' && !p.startsWith('/propuesta-');
      },
    }),
  ],
});
