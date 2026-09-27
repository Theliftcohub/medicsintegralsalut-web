#!/usr/bin/env python3
r"""
Genera las redirecciones de la migración para uno o varios entornos.

Uso:
  python3 build_redirects.py migracion/inventory.json \
      --new-routes dist/ \                # carpeta construida (para saber qué URLs existen)
      --target both \                     # netlify | apache | nginx | both (por defecto: both)
      --domain dominio.com \               # o se lee de CLAUDE.md ("Dominio canónico: ...")
      --map migracion/url-map.csv \       # opcional: CSV "antigua,nueva" para URLs que cambian
      --gone migracion/gone.txt \         # opcional: URLs (una por línea) que devuelven 410
      --legacy migracion/redirects-export.csv \  # opcional: export del plugin Redirection/Rank Math
      --media migracion/media.json \      # opcional: redirecciones 301/410 de medios
      --public public/ \                  # opcional: carpeta public/ (además de dist/) donde buscar medios
      --out public/_redirects \           # salida Netlify
      --out-htaccess public/.htaccess \   # salida Apache (Plesk/producción)
      --out-nginx nginx-directivas.conf   # salida nginx ("Additional nginx directives" en Plesk)

ARQUITECTURA (decisión del CEO, ver references/plesk-produccion.md):
- Netlify = SOLO preview/aprobación. Nunca se indexa: lleva X-Robots-Tag: noindex vía
  public/_headers (se genera siempre que el target incluya netlify).
- PRODUCCIÓN = Plesk/Ubuntu, nginx como proxy + Apache detrás, así que .htaccess
  SÍ se aplica. public/.htaccess se copia a dist/ tal cual porque Astro copia public/
  a la raíz de la build.

Reglas comunes a ambos entornos (ver también references/seo-estandar.md):
- URL que existe en la nueva build con la misma ruta: nada que hacer.
- URL en --map: 301 a la nueva. Se resuelven cadenas (A→B, B→C ⇒ A→C).
- URL en --gone o marcada spam_suspect en el inventario: 410.
- URL del inventario que NO existe en la nueva build y no está en map/gone: PENDIENTE
  en la salida para que el usuario decida. No se inventa un destino.
- Redirecciones antiguas (--legacy) se conservan, re-apuntadas si su destino también cambió.
- Medios (--media): por cada entrada de media.json se busca el archivo equivalente en dist/ o
  public/ (mismo nombre de archivo, sin el sufijo de tamaño "-300x200" ni la extensión, aceptando
  también .webp/.avif); si existe -> 301, si no -> 410. Incluye imágenes, PDF, DOCX, XLSX, ZIP y MP4.
- Sin cadenas: todo A→B→C se reescribe como A→C antes de escribir cualquier archivo.

Solo en Apache (.htaccess), porque Netlify _redirects no soporta reglas de mod_rewrite
tan finas ni cabeceras condicionales por carpeta:
- Forzar https y host sin/con www (según --domain y CLAUDE.md) con un único 301 (sin encadenar).
- Parámetros clásicos de WordPress con RewriteCond %{QUERY_STRING}: ?p=/?page_id= (por wp_id,
  ver extract_wp.py) al post real; ?s=, ?replytocom=, ?feed= a la ruta limpia.
- 410 para /wp-admin, /wp-login.php, /xmlrpc.php.
- ErrorDocument 404/410, DirectorySlash On.
- Cabeceras (mod_headers): Cache-Control immutable en /_astro/ (public/_astro/.htaccess propio,
  porque <Location> no está permitido dentro de un .htaccess de raíz), cache moderada en
  imágenes sueltas, no-cache en HTML, cabeceras de seguridad básicas + HSTS.
"""
import argparse, csv, json, os, re, sys
from urllib.parse import urlparse

# Se importa para reutilizar exactamente la misma clasificación de rutas "de sistema"
# de WordPress que usa el contrato de URLs (build_contract.py), sin duplicar los patrones.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_contract as bc  # noqa: E402

