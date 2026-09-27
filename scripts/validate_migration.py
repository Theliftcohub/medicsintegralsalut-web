#!/usr/bin/env python3
"""
Valida la web nueva contra el inventario de la antigua. Es la puerta antes de lanzar.

Uso:
  python3 validate_migration.py migracion/inventory.json --base https://preview--x.netlify.app \
      [--no-literal NO_LITERAL.md] [--old-domain cadena-logistica.com] [--i18n migracion/i18n-map.json] \
      [--contract migracion/urls.csv] [--media migracion/media.json] [--media-sample 20] \
      [--report migracion/informe.html] [--lighthouse migracion/lh.json] [--production]
  python3 validate_migration.py --links-only dist/     # solo enlaces internos (para CI)

Comprueba por URL: código esperado (200 / 301 / 410), title y description literales
(salvo excepciones registradas en NO_LITERAL.md), canonical, robots, H1, schema, restos de WordPress,
imágenes del dominio antiguo, y opcionalmente hreflang recíprocos. Devuelve código 1 si hay FAIL.

Añade:
  1) Muestreo de --media-sample URLs de media.json: cada una debe responder 301 o 410, nunca 404.
  2) Diff de tipos de schema (@type) entre el inventario y el HTML nuevo (WARN, salvo whitelist
     SCHEMA_PERDIDA_OK); BlogPosting sin author o sin datePublished -> FAIL.
  3) Referencias propias rotas: todo href/src/content del <head> y del <body> que apunte al
     dominio final o sea ruta relativa se comprueba contra --base; 404 -> FAIL.
  4) Las URLs tipo "sistema" del inventario se validan contra --contract (urls.csv) igual que el resto.
  5) --report informe.html: informe HTML autocontenido (sin dependencias externas) con KPIs, tabla
     FAIL/WARN/PASS, diff de schema y bloque de Lighthouse si se pasa --lighthouse.
"""
import argparse, base64, csv, html, json, os, random, re, sys, urllib.request, urllib.error
from urllib.parse import urlparse, urljoin

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from crawl_lib import crawl_grafo  # noqa: E402  (compartida con extract_wp.py)
import extract_wp as ew  # noqa: E402  (reutiliza detectar_tracking/detectar_formularios)

UA = {"User-Agent": "Mozilla/5.0 (TheLiftCo migration validator)"}
LEFTOVERS = re.compile(r"wp-content|wp-includes|elementor-|fusion-builder|\[/?(vc_|et_pb|fusion_)|wp-json", re.I)
REF_ATTR_RE = re.compile(r'\b(?:href|src|content)="([^"]+)"', re.I)
JSONLD_RE = re.compile(r'(?is)<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>')

# Autenticación básica para staging protegido con contraseña (Plesk "Password-protected
# directories"). Se lee de --auth o, preferiblemente, de la variable de entorno VALIDATOR_AUTH
# (user:pass) para que la contraseña nunca quede en el historial de la shell ni en logs de CI.
AUTH_HEADERS = {}


def configurar_auth(valor_cli):
    cred = valor_cli or os.environ.get("VALIDATOR_AUTH")
    if not cred:
        return
    if ":" not in cred:
        print("⚠️  --auth / VALIDATOR_AUTH debe tener el formato user:pass; se ignora.")
        return
    token = base64.b64encode(cred.encode("utf-8")).decode("ascii")
    AUTH_HEADERS["Authorization"] = f"Basic {token}"

# Tipos de schema cuya desaparición NO genera WARN (ver references/validate y schema-por-negocio.md).
# "Article" solo se acepta perdido en páginas que NO eran un post (en un post, Article/BlogPosting
# debe conservarse). "Person" solo se acepta perdido si el original no tenía un autor real asignado.
# "SearchAction" no es un @type propio, pero WebSite.potentialAction desaparece a
# veces junto con el tipo; se deja aquí documentado que el sitelinks search box
# está retirado (Google, nov. 2024) y su ausencia nunca debe contar como pérdida.
SCHEMA_PERDIDA_OK_SIMPLES = {"AggregateRating", "SiteNavigationElement"}


def get(url, metodo="GET"):
    req = urllib.request.Request(url, headers={**UA, **AUTH_HEADERS}, method=metodo)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            cuerpo = r.read().decode("utf-8", "ignore") if metodo == "GET" else ""
            return r.status, cuerpo, r.headers
    except urllib.error.HTTPError as e:
        return e.code, "", e.headers
    except Exception as e:
        return 0, str(e), {}


def head_noredirect(url):
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):
            return None
    op = urllib.request.build_opener(NoRedirect)
    req = urllib.request.Request(url, headers={**UA, **AUTH_HEADERS}, method="HEAD")
    try:
        with op.open(req, timeout=30) as r:
            return r.status, r.headers.get("Location", "")
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Location", "")
    except Exception:
        return 0, ""


def m(h, pat):
    r = re.search(pat, h, re.I | re.S)
    return html.unescape(r.group(1).strip()) if r else ""


def norm(s):
    return re.sub(r"\s+", " ", (s or "")).strip().lower()


def load_no_literal(fn):
    ok = set()
    if fn and os.path.exists(fn):
        for line in open(fn, encoding="utf-8"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) >= 2 and cells[0].startswith(("http", "/")):
                ok.add((urlparse(cells[0]).path, cells[1].lower()))
    return ok


def links_only(dist):
    routes, fails = set(), []
    for root, _, files in os.walk(dist):
        for f in files:
            if f.endswith(".html"):
                rel = os.path.relpath(os.path.join(root, f), dist)
                routes.add("/" + rel.replace("index.html", "").replace(".html", ""))
    routes = {r if r.endswith("/") or "." in r.split("/")[-1] else r + "/" for r in routes} | {"/"}
    for root, _, files in os.walk(dist):
        for f in files:
            if not f.endswith(".html"):
                continue
            h = open(os.path.join(root, f), encoding="utf-8", errors="ignore").read()
            for href in re.findall(r'href="(/[^"#?]*)', h):
                t = href if href.endswith("/") or "." in href.split("/")[-1] else href + "/"
                if t not in routes and not os.path.exists(os.path.join(dist, href.lstrip("/"))):
                    fails.append(f"{os.path.relpath(os.path.join(root,f),dist)} -> {href}")
    print(f"{len(routes)} rutas, {len(fails)} enlaces internos rotos")
    print("\n".join("  " + x for x in fails[:200]))
    return 1 if fails else 0


