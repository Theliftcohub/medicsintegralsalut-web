#!/usr/bin/env python3
"""Enlaces internos del contenido -> URL final (sin pasar por redirecciones). Se ejecuta tras vc_pages.py y redirects_contract.py.
- href a una URL con 301 en migracion/url-map.csv -> su destino final.
- href a una URL 410 -> se quita el enlace y se deja el texto.
Recorre src/content/pages/**/*.json y src/content/posts/**/*.md."""
import csv, glob, json, os, re
from urllib.parse import unquote
M = {}
for row in csv.reader(open("migracion/url-map.csv")):
    if len(row) >= 2:
        M[unquote(row[0]).rstrip("/")] = unquote(row[1])
GONE = {unquote(l.strip()).rstrip("/") for l in open("migracion/gone.txt") if l.strip()}


def fin(h):
    base, frag = (h.split("#", 1) + [""])[:2]
    k = unquote(base).rstrip("/")
    seen = set()
    while k in M and k not in seen:
        seen.add(k)
        base = M[k]
        k = unquote(base).rstrip("/")
    return base + ("#" + frag if frag else "")


# enlaces que ya estaban rotos en el WordPress (404 hoy, fuera del contrato): destino evidente o se quita el enlace
EXTRA = {"/ca/portfolio_page": "/ca/portfoli_pagina/"}
for ln, pre in [("es", "/portfolio_page/"), ("en", "/en/portfolio_page/"), ("ca", "/ca/portfoli_pagina/"), ("fr", "/fr/page_de_portfolio/"),
                ("ru", "/ru/портфолио/"), ("uk", "/uk/portfolio_page/")]:
    EXTRA[(pre + "botoox-mike-lidia").rstrip("/")] = pre + "video-prueba-4/"
M.update(EXTRA)


def existe(h):
    q = unquote(h.split("#")[0])
    return os.path.exists("dist" + q.rstrip("/") + "/index.html") or os.path.exists("public" + q) or q in ("/",)


def vivo(h):
    """Campo de enlace de un bloque (menú, tarjeta, miga): si el destino no existe, la primera página ascendente que sí."""
    if not os.path.isdir("dist") or existe(h):
        return h
    parts = unquote(h.split("#")[0]).strip("/").split("/")
    while parts:
        parts.pop()
        c = "/" + "/".join(parts) + "/" if parts else "/"
        if existe(c):
            return c
    return h


cambios = quitados = 0
A = re.compile(r'<a\b([^>]*?)href=(\\?")(/[^"\\]*)(\\?")([^>]*)>(.*?)</a>', re.S)


def rep(m):
    global cambios, quitados
    href = m.group(3)
    k = unquote(href.split("#")[0]).rstrip("/")
    if k in GONE:
        quitados += 1
        return m.group(6)
    n = fin(href)
    if os.path.isdir("dist") and not existe(n):
        quitados += 1  # destino inexistente también en el WordPress: se deja el texto sin enlace
        return m.group(6)
    if n != href:
        cambios += 1
        return f'<a{m.group(1)}href={m.group(2)}{n}{m.group(4)}{m.group(5)}>{m.group(6)}</a>'
    return m.group(0)


for f in glob.glob("src/content/pages/**/*.json", recursive=True) + glob.glob("src/content/posts/**/*.md", recursive=True) + ["src/data/vc-chrome.json"]:
    s = open(f, encoding="utf-8").read()
    n = A.sub(rep, s)
    if f.endswith(".json"):  # enlaces sueltos en campos href/path de los bloques y migas
        n = re.sub(r'("(?:href|path)": ")(/[^"]*)(")', lambda m: m.group(1) + vivo(fin(m.group(2))) + m.group(3), n)
    if n != s:
        open(f, "w", encoding="utf-8").write(n)
print("enlaces reescritos:", cambios, "· enlaces a 410 quitados:", quitados)