SUFIJO_TAMANO = re.compile(r"-\d+x\d+$")
EXT_IMAGEN = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".avif", ".svg")
# Además de imágenes: documentos y vídeo que WordPress también sirve desde /wp-content/uploads/.
EXT_MEDIA = EXT_IMAGEN + (".pdf", ".docx", ".xlsx", ".zip", ".mp4")


def path_of(u):
    p = urlparse(u).path or "/"
    return p


# Variantes de tamaño/edición que WordPress añade al nombre de archivo: "-300x200"
# (thumbnail), "-scaled" (versión reducida automática) y "-eNNNNNNNNNN" (imagen
# editada en el editor de medios). Se despojan repetidamente porque WP puede
# encadenarlas (p.ej. "foto-scaled-150x150.jpg").
SUFIJO_VARIANTE = re.compile(r"(-\d+x\d+|-scaled|-e\d{9,})$", re.I)


def nombre_base(ruta_o_url):
    """Nombre de archivo sin variantes de tamaño/edición de WP ni extensión, en
    minúsculas: la comparación entre el nombre viejo y el de la build nueva es
    case-insensitive (Astro/el equipo puede renombrar a minúsculas), aunque el
    destino que se escribe en la regla conserva las mayúsculas reales del archivo
    (Apache sí distingue mayúsculas al servirlo)."""
    nombre = os.path.basename(urlparse(ruta_o_url).path if "://" in ruta_o_url else ruta_o_url)
    nombre, _ext = os.path.splitext(nombre)
    anterior = None
    while anterior != nombre:
        anterior = nombre
        nombre = SUFIJO_VARIANTE.sub("", nombre)
    return nombre.lower()


def indice_medios_build(dirs):
    """Indexa los medios de dist/ y public/ por su nombre base (minúsculas), para casar con media.json."""
    idx = {}
    for d in dirs:
        if not d or not os.path.isdir(d):
            continue
        for root, _dirs, files in os.walk(d):
            for f in files:
                if not f.lower().endswith(EXT_MEDIA):
                    continue
                bn = nombre_base(f)
                rel = "/" + os.path.relpath(os.path.join(root, f), d).replace(os.sep, "/")
                idx.setdefault(bn, rel)
    return idx


def redirecciones_medios(media_fn, dirs, contrato_mantener=frozenset(), ahrefs=None):
    """Genera las parejas 301/410 para los medios de media.json (imágenes, PDF, DOCX, XLSX, ZIP, MP4).

    Orden de resolución para una variante de tamaño/edición (-300x200, -scaled, -eNNN):
    1) si la imagen principal (mismo nombre sin la variante) existe en la build nueva -> 301 a ella.
    2) si no existe pero el medio se usaba (`usada_en`) en una página que el contrato mantiene -> 301 a esa página.
    3) si no existe pero tiene backlinks reales (--ahrefs) -> 301 a esa página o, si no hay ninguna, a la portada.
    4) si no hay nada de lo anterior -> 410 (nunca se inventa un destino).
    Deduplica por ruta de origen (media.json puede repetir la misma URL si vino de
    varias fuentes)."""
    if not media_fn or not os.path.exists(media_fn):
        return [], [], 0, 0
    media = json.load(open(media_fn, encoding="utf-8"))
    idx = indice_medios_build(dirs)
    ahrefs = ahrefs or {}
    r301, r410, vistos = [], [], set()
    for entrada in media:
        url_vieja = entrada.get("source_url") or entrada.get("url")
        if not url_vieja:
            continue
        origen = path_of(url_vieja)
        if origen in vistos:
            continue
        vistos.add(origen)
        bn = nombre_base(url_vieja)
        destino = idx.get(bn)
        if destino and destino != origen:
            r301.append((origen, destino))
            continue
        if destino:
            continue  # destino == origen: ya está en su sitio, nada que hacer
        # Sin imagen principal en la build: ¿se usaba en una página que se mantiene?
        pagina_destino = next((path_of(p) for p in (entrada.get("usada_en") or [])
                                if path_of(p) in contrato_mantener), None)
        if pagina_destino:
            r301.append((origen, pagina_destino))
            continue
        # ¿Tiene backlinks reales? Nunca se manda a 410 un medio con enlaces entrantes
        # sin que quede constancia; a falta de una página de uso concreta, a la portada.
        backlinks = (ahrefs.get(url_vieja) or {}).get("backlinks", 0)
        try:
            tiene_backlinks = float(backlinks) > 0
        except (TypeError, ValueError):
            tiene_backlinks = False
        if tiene_backlinks:
            r301.append((origen, "/"))
            continue
        r410.append(origen)
    return r301, r410, len(r301), len(r410)


