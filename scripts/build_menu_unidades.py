#!/usr/bin/env python3
"""Submenú «Unidades» de la cabecera -> clave `units` de src/data/vc-chrome.json (los 6 idiomas).
Etiquetas LITERALES del menú del WordPress (Bridge, nav.main_menu > li[2]). Cada enlace se lleva a su URL final
(migracion/url-map.csv, sin pasar por redirecciones); los que acaban en 410 o en una página que no existe se quitan
y se listan al final. Se ejecuta después de build_chrome_vc.py.
Uso: python scripts/build_menu_unidades.py"""
import csv, glob, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from urllib.parse import unquote
from wp_lib import soup, text, rel

LANGS = ["es", "ca", "en", "fr", "ru", "uk"]
M = {unquote(r[0]).rstrip("/"): unquote(r[1]) for r in csv.reader(open("migracion/url-map.csv", encoding="utf-8")) if len(r) >= 2}
GONE = {unquote(l.strip()).rstrip("/") for l in open("migracion/gone.txt", encoding="utf-8") if l.strip()}
PATHS = set()
for f in glob.glob("src/content/pages/*/*.json"):
    PATHS.add(json.load(open(f, encoding="utf-8"))["path"])
for f in glob.glob("src/content/posts/*/*.md"):
    m = re.search(r"^path: (.*)$", open(f, encoding="utf-8").read().split("---")[1], re.M)
    PATHS.add(json.loads(m.group(1)))
quitados = []


def final(href):
    """Ruta final de un enlace del menú, o None si va a 410 o a una página inexistente."""
    k = unquote(rel(href) or "").split("#")[0].rstrip("/")
    seen = set()
    while k in M and k not in seen:
        seen.add(k)
        k = unquote(M[k]).rstrip("/")
    p = k + "/"
    return None if k in GONE or p not in PATHS else p


def items(ul, L):
    out = []
    for li in ul.find_all("li", recursive=False):
        a = li.find("a", recursive=False)
        sub = li.find("div", class_="second", recursive=False)
        sub = sub.find("ul") if sub else li.find("ul", recursive=False)
        it = {"text": text(a), "href": final(a.get("href"))}
        if it["href"] is None:
            quitados.append((L, it["text"], unquote(a.get("href") or "")))
        if sub:
            it["sub"] = items(sub, L)
        if it["href"] or it.get("sub"):
            out.append(it)
    return out


chrome = json.load(open("src/data/vc-chrome.json", encoding="utf-8"))
for L in LANGS:
    s = soup("https://www.medicsintegralsalut.com/" + ("" if L == "es" else L + "/"))
    unidades = s.select_one("nav.main_menu").find("ul").find_all("li", recursive=False)[2]
    sub = unidades.find("div", class_="second")
    chrome[L]["units"] = items(sub.find("ul") if sub else unidades.find("ul"), L)
    n = sum(1 + len(c.get("sub", [])) + sum(len(x.get("sub", [])) for x in c.get("sub", [])) for c in chrome[L]["units"])
    print(L, len(chrome[L]["units"]), "unidades ·", n, "enlaces")
json.dump(chrome, open("src/data/vc-chrome.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
for q in quitados:
    print("quitado (410 o sin página):", *q)
