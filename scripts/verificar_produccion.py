#!/usr/bin/env python3
"""Verificación estática de la build de PRODUCCIÓN (dist/ de `npm run build:produccion`) antes de subirla a Plesk.
No necesita servidor: simula el .htaccess de Apache con el contrato de URLs y revisa el HTML generado.
Comprueba:
  páginas     title, description, un H1, canonical absoluto con www, robots, lang, og:image existente
  canonical   propio = en el sitemap; ajeno = fuera del sitemap y apuntando a una página que existe
  hreflang    destinos existentes, recíprocos y con x-default
  schema      JSON-LD válido; BlogPosting completo; migas a URLs existentes; sin AggregateRating
  enlaces     internos a páginas/archivos existentes, nunca a una URL que redirige o es 410
  imágenes    src existente y atributo alt presente
  sitemap     solo URLs existentes, indexables y con canonical propio; y todas ellas están
  contrato    «mantener» construidas; 301 y 410 resueltos por el .htaccess tal y como dice el contrato, sin cadenas
Uso: npm run build:produccion && python scripts/verificar_produccion.py   (sale con código 1 si hay errores)"""
import csv, json, os, re, sys
from collections import defaultdict
from urllib.parse import unquote, urlparse

SITE = "https://www.medicsintegralsalut.com"
D = "dist"
E, W = defaultdict(list), defaultdict(list)  # errores y avisos

paginas = {}
for raiz, _, fs in os.walk(D):
    if "index.html" in fs:
        p = "/" + os.path.relpath(raiz, D).replace(os.sep, "/") + "/"
        paginas["/" if p == "/./" else p] = open(os.path.join(raiz, "index.html"), encoding="utf-8").read()
M = {unquote(r[0]).rstrip("/"): unquote(r[1]) for r in csv.reader(open("migracion/url-map.csv", encoding="utf-8")) if len(r) >= 2}
GONE = {unquote(l.strip()).rstrip("/") for l in open("migracion/gone.txt", encoding="utf-8") if l.strip()}


def existe(ruta):
    q = unquote(ruta.split("#")[0].split("?")[0])
    return q in paginas or os.path.isfile(D + q) or os.path.isfile(D + q.rstrip("/") + "/index.html")


def meta(h, nombre, attr="name"):
    m = re.search(rf'<meta[^>]+{attr}="{re.escape(nombre)}"[^>]*content="([^"]*)"', h) or re.search(rf'<meta[^>]+content="([^"]*)"[^>]*{attr}="{re.escape(nombre)}"', h)
    return m.group(1) if m else None


CATALAN_RAIZ = set(json.load(open("migracion/catalan_raiz_resultado.json", encoding="utf-8"))["declaradas_catalan"]) if os.path.exists("migracion/catalan_raiz_resultado.json") else set()
sitemap = {unquote(urlparse(u).path) for u in re.findall(r"<loc>([^<]+)</loc>", open(f"{D}/sitemap-0.xml", encoding="utf-8").read())}
hl = {}
for p, h in paginas.items():
    if p in ("/404/", "/410/"):
        continue
    head = h.split("</head>")[0]
    if not re.search(r"<title>[^<]+</title>", head): E["sin title"].append(p)
    if not meta(head, "description"): W["sin meta description (literal del WordPress)"].append(p)
    n = len(re.findall(r"<h1[\s>]", h))
    if n != 1: E[f"H1 = {n}"].append(p)
    rob = meta(head, "robots") or ""
    can = re.search(r'<link rel="canonical" href="([^"]+)"', head)
    can = can.group(1) if can else None
    if not can or not can.startswith(SITE + "/"): E["canonical ausente o sin https://www"].append((p, can)); continue
    cp = unquote(urlparse(can).path)
    lang = p.split("/")[1] if len(p.split("/")[1]) == 2 and p.split("/")[1] in ("ca", "en", "fr", "ru", "uk") else "es"
    if p in CATALAN_RAIZ: lang = "ca"   # páginas en catalán que viven en la raíz (decisión 05/10/2026)
    if f'<html lang="{lang}"' not in h: E["lang del <html> no coincide con la URL"].append(p)
    og = meta(head, "og:image", "property")
    if og and og.startswith(SITE) and not existe(urlparse(og).path): E["og:image inexistente"].append((p, og))
    noindex = "noindex" in rob
    if cp == p:
        if not noindex and p not in sitemap: E["indexable con canonical propio fuera del sitemap"].append(p)
    else:
        if p in sitemap: E["canonical ajeno pero en el sitemap"].append(p)
        if cp not in paginas: E["canonical a una página que no existe"].append((p, cp))
        elif cp.rstrip("/") in M or cp.rstrip("/") in GONE: E["canonical a una URL que redirige o es 410"].append((p, cp))
    if noindex: W["noindex (revisar que sea intencionado)"].append(p)
    alt = {l: unquote(urlparse(u).path) for l, u in re.findall(r'<link rel="alternate" hreflang="([^"]+)" href="([^"]+)"', head)}
    if alt:
        hl[p] = alt
        if "x-default" not in alt: E["hreflang sin x-default"].append(p)
        for l, u in alt.items():
            if u not in paginas: E["hreflang a página inexistente"].append((p, l, u))
    for bloque in re.findall(r'<script type="application/ld\+json">(.*?)</script>', h, re.S):
        try:
            d = json.loads(bloque)
        except Exception:
            E["JSON-LD inválido"].append(p); continue
        nodos = d.get("@graph", [d]) if isinstance(d, dict) else d
        for x in nodos:
            t = x.get("@type")
            if t == "AggregateRating" or "aggregateRating" in x: E["AggregateRating"].append(p)
            if t == "BlogPosting":
                for k in ("headline", "datePublished", "author", "image"):
                    if not x.get(k): E[f"BlogPosting sin {k}"].append(p)
            if t == "BreadcrumbList":
                for li in x.get("itemListElement", []):
                    u = unquote(urlparse(li.get("item", "")).path)
                    if u not in paginas: E["miga a página inexistente"].append((p, u))
    cuerpo = h.split("<body", 1)[-1]
    for href in re.findall(r'<a\b[^>]*href="(/[^"#?]*)', cuerpo):
        q = unquote(href)
        if q.startswith("/_astro/"): continue
        k = q.rstrip("/")
        if k in M: E["enlace interno a URL que redirige"].append((p, q))
        elif k in GONE: E["enlace interno a 410"].append((p, q))
        elif not existe(q): E["enlace interno roto"].append((p, q))
    for tag in re.findall(r"<img\b[^>]*>", cuerpo):
        src = re.search(r'src="([^"]+)"', tag)
        if src and src.group(1).startswith("/") and not existe(src.group(1)): E["imagen inexistente"].append((p, src.group(1)))
        if " alt=" not in tag: E["imagen sin atributo alt"].append((p, src.group(1) if src else tag[:60]))
