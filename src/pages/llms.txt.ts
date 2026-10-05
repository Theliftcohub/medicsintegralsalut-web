import { getCollection } from 'astro:content';
import site from '../data/site.json';
import chrome from '../data/vc-chrome.json';
// Se genera desde el contenido (no a mano): páginas y entradas en español indexables y con canonical propio.
const propia = (path: string, canonical?: string, robots = '') =>
  !robots.includes('noindex') && (!canonical || decodeURI(new URL(canonical).pathname) === path);
export async function GET() {
  const pages = (await getCollection('pages')).filter((p) => p.data.lang === 'es' && propia(p.data.path, p.data.seo.canonical, p.data.seo.robots));
  const posts = (await getCollection('posts')).filter((p) => p.data.lang === 'es' && propia(p.data.path, p.data.canonical, p.data.robots));
  const item = (title: string, path: string, desc?: string) => `- [${title}](${site.url}${path})${desc ? ': ' + desc : ''}`;
  const lines = [`# ${site.name}`, '', `> ${chrome.es.footer.brand}. ${site.address.streetAddress}, ${site.address.postalCode} ${site.address.addressLocality}. Tel. ${site.telephone}.`, '',
    '## Páginas', '', ...pages.map((p) => item(p.data.seo.title, p.data.path, p.data.seo.description)), '',
    '## Blog', '', ...posts.map((p) => item(p.data.seoTitle ?? p.data.title, p.data.path, p.data.description))];
  return new Response(lines.join('\n') + '\n', { headers: { 'Content-Type': 'text/plain; charset=utf-8' } });
}
