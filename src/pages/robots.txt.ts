import tpl from '../data/robots.txt.template?raw';
// La plantilla lleva comentarios internos (por qué se permite cada bot); el robots.txt publicado sale sin ellos.
const limpio = tpl.split('\n').filter((l) => !l.trimStart().startsWith('#')).join('\n').replace(/\n{3,}/g, '\n\n').trim();
export const GET = ({ site }: { site: URL }) =>
  new Response(limpio.replace('{{SITEMAP_URL}}', new URL('sitemap-index.xml', site).href) + '\n', { headers: { 'Content-Type': 'text/plain; charset=utf-8' } });
