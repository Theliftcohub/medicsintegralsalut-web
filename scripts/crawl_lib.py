#!/usr/bin/env python3
"""
Rastreador de enlazado interno compartido entre extract_wp.py (la web vieja) y
validate_migration.py (la web nueva, para el diff de enlazado interno de la fase 6).

Es la misma función, movida aquí para no duplicarla: BFS por <a href>, respetando
robots.txt básico, que calcula para cada URL visitada quién le enlaza (`inlinks`),
con qué texto (`anchors`, máx. 10) y a cuántos clics de la portada está (`profundidad`).
"""
import html, os, re, time, urllib.request, urllib.error
from collections import deque
from urllib.parse import urlparse, urljoin

UA = {"User-Agent": "Mozilla/5.0 (TheLiftCo migration audit)"}


def _fetch_once(url, delay=0.0):
    time.sleep(delay)
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode("utf-8", "ignore"), r.geturl()
    except urllib.error.HTTPError as e:
        return e.code, "", url
    except Exception as e:
        return 0, str(e), url



def fetch(url, delay=0.0):
    """Reintenta ante resets del firewall (status 0) o 429/503, con espera creciente.
    Caché en disco (MIG_HTML_CACHE): si la URL ya se descargó con 200, no se repite la petición."""
    import hashlib
    cache_dir = os.environ.get("MIG_HTML_CACHE")
    cfile = os.path.join(cache_dir, hashlib.md5(url.encode()).hexdigest() + ".html") if cache_dir else None
    if cfile and os.path.exists(cfile) and not ("raw" in locals() and raw):
        return 200, open(cfile, encoding="utf-8").read(), url
    for intento in range(5):
        res = _fetch_once(url, delay)
        if res[0] not in (0, 429, 503):
            if cfile and res[0] == 200 and isinstance(res[1], str) and "<html" in res[1][:2000].lower():
                os.makedirs(cache_dir, exist_ok=True)
                open(cfile, "w", encoding="utf-8").write(res[1])
            return res
        time.sleep(3 * (intento + 1))
    return res

def robots_disallow(base, delay):
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


def crawl_grafo(base, conocidas, max_urls, delay):
    """Ver docstring del módulo. `conocidas` es un set de URLs ya sabidas (no se cuentan como
    'descubiertas' aunque se visiten). Devuelve dict con descubiertas/html_cache/inlinks/anchors/profundidad."""
    host = urlparse(base).netloc
    disallowed = robots_disallow(base, delay)
    visitadas = set()
    cola = deque([(base, 0)])
    descubiertas, html_cache = [], {}
    inlinks, anchors, profundidad = {}, {}, {}
    while cola and len(visitadas) < max_urls:
        url, depth = cola.popleft()
        if url in visitadas:
            continue
        visitadas.add(url)
        profundidad.setdefault(url, depth)
        path = urlparse(url).path or "/"
        if ruta_bloqueada(path, disallowed):
            continue
        st, h, final = fetch(url, delay)
        if url not in conocidas and url != base:
            descubiertas.append(url)
        if st != 200 or not h:
            continue
        html_cache[url] = h
        for href, texto_html in re.findall(r'(?is)<a\s[^>]*href="([^"#]+)"[^>]*>(.*?)</a>', h):
            full = urljoin(url, href).split("#")[0]
            if not mismo_host(full, host) or full == url:
                continue
            inlinks.setdefault(full, set()).add(url)
            texto = re.sub(r"(?is)<[^>]+>", " ", texto_html)
            texto = html.unescape(re.sub(r"\s+", " ", texto)).strip()
            lista = anchors.setdefault(full, [])
            if texto and texto not in lista and len(lista) < 10:
                lista.append(texto)
            if full not in visitadas and len(visitadas) + len(cola) < max_urls * 3:
                cola.append((full, depth + 1))
    return {"descubiertas": descubiertas, "html_cache": html_cache,
            "inlinks": inlinks, "anchors": anchors, "profundidad": profundidad}