canon = {}
for p, h in paginas.items():
    c = re.search(r'<link rel="canonical" href="([^"]+)"', h)
    canon[p] = (unquote(urlparse(c.group(1)).path) if c else None, "noindex" in (meta(h.split("</head>")[0], "robots") or ""))
for p, alt in hl.items():
    for l, u in alt.items():
        if u in canon and (canon[u][0] != u or canon[u][1]): E["hreflang a página no canónica o noindex"].append((p, l, u))
        if l != "x-default" and u != p and u in hl and p not in hl[u].values(): E["hreflang no recíproco"].append((p, u))
for u in sitemap:
    if u not in paginas: E["sitemap con URL inexistente"].append(u)

# ---- contrato vs .htaccess (Apache: primera RewriteRule que casa, sin RewriteCond) ----
reglas, cond = [], False
for linea in open(f"{D}/.htaccess", encoding="utf-8"):
    l = linea.strip()
    if l.startswith("RewriteCond"):
        cond = True; continue
    m = re.match(r"RewriteRule\s+(\S+)\s+(\S+)\s+\[([^\]]+)\]", l)
    if m:
        if not cond:
            reglas.append((re.compile(m.group(1)), unquote(m.group(2)), m.group(3)))
        cond = False


def apache(ruta):
    r = unquote(ruta).lstrip("/")
    for rx, dst, fl in reglas:
        if rx.search(r):
            return ("410", None) if "G" in fl.split(",") else ("301", dst)
    return ("200", None)


for fila in csv.DictReader(open("migracion/urls.csv", encoding="utf-8")):
    u, dec = fila["url"] or "/", fila["decision"]
    ud = unquote(u)
    if dec == "mantener":
        if ud.startswith("/wp-content/"):
            if apache(ud)[0] != "301": E["medio «mantener» sin redirección a su copia"].append(ud)
        elif ud.endswith("/") and not existe(ud):
            E["URL «mantener» sin página"].append(ud)
    elif dec == "301":
        est, dst = apache(ud)
        if est != "301": E[f"301 del contrato que Apache sirve como {est}"].append(ud); continue
        k = dst.split("?")[0].rstrip("/")
        esperado, visto = ud.rstrip("/"), set()
        while esperado in M and esperado not in visto:
            visto.add(esperado)
            esperado = unquote(M[esperado]).rstrip("/")
        if not dst.startswith("http") and k != esperado and ud.rstrip("/") in M:
            E["301 a un destino distinto del contrato"].append((ud, dst, esperado + "/"))
        if not dst.startswith("http"):
            if k in M or k in GONE: E["cadena: el destino vuelve a redirigir"].append((ud, dst))
            elif not existe(dst): E["301 a destino inexistente"].append((ud, dst))
    elif dec == "410":
        if apache(ud)[0] != "410": E["410 del contrato que Apache no sirve como 410"].append(ud)

print(f"Páginas revisadas: {len(paginas)} · en el sitemap: {len(sitemap)} · reglas Apache: {len(reglas)}")
for k, v in sorted(W.items()):
    print(f"AVISO  {k}: {len(v)}  {v[:3]}")
for k, v in sorted(E.items()):
    print(f"ERROR  {k}: {len(v)}  {v[:5]}")
print("RESULTADO:", "OK, sin errores" if not E else f"{sum(len(v) for v in E.values())} errores")
sys.exit(1 if E else 0)
