#!/usr/bin/env python3
"""
Extrae una web WordPress para migrarla: inventario de URLs con su SEO,
contenido limpio en Markdown, lista de medios e informe.

Uso:
    python3 extract_wp.py https://dominio.com --out migracion/ [--delay 0.5]

Estrategia:
1. API REST de WordPress (/wp-json/wp/v2) si está abierta.
2. Siempre, el sitemap (Yoast, Rank Math o el nativo) para cruzar URLs.
3. Por cada URL, se descarga el HTML público para leer el SEO real
   (title, description, canonical, robots, OG, schema), que es lo que ve Google.

Sin dependencias obligatorias. Si 'markdownify' está instalado, lo usa para
convertir HTML a Markdown con más calidad; si no, usa un conversor básico.
"""
import argparse, csv, html, json, os, re, sys, time, urllib.request, urllib.error
from collections import deque
from urllib.parse import urlparse, urljoin

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from crawl_lib import crawl_grafo  # noqa: E402  (compartida con validate_migration.py)

UA = {"User-Agent": "Mozilla/5.0 (TheLiftCo migration audit)"}
SPAM_PATTERNS = re.compile(
    r"casino|slot|bet(ting)?|poker|viagra|cialis|loan|bitcoin|crypto|porn|escort|"
    r"kasyno|kazino|cazino|apuestas|ставк|казино", re.I)

# Rutas "de sistema" típicas de WordPress: no son contenido, pero deben quedar
# registradas en el inventario (marcadas tipo:"sistema") para decidir su 301/410.
SYSTEM_PATH_PATTERNS = [
    re.compile(r"/page/\d+/?$", re.I),          # /page/N/ y */page/N/
    re.compile(r"/feed/?$", re.I),               # /feed/ y */feed/
    re.compile(r"/comments/feed/?$", re.I),
    re.compile(r"^/(blog/)?category(/|$)", re.I),
    re.compile(r"/category(/|$)", re.I),
    re.compile(r"^/tag(/|$)", re.I),
    re.compile(r"^/author(/|$)", re.I),
    re.compile(r"^/wp-json(/|$)", re.I),
    re.compile(r"^/xmlrpc\.php$", re.I),
    re.compile(r"^/wp-login\.php$", re.I),
]
SYSTEM_QUERY_KEYS = ("p", "s", "replytocom")
# URLs con medios: se extraen de src, srcset (lista separada por comas), og:image
# y CSS background(url(...)); cubre tanto URL absoluta como ruta relativa.
MEDIA_URL_RE = re.compile(r"""(https?://[^\s"'()]+/wp-content/uploads/[^\s"'()]+|/wp-content/uploads/[^\s"'()]+)""", re.I)

# Extensiones de medio real (mismas que build_redirects.py). Cualquier URL de
# /wp-content/uploads/ que NO termine en una de estas no es un medio migrable: es
# CSS/JS generado por un plugin, un placeholder sin resolver, etc.
EXTENSIONES_MEDIA_VALIDAS = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".avif", ".svg",
                             ".pdf", ".docx", ".xlsx", ".zip", ".mp4")
# Subcarpetas de /uploads/ que son artefactos de plugins (CSS generado, cachés,
# banners de consentimiento con placeholders sin resolver...), nunca medios reales.
RUTA_PLUGIN_BASURA = re.compile(
    r"/uploads/(complianz|elementor/css|cache|wpforms|wp-rocket|wc-logs|w3tc)/", re.I)


def es_medio_real(url):
    """True si la URL de /wp-content/uploads/ es un medio real que vale la pena
    registrar en media.json: sin comodines/placeholders sin resolver ({...}, *, %7B,
    espacios), fuera de carpetas de plugins, y con una extensión de medio válida."""
    if any(c in url for c in ("{", "}", "*", " ")) or "%7b" in url.lower():
        return False
    if RUTA_PLUGIN_BASURA.search(url):
        return False
    return url.lower().split("?")[0].endswith(EXTENSIONES_MEDIA_VALIDAS)


def es_sistema(url):
    """True si la URL es una ruta 'de sistema' de WordPress (no contenido)."""
    parsed = urlparse(url)
    if any(p.search(parsed.path) for p in SYSTEM_PATH_PATTERNS):
        return True
    qs = parsed.query
    if qs:
        keys = {kv.split("=", 1)[0] for kv in qs.split("&") if kv}
        if keys & set(SYSTEM_QUERY_KEYS):
            return True
    return False


