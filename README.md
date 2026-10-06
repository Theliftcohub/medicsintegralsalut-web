# medicsintegralsalut-web

Web estática de Médics Integral Salut (www.medicsintegralsalut.com) migrada de WordPress a Astro por The Lift Co.
Reglas, decisiones y flujo completo: **CLAUDE.md**. Cambios de texto respecto al WordPress: **NO_LITERAL.md**.

## Puesta en marcha
```bash
npm ci
cat _datos/contenido-web.tgz.part* | tar -xz      # src/content/ + public/images/ + public/media/ (no van sueltos en git)
cat migracion/content.tgz.part0* | tar -xz && gunzip -k migracion/inventory.json.gz   # datos de migración
npm run dev          # http://localhost:4321
npm run build                 # dist/ para la preview (noindex, sin GTM, formularios desactivados)
npm run build:produccion      # dist/ para Plesk (indexable, GTM, formularios activos)
python scripts/verificar_produccion.py   # verificación estática de la build de producción: tiene que dar «OK, sin errores»
```

## Dónde está cada cosa
| Carpeta | Qué hay |
|---|---|
| `src/content/pages/<idioma>/*.json` | Una página por idioma: `path`, `title`, `seo`, `schema`, `breadcrumbs`, `blocks[]` |
| `src/content/posts/<idioma>/*.md` | Entradas del blog (frontmatter + HTML literal) |
| `src/pages/[...slug].astro` | La única ruta: pinta páginas y entradas |
| `src/layouts/Base.astro` | `<head>` SEO, cabecera, migas, pie, cookies |
| `src/blocks/Block.astro` + `src/blocks/vc/` | Tipos de bloque → componentes |
| `src/components/vc/` | Cabecera (mega menú de Unidades, selector de idioma) y pie |
| `src/data/vc-chrome.json` | Menú, submenú de Unidades y pie de cada idioma (generado) |
| `src/i18n/ui.json` | Textos de interfaz en los 6 idiomas |
| `src/styles/` | CSS (orden y papel de cada archivo en CLAUDE.md) |
| `public/` | `.htaccess` (Plesk), `_redirects` y `_headers` (Netlify), `form-handler.php`, favicons |
| `scripts/` | Extracción, generación, limpieza, redirecciones y validación (Python) |
| `migracion/` | Inventario, contrato de URLs (`urls.csv`), redirecciones, informes |

## Validar
```bash
PYTHONUTF8=1 python scripts/validar_rapido.py https://medicsintegralsalut-preview.netlify.app
```