def route_exists(dist, path):
    p = path.strip("/")
    cands = [os.path.join(dist, p, "index.html"), os.path.join(dist, p + ".html"),
             os.path.join(dist, p)] if p else [os.path.join(dist, "index.html")]
    return any(os.path.isfile(c) for c in cands)


def read_pairs(fn):
    pairs = {}
    if not fn:
        return pairs
    with open(fn, newline="", encoding="utf-8") as f:
        for row in csv.reader(f):
            if len(row) >= 2 and row[0].strip() and not row[0].startswith("#"):
                pairs[path_of(row[0].strip())] = path_of(row[1].strip()) if "://" in row[1] else row[1].strip()
    return pairs


def resolve(pairs, gone=frozenset()):
    """Sigue la cadena A->B->C... hasta el final (sin cadenas: A->B->C se reescribe
    como A->C). Si el destino final cae en `gone`, la redirección se devuelve como
    ('410', None) en vez de un 301 que a su vez sería 410: ninguna redirección
    generada puede apuntar a una URL que es 410 o que a su vez redirige a otra parte
    sin resolver también ese salto."""
    out = {}
    for src in pairs:
        dst, seen = pairs[src], {src}
        while dst in pairs and dst not in seen:
            seen.add(dst)
            dst = pairs[dst]
        out[src] = ("410", None) if dst in gone else ("301", dst)
    return out


