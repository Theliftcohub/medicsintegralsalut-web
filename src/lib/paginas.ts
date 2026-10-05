// Preparación de los bloques de una página antes de pintarlos (sin tocar el JSON):
// 1) Cabecera de página: si el primer bloque es una sección de prosa que solo tiene un encabezado (y, como mucho,
//    un par de líneas de subtítulo), se pinta como cabecera (banda compacta y centrada) en vez de como sección normal.
// 2) Un H1 por página: si la página no tiene ninguno, el encabezado de esa cabecera pasa a H1; si no hay cabecera,
//    se antepone una con el título literal de la página (`title`). Si tiene varios (el WordPress los repetía), del
//    segundo en adelante pasan a <h2 class="h-as-h1"> con el mismo aspecto. Registrado en NO_LITERAL.md.
const SOLO_ENCABEZADO = /^\s*<h([1-6])([^>]*)>([\s\S]*?)<\/h\1>((?:\s*<p>[^<]{0,180}<\/p>){0,2})\s*$/;
const tieneH1 = (blocks: any[]) => blocks.some((b) => b.headingTag === 'h1' || /<h1[\s>]/.test(JSON.stringify(b)));

export function prepararBloques(blocks: any[], title?: string) {
  const out = blocks.map((b) => ({ ...b }));
  const first = out[0];
  const cab = first?.type === 'vc-prosa' && first.cols?.length === 1 && !first.intro ? SOLO_ENCABEZADO.exec(first.cols[0].html ?? '') : null;
  const h1 = tieneH1(out);
  if (cab) {
    const [, n, attrs, inner, sub = ''] = cab;
    const tag = h1 && n !== '1' ? `h${n}` : 'h1';
    out[0] = { ...first, head: true, cols: [{ html: `<${tag}${attrs}>${inner}</${tag}>${sub.replace(/<p>/g, '<p class="vc-pagehead-sub">')}` }] };
  } else if (!h1 && title) {
    out.unshift({ type: 'vc-prosa', head: true, bg: 'crema', cols: [{ html: `<h1>${title}</h1>` }] });
  }
  // del segundo H1 en adelante -> H2 con aspecto de H1
  let visto = false;
  const uno = (h: string) => h.replace(/<h1(\s[^>]*)?>([\s\S]*?)<\/h1>/g, (m, attrs = '', inner) => {
    if (!visto) { visto = true; return m; }
    const a = attrs.includes('class="') ? attrs.replace('class="', 'class="h-as-h1 ') : `${attrs} class="h-as-h1"`;
    return `<h2${a}>${inner}</h2>`;
  });
  return out.map((b) => {
    if (b.headingTag === 'h1') { if (visto) return { ...b, headingTag: 'h2' }; visto = true; return b; }
    if (b.html) return { ...b, html: uno(b.html) };
    if (b.cols) return { ...b, intro: b.intro && uno(b.intro), cols: b.cols.map((c: any) => ({ ...c, html: c.html && uno(c.html), after: c.after && uno(c.after) })) };
    return b;
  });
}
