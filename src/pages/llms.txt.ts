import { getCollection } from 'astro:content';
import site from '../data/site.json';
// Se genera desde el contenido (no a mano). No se vende como palanca: Google no lo usa.
export async function GET() {
  const pages = (await getCollection('pages')).filter((p) => p.data.lang === 'es' && !p.data.seo.robots.includes('noindex'));
  const lines = [`# ${site.name}`, '', `> ${site.type} en ${site.address.streetAddress}, ${site.address.postalCode} ${site.address.addressLocality}. Tel. ${site.telephone}.`, '', '## Páginas principales', ''];
  for (const p of pages) lines.push(`- [${p.data.seo.title}](${site.url}${p.data.path})${p.data.seo.description ? ': ' + p.data.seo.description : ''}`);
  return new Response(lines.join('\n') + '\n', { headers: { 'Content-Type': 'text/plain; charset=utf-8' } });
}
