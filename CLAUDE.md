# CLAUDE.md · Médics Integral Salut (www.medicsintegralsalut.com)

Este archivo es el contrato del proyecto. Se lee al empezar cada sesión. Cuando cometas un error y lo corrijas, añade aquí la regla que lo evita. Cuando el usuario tome una decisión, apúntala aquí.

## Qué es este proyecto
Web estática de Médics Integral Salut (clínica de cirugía y medicina estética, Girona) migrada desde WordPress (Elementor con restos de Divi, Yoast SEO, TranslatePress) a Astro. Preview de aprobación en Netlify (noindex); producción en Plesk. Sin CMS: el contenido vive en `src/content/` y se edita con Claude Code. Agencia: The Lift Co. Playbook: skill `migracion-wp-theliftv2`. Item de Monday: board Medicsalut (6926832316) · item 13144642709.

## Decisiones fijas
- Dominio canónico: `https://www.medicsintegralsalut.com/` (CON www — decisión 27/09/2026, se mantiene el host actual; barra final: sí).
- **Subdominios fuera de alcance** (info., consultas., balon., estetica.): no se tocan, no se redirigen, no entran en el contrato (decisión 27/09/2026).
- Idiomas: se migran los 6 (decisión Oscar 27/09/2026): es (por defecto, sin prefijo), ca, en, fr, ru, uk con prefijo `/xx/`. Slugs traducidos: sí (TranslatePress), se conservan exactos.
- URLs duplicadas con canonical a otra URL (árbol catalán antiguo sin prefijo y slugs viejos de TranslatePress, ~456): 301 a su canónica (aprobado por Oscar 27/09/2026). No se reconstruyen.
- Tipo de negocio para schema: `MedicalClinic` (ya existente, no se rebaja).
- NAP (Google Business Profile, 27/09/2026): Plaça Poeta Marquina 3, 17002 Girona · 972 20 90 86 · L-V 10:00-20:00 (horario de la web, confirmado por Oscar 28/09/2026; la ficha de Google tiene el viernes mal, 10-16, y hay que corregirla). Ver `migracion/gbp.json`.
- Formularios: Contact Form 7 → `form-handler.php` en Plesk. **Todo envío tiene que llegar a Kommo (CRM)** además del email (decisión Oscar 27/09/2026). Implementado: `public/form-handler.php` envía (1) a n8n → workflow `4oQdrYDIlqEjaKpK` "Web Medics · Formularios web (Astro) → Kommo" (INACTIVO hasta lanzamiento; embudo 13319963 / etapa 102721747, como Landing /clinica; crea lead también si solo hay teléfono) y (2) email de RESPALDO a `FORM_DESTINATARIO` solo si Kommo falla (decisión Oscar 27/09: los leads van a Kommo, CRM de Medics; la autorrespuesta al paciente la da Kommo al entrar el lead, la web no envía ninguna). Variables en Plesk: `N8N_FORM_URL` (https://n8n-s57z.sliplane.app/webhook/web-medics-formularios), `N8N_FORM_TOKEN` (en `secrets/n8n_form_token.txt`, nunca en el repo), `FORM_DESTINATARIO`, SMTP_*. Activar el workflow solo con OK de Abi y tras un envío real de prueba en staging (lead TEST, borrar después).
- Analítica: GTM-K63QVGT. El píxel de Meta (1839689313580301) pasa DENTRO de GTM, sujeto a Consent Mode (decisión 27/09/2026); en la web nueva no va inline.
- Política de bots de IA en robots.txt: permitir búsqueda y entrenamiento (confirmado por Oscar 27/09/2026).
- Spam de un hackeo anterior (casinos, en todos los idiomas): 410. Nunca se migra. El hackeo se dio por limpiado; la migración lo deja fuera (no se copia ni código ni base de datos de WordPress, solo contenido revisado).
- Repositorio: GitHub de la agencia (URL pendiente). Item de Monday en el grupo "Otros" del board Medicsalut.
- Fecha de lanzamiento prevista: pendiente. Orden: primero preview en Netlify (noindex) para validar todo; después staging en Plesk.
- Páginas Elementor (portada, blog, legales, antiguas): se RENUEVAN con la línea visual de las páginas de tratamiento nuevas (decisión Oscar 27/09/2026). Contenido, H1/H2, enlaces, imágenes/alt, URL y metadatos literales; solo cambia la plantilla. Empieza por la portada y se valida antes de extender. Se factura aparte: item Monday 13145210372.
- Portfolio de antes/después: la clínica tiene el consentimiento de los pacientes (confirmado por Oscar 27/09/2026); se mantiene publicado.

## Reglas de contenido
1. Los textos son **literales** del WordPress. Cualquier cambio de texto se registra en `NO_LITERAL.md` (URL, campo, original, nuevo, motivo). Sin excepciones.
2. Las URLs no cambian. Si una URL nueva es inevitable, se añade a `migracion/urls.csv` y se regeneran las redirecciones.
3. Contenido eliminado o spam: 410. Nunca 301 a la portada.
4. Title, description, canonical y robots por página vienen del inventario (`migracion/inventory.json`). No se "mejoran" durante la migración.
5. Imágenes: en el proyecto, WebP, con el alt original y el nombre de archivo original. Nunca enlazar a `/wp-content/`.
6. Datos de médicos en schema solo si figuran literalmente en la web.

## Arquitectura (no cambiar sin hablarlo)
- Una página = un JSON por idioma en `src/content/pages/<lang>/` con `path`, `seo`, `schema`, `breadcrumbs`, `blocks[]`.
- Un post = un `.md` en `src/content/posts/` con frontmatter completo (author, datePublished, dateModified).
- Ruta `[...slug].astro` con el español sin prefijo. `build.format: 'directory'`, `trailingSlash: 'always'`.
- Mapa de traducciones en `migracion/i18n-map.json`; hreflang solo a URLs existentes + x-default.
- Textos de interfaz en `src/i18n/ui.json`.
- Colores, tipografías y espaciados solo desde `src/styles/tokens.css` (sin Tailwind: CSS plano en `base.css` y en cada bloque).
- Astro 7 · colecciones en `src/content.config.ts` (loader glob). `npm run build` copia `dist/410/index.html` a `dist/410.html` para el ErrorDocument de Apache.
- `PUBLIC_ENTORNO`: `preview` (por defecto: noindex, sin GTM, formularios desactivados) · `staging` (noindex, GTM) · `produccion`.
- Los componentes no contienen textos de negocio.

## Bloques disponibles
| Tipo | Campos | Variantes |
|---|---|---|
| `hero` | title, text, image, imageAlt, cta{text,href} | `imagen-derecha`, `fondo`, `simple` |
| `texto` | html | — |
| `tarjetas` | columns, items[{title,text,icon,href}] | — |
| `faq` | items[{q,a}] | — |
| `cta` | title, text, button{text,href} | `banda`, `caja` |
| `galeria` | images[{src,alt}] | — |
| `formulario` | name, fields[], destination | — |
| `lista-posts` | limit, category | — |

## Flujo de trabajo
- Un commit por página migrada: `feat(page): migrar /ruta/`.
- Antes de cada commit: `npm run build` sin errores y validación de enlaces.
- Antes de lanzar: `validate_migration.py` completo, cero FAIL, en staging de Plesk.
- Credenciales solo en `.env` / `secrets/` (ignorados por git). Nunca leerlas en el chat.
- El servidor WordPress corta conexiones (firewall): extraer siempre con `--delay` ≥0.6; `fetch` reintenta 5 veces.

## Despliegue de la preview (Netlify)
- Proyecto Netlify `medicsintegralsalut-preview` (id ce4301a0-b2c3-4f26-bd12-1c08c88b90ee, equipo Belba). URL: https://medicsintegralsalut-preview.netlify.app — siempre con `X-Robots-Tag: noindex` (`public/_headers`) y `PUBLIC_ENTORNO=preview` (`netlify.toml`).
- Cómo desplegar: herramienta MCP de Netlify `deploy-site` con ese siteId → devuelve un comando `npx @netlify/mcp ... --proxy-path` de un solo uso. Ejecutarlo desde una copia limpia (`git archive HEAD`), SIN `migracion/` (530 MB de html_cache), nunca desde el repo de trabajo.
- GitHub: github.com/Theliftcohub/medicsintegralsalut-web. Si la sesión no tiene el repo autorizado para git, se sube por la web de GitHub (upload por carpeta, ≤100 archivos y ≤25 MB por archivo).

## Errores ya cometidos y sus reglas
- 27/09/2026 · El export de GSC incluía subdominios y sus rutas colisionaban con las del www · filtrar siempre `gsc.csv` al host www antes de construir el contrato.

## Modelos
Opus para decisiones de arquitectura y bloques nuevos (fases 0-2). Sonnet para migrar páginas, corregir y ediciones de contenido (fases 3-7).