# ---------------------------------------------------------------------------
# (2) Diff de schema: parsea los bloques JSON-LD del HTML nuevo (resolviendo @graph)
# ---------------------------------------------------------------------------
def parse_jsonld_objetos(h):
    objetos = []
    for bloque in JSONLD_RE.findall(h or ""):
        try:
            data = json.loads(bloque.strip())
        except json.JSONDecodeError:
            continue
        candidatos = data if isinstance(data, list) else [data]
        for c in candidatos:
            if not isinstance(c, dict):
                continue
            if isinstance(c.get("@graph"), list):
                objetos.extend(g for g in c["@graph"] if isinstance(g, dict))
            else:
                objetos.append(c)
    return objetos


def tipos_de(objetos):
    tipos = set()
    for o in objetos:
        t = o.get("@type")
        if isinstance(t, list):
            tipos.update(x for x in t if isinstance(x, str))
        elif isinstance(t, str):
            tipos.add(t)
    return tipos


def perdida_aceptable(tipo, it):
    if tipo in SCHEMA_PERDIDA_OK_SIMPLES:
        return True
    if tipo == "Article":
        return it.get("type") != "post"
    if tipo == "Person":
        return not it.get("author")
    return False


# ---------------------------------------------------------------------------
# (3) Referencias propias rotas (href/src/content al dominio final o relativas)
# ---------------------------------------------------------------------------
def referencias_propias(h, url, base_netloc):
    refs = []
    for v in REF_ATTR_RE.findall(h or ""):
        v = v.strip()
        if not v or v.startswith(("mailto:", "tel:", "javascript:", "data:", "#")):
            continue
        if v.startswith("http://") or v.startswith("https://"):
            neto = urlparse(v).netloc.replace("www.", "")
            if neto != base_netloc.replace("www.", ""):
                continue
            refs.append(urlparse(v).path or "/")
        elif v.startswith("/"):
            refs.append(v.split("#")[0].split("?")[0])
        elif not re.match(r"^[a-zA-Z][a-zA-Z0-9+.\-]*:", v):
            full = urljoin(url, v)
            if urlparse(full).netloc.replace("www.", "") == base_netloc.replace("www.", ""):
                refs.append(urlparse(full).path.split("#")[0].split("?")[0] or "/")
    return refs


# ---------------------------------------------------------------------------
# (1) Muestreo de medios
# ---------------------------------------------------------------------------
def validar_medios(media_fn, base, muestra):
    if not media_fn or not os.path.exists(media_fn):
        return [], 0
    media = json.load(open(media_fn, encoding="utf-8"))
    random.seed(42)  # muestreo reproducible entre corridas
    elegidos = random.sample(media, min(muestra, len(media))) if media else []
    fails, verificados = [], 0
    for entrada in elegidos:
        u = entrada.get("source_url") or entrada.get("url")
        if not u:
            continue
        path = urlparse(u).path
        code, _loc = head_noredirect(base + path)
        verificados += 1
        if code == 404:
            fails.append((path, ["medio responde 404 (debe ser 301 o 410, nunca 404)"]))
        elif code not in (301, 308, 410):
            fails.append((path, [f"medio responde {code} (esperado 301 o 410)"]))
    return fails, verificados


def cargar_redirects_export(fn):
    """Lee public/_redirects (formato Netlify) y devuelve un dict origen -> (estado, destino).

    Soporta tanto líneas clásicas de página/medio ("origen  destino  estado") como las
    líneas con cláusula de query de las reglas ?p=/?page_id= ("origen  p=123  destino
    estado"): estas últimas se guardan bajo una clave sintética "origen?query" para no
    pisar la entrada real de `origen` (un fallo del parser anterior: toda línea de
    query tiene origen "/", así que sobrescribía silenciosamente lo que hubiera para
    "/"). Sirve tanto para las comprobaciones por URL como para el chequeo de cadenas.
    """
    mapa = {}
    if not fn or not os.path.exists(fn):
        return mapa
    for line in open(fn, encoding="utf-8"):
        if not line.strip() or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) == 3:
            origen, destino, estado = parts
        elif len(parts) == 4 and "=" in parts[1]:
            origen, destino, estado = f"{parts[0]}?{parts[1]}", parts[2], parts[3]
        else:
            continue
        mapa[origen] = ("410" if estado.startswith("410") else "301", destino)
    return mapa


def verificar_sin_cadenas(mapa):
    """Ninguna redirección generada (página, query o medio) puede apuntar a una URL
    que a su vez es 410 o vuelve a redirigir: si build_redirects.py tiene una
    regresión, esto lo atrapa antes de subir a producción."""
    fails = []
    for origen, (estado, destino) in mapa.items():
        if estado != "410" and destino:
            d = destino.split("?")[0]
            if d in mapa:
                estado2, destino2 = mapa[d]
                if estado2 == "410":
                    fails.append((origen, [f"redirige a {d}, que a su vez es 410 (cadena rota, revisa build_redirects.py)"]))
                elif estado2 == "301" and destino2.split("?")[0] != d:
                    fails.append((origen, [f"redirige a {d}, que a su vez redirige a {destino2} (cadena, revisa build_redirects.py)"]))
    return fails


def noindex_presente(hdr, h):
    """True si la respuesta lleva X-Robots-Tag: noindex o <meta name=robots content=noindex>."""
    try:
        xrt = (hdr.get("X-Robots-Tag") or "") if hasattr(hdr, "get") else ""
    except Exception:
        xrt = ""
    if "noindex" in xrt.lower():
        return True
    return "noindex" in (m(h, r'<meta\s+name="robots"\s+content="([^"]*)"') or "").lower()