def extraer_media_urls(h, base=""):
    """Devuelve el conjunto de URLs /wp-content/uploads/... presentes en el HTML
    (src, srcset, og:image, CSS background), normalizadas a URL absoluta. Filtra
    comodines/placeholders sin resolver y rutas de plugins (ver es_medio_real)."""
    if not h:
        return set()
    candidatas = {urljoin(base, u.strip().rstrip(",")) for u in MEDIA_URL_RE.findall(h)}
    return {u for u in candidatas if es_medio_real(u)}


def robots_disallow(base, delay):
    """Lee robots.txt y devuelve las rutas Disallow para User-agent: * (básico)."""
    st, body, _ = fetch(f"{base}/robots.txt", delay)
    disallowed = []
    if st == 200 and body:
        aplica = False
        for line in body.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if re.match(r"(?i)user-agent\s*:\s*\*", line):
                aplica = True
            elif re.match(r"(?i)user-agent\s*:", line):
                aplica = False
            elif aplica and re.match(r"(?i)disallow\s*:", line):
                ruta = line.split(":", 1)[1].strip()
                if ruta:
                    disallowed.append(ruta)
    return disallowed


def ruta_bloqueada(path, disallowed):
    return any(path.startswith(d) for d in disallowed)


def mismo_host(url, host):
    h = urlparse(url).netloc.lower()
    host = host.lower()
    return h == host or h == "www." + host or "www." + h == host or h.replace("www.", "") == host.replace("www.", "")


# ---------------------------------------------------------------------------
# Medición y consentimiento: IDs de tracking, CMP, verificaciones y formularios
# ---------------------------------------------------------------------------
TRACKING_PATTERNS = {
    "gtm": re.compile(r"\bGTM-[A-Z0-9]+\b"),
    "ga4": re.compile(r"\bG-[A-Z0-9]+\b"),
    "ads": re.compile(r"\bAW-[0-9]+\b"),
}
META_PIXEL_RE = re.compile(r"""fbq\(\s*['"]init['"]\s*,\s*['"](\d+)['"]""")
HOTJAR_RE = re.compile(r"""hjid\s*[:=]\s*(\d+)|hotjar\.com/c/hotjar-(\d+)""", re.I)
CLARITY_RE = re.compile(r"clarity\.ms/tag/([a-zA-Z0-9]+)")
LINKEDIN_RE = re.compile(r"""_linkedin_partner_id\s*=\s*["'](\d+)["']""")
CMP_MARCAS = {
    "Complianz": re.compile(r"complianz|cmplz", re.I),
    "CookieYes": re.compile(r"cookieyes|cky-consent", re.I),
    "Cookiebot": re.compile(r"consent\.cookiebot\.com|Cookiebot", re.I),
    "Iubenda": re.compile(r"iubenda\.com|_iub", re.I),
    "Borlabs": re.compile(r"BorlabsCookie|borlabs-cookie", re.I),
}
FORM_PLUGINS = {
    "Contact Form 7": re.compile(r'class="[^"]*\bwpcf7\b', re.I),
    "Elementor Forms": re.compile(r'class="[^"]*\belementor-form\b', re.I),
    "Gravity Forms": re.compile(r'class="[^"]*\bgform_wrapper\b|id="gform_\d+"', re.I),
    "WPForms": re.compile(r'class="[^"]*\bwpforms-form\b', re.I),
    "Divi": re.compile(r'class="[^"]*\bet_pb_contact_form\b', re.I),
}
FORM_TAG_RE = re.compile(r"(?is)<form\b[^>]*>(.*?)</form>")
FORM_FIELD_RE = re.compile(r'(?is)<(?:input|textarea|select)\b[^>]*\bname="([^"]+)"')
FORM_ACTION_RE = re.compile(r'(?is)<form\b[^>]*\baction="([^"]*)"')
THANKYOU_RE = re.compile(r"""["'](?:[^"']*(?:gracias|thank-?you)[^"']*)["']""", re.I)


