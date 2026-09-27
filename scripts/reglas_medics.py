#!/usr/bin/env python3
"""Reglas propias de Medics sobre migracion/urls.csv (se ejecuta después de build_contract.py
y contrato_extra.py). Todo lo que no es regla de sistema queda REVISAR con destino PROPUESTO
en la columna `destino` y la palabra PROPUESTA en `notas`: nadie decide en silencio."""
import csv, json, re, os
from urllib.parse import unquote, urlparse
R = "migracion/urls.csv"
rows = list(csv.DictReader(open(R, encoding="utf-8")))
inv = json.load(open("migracion/inventory.json"))["items"]
i18n = json.load(open("migracion/i18n-map.json"))
U = lambda p: unquote(p)
def lang(p):
    s = p.split("/"); return s[1] if len(s) > 1 and s[1] in ("ca", "en", "fr", "ru", "uk") else "es"
def grupo_de(es_path):
    for g in i18n.values():
        if U(g.get("es", "")) == es_path: return {k: v for k, v in g.items()}
    return {"es": es_path}
BLOG, PRIV, EQUIPO = grupo_de("/blog/"), grupo_de("/politica-de-privacidad/"), grupo_de("/cirugia-plastica-girona-equipo-medico/")
home = lambda l: "/" if l == "es" else f"/{l}/"
nota = lambda r, t: r.__setitem__("notas", (r["notas"] + "; " if r["notas"] else "") + t)

# 0) filas duplicadas (mismo path) -> una
vistos, dedup = set(), []
for r in rows:
    k = U(r["url"]).lower()
    if k in vistos: continue
    vistos.add(k); dedup.append(r)
rows = dedup
por_path = {U(r["url"]): r for r in rows}
canon = {U(urlparse(i["url"]).path): U(urlparse(i["seo"]["canonical"]).path) for i in inv
         if i.get("status") == 200 and i.get("seo", {}).get("canonical")}
estado = {U(urlparse(i["url"]).path): i.get("status") for i in inv}

TAXO = re.compile(r"^/(ca|en|fr|ru|uk)/(categoria|category|categorie|категория|категорія|tag|etiqueta|etiquette|метка|мітка|autor|author|auteur|автор)(/|$)", re.I)
PAG = re.compile(r"/(page|pagina|страница|сторінка)/\d+/?$", re.I)
for r in rows:
    p, l = U(r["url"]), lang(U(r["url"]))
    if urlparse(r["url"]).query or "?" in r["url"]:
        r["decision"], r["destino"], r["estado_esperado"] = "ignorar", "", ""
        nota(r, "variante con parámetros (utm): Apache sirve la misma página; NUNCA redirigir utm"); continue
    if "barbeta" in p and r["decision"] in ("410", "REVISAR"):
        r["decision"], r["destino"], r["estado_esperado"] = "mantener", r["url"], "200"
        nota(r, "falso positivo de spam ('bet' en 'barbeta')"); continue
    if r["decision"] in ("mantener", "REVISAR") and not r["notas"] and (TAXO.search(p) or PAG.search(p)):
        destino = re.sub(PAG, "/", p) if PAG.search(p) and not TAXO.search(p) else BLOG.get(l, home(l))
        r["decision"], r["destino"], r["estado_esperado"] = "301", destino, "301"
        nota(r, "sistema traducido (taxonomía/autor/paginación) → regla E-bis"); continue
    if r["decision"] == "mantener" and p in canon and canon[p].rstrip("/") != p.rstrip("/"):
        d = canon[p]
        if por_path.get(d, {}).get("decision") == "mantener":
            r["decision"], r["destino"], r["estado_esperado"] = "301", d, "301"
            nota(r, "duplicada: 301 a su canónica (aprobado Oscar 27/09/2026)")
        continue
    if r["decision"] != "REVISAR": continue
    st = estado.get(p)
    if p == "/home/":
        r["destino"], r["estado_esperado"] = "/", "301"; nota(r, "PROPUESTA: 301 a portada (hoy 403)")
    elif "emma-brugue" in p:
        r["destino"], r["estado_esperado"] = EQUIPO.get(l, home(l)), "301"; nota(r, "PROPUESTA: ficha de médico que ya no existe (404) → página de equipo")
    elif "politica-de-privacitat" in p:
        r["destino"], r["estado_esperado"] = PRIV.get(l, PRIV["es"]), "301"; nota(r, "PROPUESTA: 404 hoy → política de privacidad del idioma")
    elif "LANDING" in p:
        r["destino"], r["estado_esperado"] = "", "410"; nota(r, "PROPUESTA: 410 (404 hoy, landing retirada, sin tráfico)")
    elif re.search(r"-2/$", p) and st == 404 and por_path.get(re.sub(r"-2/$", "/", p), {}).get("decision") == "mantener":
        r["destino"], r["estado_esperado"] = re.sub(r"-2/$", "/", p), "301"; nota(r, "PROPUESTA: 301 a la versión sin -2")
    elif p in ("/tag/mounjaro/", "/tag/ozempic/"):
        r["destino"], r["estado_esperado"] = "/la-importante-ayuda-de-los-farmacos-en-la-perdida-de-peso-ozempic-y-mounjaro-en-nuestra-clinica/", "301"
        nota(r, "PROPUESTA: 301 al post de Ozempic/Mounjaro (tiene clics)")
    elif st == 404 and not r["backlinks"] and not int(r["trafico"] or 0):
        r["destino"], r["estado_esperado"] = "", "410"; nota(r, "PROPUESTA: 410 (404 hoy, sin tráfico ni backlinks)")
    elif st == 500:
        nota(r, "da 500 en WordPress: reintentar y decidir")
with open(R, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
c = {}
for r in rows: c[r["decision"]] = c.get(r["decision"], 0) + 1
print("tras reglas:", c, "· REVISAR con propuesta:", sum(1 for r in rows if r["decision"] == "REVISAR" and "PROPUESTA" in r["notas"]))
