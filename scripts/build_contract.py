#!/usr/bin/env python3
"""
Genera migracion/urls.csv (contrato de URLs) desde inventory.json.

Uso:
  python3 build_contract.py migracion/inventory.json [--out migracion/urls.csv] \
      [--ahrefs migracion/ahrefs.json] [--sin-rss]

Decisión por defecto:
- 200 e indexable            -> mantener (misma URL, estado 200)
- sospecha de spam           -> 410
- noindex                    -> REVISAR (el usuario decide: mantener con noindex o 410)
- error HTTP en el original  -> REVISAR

Rutas "de sistema" de WordPress (campo tipo/inventory "sistema", ver extract_wp.py):
- /page/N/ y */page/N/            -> 301 a la raíz de la lista (se quita el /page/N/)
- /feed/ y */feed/                -> 301 a /rss.xml (o 410 con --sin-rss)
- category/tag/author             -> 301 a /blog/ (o a la raíz "/" si no hay blog)
- wp-json, xmlrpc.php, wp-login.php -> 410
- ?p=, ?s=, ?replytocom=          -> 301 a la ruta limpia (sin la query)

Con --ahrefs: si backlinks>0 y la decisión propuesta era 410, se cambia a 301
(a la raíz "/") y se marca nota "tiene backlinks". Nunca se manda a 410 una URL
con backlinks reales sin que el usuario lo vea primero.

Con --gsc gsc.csv (export de Search Console: página, clics, impresiones): cualquier
URL "de sistema" (category/tag/author/page) o marcada 410 que tenga impresiones>100
o clics>0 pasa a REVISAR con una nota explicando por qué (Google la sigue mostrando;
que el usuario decida en persona en vez de perderla en silencio). Rellena además la
columna `trafico` con los clics de GSC cuando --ahrefs no ha traído ese dato.

Las filas REVISAR bloquean el lanzamiento hasta que se decidan.
"""
import argparse, csv, json, re
from urllib.parse import urlparse


def leer_gsc(fn):
    """Lee un export de Search Console (columnas: página/page/url, clics/clicks,
    impresiones/impressions) y lo indexa por ruta (path)."""
    datos = {}
    with open(fn, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            claves = {k.strip().lower(): k for k in row}
            col_url = claves.get("página") or claves.get("pagina") or claves.get("page") or claves.get("url")
            col_clics = claves.get("clics") or claves.get("clicks")
            col_impr = claves.get("impresiones") or claves.get("impressions")
            if not col_url:
                continue
            url = row[col_url].strip()
            path = urlparse(url).path or url
            try:
                clics = float((row.get(col_clics) or "0").replace(",", "."))
            except ValueError:
                clics = 0.0
            try:
                impresiones = float((row.get(col_impr) or "0").replace(",", "."))
            except ValueError:
                impresiones = 0.0
            datos[path] = {"clics": clics, "impresiones": impresiones}
    return datos

SISTEMA_PAGE = re.compile(r"/page/\d+/?$", re.I)
SISTEMA_FEED = re.compile(r"(^|/)(comments/)?feed/?$", re.I)
SISTEMA_TAXO = re.compile(r"^/(blog/)?(category|tag|author)(/|$)", re.I)
SISTEMA_BLOQUEO = re.compile(r"^/(wp-json|xmlrpc\.php|wp-login\.php)", re.I)


def decision_sistema(path, query, sin_rss):
    """Decisión por defecto (B) para una URL 'de sistema' de WordPress."""
    if SISTEMA_PAGE.search(path):
        raiz = re.sub(r"/page/\d+/?$", "/", path) or "/"
        return "301", raiz, "301"
    if SISTEMA_FEED.search(path):
        return ("410", "", "410") if sin_rss else ("301", "/rss.xml", "301")
    if SISTEMA_TAXO.search(path):
        return "301", "/blog/", "301"
    if SISTEMA_BLOQUEO.search(path):
        return "410", "", "410"
    for clave in ("p", "s", "replytocom"):
        if query and re.search(rf"(^|&){clave}=", query):
            limpio = path or "/"
            return "301", limpio, "301"
    return "REVISAR", "", ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("inventory")
    ap.add_argument("--out", default="migracion/urls.csv")
    ap.add_argument("--ahrefs", help="JSON {url: {backlinks, trafico}} (ver references/ahrefs-y-crawl.md)")
    ap.add_argument("--gsc", help="export de Search Console (página, clics, impresiones): revisa sistema/410 con tráfico real")
    ap.add_argument("--sin-rss", action="store_true", help="sin feed RSS en la nueva web: /feed/ -> 410 en vez de 301 a /rss.xml")
    a = ap.parse_args()
    inv = json.load(open(a.inventory))
    ahrefs = json.load(open(a.ahrefs)) if a.ahrefs else {}
    gsc = leer_gsc(a.gsc) if a.gsc else {}

    rows, counts = [], {}
    for it in inv["items"]:
        parsed = urlparse(it["url"])
        path = parsed.path
        backlinks = ahrefs.get(it["url"], {}).get("backlinks", "")
        trafico = ahrefs.get(it["url"], {}).get("trafico", "")
        nota = ""
        if it.get("tipo") == "sistema":
            d, dst, st = decision_sistema(path, parsed.query, a.sin_rss)
        elif it.get("spam_suspect"):
            d, dst, st = "410", "", "410"
        elif it.get("indexable"):
            d, dst, st = "mantener", path, "200"
        else:
            d, dst, st = "REVISAR", "", ""
        if d == "410" and backlinks not in ("", None) and int(backlinks) > 0:
            d, dst, st = "301", "/", "301"
            nota = "tiene backlinks"
        gsc_fila = gsc.get(path)
        if gsc_fila and (it.get("tipo") == "sistema" or d == "410") and \
                (gsc_fila["impresiones"] > 100 or gsc_fila["clics"] > 0):
            d, dst, st = "REVISAR", dst, st
            nota = (nota + "; " if nota else "") + \
                f"GSC: {int(gsc_fila['clics'])} clics / {int(gsc_fila['impresiones'])} impresiones — no perder en silencio"
        if trafico in ("", None) and gsc_fila:
            trafico = int(gsc_fila["clics"])
        counts[d] = counts.get(d, 0) + 1
        rows.append({"url": path, "decision": d, "destino": dst, "estado_esperado": st,
                     "title": it.get("seo", {}).get("title", ""), "robots": it.get("seo", {}).get("robots", ""),
                     "tipo": it.get("tipo") or it.get("type", ""), "backlinks": backlinks, "trafico": trafico,
                     "notas": nota})
    with open(a.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    print(f"{a.out}: " + ", ".join(f"{k}={v}" for k, v in counts.items()))
    if counts.get("REVISAR"):
        print("⚠️  Hay filas REVISAR: el usuario debe decidir antes de lanzar.")


if __name__ == "__main__":
    main()