def detectar_tracking(h, site):
    """IDs de tracking, CMP y verificaciones de propiedad presentes en el HTML de una página."""
    d = {"gtm": set(), "ga4": set(), "ads": set(), "meta_pixel": set(),
         "hotjar": set(), "clarity": set(), "linkedin": set(), "cmp": set(),
         "google_site_verification": set(), "msvalidate": set()}
    if not h:
        return d
    for clave, pat in TRACKING_PATTERNS.items():
        d[clave] |= set(pat.findall(h))
    d["meta_pixel"] |= set(META_PIXEL_RE.findall(h))
    d["hotjar"] |= {a or b for a, b in HOTJAR_RE.findall(h)}
    d["clarity"] |= set(CLARITY_RE.findall(h))
    d["linkedin"] |= set(LINKEDIN_RE.findall(h))
    for nombre, pat in CMP_MARCAS.items():
        if pat.search(h):
            d["cmp"].add(nombre)
    gsv = meta(h, r'<meta\s+name="google-site-verification"\s+content="([^"]*)"')
    if gsv:
        d["google_site_verification"].add(gsv)
    msv = meta(h, r'<meta\s+name="msvalidate\.01"\s+content="([^"]*)"')
    if msv:
        d["msvalidate"].add(msv)
    return d


def detectar_formularios(h, url):
    """Formularios de la página: plugin detectado, campos y URL de gracias si se ve."""
    encontrados = []
    if not h:
        return encontrados
    for bloque in FORM_TAG_RE.findall(h):
        plugin = next((nombre for nombre, pat in FORM_PLUGINS.items() if pat.search(bloque)), "desconocido/genérico")
        campos = sorted(set(FORM_FIELD_RE.findall(bloque)))
        gracias = ""
        m_thanks = THANKYOU_RE.search(bloque)
        if m_thanks:
            gracias = m_thanks.group(0).strip("\"'")
        encontrados.append({"plugin": plugin, "campos": campos, "gracias_detectada": gracias})
    return encontrados


def verificaciones_por_archivo(base, delay):
    """Comprueba BingSiteAuth.xml y sondea el patrón googleXXXXXXXX.html en la raíz."""
    out = {"bingsiteauth": False, "google_html_files": []}
    st, body, _ = fetch(f"{base}/BingSiteAuth.xml", delay)
    out["bingsiteauth"] = st == 200 and "<users>" in (body or "")
    return out


