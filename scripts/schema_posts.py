#!/usr/bin/env python3
"""Schema y migas de las ENTRADAS del blog, recuperados del WordPress, sin tocar el texto.
vc_pages.py (build_post) descartaba el JSON-LD propio de cada entrada (FAQPage, MedicalProcedure, MedicalWebPage,
VideoObject…) y las migas de Yoast. Este script lee el HTML original de cada entrada (migracion/html_cache o, si
falta, lo descarga) y escribe en el frontmatter del .md:
  breadcrumbs: [{name, path}]   (la BreadcrumbList de Yoast; la del layout la convierte en schema)
  schema: [{type, ...}]         (JSON-LD propio de la entrada, sin BreadcrumbList)
Idempotente: reescribe solo esas dos líneas. Uso: python scripts/schema_posts.py [ruta…]"""
import csv, glob, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from urllib.parse import unquote
from bs4 import BeautifulSoup
from wp_lib import BASE, html_of, rel

URL = {unquote(r["url"]): r["url"] for r in csv.DictReader(open("migracion/urls.csv", encoding="utf-8"))}
M = {unquote(r[0]).rstrip("/"): unquote(r[1]) for r in csv.reader(open("migracion/url-map.csv", encoding="utf-8")) if len(r) >= 2}


def final(p):
    """Ruta final de una miga (sin pasar por redirecciones)."""
    k, seen = unquote(p).rstrip("/"), set()
    while k in M and k not in seen:
        seen.add(k)
        k = unquote(M[k]).rstrip("/")
    return k + "/"
OWN = ("FAQPage", "VideoObject", "MedicalProcedure", "MedicalWebPage", "MedicalOrganization", "Service", "Product", "Event")


def nodes(d):
    if isinstance(d, list):
        for x in d:
            yield from nodes(x)
    elif isinstance(d, dict):
        if "@graph" in d:
            yield from nodes(d["@graph"])
        else:
            yield d


def extraer(html):
    s = BeautifulSoup(html, "html.parser")
    listas, own = [], []
    for sc in s.find_all("script", type="application/ld+json"):
        try:
            d = json.loads(sc.get_text())
        except Exception:
            continue
        for n in nodes(d):
            t = n.get("@type")
            if t == "BreadcrumbList":
                listas.append([{"name": li.get("name"), "path": rel(li.get("item")) if li.get("item") else None}
                               for li in n.get("itemListElement", [])])
            elif t in OWN or (isinstance(t, list) and set(t) & set(OWN)):
                n = dict(n)
                n.pop("@context", None)
                own.append({"type": n.pop("@type"), **n})
    # el WordPress publica dos BreadcrumbList (Yoast y la del bloque .mpost): se queda la más completa
    crumbs = max(listas, key=len) if listas else []
    return crumbs, own


def escribir(md, path, crumbs, own):
    raw = open(md, encoding="utf-8").read()
    _, fm, body = raw.split("---", 2)
    lines = [l for l in fm.strip("\n").split("\n") if not l.startswith(("schema: ", "breadcrumbs: "))]
    if len(crumbs) > 1:
        lines.append("breadcrumbs: " + json.dumps([{"name": c["name"], "path": final(c["path"] or path)} for c in crumbs], ensure_ascii=False))
    if own:
        lines.append("schema: " + json.dumps(own, ensure_ascii=False))
    open(md, "w", encoding="utf-8").write("---\n" + "\n".join(lines) + "\n---" + body)


if __name__ == "__main__":
    solo = set(sys.argv[1:])
    n = 0
    for md in sorted(glob.glob("src/content/posts/*/*.md")):
        fm = open(md, encoding="utf-8").read().split("---")[1]
        path = json.loads(re.search(r"^path: (.*)$", fm, re.M).group(1))
        if solo and path not in solo:
            continue
        url = URL.get(path) or URL.get(path.rstrip("/"))
        if not url:
            print("sin fila en urls.csv:", path)
            continue
        crumbs, own = extraer(html_of(BASE + url))
        escribir(md, path, crumbs, own)
        n += 1
        print(n, path, len(crumbs), "migas ·", [o["type"] for o in own], flush=True)
