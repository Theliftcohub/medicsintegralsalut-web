// Utilidades de la portada «Versión C». Las cifras de Google salen de site.json -> rating (dato de GBP con fecha).
import site from '../data/site.json';
const r: any = (site as any).rating ?? {};
export const ratingText = (lang = 'es') => (r.value ?? 0).toLocaleString(lang === 'en' ? 'en' : 'es', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
export const fill = (s: string = '', lang = 'es') => s.replace('{count}', String(r.count ?? '')).replace('{since}', String(r.since ?? '')).replace('{rating}', ratingText(lang));
export const btnClass = (style?: string) => ['btn', style].filter(Boolean).join(' ');
export const ext = (href: string) => /^https?:/.test(href ?? '') ? { rel: 'noopener', target: '_blank' } : {};