# ---------------------------------------------------------------------------
# Comprobaciones específicas de staging/producción sobre Apache (.htaccess) —
# criterio propio, documentado en references/plesk-produccion.md.
# ---------------------------------------------------------------------------
def comprobaciones_apache(base, inv, contrato_fn, sin_barra_final_ok=True):
    fails, warns = [], []
    base_netloc = urlparse(base).netloc
    esquema = urlparse(base).scheme

    # (a) 10 URLs "mantener" sin barra -> exactamente un 301 a la misma con barra final.
    if contrato_fn and os.path.exists(contrato_fn):
        muestra = []
        for row in csv.DictReader(open(contrato_fn, encoding="utf-8")):
            if row.get("decision") == "mantener" and row.get("url", "/") not in ("/",) and row["url"].endswith("/"):
                muestra.append(row["url"])
            if len(muestra) >= 10:
                break
        for path in muestra:
            sin_barra = path.rstrip("/")
            code, loc = head_noredirect(base + sin_barra)
            if code not in (301, 308) or not urlparse(loc).path.rstrip("/") == sin_barra:
                fails.append((sin_barra, [f"esperaba un único 301 a {path}, da {code}→{loc}"]))
    else:
        warns.append(("[apache] barra final", ["sin --contract: no se ha podido probar la muestra de barra final"]))

    # (b) http -> https y www <-> sin-www en un solo salto (probado sobre la portada).
    otro_host = base_netloc[4:] if base_netloc.startswith("www.") else f"www.{base_netloc}"
    for host_probado in (base_netloc, otro_host):
        for esquema_probado in ("http", "https"):
            if esquema_probado == esquema and host_probado == base_netloc:
                continue  # esa es la combinación canónica, no debe redirigir
            url_probada = f"{esquema_probado}://{host_probado}/"
            code, loc = head_noredirect(url_probada)
            destino_ok = urlparse(loc).scheme == esquema and urlparse(loc).netloc == base_netloc
            if code not in (301, 308) or not destino_ok:
                warns.append((f"[apache] host/https {url_probada}", [f"esperaba un único 301 a {esquema}://{base_netloc}/, da {code}→{loc}"]))

    # (c) cada 410 del contrato responde 410 tanto en GET como en HEAD.
    if contrato_fn and os.path.exists(contrato_fn):
        for row in csv.DictReader(open(contrato_fn, encoding="utf-8")):
            if row.get("decision") != "410":
                continue
            code_get, _, _ = get(base + row["url"])
            code_head, _ = head_noredirect(base + row["url"])
            if code_get != 410 or code_head != 410:
                fails.append((row["url"], [f"410 esperado en GET y HEAD, da GET={code_get} HEAD={code_head}"]))

    # (d) parámetros de WordPress con y sin UTM -> 301 al destino esperado, nunca 200 en portada.
    muestra_ids = [it for it in inv["items"] if it.get("wp_id")][:5]
    for it in muestra_ids:
        path_original = urlparse(it["url"]).path
        for extra in ("", "&utm_source=test"):
            probada = f"{base}/?p={it['wp_id']}{extra}"
            code, loc = head_noredirect(probada)
            destino = urlparse(loc).path
            if code not in (301, 308):
                warns.append((f"[apache] ?p={it['wp_id']}{extra}", [f"esperaba 301, da {code}"]))
            elif destino == "/" and path_original != "/":
                fails.append((f"[apache] ?p={it['wp_id']}{extra}", ["el parámetro cae en la portada (200 en portada), no en el post"]))

    # (f) cabeceras: una sola Cache-Control, immutable solo en /_astro/, HSTS presente.
    code, h, hdr = get(base + "/")
    ccs = hdr.get_all("Cache-Control") if hasattr(hdr, "get_all") else ([hdr["Cache-Control"]] if hdr.get("Cache-Control") else [])
    if ccs and len(ccs) > 1:
        fails.append(("/", [f"múltiples cabeceras Cache-Control: {ccs}"]))
    if not (hdr.get("Strict-Transport-Security") or ""):
        fails.append(("/", ["falta la cabecera HSTS (Strict-Transport-Security)"]))
    m_astro = re.search(r'(?:href|src)="(/_astro/[^"]+)"', h or "")
    if m_astro:
        _, _, hdr_astro = get(base + m_astro.group(1))
        cc_astro = (hdr_astro.get("Cache-Control") or "") if hasattr(hdr_astro, "get") else ""
        if "immutable" not in cc_astro:
            fails.append((m_astro.group(1), [f"sin Cache-Control immutable en /_astro/ (da '{cc_astro}')"]))
    else:
        warns.append(("[apache] /_astro/", ["no se ha encontrado ningún asset /_astro/ en la portada para comprobar el cache"]))
    cc_home = (hdr.get("Cache-Control") or "") if hasattr(hdr, "get") else ""
    if "immutable" in cc_home:
        fails.append(("/", ["la portada (HTML) lleva Cache-Control immutable; debe ser no-cache/must-revalidate"]))

    # (g) rutas de administración de WordPress -> 410.
    for ruta in ("/wp-admin/", "/wp-login.php", "/xmlrpc.php"):
        code, _ = head_noredirect(base + ruta)
        if code != 410:
            fails.append((ruta, [f"esperaba 410, da {code}"]))

    return fails, warns


# ---------------------------------------------------------------------------
# Diff de enlazado interno (fase 6): rastrea la web nueva con crawl_grafo (la misma
# función que usa extract_wp.py sobre la vieja) y compara con inventory.json.
# Criterio propio (documentado): WARN si una URL con tráfico>0 o backlinks>0 en el
# contrato pierde más de --inlinks-umbral (20% por defecto) de sus inlinks internos,
# o si aumenta su profundidad; FAIL si una URL "mantener" queda huérfana (0 inlinks).
# ---------------------------------------------------------------------------
def diff_enlazado_interno(inv, contrato_fn, base, delay, max_urls, umbral):
    fails, warns = [], []
    if not contrato_fn or not os.path.exists(contrato_fn):
        return fails, warns
    filas = {row["url"]: row for row in csv.DictReader(open(contrato_fn, encoding="utf-8"))}
    known = {urlparse(it["url"]).path for it in inv["items"]}
    grafo = crawl_grafo(base, known, max_urls, delay)
    for it in inv["items"]:
        path = urlparse(it["url"]).path
        fila = filas.get(path)
        if not fila:
            continue

        def numero(v):
            try:
                return float(v)
            except (TypeError, ValueError):
                return 0.0

        if numero(fila.get("trafico")) <= 0 and numero(fila.get("backlinks")) <= 0:
            continue
        viejo = len(it.get("inlinks") or [])
        nuevos = len(grafo["inlinks"].get(base.rstrip("/") + path, set()))
        vieja_prof, nueva_prof = it.get("profundidad"), grafo["profundidad"].get(base.rstrip("/") + path)
        if fila.get("decision") == "mantener" and viejo > 0 and nuevos == 0:
            fails.append((path, [f"URL con tráfico/backlinks ha quedado huérfana (antes {viejo} inlinks, ahora 0)"]))
            continue
        if viejo > 0:
            perdida = (viejo - nuevos) / viejo
            if perdida > umbral:
                warns.append((path, [f"pierde {perdida:.0%} de inlinks internos ({viejo}→{nuevos}, umbral {umbral:.0%})"]))
                continue
        if vieja_prof is not None and nueva_prof is not None and nueva_prof > vieja_prof:
            warns.append((path, [f"aumenta la profundidad ({vieja_prof}→{nueva_prof} clics desde portada)"]))
    return fails, warns