def leer_contrato(fn):
    """migracion/urls.csv (build_contract.py): path -> fila (decision, destino, ...).
    Se usa para resolver el estado final real de una URL (410/301/mantener) más allá
    de --gone/--map, y para el fallback de miniaturas sin imagen principal."""
    filas = {}
    if not fn or not os.path.exists(fn):
        return filas
    with open(fn, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("url"):
                filas[path_of(row["url"])] = row
    return filas


# ---------------------------------------------------------------------------
# CLAUDE.md: lee el dominio canónico y las preferencias de www/barra final si no
# se han pasado por flag, para no tener que repetirlas a mano en cada comando.
# ---------------------------------------------------------------------------
def leer_claude_md(fn):
    datos = {}
    if not fn or not os.path.exists(fn):
        return datos
    texto = open(fn, encoding="utf-8").read()
    m = re.search(r"Dominio canónico:\s*`https?://([^/`]+)/?`\s*\(([^,]+),\s*barra final:\s*([^)]+)\)", texto)
    if m:
        datos["domain"] = m.group(1).replace("www.", "")
        datos["con_www"] = "con www" in m.group(2).lower()
        datos["barra_final"] = "sin" not in m.group(3).lower()
    return datos


# ---------------------------------------------------------------------------
# Modelo común de redirecciones (compartido por Netlify, Apache y nginx)
# ---------------------------------------------------------------------------
def construir_modelo(inv, new_routes, mapping, legacy, gone_extra, media_fn, public_dir,
                      contrato=None, ahrefs=None):
    contrato = contrato or {}
    # El contrato (urls.csv) es la fuente de verdad de qué URL es 410/301/mantener
    # más allá de --gone/--map: sin esto, una regla podía apuntar a una URL que el
    # contrato ya había decidido 410 (p.ej. ?p=220 -> /blog/consultoria/, que es 410).
    contract_301 = {p: row["destino"] for p, row in contrato.items()
                     if row.get("decision") == "301" and row.get("destino")}
    contract_410 = {p for p, row in contrato.items() if row.get("decision") == "410"}
    contract_mantener = {p for p, row in contrato.items() if row.get("decision") == "mantener"}

    gone = set(gone_extra) | contract_410
    gone |= {path_of(i["url"]) for i in inv["items"] if i.get("spam_suspect")}

    # Los pares explícitos (--map/--legacy) pisan al contrato si coinciden (son la
    # decisión más reciente/manual del usuario); todo se resuelve junto para que las
    # cadenas A->B->C, vengan de donde vengan, se colapsen en un único salto.
    pares_crudos = {**contract_301, **legacy, **mapping}
    resueltos = resolve(pares_crudos, gone)

    r301, pending = [], []
    for src, (kind, dst) in sorted(resueltos.items()):
        if kind == "410":
            gone.add(src)
            continue
        if src in gone or src == dst:
            continue
        if not route_exists(new_routes, dst) and not dst.startswith("http"):
            pending.append(f"{src} -> {dst} (destino no existe en la build)")
            continue
        r301.append((src, dst))
    for it in inv["items"]:
        p = path_of(it["url"])
        if p in gone or p in pares_crudos:
            continue
        if not route_exists(new_routes, p):
            pending.append(f"{p} (existía, no está en la nueva build y no tiene destino)")

    media_301, media_410, n_media_301, n_media_410 = redirecciones_medios(
        media_fn, [new_routes, public_dir], contrato_mantener=contract_mantener, ahrefs=ahrefs)

    # wp_id -> (estado, destino) para las reglas ?p=/?page_id= en Apache/nginx/_redirects.
    # Resuelto exactamente igual que el resto: nunca apunta a una URL que a su vez sea
    # 410 o que redirija de nuevo sin colapsar (misma garantía "sin cadenas").
    wp_id_dest = {}
    for it in inv["items"]:
        wid = it.get("wp_id")
        if wid is None:
            continue
        p = path_of(it["url"])
        if p in gone:
            wp_id_dest[str(wid)] = ("410", None)
        elif p in resueltos:
            wp_id_dest[str(wid)] = resueltos[p]
        else:
            wp_id_dest[str(wid)] = ("301", p)

    return {
        "gone": sorted(gone), "r301": r301, "pending": pending,
        "media_301": media_301, "media_410": media_410,
        "n_media_301": n_media_301, "n_media_410": n_media_410,
        "wp_id_dest": wp_id_dest,
    }


# ---------------------------------------------------------------------------
# Netlify (_redirects + _headers)
# ---------------------------------------------------------------------------
def reglas_query_wp_netlify(wp_id_dest):
    """Query strings clásicas de WordPress en sintaxis _redirects. Las reglas por
    wp_id van primero (resueltas sin cadenas, igual que en Apache: si el post es 410
    o redirige a otro sitio, la regla de query lo refleja directamente) y el genérico
    p=:id/s=:q/replytocom al final, como red de seguridad para IDs no vistos."""
    lines = ["# Query strings clásicas de WordPress (?p=, ?s=, ?replytocom=)"]
    for wid, (kind, dest) in sorted(wp_id_dest.items(), key=lambda kv: int(kv[0])):
        if kind == "410":
            lines.append(f"/  p={wid}  /410.html  410")
            lines.append(f"/  page_id={wid}  /410.html  410")
        else:
            lines.append(f"/  p={wid}  {dest}  301")
            lines.append(f"/  page_id={wid}  {dest}  301")
    lines += [
        "/  p=:id  /  301",
        "/  s=:q  /  301",
        "/*  replytocom=:rc  /:splat  301",
    ]
    return lines


def escribir_netlify(modelo, out_fn, headers_fn):
    lines = ["# Generado por build_redirects.py · no editar a mano, edita url-map.csv / gone.txt"]
    for src in modelo["gone"]:
        lines.append(f"{src}  /410.html  410")
    for src, dst in modelo["r301"]:
        lines.append(f"{src}  {dst}  301!")
    if modelo["media_301"] or modelo["media_410"]:
        lines.append("# Medios (imágenes, PDF, DOCX, XLSX, ZIP, MP4 de /wp-content/uploads/, ver media.json)")
        for src, dst in modelo["media_301"]:
            lines.append(f"{src}  {dst}  301!")
        for src in modelo["media_410"]:
            lines.append(f"{src}  /410.html  410")
    lines.extend(reglas_query_wp_netlify(modelo["wp_id_dest"]))
    os.makedirs(os.path.dirname(out_fn) or ".", exist_ok=True)
    open(out_fn, "w", encoding="utf-8").write("\n".join(lines) + "\n")

    # public/_headers: la preview de Netlify NO se indexa nunca (ver references/netlify-preview.md).
    os.makedirs(os.path.dirname(headers_fn) or ".", exist_ok=True)
    open(headers_fn, "w", encoding="utf-8").write(
        "# Generado por build_redirects.py · preview Netlify: nunca se indexa\n"
        "/*\n  X-Robots-Tag: noindex\n"
    )
    return len(modelo["gone"]), len(modelo["r301"]) + modelo["n_media_301"], modelo["n_media_410"]


# ---------------------------------------------------------------------------
# Apache (.htaccess de producción en Plesk)
# ---------------------------------------------------------------------------
def escribir_apache(inv, modelo, domain, con_www, barra_final, sin_rss, out_fn):
    host_line = f"www.{domain}" if con_www else domain
    otro_host = domain if con_www else f"www.{domain}"

    L = []
    L.append("# Generado por build_redirects.py · no editar a mano, edita url-map.csv / gone.txt")
    L.append("# Producción Plesk (nginx como proxy + Apache) — ver references/plesk-produccion.md")
    L.append("")
    L.append("RewriteEngine On")
    L.append("")
    L.append("# 1) Forzar https y el host canónico (con/sin www) en un único salto, sin cadenas")
    L.append("RewriteCond %{HTTPS} off [OR]")
    L.append(f"RewriteCond %{{HTTP_HOST}} ^{re.escape(otro_host)}$ [NC]")
    L.append(f"RewriteRule ^ https://{host_line}%{{REQUEST_URI}} [L,R=301]")
    L.append("")
    L.append("# 2) Bloqueo de rutas de administración de WordPress (ya no existen en esta web)")
    L.append("RewriteRule ^wp-admin(/.*)?$ - [G,L]")
    L.append("RewriteRule ^wp-login\\.php$ - [G,L]")
    L.append("RewriteRule ^xmlrpc\\.php$ - [G,L]")
    L.append("")

    # 3) Parámetros clásicos de WordPress (RewriteCond %{QUERY_STRING})
    L.append("# 3) Parámetros clásicos de WordPress")
    wp_id_dest = modelo["wp_id_dest"]
    if wp_id_dest:
        L.append("# ?p=ID / ?page_id=ID -> URL real del post/página (por wp_id, ver extract_wp.py).")
        L.append("# Resuelto sin cadenas: si el post es 410 o su URL redirige a otra parte, la regla")
        L.append("# de query lo refleja directamente (nunca a un destino que a su vez es 410/301).")
        L.append("# QSD descarta la query completa: si el enlace llevaba también UTM, se pierde aquí;")
        L.append("# es la contrapartida aceptada por conservar una URL de destino limpia.")
        for wid, (kind, dest) in sorted(wp_id_dest.items(), key=lambda kv: int(kv[0])):
            L.append(f"RewriteCond %{{QUERY_STRING}} (^|&)(p|page_id)={wid}(&|$)")
            if kind == "410":
                L.append("RewriteRule ^ - [G,L]")
            else:
                L.append(f"RewriteRule ^ {dest} [R=301,L,QSD]")
    L.append("# Búsqueda interna, comentarios y feed en query string: a la ruta limpia (QSD)")
    L.append("RewriteCond %{QUERY_STRING} (^|&)s=([^&]*)")
    L.append("RewriteRule ^ / [R=301,L,QSD]")
    L.append("RewriteCond %{QUERY_STRING} (^|&)replytocom=([^&]*)")
    L.append("RewriteRule ^ %{REQUEST_URI} [R=301,L,QSD]")
    L.append("RewriteCond %{QUERY_STRING} (^|&)feed=([^&]*)")
    if sin_rss:
        L.append("RewriteRule ^ - [G,L]")
    else:
        L.append("RewriteRule ^ /rss.xml [R=301,L,QSD]")
    L.append("")

    # 4) Rutas "de sistema" basadas en la ruta (no en query string): /page/N/, feed/, category/tag/author
    L.append("# 4) Rutas de sistema de WordPress (ver references/seo-estandar.md, sección E-bis)")
    for it in inv["items"]:
        if it.get("tipo") != "sistema":
            continue
        path = path_of(it["url"])
        if bc.SISTEMA_PAGE.search(path):
            raiz = re.sub(r"/page/\d+/?$", "/", path) or "/"
            ruta_re = re.escape(path.lstrip("/"))
            L.append(f"RewriteRule ^{ruta_re}$ {raiz} [R=301,L]")
        elif bc.SISTEMA_FEED.search(path):
            ruta_re = re.escape(path.lstrip("/"))
            if sin_rss:
                L.append(f"RewriteRule ^{ruta_re}$ - [G,L]")
            else:
                L.append(f"RewriteRule ^{ruta_re}$ /rss.xml [R=301,L]")
        elif bc.SISTEMA_TAXO.search(path):
            ruta_re = re.escape(path.lstrip("/"))
            L.append(f"RewriteRule ^{ruta_re}$ /blog/ [R=301,L]")
        elif bc.SISTEMA_BLOQUEO.search(path):
            pass  # ya cubierto por el bloqueo genérico de wp-admin/wp-login/xmlrpc arriba
    L.append("")

    # 5) 410 explícitos (spam, contenido eliminado)
    if modelo["gone"]:
        L.append("# 5) Contenido eliminado o spam -> 410 (nunca 301 a portada, ver seo-estandar.md)")
        for src in modelo["gone"]:
            ruta_re = re.escape(src.lstrip("/"))
            if src.rstrip("/") == "":
                L.append("RewriteRule ^$ - [G,L]")
            else:
                L.append(f"RewriteRule ^{ruta_re}/?$ - [G,L]")
        L.append("")

    # 6) 301 página a página
    if modelo["r301"]:
        L.append("# 6) 301 página a página (url-map.csv / redirects-export.csv), sin cadenas")
        for src, dst in modelo["r301"]:
            if src.strip("/") == "":
                L.append(f"RewriteRule ^$ {dst} [R=301,L]")
                continue
            ruta_re = re.escape(src.strip("/"))
            L.append(f"RewriteRule ^{ruta_re}/?$ {dst} [R=301,L]")
        L.append("")

    # 7) Medios: imágenes, PDF, DOCX, XLSX, ZIP, MP4
    if modelo["media_301"] or modelo["media_410"]:
        L.append("# 7) Medios de /wp-content/uploads/ (imágenes, PDF, DOCX, XLSX, ZIP, MP4)")
        for src, dst in modelo["media_301"]:
            ruta_re = re.escape(src.lstrip("/"))
            L.append(f"RewriteRule ^{ruta_re}$ {dst} [R=301,L]")
        for src in modelo["media_410"]:
            ruta_re = re.escape(src.lstrip("/"))
            L.append(f"RewriteRule ^{ruta_re}$ - [G,L]")
        L.append("")

    # 8) Barra final, páginas de error, directorios
    L.append("# 8) Barra final y páginas de error")
    L.append("DirectorySlash On")
    L.append("ErrorDocument 404 /404.html")
    L.append("ErrorDocument 410 /410.html")
    L.append("")

    # 9) Cabeceras (mod_headers): seguridad + cache. El cache immutable de /_astro/ vive en su
    #    propio public/_astro/.htaccess porque <Location>/<LocationMatch> no están permitidos aquí.
    L.append("# 9) Cabeceras")
    L.append("<IfModule mod_headers.c>")
    L.append('  Header always set X-Content-Type-Options "nosniff"')
    L.append('  Header always set Referrer-Policy "strict-origin-when-cross-origin"')
    L.append('  Header always set X-Frame-Options "SAMEORIGIN"')
    L.append('  Header always set Strict-Transport-Security "max-age=31536000; includeSubDomains"')
    L.append("</IfModule>")
    L.append("<FilesMatch \"\\.(html?)$\">")
    L.append("  <IfModule mod_headers.c>")
    L.append('    Header set Cache-Control "no-cache, must-revalidate"')
    L.append("  </IfModule>")
    L.append("</FilesMatch>")
    L.append("<FilesMatch \"\\.(jpe?g|png|gif|webp|avif|svg)$\">")
    L.append("  <IfModule mod_headers.c>")
    L.append('    Header set Cache-Control "public, max-age=604800"')
    L.append("  </IfModule>")
    L.append("</FilesMatch>")
    L.append("")

    os.makedirs(os.path.dirname(out_fn) or ".", exist_ok=True)
    open(out_fn, "w", encoding="utf-8").write("\n".join(L) + "\n")

    # public/_astro/.htaccess: cache immutable de 1 año solo para los assets con hash de Astro.
    astro_dir = os.path.join(os.path.dirname(out_fn) or ".", "_astro")
    os.makedirs(astro_dir, exist_ok=True)
    open(os.path.join(astro_dir, ".htaccess"), "w", encoding="utf-8").write(
        "# Generado por build_redirects.py · cache larga solo para assets con hash (Astro los\n"
        "# renombra si cambian, así que 1 año + immutable es seguro)\n"
        "<IfModule mod_headers.c>\n"
        '  Header set Cache-Control "public, max-age=31536000, immutable"\n'
        "</IfModule>\n"
    )
    return len(modelo["gone"]), len(modelo["r301"]) + modelo["n_media_301"] + len(wp_id_dest), modelo["n_media_410"]


# ---------------------------------------------------------------------------
# nginx (alternativa si Plesk solo tiene nginx, sin Apache detrás — ver plesk-produccion.md)
# ---------------------------------------------------------------------------
def escribir_nginx(modelo, domain, con_www, out_fn):
    host_line = f"www.{domain}" if con_www else domain
    otro_host = domain if con_www else f"www.{domain}"
    L = []
    L.append("# Generado por build_redirects.py · pegar en Plesk > Apache & nginx > Additional nginx directives")
    L.append("# Alternativa SOLO si el dominio no tiene Apache detrás (ver references/plesk-produccion.md).")
    L.append("# Estas directivas cubren host/https y redirecciones de ruta + cabeceras; NO reproducen las")
    L.append("# reglas de query string (?p=, ?s=...) del .htaccess: si el sitio depende de ellas, usa Apache.")
    L.append("")
    L.append(f'if ($host = "{otro_host}") {{ return 301 https://{host_line}$request_uri; }}')
    L.append('if ($scheme != "https") { return 301 https://$host$request_uri; }')
    L.append("")
    L.append("location = /wp-login.php { return 410; }")
    L.append("location = /xmlrpc.php { return 410; }")
    L.append("location ^~ /wp-admin/ { return 410; }")
    L.append("")
    for src in modelo["gone"]:
        L.append(f"location = {src} {{ return 410; }}")
    for src, dst in modelo["r301"] + modelo["media_301"]:
        L.append(f"location = {src} {{ return 301 {dst}; }}")
    for src in modelo["media_410"]:
        L.append(f"location = {src} {{ return 410; }}")
    L.append("")
    L.append("location ~* \\.(html?)$ { add_header Cache-Control \"no-cache, must-revalidate\" always; }")
    L.append("location ~* \\.(jpe?g|png|gif|webp|avif|svg)$ { add_header Cache-Control \"public, max-age=604800\" always; }")
    L.append("location ^~ /_astro/ { add_header Cache-Control \"public, max-age=31536000, immutable\" always; }")
    L.append("add_header X-Content-Type-Options nosniff always;")
    L.append("add_header Referrer-Policy \"strict-origin-when-cross-origin\" always;")
    L.append("add_header X-Frame-Options SAMEORIGIN always;")
    os.makedirs(os.path.dirname(out_fn) or ".", exist_ok=True)
    open(out_fn, "w", encoding="utf-8").write("\n".join(L) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("inventory")
    ap.add_argument("--new-routes", required=True)
    ap.add_argument("--target", choices=["netlify", "apache", "nginx", "both"], default="both",
                     help="netlify (preview), apache (producción Plesk), nginx (alternativa sin Apache) o both (netlify+apache, por defecto)")
    ap.add_argument("--domain", help="dominio canónico (sin www, sin esquema). Si falta, se lee de CLAUDE.md")
    ap.add_argument("--claude-md", default="CLAUDE.md", help="ruta a CLAUDE.md para leer el dominio canónico (por defecto ./CLAUDE.md)")
    ap.add_argument("--con-www", action="store_true", help="el dominio canónico lleva www (por defecto: sin www)")
    ap.add_argument("--map")
    ap.add_argument("--gone")
    ap.add_argument("--legacy")
    ap.add_argument("--media", help="migracion/media.json: genera 301/410 de medios")
    ap.add_argument("--public", default="public", help="carpeta public/ donde también buscar medios (además de --new-routes)")
    ap.add_argument("--out", default="public/_redirects", help="salida Netlify (_redirects)")
    ap.add_argument("--headers-out", default="public/_headers", help="salida Netlify (_headers, noindex de la preview)")
    ap.add_argument("--out-htaccess", default="public/.htaccess", help="salida Apache (producción Plesk)")
    ap.add_argument("--out-nginx", default="nginx-directivas.conf", help="salida nginx (solo con --target nginx)")
    ap.add_argument("--sin-rss", action="store_true", help="sin feed RSS en la nueva web: /feed/ y ?feed= -> 410 en vez de 301 a /rss.xml")
    ap.add_argument("--contract", help="migracion/urls.csv (build_contract.py): resuelve el estado final real "
                                        "(410/301/mantener) para que ninguna regla generada apunte a una URL "
                                        "que a su vez es 410 o redirige, y da el fallback de miniaturas sin imagen principal")
    ap.add_argument("--ahrefs", help="migracion/ahrefs.json {url: {backlinks, trafico}}: si un medio sin imagen "
                                      "principal en la build tiene backlinks reales, se redirige en vez de 410")
    a = ap.parse_args()

    inv = json.load(open(a.inventory))
    mapping = read_pairs(a.map)
    legacy = read_pairs(a.legacy)
    gone_extra = {path_of(l.strip()) for l in open(a.gone)} if a.gone and os.path.exists(a.gone) else set()
    contrato = leer_contrato(a.contract)
    ahrefs = json.load(open(a.ahrefs, encoding="utf-8")) if a.ahrefs and os.path.exists(a.ahrefs) else {}

    modelo = construir_modelo(inv, a.new_routes, mapping, legacy, gone_extra, a.media, a.public,
                               contrato=contrato, ahrefs=ahrefs)

    quiere_apache = a.target in ("apache", "both")
    quiere_netlify = a.target in ("netlify", "both")
    quiere_nginx = a.target == "nginx"

    if quiere_apache or quiere_nginx:
        claude_md = leer_claude_md(a.claude_md)
        domain = a.domain or claude_md.get("domain")
        if not domain:
            ap.error("Falta --domain (y no se pudo leer 'Dominio canónico' de CLAUDE.md). "
                     "Necesario para las reglas de host/https de Apache/nginx.")
        con_www = a.con_www or claude_md.get("con_www", False)

    if quiere_netlify:
        n_gone, n_301, n_410 = escribir_netlify(modelo, a.out, a.headers_out)
        print(f"{a.out}: {n_gone} respuestas 410, {n_301} redirecciones 301 (netlify) · {a.headers_out}: noindex")

    if quiere_apache:
        n_gone, n_301, n_410 = escribir_apache(inv, modelo, domain, con_www, False, a.sin_rss, a.out_htaccess)
        astro_htaccess = os.path.join(os.path.dirname(a.out_htaccess) or ".", "_astro", ".htaccess")
        print(f"{a.out_htaccess}: {n_gone} respuestas 410, {n_301} redirecciones 301 (apache) · {astro_htaccess}: cache immutable")

    if quiere_nginx:
        escribir_nginx(modelo, domain, con_www, a.out_nginx)
        print(f"{a.out_nginx}: generado (revísalo antes de pegarlo en Plesk)")

    if modelo["pending"]:
        print(f"\n⚠️  {len(modelo['pending'])} URLs PENDIENTES de decisión (añádelas a url-map.csv o gone.txt):")
        print("\n".join("  " + p for p in modelo["pending"]))
        sys.exit(2)


if __name__ == "__main__":
    main()
