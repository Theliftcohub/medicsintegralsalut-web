#!/usr/bin/env python3
"""Aplica migracion/historicas_estado.json al contrato: hereda las 301 actuales de WordPress
(resolviendo cadenas contra el contrato) y propone 410 / 301 por slug para las que hoy dan 404.
Orden del pipeline: build_contract.py -> contrato_extra.py -> reglas_medics.py -> merge_historicas.py"""
import csv, json
from urllib.parse import urlparse, unquote

R = "migracion/urls.csv"
rows = list(csv.DictReader(open(R, encoding="utf-8")))
est = json.load(open("migracion/historicas_estado.json"))
U = lambda p: unquote(p)
key = lambda p: U(p).rstrip("/").lower()
by = {key(r["url"]): r for r in rows}


def lang(p):
    s = p.split("/")
    return s[1] if len(s) > 1 and s[1] in ("ca", "en", "fr", "ru", "uk") else "es"


def resolver(path, n=0):
    r = by.get(key(path))
    if not r or n > 5:
        return path, (r["decision"] if r else None)
    if r["decision"] == "301" and r["destino"]:
        return resolver(r["destino"], n + 1)
    return r["url"], r["decision"]


slug_idx = {}
for r in rows:
    if r["decision"] == "mantener":
        s = U(r["url"]).rstrip("/").split("/")[-1].lower()
        slug_idx.setdefault((lang(U(r["url"])), s), r["url"])

c = {}
def add(k): c[k] = c.get(k, 0) + 1
def nota(r, t): r["notas"] = (r["notas"] + "; " if r["notas"] else "") + t

for r in rows:
    if r["tipo"] != "historica" or r["decision"] != "REVISAR":
        continue
    e = est.get(r["url"])
    if not e:
        continue
    bl = r["backlinks"] not in ("", "0", None)
    tr = int(r["trafico"] or 0)
    fin = e.get("final")
    if fin and e["status_final"] == 200 and urlparse(fin).netloc == "www.medicsintegralsalut.com":
        dest, dec = resolver(urlparse(fin).path)
        if dec == "mantener":
            r["decision"], r["destino"], r["estado_esperado"] = "301", dest, "301"
            nota(r, "WordPress ya la redirige: se hereda la 301"); add("hereda_301"); continue
    if e["status_final"] in (404, 410):
        s = U(r["url"]).rstrip("/").split("/")[-1].lower()
        m = slug_idx.get((lang(U(r["url"])), s)) or slug_idx.get(("es", s))
        if m:
            dest, _ = resolver(m)
            r["decision"], r["destino"], r["estado_esperado"] = "301", dest, "301"
            nota(r, "hoy 404; mismo slug en URL vigente → 301"); add("301_por_slug")
        elif not bl and tr == 0:
            r["decision"], r["estado_esperado"] = "410", "410"
            nota(r, "hoy 404, sin clics ni backlinks → 410"); add("410");
        else:
            nota(r, f"hoy {e['status_final']} con valor (clics/backlinks): decidir destino"); add("revisar_valor")
    elif e["status_final"] == 200 and not fin:
        nota(r, "hoy responde 200 y no está en el inventario: incorporar o redirigir"); add("200_fuera_inventario")
    else:
        nota(r, f"estado actual {e['status_final']}"); add(f"otro_{e['status_final']}")

with open(R, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
t = {}
for r in rows:
    t[r["decision"]] = t.get(r["decision"], 0) + 1
print(c, "→ contrato:", t)
