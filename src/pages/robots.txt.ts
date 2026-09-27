import tpl from '../data/robots.txt.template?raw';
export const GET = ({ site }: { site: URL }) =>
  new Response(tpl.replace('{{SITEMAP_URL}}', new URL('sitemap-index.xml', site).href), { headers: { 'Content-Type': 'text/plain; charset=utf-8' } });