# ---------------------------------------------------------------------------
# Paridad de medición: cada ID de tracking.json debe seguir presente, o estar
# justificado en migracion/tracking_decisiones.md.
# ---------------------------------------------------------------------------
def paridad_medicion(tracking_fn, decisiones_fn, tracking_nuevo, verif_archivo_nuevo):
    fails, warns = [], []
    if not tracking_fn or not os.path.exists(tracking_fn):
        return fails, warns
    tracking_viejo = json.load(open(tracking_fn, encoding="utf-8"))
    justificado = ""
    if decisiones_fn and os.path.exists(decisiones_fn):
        justificado = open(decisiones_fn, encoding="utf-8").read()
    categorias = ("gtm", "ga4", "ads", "meta_pixel", "hotjar", "clarity", "linkedin")
    for cat in categorias:
        for id_ in tracking_viejo.get(cat, []):
            if id_ in tracking_nuevo.get(cat, set()):
                continue
            if id_ in justificado:
                continue
            fails.append((f"[medición] {cat}", [f"ID {id_} presente en la web vieja y no en la nueva, sin justificar en tracking_decisiones.md"]))
    if tracking_viejo.get("google_site_verification") and not tracking_nuevo.get("google_site_verification"):
        if not any(v in justificado for v in tracking_viejo["google_site_verification"]):
            fails.append(("[medición] GSC", ["falta la verificación google-site-verification de Search Console"]))
    if tracking_viejo.get("msvalidate") and not tracking_nuevo.get("msvalidate"):
        if not any(v in justificado for v in tracking_viejo["msvalidate"]):
            fails.append(("[medición] Bing", ["falta la verificación msvalidate.01 de Bing Webmaster"]))
    if (tracking_viejo.get("verificaciones_archivo") or {}).get("bingsiteauth") and not verif_archivo_nuevo.get("bingsiteauth"):
        if "bingsiteauth" not in justificado.lower():
            fails.append(("[medición] Bing", ["falta BingSiteAuth.xml (verificación de Bing por archivo)"]))
    return fails, warns


# ---------------------------------------------------------------------------
# Formularios: cada URL con formulario en tracking.json debe tener <form> con
# action al handler PHP (o endpoint documentado) y honeypot detectable.
# ---------------------------------------------------------------------------
HONEYPOT_HINT_RE = re.compile(r'name="(?:website|url|hp_\w*|company)"|aria-hidden="true"[^>]*>\s*<input', re.I)


def validar_formularios_tracking(tracking_fn, base, entorno):
    fails, warns = [], []
    if not tracking_fn or not os.path.exists(tracking_fn):
        return fails, warns
    tracking = json.load(open(tracking_fn, encoding="utf-8"))
    destino = warns if entorno == "preview" else fails
    for url_vieja in (tracking.get("formularios") or {}):
        path = urlparse(url_vieja).path
        st, h, _ = get(base + path)
        if st != 200 or "<form" not in (h or "").lower():
            destino.append((path, ["formulario perdido: la URL no tiene <form> en la web nueva"]))
            continue
        bloque = ew.FORM_TAG_RE.search(h)
        cuerpo = bloque.group(0) if bloque else h
        if not re.search(r'action="[^"]+"', cuerpo, re.I):
            destino.append((path, ["<form> sin action reconocible (debería apuntar a form-handler.php o al endpoint documentado)"]))
        if not HONEYPOT_HINT_RE.search(cuerpo):
            destino.append((path, ["no se detecta honeypot en el formulario (campo trampa oculto)"]))
    return fails, warns


# ---------------------------------------------------------------------------
# Funciones de Google e IA (ver references/funciones-google-y-llm.md): checks
# sobre la portada + una muestra, no por cada URL del inventario (serían
# redundantes con el bucle principal). WARN salvo que se indique FAIL.
# ---------------------------------------------------------------------------
BOTS_BUSQUEDA_IA = ("OAI-SearchBot", "PerplexityBot", "Claude-SearchBot", "Googlebot")


def _bloqueado_en_robots(robots_txt, agente):
    """True si el bloque de `agente` (o el `*` si no tiene bloque propio) lleva
    'Disallow: /' sin excepciones. Parser deliberadamente simple: basta para
    detectar el caso que de verdad rompe la visibilidad (bloqueo total)."""
    bloques, actual = {}, None
    for linea in robots_txt.splitlines():
        linea = linea.split("#", 1)[0].strip()
        if not linea:
            continue
        if ":" not in linea:
            continue
        campo, _, valor = linea.partition(":")
        campo, valor = campo.strip().lower(), valor.strip()
        if campo == "user-agent":
            actual = valor
            bloques.setdefault(actual, [])
        elif campo == "disallow" and actual is not None:
            bloques[actual].append(valor)
    reglas = bloques.get(agente)
    if reglas is None:
        reglas = bloques.get("*", [])
    return "/" in reglas