def leer_screaming_frog(fn):
    """Lee un export 'Internal HTML' de Screaming Frog y devuelve la lista de URLs (columna Address)."""
    urls = []
    with open(fn, encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        header = next(reader, [])
        idx = None
        for i, col in enumerate(header):
            if col.strip().lower() == "address":
                idx = i
                break
        if idx is None:
            return urls
        for row in reader:
            if len(row) > idx and row[idx].strip():
                urls.append(row[idx].strip())
    return urls


def _fetch_once(url, delay=0.0, raw=False):
    time.sleep(delay)
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read()
            return r.status, (body if raw else body.decode("utf-8", "ignore")), r.geturl()
    except urllib.error.HTTPError as e:
        return e.code, "", url
    except Exception as e:  # red, SSL, timeout
        return 0, str(e), url



def fetch(url, delay=0.0, raw=False):
    """Reintenta ante resets del firewall (status 0) o 429/503, con espera creciente.
    Caché en disco (MIG_HTML_CACHE): si la URL ya se descargó con 200, no se repite la petición."""
    import hashlib
    cache_dir = os.environ.get("MIG_HTML_CACHE")
    cfile = os.path.join(cache_dir, hashlib.md5(url.encode()).hexdigest() + ".html") if cache_dir else None
    if cfile and os.path.exists(cfile) and not ("raw" in locals() and raw):
        return 200, open(cfile, encoding="utf-8").read(), url
    for intento in range(5):
        res = _fetch_once(url, delay, raw)
        if res[0] not in (0, 429, 503):
            if cfile and res[0] == 200 and isinstance(res[1], str) and "<html" in res[1][:2000].lower():
                os.makedirs(cache_dir, exist_ok=True)
                open(cfile, "w", encoding="utf-8").write(res[1])
            return res
        time.sleep(3 * (intento + 1))
    return res

def api_all(base, endpoint, fields, delay):
    items, page = [], 1
    while True:
        st, body, _ = fetch(f"{base}/wp-json/wp/v2/{endpoint}?per_page=100&page={page}&_fields={fields}", delay)
        if st != 200:
            break
        try:
            batch = json.loads(body)
        except json.JSONDecodeError:
            break
        if not batch:
            break
        items += batch
        if len(batch) < 100:
            break
        page += 1
    return items


def sitemap_urls(base, delay):
    for idx in ("sitemap_index.xml", "wp-sitemap.xml", "sitemap.xml"):
        st, body, _ = fetch(f"{base}/{idx}", delay)
        if st == 200 and "<loc>" in body:
            locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", body)
            urls = []
            for loc in locs:
                if re.search(r"sitemap[^/]*\.xml", loc):
                    st2, b2, _ = fetch(loc, delay)
                    urls += re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", b2)
                else:
                    urls.append(loc)
            return [u for u in urls if not re.search(r"\.(jpe?g|png|webp|gif|svg|pdf)$", u, re.I)]
    return []


def meta(h, pattern):
    m = re.search(pattern, h, re.I | re.S)
    return html.unescape(m.group(1).strip()) if m else ""


def seo_of(h):
    return {
        "title": meta(h, r"<title[^>]*>(.*?)</title>"),
        "meta_description": meta(h, r'<meta\s+name="description"\s+content="([^"]*)"'),
        "canonical": meta(h, r'<link\s+rel="canonical"\s+href="([^"]*)"'),
        "robots": meta(h, r'<meta\s+name="robots"\s+content="([^"]*)"'),
        "og_title": meta(h, r'<meta\s+property="og:title"\s+content="([^"]*)"'),
        "og_description": meta(h, r'<meta\s+property="og:description"\s+content="([^"]*)"'),
        "og_image": meta(h, r'<meta[^>]+property="og:image"[^>]+content="([^"]*)"') or meta(h, r'<meta[^>]+content="([^"]*)"[^>]+property="og:image"'),
        "shortlink": meta(h, r'<link[^>]+rel="shortlink"[^>]+href="([^"]*)"') or meta(h, r'<link[^>]+href="([^"]*)"[^>]+rel="shortlink"'),
        "h1": re.sub(r"<[^>]+>", "", meta(h, r"<h1[^>]*>(.*?)</h1>")).strip(),
        "hreflang": sorted(set(re.findall(r'hreflang="([^"]+)"', h, re.I))),
        "hreflang_map": {l: u for u, l in re.findall(r'<link[^>]+href="([^"]+)"[^>]+hreflang="([^"]+)"', h, re.I)}
                        | {l: u for l, u in re.findall(r'<link[^>]+hreflang="([^"]+)"[^>]+href="([^"]+)"', h, re.I)},
        "jsonld_types": sorted(set(re.findall(r'"@type"\s*:\s*"([A-Za-z]+)"', h))),
    }


def html_to_md(fragment):
    # Elementor/Avada incrustan <style> y <script> dentro del contenido: fuera siempre
    fragment = re.sub(r"(?is)<(script|style|noscript|svg)[^>]*>.*?</\1>", "", fragment)
    fragment = re.sub(r"(?is)<!--.*?-->", "", fragment)
    try:
        from markdownify import markdownify
        md = markdownify(fragment, heading_style="ATX", strip=["script", "style"])
    except ImportError:
        s = re.sub(r"(?is)<(script|style|svg|noscript)[^>]*>.*?</\1>", "", fragment)
        for n in range(6, 0, -1):
            s = re.sub(rf"(?is)<h{n}[^>]*>(.*?)</h{n}>", lambda m: "\n\n" + "#" * n + " " + m.group(1) + "\n\n", s)
        s = re.sub(r'(?is)<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', r"[\2](\1)", s)
        s = re.sub(r'(?is)<img[^>]*src="([^"]+)"[^>]*?(?:alt="([^"]*)")?[^>]*>', r"![\2](\1)", s)
        s = re.sub(r"(?is)<li[^>]*>", "\n- ", s)
        s = re.sub(r"(?is)</?(p|div|section|br|tr|ul|ol)[^>]*>", "\n", s)
        s = re.sub(r"(?is)<(strong|b)[^>]*>(.*?)</\1>", r"**\2**", s)
        s = re.sub(r"<[^>]+>", "", s)
        md = html.unescape(s)
    md = re.sub(r"[ \t]+\n", "\n", md)
    md = re.sub(r"\n{3,}", "\n\n", md)
    return md.strip()


def slug_file(url, base):
    path = urlparse(url).path.strip("/") or "index"
    name = path.replace("/", "__")
    if len(name.encode()) > 180:  # rutas cirílicas codificadas: hash estable
        import hashlib
        name = name[:60] + "__" + hashlib.md5(path.encode()).hexdigest()[:12]
    return name + ".md"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("site")
    ap.add_argument("--out", default="migracion")
    ap.add_argument("--delay", type=float, default=0.3, help="pausa entre peticiones (subir si hay firewall)")
    ap.add_argument("--no-crawl", action="store_true", help="desactiva el rastreo de enlaces internos (activado por defecto)")
    ap.add_argument("--max-urls", type=int, default=2000, help="tope de URLs a visitar en el rastreo (por defecto 2000)")
    ap.add_argument("--screaming-frog", help="export 'Internal HTML' de Screaming Frog (CSV, columna Address) a fusionar")
    a = ap.parse_args()
    base = a.site.rstrip("/")
    os.makedirs(f"{a.out}/content", exist_ok=True)

    st, body, _ = fetch(f"{base}/wp-json/", a.delay)
    api_ok = st == 200 and body.strip().startswith("{")
    print(f"API REST: {'abierta' if api_ok else 'cerrada'}")

    items = []
    if api_ok:
        f = "id,slug,link,title,content,excerpt,date,modified,parent,categories,tags,author,featured_media,status"
        for kind in ("pages", "posts"):
            for it in api_all(base, kind, f, a.delay):
                items.append({"type": kind[:-1], "origen": "api", "id": it["id"], "url": it["link"],
                              "wp_title": html.unescape(it["title"]["rendered"]),
                              "content_html": it["content"]["rendered"],
                              "date": it.get("date"), "modified": it.get("modified"),
                              "categories": it.get("categories", []), "tags": it.get("tags", []),
                              "author": it.get("author"), "featured_media": it.get("featured_media")})
        cats = api_all(base, "categories", "id,name,slug,count", a.delay)
        tags = api_all(base, "tags", "id,name,slug,count", a.delay)
        media_api = api_all(base, "media", "id,source_url,alt_text,mime_type", a.delay)
    else:
        cats, tags, media_api = [], [], []

    smap = sitemap_urls(base, a.delay)
    known = {i["url"] for i in items}
    for u in smap:
        if u not in known:
            items.append({"type": "sitemap_only", "origen": "sitemap", "url": u, "content_html": None})
    known = {i["url"] for i in items}

    # Rastreo de enlaces internos (activado por defecto): descubre URLs que no
    # están ni en la API ni en el sitemap, y de paso cachea el HTML de cada página
    # visitada (se reutiliza abajo para no repetir peticiones).
    html_cache = {}
    grafo = {"inlinks": {}, "anchors": {}, "profundidad": {}}
    if not a.no_crawl:
        print(f"Rastreando enlaces internos desde {base} (máx. {a.max_urls} URLs)...")
        grafo = crawl_grafo(base, known, a.max_urls, a.delay)
        html_cache = grafo["html_cache"]
        for u in grafo["descubiertas"]:
            items.append({"type": "sistema" if es_sistema(u) else "crawl_only",
                          "origen": "crawl", "url": u, "content_html": None})
        known = {i["url"] for i in items}
        print(f"Rastreo: {len(grafo['descubiertas'])} URLs nuevas (no en sitemap/API). "
              f"Grafo de enlazado: {len(grafo['profundidad'])} URLs con profundidad conocida.")

    # Fusión de export "Internal HTML" de Screaming Frog (para sitios grandes o con JS)
    if a.screaming_frog:
        sf_urls = leer_screaming_frog(a.screaming_frog)
        nuevas_sf = 0
        for u in sf_urls:
            if u not in known:
                items.append({"type": "sistema" if es_sistema(u) else "screamingfrog_only",
                              "origen": "screamingfrog", "url": u, "content_html": None})
                nuevas_sf += 1
        known = {i["url"] for i in items}
        print(f"Screaming Frog: {nuevas_sf} URLs nuevas fusionadas desde {a.screaming_frog}.")

    media_urls_vistas = {}  # url_media -> set(paginas donde aparece)

    def registrar_media(pagina, urls):
        for mu in urls:
            media_urls_vistas.setdefault(mu, set()).add(pagina)

    tracking_global = {"gtm": set(), "ga4": set(), "ads": set(), "meta_pixel": set(),
                        "hotjar": set(), "clarity": set(), "linkedin": set(), "cmp": set(),
                        "google_site_verification": set(), "msvalidate": set()}
    formularios_por_url = {}

    for i, it in enumerate(items, 1):
        if it["url"] in html_cache:
            # ya se descargó durante el rastreo; nos ahorramos repetir la petición
            st, h, final = 200, html_cache[it["url"]], it["url"]
        else:
            st, h, final = fetch(it["url"], a.delay)
        it["status"] = st
        it["final_url"] = final
        it["in_sitemap"] = it["url"] in smap
        it["seo"] = seo_of(h) if h else {}
        if h:  # HTML integro: fuente para reconstruir bloques en la fase 3 (no se versiona)
            import hashlib
            os.makedirs(f"{a.out}/html_cache", exist_ok=True)
            it["html_file"] = "html_cache/" + hashlib.md5(it["url"].encode()).hexdigest() + ".html"
            open(f"{a.out}/{it['html_file']}", "w", encoding="utf-8").write(h)
        # wp_id: de la API si viene de ahí; si no, del <link rel="shortlink" href="...?p=ID">
        it["wp_id"] = it.get("id")
        if it["wp_id"] is None:
            m_sl = re.search(r"[?&]p=(\d+)", it["seo"].get("shortlink", "") or "")
            if m_sl:
                it["wp_id"] = int(m_sl.group(1))
        it["inlinks"] = sorted(grafo["inlinks"].get(it["url"], set()))
        it["anchors"] = grafo["anchors"].get(it["url"], [])[:10]
        it["profundidad"] = grafo["profundidad"].get(it["url"])
        if it["profundidad"] is None and it["url"].rstrip("/") == base.rstrip("/"):
            it["profundidad"] = 0
        if it.get("tipo") is None and es_sistema(it["url"]):
            it["tipo"] = "sistema"
        if h:
            td = detectar_tracking(h, base)
            for k in tracking_global:
                tracking_global[k] |= td[k]
            forms = detectar_formularios(h, it["url"])
            if forms:
                formularios_por_url[it["url"]] = forms
        if not it.get("content_html") and h:
            m = re.search(r"(?is)<main[^>]*>(.*?)</main>", h) or re.search(r"(?is)<body[^>]*>(.*?)</body>", h)
            it["content_html"] = m.group(1) if m else ""
        text = (it.get("wp_title", "") + " " + it["url"])
        it["spam_suspect"] = bool(SPAM_PATTERNS.search(text))
        rob = it["seo"].get("robots", "")
        it["indexable"] = it["status"] == 200 and "noindex" not in rob
        if h:
            registrar_media(it["url"], extraer_media_urls(h, base))
        if it.get("content_html"):
            md = html_to_md(it["content_html"])
            fn = slug_file(it["url"], base)
            fm = {"url": it["url"], "type": it["type"], **{k: it["seo"].get(k, "") for k in
                  ("title", "meta_description", "canonical", "robots", "og_image")},
                  "date": it.get("date"), "modified": it.get("modified")}
            os.makedirs(f"{a.out}/content", exist_ok=True)
            with open(f"{a.out}/content/{fn}", "w", encoding="utf-8") as fh:
                fh.write("---\n" + "\n".join(f"{k}: {json.dumps(v, ensure_ascii=False)}" for k, v in fm.items()) + "\n---\n\n" + md + "\n")
            it["content_file"] = f"content/{fn}"
        it.pop("content_html", None)
        print(f"[{i}/{len(items)}] {it['status']} {it['url']}")

    json.dump({"site": base, "api": api_ok, "items": items, "categories": cats, "tags": tags},
              open(f"{a.out}/inventory.json", "w"), ensure_ascii=False, indent=1)

    # media.json: medios de la API + todos los /wp-content/uploads/ vistos en el HTML,
    # cada uno con las páginas donde se usa (usada_en).
    media_final, vistos = [], set()
    for m in media_api:
        u = m.get("source_url", "")
        if not u or u in vistos or not es_medio_real(u):
            continue
        vistos.add(u)
        media_final.append({**m, "usada_en": sorted(media_urls_vistas.get(u, set()))})
    for u, paginas in media_urls_vistas.items():
        if u in vistos or not es_medio_real(u):
            continue
        vistos.add(u)
        media_final.append({"source_url": u, "usada_en": sorted(paginas)})
    json.dump(media_final, open(f"{a.out}/media.json", "w"), ensure_ascii=False, indent=1)
    media = media_final

    # migracion/tracking.json: IDs de medición, CMP, verificaciones de propiedad y formularios.
    verif_archivo = verificaciones_por_archivo(base, a.delay)
    tracking_out = {k: sorted(v) for k, v in tracking_global.items()}
    tracking_out["verificaciones_archivo"] = verif_archivo
    tracking_out["formularios"] = formularios_por_url
    json.dump(tracking_out, open(f"{a.out}/tracking.json", "w"), ensure_ascii=False, indent=1)

    # Informe
    idx = [i for i in items if i["indexable"]]
    noidx = [i for i in items if i["status"] == 200 and not i["indexable"]]
    spam = [i for i in items if i["spam_suspect"]]
    only_api = [i for i in items if i["type"] in ("page", "post") and not i["in_sitemap"]]
    only_map = [i for i in items if i["type"] == "sitemap_only"]
    rastreadas = [i for i in items if i.get("origen") in ("crawl", "screamingfrog")]
    sistema = [i for i in items if i.get("tipo") == "sistema"]
    empty_desc = [i for i in idx if not i["seo"].get("meta_description")]
    trunc = [i for i in idx if i["seo"].get("meta_description", "").rstrip().endswith(("...", "…", "[…]"))]
    broken = [i for i in items if i["status"] not in (200,)]
    langs = sorted({l for i in items for l in i["seo"].get("hreflang", [])})
    r = [f"# Informe de extracción · {base}", "",
         f"- API REST: {'abierta' if api_ok else 'cerrada'}",
         f"- URLs totales: {len(items)} · indexables: {len(idx)} · noindex: {len(noidx)} · errores: {len(broken)}",
         f"- Medios: {len(media)} · Categorías: {len(cats)} · Etiquetas: {len(tags)}",
         f"- Idiomas (hreflang): {', '.join(langs) if langs else 'monoidioma'}", ""]
    def sec(title, lst, fmt=lambda i: f"- {i['url']}"):
        r.extend([f"## {title} ({len(lst)})", *(fmt(i) for i in lst), ""])
    sec("⚠️ Sospecha de spam / hackeo → candidatas a 410", spam)
    sec("noindex (decidir: mantener noindex o 410)", noidx)
    sec("En la API pero no en el sitemap", only_api)
    sec("Solo en el sitemap", only_map)
    sec("URLs descubiertas por rastreo (no en sitemap)", rastreadas, lambda i: f"- [{i.get('origen')}] {i['url']}")
    sec("Rutas de sistema de WordPress detectadas (tipo: sistema)", sistema)
    sec("Errores HTTP", broken, lambda i: f"- {i['status']} {i['url']}")
    sec("Metadescripción vacía", empty_desc)
    sec("Metadescripción truncada", trunc)
    r.extend(["## Medición, consentimiento y formularios", "",
        f"- GTM: {', '.join(tracking_out['gtm']) or 'ninguno detectado'}",
        f"- GA4: {', '.join(tracking_out['ga4']) or 'ninguno detectado'}",
        f"- Google Ads (AW-): {', '.join(tracking_out['ads']) or 'ninguno detectado'}",
        f"- Meta Pixel: {', '.join(tracking_out['meta_pixel']) or 'ninguno detectado'}",
        f"- Hotjar: {', '.join(tracking_out['hotjar']) or 'ninguno detectado'}",
        f"- Clarity: {', '.join(tracking_out['clarity']) or 'ninguno detectado'}",
        f"- LinkedIn Insight: {', '.join(tracking_out['linkedin']) or 'ninguno detectado'}",
        f"- CMP detectado: {', '.join(tracking_out['cmp']) or 'ninguno (⚠️ revisar si hay consentimiento real)'}",
        f"- google-site-verification: {', '.join(tracking_out['google_site_verification']) or 'no encontrado'}",
        f"- msvalidate.01 (Bing): {', '.join(tracking_out['msvalidate']) or 'no encontrado'}",
        f"- BingSiteAuth.xml: {'presente' if verif_archivo['bingsiteauth'] else 'no encontrado'}",
        f"- Formularios detectados en {len(formularios_por_url)} URLs (ver migracion/tracking.json)",
        "",
        "⚠️ Pide al usuario: export JSON del contenedor GTM (si hay) y lista de conversiones",
        "configuradas en Google Ads/Meta, para comprobar en la fase 6 que todo sigue disparando",
        "tras la migración (ver `references/medicion-y-formularios.md`).", ""])
    open(f"{a.out}/REPORT.md", "w", encoding="utf-8").write("\n".join(r))
    print(f"\nListo. Revisa {a.out}/REPORT.md")


if __name__ == "__main__":
    sys.exit(main())
