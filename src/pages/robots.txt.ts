import tpl from '../data/robots.txt.template?raw';
// La plantilla documenta la política por bot. El robots.txt publicado sale compacto: sin comentarios y sin los grupos
// que solo repiten «Allow: /» (ya los cubre «User-agent: *»), con el mismo efecto para todos los rastreadores.
const grupos = tpl.split('\n').filter((l) => !l.trimStart().startsWith('#')).join('\n').split(/\n\s*\n/).map((g) => g.trim()).filter(Boolean);
const util = grupos.filter((g) => {
  const reglas = g.split('\n').filter((l) => !/^user-agent:/i.test(l.trim()));
  return !(g.toLowerCase().startsWith('user-agent:') && reglas.length > 0 && reglas.every((l) => /^allow:\s*\/\s*$/i.test(l.trim())));
});
export const GET = ({ site }: { site: URL }) =>
  new Response(util.join('\n\n').replace('{{SITEMAP_URL}}', new URL('sitemap-index.xml', site).href) + '\n', { headers: { 'Content-Type': 'text/plain; charset=utf-8' } });