def comprobaciones_google_ia(base, html_portada, hdr_portada, entorno):
    """Checks nuevos de la matriz de funciones de Google/IA. Devuelve (fails, warns)."""
    fails, warns = [], []
    h = html_portada or ""

    # WebSite.name en la portada (los objetos ya se han parseado en el bucle principal
    # para el diff de schema; aquí se repite el parseo porque esta función es
    # independiente y se puede llamar sola en tests).
    objetos = parse_jsonld_objetos(h)
    website = next((o for o in objetos if "WebSite" in (o.get("@type") if isinstance(o.get("@type"), list) else [o.get("@type")])), None)
    if not website or not website.get("name"):
        fails.append(("[schema] WebSite.name", ["falta WebSite con 'name' en la portada"]))

    org = next((o for o in objetos if any(t in (o.get("@type") if isinstance(o.get("@type"), list) else [o.get("@type")])
                                           for t in ("Organization", "LocalBusiness")) or
                (isinstance(o.get("@type"), str) and o["@type"].endswith(("Business", "Clinic", "Store")))), None)

    # Logo de Organization: accesible y rastreable.
    logo = None
    if org:
        logo = org.get("logo")
        logo = logo.get("url") if isinstance(logo, dict) else logo
    if not logo:
        warns.append(("[schema] Organization.logo", ["no se encuentra 'logo' en el Organization/LocalBusiness de portada"]))
    else:
        # El schema suele llevar la URL absoluta del dominio final (correcto: las URLs de
        # producción no cambian entre preview y prod), pero el asset vive en el mismo path
        # relativo en cualquier entorno servido desde el mismo build: se comprueba siempre
        # contra --base, nunca contra el dominio absoluto embebido en el JSON-LD.
        logo_path = urlparse(logo).path if logo.startswith("http") else logo
        code, _ = head_noredirect(base + logo_path)
        if code != 200:
            fails.append(("[schema] Organization.logo", [f"logo en {logo_path} responde {code} sobre {base} (debe ser 200 y rastreable)"]))

    # NAP: teléfono/dirección del schema deben aparecer también en el texto visible.
    if org:
        tel = org.get("telephone")
        if tel:
            tel_visible = re.sub(r"[^\d+]", "", tel) in re.sub(r"[^\d+]", "", re.sub(r"<[^>]+>", " ", h))
            if not tel_visible:
                warns.append(("[NAP] teléfono", [f"'{tel}' del schema no aparece (o aparece con otro formato) en el texto visible de portada"]))
        direccion = org.get("address")
        if isinstance(direccion, dict):
            calle = direccion.get("streetAddress")
            if calle and calle not in h:
                warns.append(("[NAP] dirección", [f"'{calle}' del schema no aparece literal en el HTML visible de portada"]))

    # Favicon: presente y accesible.
    favicon = m(h, r'<link[^>]+rel="(?:shortcut )?icon"[^>]+href="([^"]+)"') or \
              m(h, r'<link[^>]+href="([^"]+)"[^>]+rel="(?:shortcut )?icon"')
    if not favicon:
        fails.append(("[favicon] /", ["no se encuentra <link rel=\"icon\"> en la portada"]))
    else:
        favicon_path = urlparse(favicon).path if favicon.startswith("http") else favicon
        code, _ = head_noredirect(base + favicon_path)
        if code != 200:
            fails.append(("[favicon] " + favicon_path, [f"responde {code} sobre {base} (debe ser 200 y rastreable por Googlebot-Image)"]))

    # BreadcrumbList en una página no-portada (se comprueba en el bucle principal vía
    # el diff de schema general; aquí solo se avisa si faltó en todas).

    # meta robots max-image-preview:large en producción.
    if entorno == "produccion":
        rob = m(h, r'<meta\s+name="robots"\s+content="([^"]*)"')
        if "max-image-preview:large" not in rob:
            warns.append(("[robots meta] /", ["falta 'max-image-preview:large' en meta robots de producción (necesario para Discover)"]))

    # imágenes sin alt (contador, no bloquea).
    imgs = re.findall(r"<img\b[^>]*>", h, re.I)
    sin_alt = [i for i in imgs if not re.search(r'\balt="[^"]*"', i, re.I)]
    if sin_alt:
        warns.append(("[imágenes] /", [f"{len(sin_alt)}/{len(imgs)} <img> sin atributo alt en portada"]))

    # fechas visibles: si hay algún <time datetime=...> en la portada de posts, ok;
    # si no, solo se avisa (el check fuerte está en el bucle de BlogPosting).
    if "<article" in h.lower() and "<time" not in h.lower():
        warns.append(("[fechas] /", ["no se detecta <time> visible en el HTML (fechas solo en JSON-LD, no en el texto)"]))

    # llms.txt
    code, _, _ = get(base + "/llms.txt")
    if code != 200:
        warns.append(("[llms.txt] /", ["no existe /llms.txt (coste cero; ver seo-estandar.md sección D)"]))

    # robots.txt: bots de búsqueda/citación de IA no bloqueados sin decisión documentada.
    code, robots_txt, _ = get(base + "/robots.txt")
    if code == 200:
        claude_md = ""
        if os.path.exists("CLAUDE.md"):
            claude_md = open("CLAUDE.md", encoding="utf-8").read()
        for agente in BOTS_BUSQUEDA_IA:
            if _bloqueado_en_robots(robots_txt, agente):
                if "política de bots de ia" in claude_md.lower() and agente.lower() in claude_md.lower():
                    warns.append((f"[robots.txt] {agente}", [f"{agente} bloqueado, pero hay una decisión documentada en CLAUDE.md"]))
                else:
                    fails.append((f"[robots.txt] {agente}", [f"{agente} (bot de búsqueda/citación de IA) bloqueado sin decisión documentada en CLAUDE.md"]))
    else:
        warns.append(("[robots.txt] /", ["no se pudo leer robots.txt para comprobar los bots de IA"]))

    return fails, warns


# ---------------------------------------------------------------------------
# (5) Informe HTML autocontenido
# ---------------------------------------------------------------------------
def generar_informe_html(ruta, kpis, filas, schema_diffs, lighthouse, extra_html=""):
    def esc(s):
        return html.escape(str(s), quote=True)

    color = {"FAIL": "#b3261e", "WARN": "#8a6100", "PASS": "#1e6b3a"}
    filas_html = []
    for path, estado, motivos in filas:
        cls = color.get(estado, "#333")
        motivos_txt = esc("; ".join(motivos)) if motivos else "—"
        filas_html.append(
            f'<tr><td>{esc(path)}</td><td style="color:{cls};font-weight:600">{estado}</td>'
            f'<td>{motivos_txt}</td></tr>'
        )

    schema_html = "".join(
        f'<tr><td>{esc(path)}</td><td>{esc(", ".join(perdidos))}</td></tr>'
        for path, perdidos in schema_diffs
    ) or '<tr><td colspan="2">Sin tipos de schema perdidos.</td></tr>'

    lh_html = "<p>No se ha pasado --lighthouse.</p>"
    if lighthouse:
        cats = lighthouse.get("categories", {})
        audits = lighthouse.get("audits", {})
        filas_cat = "".join(
            f'<tr><td>{esc(c.get("title", k))}</td><td>{round((c.get("score") or 0) * 100)}</td></tr>'
            for k, c in cats.items()
        )
        lcp = audits.get("largest-contentful-paint", {}).get("displayValue", "—")
        tbt = audits.get("total-blocking-time", {}).get("displayValue", "—")
        cls_metric = audits.get("cumulative-layout-shift", {}).get("displayValue", "—")
        lh_html = f"""
        <table><thead><tr><th>Categoría</th><th>Puntuación</th></tr></thead>
        <tbody>{filas_cat}</tbody></table>
        <p><strong>LCP:</strong> {esc(lcp)} · <strong>TBT:</strong> {esc(tbt)} · <strong>CLS:</strong> {esc(cls_metric)}</p>
        """

    css = """
    body{font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;max-width:1000px;margin:2rem auto;
         padding:0 1rem;color:#1a1a1a;background:#fff}
    h1{font-size:1.4rem} h2{font-size:1.1rem;margin-top:2.5rem;border-bottom:1px solid #ddd;padding-bottom:.3rem}
    table{border-collapse:collapse;width:100%;font-size:.9rem;margin-top:.5rem}
    th,td{border:1px solid #ddd;padding:.4rem .6rem;text-align:left;vertical-align:top}
    th{background:#f5f5f5}
    .kpis{display:flex;flex-wrap:wrap;gap:1rem;margin-top:1rem}
    .kpi{background:#f5f5f5;border-radius:8px;padding:.8rem 1.2rem;min-width:150px}
    .kpi b{display:block;font-size:1.4rem}
    """
    kpis_html = "".join(
        f'<div class="kpi"><b>{esc(v)}</b>{esc(k)}</div>' for k, v in kpis.items()
    )
    out = f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<title>Informe de validación · migración</title><style>{css}</style></head><body>
