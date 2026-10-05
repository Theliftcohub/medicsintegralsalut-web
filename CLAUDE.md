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
- NAP (Google Business Profile, 27/09/2026): Plaça Poeta Marquina 3, 17002 Girona · 972 20 90 86 · L-V 10:00-20:00 (horario de la web, confirmado por Oscar 28/09/2026; ficha de Google corregida el 28/09/2026: el viernes pasa de 10-16 a 10-20, verificado leyendo la ficha). Ver `migracion/gbp.json`.
- Formularios: Contact Form 7 → `form-handler.php` en Plesk. **Todo envío tiene que llegar a Kommo (CRM)** además del email (decisión Oscar 27/09/2026). Implementado: `public/form-handler.php` envía (1) a n8n → workflow `4oQdrYDIlqEjaKpK` "Web Medics · Formularios web (Astro) → Kommo" (INACTIVO hasta lanzamiento; embudo 13319963 / etapa 102721747, como Landing /clinica; crea lead también si solo hay teléfono) y (2) email de RESPALDO a `FORM_DESTINATARIO` solo si Kommo falla (decisión Oscar 27/09: los leads van a Kommo, CRM de Medics; la autorrespuesta al paciente la da Kommo al entrar el lead, la web no envía ninguna). Variables en Plesk: `N8N_FORM_URL` (https://n8n-s57z.sliplane.app/webhook/web-medics-formularios), `N8N_FORM_TOKEN` (en `secrets/n8n_form_token.txt`, nunca en el repo), `FORM_DESTINATARIO`, SMTP_*. Activar el workflow solo con OK de Abi y tras un envío real de prueba en staging (lead TEST, borrar después).
- Analítica: GTM-K63QVGT. El píxel de Meta (1839689313580301) pasa DENTRO de GTM, sujeto a Consent Mode (decisión 27/09/2026); en la web nueva no va inline.
- Política de bots de IA en robots.txt: permitir búsqueda y entrenamiento (confirmado por Oscar 27/09/2026).
- Spam de un hackeo anterior (casinos, en todos los idiomas): 410. Nunca se migra. El hackeo se dio por limpiado; la migración lo deja fuera (no se copia ni código ni base de datos de WordPress, solo contenido revisado).
- Repositorio: GitHub de la agencia (URL pendiente). Item de Monday en el grupo "Otros" del board Medicsalut.
- Fecha de lanzamiento prevista: pendiente. Orden: primero preview en Netlify (noindex) para validar todo; después staging en Plesk.
- Páginas Elementor (portada, blog, legales, antiguas): se RENUEVAN (decisión Oscar 27/09/2026); desde el 28/09/2026 la línea es «Versión C» para toda la web, incluidas las páginas de tratamiento. Contenido, H1/H2, enlaces, imágenes/alt, URL y metadatos literales; solo cambia la plantilla. Empieza por la portada y se valida antes de extender. Se factura aparte: item Monday 13145210372.
- Portada con el diseño «Versión C» (maqueta de The Lift que pasó Oscar el 28/09/2026, guardada en `migracion/diseno/home-version-c.html`): `theme: "vc"` en `home.json`, bloques `vc-*` (`src/blocks/vc/`), cabecera y pie propios (`src/components/vc/`), Raleway 200/300/500/600. `src/styles/vc.css` es copia LITERAL del CSS de la maqueta acotada a `body.vc` y se regenera con `scripts/build_vc_css.py`; los ajustes van en `vc-extra.css`. Contenido: `build_home.py` (literal) → `build_home_vc.py` (reordena en vc-*). **«Versión C» es la línea visual de TODA la web** (decisión Oscar 28/09/2026): cada página nueva se construye con bloques `vc-*`, cabecera y pie vc (`theme: "vc"`); el sistema .mpost queda solo como referencia de las páginas de tratamiento hasta migrarlas a vc.
- Nota y nº de reseñas de Google se muestran desde `site.json → rating` (dato de GBP con fecha). Refrescar antes de lanzar. Nunca AggregateRating.
- Portfolio de antes/después: la clínica tiene el consentimiento de los pacientes (confirmado por Oscar 27/09/2026); se mantiene publicado.

## Formularios: TODOS nativos (decisión Oscar 28/09/2026)
- Todos los formularios de la web son propios (HTML + `form-handler.php` → n8n → Kommo), sin embeds de terceros (Typeform, iframes, widgets). Motivo: antes la medición orgánica fallaba; con formularios nativos el envío, el evento `form_submit`, la página /gracias/ y el canal en Kommo quedan bajo control.

### Typeform: se elimina SIEMPRE
- En esta web (y en todas las migraciones de la agencia) cualquier Typeform se sustituye por el formulario propio (`mp-contact` / `formulario`) → `form-handler.php` → n8n → Kommo. Nunca se reincorpora un embed de Typeform.
- Aquí hay dos: `01J3GWRH78BRMG20DQVDE7JP7F` (portada en todos los idiomas, 13 páginas) y `ZTDKPHl5` (landing /w-lp-ginecomastia/ y variantes, 12 páginas). Campos y textos del formulario propio = los literales del CF7 de /contacto/.
- Antes de apagar los Typeform en Typeform/n8n: comprobar que ningún anuncio activo ni subdominio los usa (los subdominios no se tocan).

## Medición orgánica (la web principal es solo tráfico orgánico; las landings de publicidad son otras webs)
- Cada formulario hace `dataLayer.push({event:'form_submit', form_name, page_path})` al enviar y redirige a la página de gracias de su idioma (conversión definitiva): `/gracias/`, `/ca/gracies/`, `/en/thank-you/`, `/fr/merci/`, `/ru/спасибо/`, `/uk/дякую/` (todas noindex).
- n8n añade al lead de Kommo una línea "Canal:" (Orgánico buscador / asistente IA / redes / referido / directo, o la campaña si hay UTM) a partir del referrer de la primera página de la visita.
- GTM-K63QVGT, a preparar en un espacio de trabajo y publicar EL DÍA DEL LANZAMIENTO: (1) quitar la excepción "All Pages" de la etiqueta GA4 G-7WJ693DDXH (hoy no se ejecuta nunca); (2) evento GA4 `generate_lead` con el activador `form_submit` + página vista de las 6 páginas de gracias; (3) píxel de Meta 1839689313580301 con PageView y Lead; (4) pausar el píxel antiguo 339816866888771 y la etiqueta UA. Todo sujeto a Consent Mode.

## Reglas de contenido
1. Los textos son **literales** del WordPress. Cualquier cambio de texto se registra en `NO_LITERAL.md` (URL, campo, original, nuevo, motivo). Sin excepciones.
2. Las URLs no cambian. Si una URL nueva es inevitable, se añade a `migracion/urls.csv` y se regeneran las redirecciones.
3. Contenido eliminado o spam: 410. Nunca 301 a la portada.
4. Title, description, canonical y robots por página vienen del inventario (`migracion/inventory.json`). No se "mejoran" durante la migración.
5. Imágenes: en el proyecto, WebP, con el alt original y el nombre de archivo original. Nunca enlazar a `/wp-content/`.
6. Datos de médicos en schema solo si figuran literalmente en la web.

## Arquitectura (no cambiar sin hablarlo)
- Una página = un JSON por idioma en `src/content/pages/<lang>/` con `path`, `title` (título literal), `seo`, `schema`, `breadcrumbs`, `blocks[]`.
- Un post = un `.md` en `src/content/posts/<lang>/` con frontmatter completo (author, date, modified, `breadcrumbs` y `schema` del WordPress). Una URL es O página O entrada, nunca las dos (Astro descarta una en silencio).
- Ruta única `src/pages/[...slug].astro` (español sin prefijo). `build.format: 'directory'`, `trailingSlash: 'always'`.
- Toda la web usa el diseño «Versión C» (`body.vc`): `src/layouts/Base.astro` → `VcHeader` + migas + bloques + `VcFooter` + banner de cookies.
- Antes de pintar una página, `src/lib/paginas.ts` marca la cabecera de página (primer bloque con solo un encabezado) y garantiza un H1.
- Mapa de traducciones en `migracion/i18n-map.json` (`i18nGroup` en cada página/entrada); hreflang solo a URLs existentes + x-default. El selector de idioma muestra siempre los 6; si la página no tiene traducción, lleva a la portada de ese idioma.
- Textos de interfaz (cookies, menú, «Publicado/por», mapa) en `src/i18n/ui.json`, los 6 idiomas.
- Estilos, en este orden (`Base.astro`): `tokens.css` (variables de .mpost) · `comun.css` (reset, cookies, formularios) · `mpost.css` · `vc.css` (copia literal de la maqueta, generada) · `vc-extra.css` (cabecera, mega menú, idioma, ajustes) · `mpost-posts.css` (generado) · `vc-mpost.css` (piel de tratamientos) · `vc-prosa.css` (páginas de texto, blog y entradas). Sin Tailwind.
- Astro 7 · colecciones en `src/content.config.ts` (loader glob). `npm run build` copia `dist/410/index.html` a `dist/410.html` para el ErrorDocument de Apache.
- `PUBLIC_ENTORNO`: `preview` (por defecto: noindex, sin GTM, formularios desactivados) · `staging` (noindex, GTM) · `produccion`.
- Los componentes no contienen textos de negocio.
- `src/content/` y `public/images|media` NO están en git: van empaquetados en `_datos/contenido-web.tgz.part*` (ver `_datos/LEEME_CONTENIDO.md`). Tras cambiar contenido, regenerar el paquete.

## Construcción de páginas «Versión C» (28/09/2026)
- `scripts/vc_pages.py <ruta…> | --todas`: genera TODAS las páginas y entradas desde el HTML del WordPress (6 idiomas).
  - Con componentes `.mpost` (tratamientos): bloque `vc-mpost` con el marcado literal limpio + piel `src/styles/vc-mpost.css`.
  - Resto (WPBakery/Bridge, fichas, legales, landings): bloques `vc-prosa` (HTML semántico literal por fila; columnas en rejilla). CF7 y Typeform → formulario propio (`NativeForm`).
  - Entradas: `src/content/posts/<lang>/*.md` (frontmatter completo; `mpost: true` si la entrada está maquetada con .mpost, CSS literal en `src/styles/mpost-posts.css` generado por `scripts/build_mpost_posts_css.py`).
  - Informe de incidencias: `migracion/vc_pages_report.json` (imágenes sin copia local, Typeform, formularios, páginas vacías).
- El HTML del WordPress se lee de `migracion/html_cache/` (530 MB, fuera del repo); `wp_lib.html_of` lo descarga y lo guarda si falta (con pausa de 0,6 s).
- Después de generar, SIEMPRE: `scripts/schema_posts.py` (migas y JSON-LD propio de cada entrada) → `scripts/pulir_contenido.py` (limpieza idempotente: duplicados página/entrada, migas concatenadas, entidad MedicalClinic, título, texto oculto, iconos, bloque de contacto, enlaces a /media/, página de gracias por idioma y su noindex).
- Portadas: `build_home.py <url> <lang> <out>` (literal) → `build_home_vc.py <lang>` (textos nuevos de la maqueta por idioma en `scripts/home_vc_textos.json`).
- Cabecera y pie por idioma: `scripts/build_chrome_vc.py` → `src/data/vc-chrome.json` (etiquetas y enlaces literales de cada portada) → `scripts/build_menu_unidades.py` (submenú de Unidades del WordPress, clave `units`, enlaces a su URL final).
- Redirecciones: `scripts/resolver_revisar.py` (cerró las 69 REVISAR con criterios escritos en `notas`) → `scripts/redirects_contract.py` (url-map.csv + gone.txt, cadenas resueltas) → `build_redirects.py … --con-www --contract migracion/urls.csv --sin-rss` → `scripts/redirects_post.py` (OBLIGATORIO: Netlify compara en %MAYÚSCULAS y Apache con la ruta decodificada; quita reglas de solo barra final, que en Netlify hacen bucle).
- Enlaces internos: `scripts/enlaces_finales.py` (tras construir `dist/`) reescribe cada enlace a su URL final y quita los que van a 410/404.
- Validación: `scripts/validar_rapido.py <base>` (paralelo: estado de las 3.063 URLs del contrato + title/H1/restos/imágenes/enlaces en dist/). Probado contra Netlify y contra un Apache local con el `.htaccess` (sin el bloque https): 0 fallos de estado. `validate_migration.py` completo tarda horas en serie: usarlo solo en staging.
- Descargas: `wp_lib.fetch_bytes` recuerda las URL que fallan en `migracion/fetch_fallidos.txt`.
- En Windows, los scripts de Python se lanzan con `PYTHONUTF8=1` (y `MSYS_NO_PATHCONV=1` si se les pasan rutas que empiezan por `/` desde Git Bash).

## Bloques disponibles (`src/blocks/Block.astro` es el único punto que conecta tipo y componente)
| Tipo | Componente | Uso |
|---|---|---|
| `vc-prosa` | `vc/Prosa.astro` | Páginas de texto: `cols[{html?, form?, after?}]`, `intro`, `bg` (`crema`), `stack`, `variant` (`tarjetas`); `head` lo pone `paginas.ts`. Texto + formulario apilados se pintan en dos columnas |
| `vc-tarjetas` | `vc/Tarjetas.astro` | Tratamientos de una unidad: `heading`, `items[{text, href}]`; foto y descripción salen de la página enlazada |
| `vc-mpost` | `vc/Mpost.astro` | Páginas de tratamiento: `html` literal con componentes .mpost |
| `vc-hero`, `vc-editorial`, `vc-trat`, `vc-unidades`, `vc-resenas`, `vc-videos`, `vc-ventajas`, `vc-equipo`, `vc-distintivos`, `vc-contacto`, `vc-cierre` | `vc/*.astro` | Portadas (6 idiomas); `vc-unidades` también en /unidades/ |

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
- 05/10/2026 · 46 entradas en español tenían además un JSON de página con la misma URL: Astro renderiza una y descarta la otra sin fallar el build (solo un WARN) · `pulir_contenido.py` borra el JSON; revisar los WARN «conflicts with higher priority route» en cada build.
- 05/10/2026 · `build_post` descartaba el JSON-LD propio y las migas de las entradas (612 entradas sin FAQPage/VideoObject/MedicalWebPage ni BreadcrumbList) · `schema_posts.py` los recupera al frontmatter y la plantilla los publica.
- 05/10/2026 · Los formularios de ca/en/fr/ru/uk enviaban a `/xx/gracias/` (URLs de TranslatePress que no existen): 404 tras enviar · cada idioma va a su página de gracias real (`GRACIAS` en `pulir_contenido.py`). Las páginas de gracias de todos los idiomas cuentan como conversión.
- 05/10/2026 · `ui.json` solo tenía español: banner de cookies, «Publicado/por» y «Ver el mapa» salían en español en los 6 idiomas · todo texto de interfaz nuevo se añade en los 6 idiomas a la vez.
- 05/10/2026 · `redirects_contract.py` no resolvía cadenas cuando la URL y el destino tenían distinta caja de %-encoding (%D0 / %d0): 2 redirecciones ru/uk caían al índice · claves siempre decodificadas (`unquote`).
- 05/10/2026 · El submenú de Unidades no se migró (solo el enlace «unidades») · el menú se extrae entero, con todos sus niveles (`build_menu_unidades.py`).
- 05/10/2026 · Tras ejecutar `pulir_contenido.py` el `npm run dev` abierto siguió pintando el contenido anterior · después de cambiar muchos archivos de `src/content`, reiniciar el servidor de desarrollo antes de revisar.
- 05/10/2026 · Se borró `Icon.astro` creyéndolo muerto y lo usa `NativeForm` · antes de borrar un componente, buscar su nombre de archivo en todos los `import` y probar el build.
- 28/09/2026 · Se migraba contenido que en el WordPress está OCULTO en todos los tamaños (vc_hidden-lg/md/sm/xs: «Lorem ipsum», FAQ de rinoplastia en páginas de rejuvenecimiento, vídeo de otra clínica en /financiacion/; 145 páginas) · `hidden_filter()` lo elimina; lo oculto solo en móvil o solo en escritorio va en `.vc-solo-movil` / `.vc-solo-escritorio(-sm)`. Los enlaces dentro de `.visitabuttonp` son botones.
- 28/09/2026 · Las entradas .mpost se veían distintas al original: (1) compartían clases con las páginas de tratamiento y les aplicaban mpost.css y la piel vc-mpost.css; (2) mpost-posts.css mezclaba el CSS de las 5 variantes de entrada; (3) con el peso 300 de la maqueta, `<b>` («bolder») quedaba en 400 · en las entradas las clases `mpost*` se renombran a `mpp*` y cada entrada va dentro de `.mpv-<huella de su <style>>`, con SU CSS solo. El listado del blog (.grid > .mason-item) pasa a rejilla `.vc-bloglist` y el extracto se corta donde el WordPress coló CSS.
- 28/09/2026 · La prosa aplanaba acordeones de Bridge (se veían abiertos), filas internas de WPBakery (fotos enormes) y ponía el formulario antes/después del texto sin respetar el original · `structure_widgets()` convierte acordeones en `<details>` y `.vc_inner` en rejilla `.vc-in` con las proporciones vc_col-sm-N; el CF7 deja un marcador `{{CF7}}` en su sitio. Los fondos CSS en línea se leen ANTES de `clean_common` (que borra los `style`).
- 28/09/2026 · El detector de spam de build_redirects marcaba 410 una página "mantener" (cirurgia-de-barbeta, "bet") · el contrato manda: `gone -= contract_mantener`.
- 28/09/2026 · `pkill -f <patrón>` mató la propia shell porque el patrón aparecía en su línea de comandos · lanzar procesos largos con `setsid nohup` y no usar pkill con patrones que estén en el mismo comando.
- 28/09/2026 · Las rutas de ru/uk están codificadas (%d0…) en urls.csv: el `path` de las páginas va DECODIFICADO (Astro lo exige) y los archivos se nombran decodificados (hash si >150 bytes).
- 28/09/2026 · `find_parent(class_=…)` llega hasta `<body>`, cuyas clases incluyen "sticky"/"header": excluir body/html al filtrar contenedores de cabecera.
- 28/09/2026 · Al filtrar las notas del diseñador (`.nota`) se cayeron también las reglas de `.nota-g` · filtrar clases por palabra completa (`\.nota(?![\w-])`), nunca por subcadena.
- 28/09/2026 · La maqueta atribuía un testimonio a "Amador", que es el médico (Dr. Amador García) · contrastar nombres de pacientes con la fuente (miniatura/vídeo) antes de publicar un título.
- 27/09/2026 · El export de GSC incluía subdominios y sus rutas colisionaban con las del www · filtrar siempre `gsc.csv` al host www antes de construir el contrato.

## Modelos
Opus para decisiones de arquitectura y bloques nuevos (fases 0-2). Sonnet para migrar páginas, corregir y ediciones de contenido (fases 3-7).