<h1>Informe de validación de migración</h1>
<div class="kpis">{kpis_html}</div>
<h2>URLs (FAIL / WARN / PASS)</h2>
<table><thead><tr><th>URL</th><th>Estado</th><th>Motivo</th></tr></thead>
<tbody>{''.join(filas_html)}</tbody></table>
<h2>Diff de schema (tipos perdidos)</h2>
<table><thead><tr><th>URL</th><th>Tipos perdidos</th></tr></thead>
<tbody>{schema_html}</tbody></table>
<h2>Lighthouse</h2>
{lh_html}
{extra_html}
</body></html>"""
    os.makedirs(os.path.dirname(ruta) or ".", exist_ok=True)
    open(ruta, "w", encoding="utf-8").write(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("inventory", nargs="?")
    ap.add_argument("--base")
    ap.add_argument("--no-literal")
    ap.add_argument("--old-domain")
    ap.add_argument("--redirects", help="public/_redirects para saber qué URLs deben dar 301/410")
    ap.add_argument("--i18n")
    ap.add_argument("--links-only")
    ap.add_argument("--contract", help="migracion/urls.csv: comprueba el estado esperado de cada URL")
    ap.add_argument("--production", action="store_true", help="puerta anti-noindex: falla si producción no es indexable")
    ap.add_argument("--media", help="migracion/media.json: muestrea URLs de medios y comprueba 301/410")
    ap.add_argument("--media-sample", type=int, default=20, help="tamaño de la muestra de medios (por defecto 20)")
    ap.add_argument("--report", help="ruta de salida para el informe HTML autocontenido")
    ap.add_argument("--lighthouse", help="JSON de un run de Lighthouse (categories, audits) para incluir en --report")
    ap.add_argument("--entorno", choices=["preview", "staging", "produccion"], default="preview",
                     help="preview (Netlify, exige noindex), staging o produccion (Plesk/Apache, exigen indexable). Por defecto: preview")
    ap.add_argument("--auth", help="user:pass para staging protegido con contraseña. Prefiere la variable de "
                                    "entorno VALIDATOR_AUTH: pasarlo aquí lo deja visible en el historial de la shell")
    ap.add_argument("--preview-url", help="con --entorno produccion: comprueba que esta URL de preview de Netlify "
                                           "ya no es accesible sin contraseña, o que devuelve noindex")
    ap.add_argument("--check-inlinks", action="store_true",
                     help="activa el diff de enlazado interno (rastrea --base con crawl_grafo; puede tardar)")
    ap.add_argument("--inlinks-umbral", type=float, default=0.2,
                     help="pérdida de inlinks internos que dispara WARN, como fracción (por defecto 0.2 = 20%%)")
    ap.add_argument("--crawl-max-urls", type=int, default=500, help="tope de URLs para --check-inlinks (por defecto 500)")
    ap.add_argument("--crawl-delay", type=float, default=0.2, help="pausa entre peticiones del rastreo de --check-inlinks")
    ap.add_argument("--tracking", default="migracion/tracking.json",
                     help="migracion/tracking.json (de extract_wp.py): paridad de medición y formularios")
    ap.add_argument("--tracking-decisiones", default="migracion/tracking_decisiones.md",
                     help="justificaciones de IDs de tracking que no se han migrado (ver medicion-y-formularios.md)")
    ap.add_argument("--rich-results", action="store_true",
                     help="genera migracion/rich-results-urls.txt con la lista de URLs y el enlace a la "
                          "prueba de resultados enriquecidos de Google para revisarlas a mano (no la automatiza)")
    ap.add_argument("--tracking-playwright", action="store_true",
                     help="opcional: con Playwright, comprueba Consent Mode (sin hits antes de aceptar, GA4 después). "
                          "Si Playwright no está instalado, se salta con un aviso, nunca falla")
    a = ap.parse_args()
    configurar_auth(a.auth)
    if a.links_only:
        sys.exit(links_only(a.links_only))
    if not (a.inventory and a.base):
        ap.error("inventory y --base son obligatorios")

    inv = json.load(open(a.inventory))
    base = a.base.rstrip("/")
    base_netloc = urlparse(base).netloc
    old_domain = a.old_domain or urlparse(inv["site"]).netloc
    allowed = load_no_literal(a.no_literal)
    expected = cargar_redirects_export(a.redirects)
    cadenas_fails = verificar_sin_cadenas(expected) if a.redirects else []
    i18n = json.load(open(a.i18n)) if a.i18n else None

    fails, warns, passes = [], [], 0
    todas_filas = []          # (path, "FAIL"/"WARN"/"PASS", [motivos]) — para el informe
    schema_diffs = []          # (path, [tipos perdidos]) — para el informe
    ref_cache = {}
    contadores = {"titles_total": 0, "titles_ok": 0, "desc_total": 0, "desc_ok": 0}
    tracking_nuevo = {"gtm": set(), "ga4": set(), "ads": set(), "meta_pixel": set(),
                       "hotjar": set(), "clarity": set(), "linkedin": set(), "cmp": set(),
                       "google_site_verification": set(), "msvalidate": set()}

    for it in inv["items"]:
        path = urlparse(it["url"]).path
        url = base + path
        seo = it.get("seo", {})
        F, W = [], []
        if path in expected:
            code, loc = head_noredirect(url)
            want, dst = expected[path]
            if want == "410" and code != 410:
                F.append(f"esperaba 410, da {code}")
            if want == "301" and (code not in (301, 308) or urlparse(loc).path != dst):
                F.append(f"esperaba 301→{dst}, da {code}→{loc}")
        else:
            st, h, hdr = get(url)
            if it.get("status") == 200 and st != 200:
                F.append(f"HTTP {st}")
            elif st == 200:
                if a.entorno == "preview" and not noindex_presente(hdr, h):
                    F.append("preview SIN noindex (X-Robots-Tag ni meta robots): no debe indexarse nunca")
                elif a.entorno in ("staging", "produccion") and noindex_presente(hdr, h):
                    F.append(f"{a.entorno.upper()} con noindex: debe ser indexable")
                td = ew.detectar_tracking(h, base)
                for k in tracking_nuevo:
                    tracking_nuevo[k] |= td[k]
                nt, nd = m(h, r"<title[^>]*>(.*?)</title>"), m(h, r'<meta\s+name="description"\s+content="([^"]*)"')
                if seo.get("title"):
                    contadores["titles_total"] += 1
                if norm(nt) != norm(seo.get("title")) and (path, "title") not in allowed:
                    F.append(f"title distinto: '{seo.get('title')}' → '{nt}'")
                elif seo.get("title"):
                    contadores["titles_ok"] += 1
                if seo.get("meta_description"):
                    contadores["desc_total"] += 1
                if seo.get("meta_description") and norm(nd) != norm(seo["meta_description"]) and (path, "meta_description") not in allowed:
                    F.append(f"description distinta")
                elif seo.get("meta_description"):
                    contadores["desc_ok"] += 1
                if seo.get("meta_description") == "" and nd == "":
                    W.append("sin metadescripción (tampoco la tenía)")
                canon = m(h, r'<link\s+rel="canonical"\s+href="([^"]*)"')
                if canon and urlparse(canon).path != path:
                    F.append(f"canonical apunta a {canon}")
                if not canon:
                    W.append("sin canonical")
                rob = m(h, r'<meta\s+name="robots"\s+content="([^"]*)"')
                if ("noindex" in seo.get("robots", "")) != ("noindex" in rob):
                    F.append(f"robots cambió: '{seo.get('robots')}' → '{rob}'")
                h1s = re.findall(r"<h1[^>]*>(.*?)</h1>", h, re.I | re.S)
                if len(h1s) != 1:
                    F.append(f"{len(h1s)} H1")
                elif seo.get("h1") and norm(re.sub("<[^>]+>", "", h1s[0])) != norm(seo["h1"]) and (path, "h1") not in allowed:
                    W.append("H1 distinto")
                if LEFTOVERS.search(h):
                    F.append("restos de WordPress/constructor en el HTML")
                if old_domain and re.search(rf'(src|href)="https?://(www\.)?{re.escape(old_domain)}/wp-content/[^"]*', h, re.I):
                    F.append("imágenes/archivos aún servidos desde el dominio antiguo")
                if "application/ld+json" not in h:
                    W.append("sin schema JSON-LD")

                # (2) diff de schema
                tipos_viejos = set(seo.get("jsonld_types", []))
                tipos_nuevos = tipos_de(parse_jsonld_objetos(h))
                perdidos = sorted(t for t in (tipos_viejos - tipos_nuevos) if not perdida_aceptable(t, it))
                if perdidos:
                    W.append("schema perdido: " + ", ".join(perdidos))
                    schema_diffs.append((path, perdidos))
                for o in parse_jsonld_objetos(h):
                    t = o.get("@type")
                    tset = set(t) if isinstance(t, list) else {t}
                    if "BlogPosting" in tset:
                        autor = o.get("author")
                        if not autor:
                            F.append("BlogPosting sin author")
                        elif isinstance(autor, dict) and "Person" in (autor.get("@type") or "") and not autor.get("url"):
                            W.append("BlogPosting.author (Person) sin url a página de autor")
                        if not o.get("datePublished"):
                            F.append("BlogPosting sin datePublished")
                        if not o.get("dateModified"):
                            W.append("BlogPosting sin dateModified")
                        img = o.get("image")
                        img_url = img.get("url") if isinstance(img, dict) else img
                        if not img_url:
                            W.append("BlogPosting sin image")
                        else:
                            ancho = img.get("width") if isinstance(img, dict) else None
                            if ancho and int(ancho) < 1200:
                                W.append(f"BlogPosting.image con width {ancho} (recomendado >=1200px)")

                # (3) referencias propias rotas
                for ref_path in sorted(set(referencias_propias(h, url, base_netloc))):
                    if ref_path not in ref_cache:
                        code, _ = head_noredirect(base + ref_path)
                        ref_cache[ref_path] = code
                    if ref_cache[ref_path] == 404:
                        F.append(f"referencia rota a {ref_path}")

                if i18n:
                    want_i18n = {k: v for g in i18n.values() for k, v in g.items() if path in g.values()}
                    have = dict(re.findall(r'hreflang="([^"]+)"[^>]*href="([^"]+)"', h) + re.findall(r'href="([^"]+)"[^>]*hreflang="([^"]+)"', h)[::-1])
                    for lang, p in want_i18n.items():
                        if lang not in have:
                            F.append(f"falta hreflang {lang}")
                    if want_i18n and "x-default" not in have:
                        F.append("falta x-default")
        if F:
            fails.append((path, F))
            todas_filas.append((path, "FAIL", F))
        elif W:
            warns.append((path, W))
            passes += 1
            todas_filas.append((path, "WARN", W))
        else:
            passes += 1
            todas_filas.append((path, "PASS", []))

    # (4) contrato de URLs, incluidas las "sistema"
    contrato_kpis = {"mantener_total": 0, "mantener_ok": 0, "301_total": 0, "301_ok": 0, "410_total": 0, "410_ok": 0}
    if a.contract and os.path.exists(a.contract):
        import csv
        for row in csv.DictReader(open(a.contract, encoding="utf-8")):
            etiqueta = "[sistema] " if row.get("tipo") == "sistema" else ""
            if row["decision"] == "REVISAR":
                fails.append((row["url"], [f"{etiqueta}contrato: decisión pendiente (REVISAR)"]))
                continue
            want = row.get("estado_esperado", "")
            if not want:
                continue
            clave = {"200": "mantener_total", "301": "301_total", "410": "410_total"}.get(want)
            if clave:
                contrato_kpis[clave] += 1
            code, loc = head_noredirect(base + row["url"])
            ok = str(code) == want or (want == "301" and code in (301, 308)) or (want == "200" and code == 200)
            if not ok:
                fails.append((row["url"], [f"{etiqueta}contrato: esperaba {want}, da {code}"]))
            elif clave:
                contrato_kpis[clave.replace("_total", "_ok")] += 1

    # (1) muestreo de medios
    medios_fails, medios_verificados = validar_medios(a.media, base, a.media_sample)
    for path, motivos in medios_fails:
        fails.append((path, motivos))
        todas_filas.append((path, "FAIL", motivos))

    if a.production or a.entorno == "produccion":
        st, rb, _ = get(base + "/robots.txt")
        if re.search(r"(?im)^\s*Disallow:\s*/\s*$", rb or ""):
            fails.append(("/robots.txt", ["PRODUCCIÓN con Disallow: / (bloquea todo)"]))
        st, h, hdr = get(base + "/")
        if "noindex" in (m(h, r'<meta\s+name="robots"\s+content="([^"]*)"') or "").lower():
            fails.append(("/", ["PRODUCCIÓN con meta robots noindex en la portada"]))
        try:
            if "noindex" in (hdr.get("X-Robots-Tag") or "").lower():
                fails.append(("/", ["PRODUCCIÓN con cabecera X-Robots-Tag: noindex"]))
        except AttributeError:
            pass
        if a.preview_url:
            st_p, h_p, hdr_p = get(a.preview_url.rstrip("/") + "/")
            if st_p == 200 and not noindex_presente(hdr_p, h_p):
                fails.append(("[preview] " + a.preview_url, ["la preview de Netlify sigue accesible sin contraseña Y sin noindex: bórrala o protégela"]))

    for p, f in cadenas_fails:
        fails.append((p, f)); todas_filas.append((p, "FAIL", f))

    apache_fails, apache_warns = [], []
    if a.entorno in ("staging", "produccion"):
        apache_fails, apache_warns = comprobaciones_apache(base, inv, a.contract)
        for p, f in apache_fails:
            fails.append((p, f)); todas_filas.append((p, "FAIL", f))
        for p, w in apache_warns:
            warns.append((p, w)); todas_filas.append((p, "WARN", w))

    inlinks_fails, inlinks_warns = [], []
    if a.check_inlinks:
        inlinks_fails, inlinks_warns = diff_enlazado_interno(inv, a.contract, base, a.crawl_delay, a.crawl_max_urls, a.inlinks_umbral)
        for p, f in inlinks_fails:
            fails.append((p, f)); todas_filas.append((p, "FAIL", f))
        for p, w in inlinks_warns:
            warns.append((p, w)); todas_filas.append((p, "WARN", w))

    medicion_fails = []
    if os.path.exists(a.tracking):
        verif_nuevo = ew.verificaciones_por_archivo(base, 0.1)
        medicion_fails, _ = paridad_medicion(a.tracking, a.tracking_decisiones, tracking_nuevo, verif_nuevo)
        formularios_fails, formularios_warns = validar_formularios_tracking(a.tracking, base, a.entorno)
        for p, f in medicion_fails + formularios_fails:
            fails.append((p, f)); todas_filas.append((p, "FAIL", f))
        for p, w in formularios_warns:
            warns.append((p, w)); todas_filas.append((p, "WARN", w))

    # Funciones de Google e IA (favicon, logo, WebSite.name, NAP, robots.txt por bot, llms.txt...)
    _, html_portada, hdr_portada = get(base + "/")
    google_ia_fails, google_ia_warns = comprobaciones_google_ia(base, html_portada, hdr_portada, a.entorno)
    for p, f in google_ia_fails:
        fails.append((p, f)); todas_filas.append((p, "FAIL", f))
    for p, w in google_ia_warns:
        warns.append((p, w)); todas_filas.append((p, "WARN", w))

    if a.rich_results:
        ruta_rr = os.path.join(os.path.dirname(a.inventory) if a.inventory else ".", "rich-results-urls.txt")
        with open(ruta_rr, "w", encoding="utf-8") as f:
            f.write("# Revisión manual con la prueba de resultados enriquecidos de Google.\n")
            f.write("# https://search.google.com/test/rich-results\n\n")
            for it in inv["items"]:
                url = base + urlparse(it["url"]).path
                f.write(f"{url}\thttps://search.google.com/test/rich-results?url={url}\n")
        print(f"\n--rich-results: lista guardada en {ruta_rr} (revisión manual, no se automatiza)")

    if a.tracking_playwright:
        try:
            import importlib
            importlib.import_module("playwright.sync_api")
            print("⚠️  --tracking-playwright: implementación pendiente de credenciales del CMP en este entorno; "
                  "revisa manualmente Consent Mode con Tag Assistant (ver references/lanzamiento.md).")
        except ImportError:
            print("⚠️  Playwright no está instalado: se salta --tracking-playwright (no es obligatorio, ver SKILL.md).")

    print(f"\nEntorno: {a.entorno} · PASS {passes}  WARN {len(warns)}  FAIL {len(fails)}  (de {len(inv['items'])} URLs)\n")
    for p, f in fails:
        print(f"FAIL {p}\n  " + "\n  ".join(f))
    for p, w in warns:
        print(f"WARN {p}\n  " + "\n  ".join(w))
    if a.media:
        print(f"\nMedios muestreados: {medios_verificados}, con FAIL: {len(medios_fails)}")

    if a.report:
        lighthouse = json.load(open(a.lighthouse, encoding="utf-8")) if a.lighthouse and os.path.exists(a.lighthouse) else None
        kpis = {
            "Entorno": a.entorno,
            "Titles literales": f"{contadores['titles_ok']}/{contadores['titles_total']}",
            "Descriptions literales": f"{contadores['desc_ok']}/{contadores['desc_total']}",
            "URLs mantener OK": f"{contrato_kpis['mantener_ok']}/{contrato_kpis['mantener_total']}",
            "URLs 301 OK": f"{contrato_kpis['301_ok']}/{contrato_kpis['301_total']}",
            "URLs 410 OK": f"{contrato_kpis['410_ok']}/{contrato_kpis['410_total']}",
            "Medios verificados": f"{medios_verificados - len(medios_fails)}/{medios_verificados}",
            "FAIL": len(fails), "WARN": len(warns), "PASS": passes,
        }

        def lista(titulo, filas):
            if not filas:
                return f"<p><strong>{html.escape(titulo)}:</strong> sin hallazgos.</p>"
            items = "".join(f"<li>{html.escape(p)}: {html.escape('; '.join(f_))}</li>" for p, f_ in filas)
            return f"<p><strong>{html.escape(titulo)}:</strong></p><ul>{items}</ul>"

        extra = f"""
        <h2>Entorno</h2>
        <p>Validado contra <code>{html.escape(base)}</code> como <strong>{html.escape(a.entorno)}</strong>.
        {"Preview: debe llevar noindex en toda respuesta." if a.entorno == "preview" else
         "Debe ser indexable (sin noindex) y con las reglas de Apache activas."}</p>
        <h2>Redirecciones Apache</h2>
        {lista("Comprobaciones de .htaccess (host/https, barra final, 410, parámetros, cabeceras, wp-admin)", apache_fails + apache_warns)}
        <h2>Enlazado interno</h2>
        {lista(f"Diff contra inventory.json (umbral {a.inlinks_umbral:.0%})", inlinks_fails + inlinks_warns) if a.check_inlinks
         else "<p>No se ha pasado --check-inlinks.</p>"}
        <h2>Medición y formularios</h2>
        {lista("Paridad de tracking.json y formularios", medicion_fails if os.path.exists(a.tracking) else [])}
        <h2>Funciones de Google e IA</h2>
        <p>Ver <code>references/funciones-google-y-llm.md</code> para el detalle de cada función y su fuente.</p>
        {lista("WebSite.name, logo, favicon, NAP, robots meta, imágenes sin alt, fechas visibles, llms.txt, robots.txt por bot de IA", google_ia_fails + google_ia_warns)}
        <h2>Pruebas manuales obligatorias antes del DNS</h2>
        <ul>
          <li>Envío real de cada formulario en staging Plesk: llega el email y la autorrespuesta, y se
              dispara la conversión en GA4/Ads (ver <code>references/medicion-y-formularios.md</code>).</li>
          <li>Tag Assistant sobre staging: Consent Mode v2 con defaults denied antes de aceptar.</li>
          <li>Gestor de eventos de Meta: el pixel dispara tras aceptar el CMP.</li>
        </ul>
        """
        generar_informe_html(a.report, kpis, todas_filas, schema_diffs, lighthouse, extra_html=extra)
        print(f"\nInforme HTML: {a.report}")

    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
