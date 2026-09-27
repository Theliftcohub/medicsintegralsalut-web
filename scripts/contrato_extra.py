#!/usr/bin/env python3
"""Completa migracion/urls.csv con URLs que Google conoce (GSC) o que tienen backlinks (Ahrefs)
pero que no están en el inventario (p. ej. spam ya borrado, URLs antiguas que hoy dan 404).
Spam -> 410 con nota. Resto -> REVISAR. Nunca decide 301 en silencio."""
import csv, json, re
from urllib.parse import urlparse, unquote
SPAM = re.compile(r"casino|kazino|kasyn|kasiin|cassino|vavada|mostbet|pinco|pinko|slot|apuestas|casa-de-apostas|bet(ting)?\b", re.I)
rows = list(csv.DictReader(open("migracion/urls.csv", encoding="utf-8")))
norm = lambda p: unquote(p).rstrip("/").lower()
conocidas = {norm(r["url"]) for r in rows}
gsc = {urlparse(r["page"]).path: r for r in csv.DictReader(open("migracion/gsc.csv"))}
ahr = {urlparse(u).path: v for u, v in json.load(open("migracion/ahrefs.json")).items() if urlparse(u).netloc == "www.medicsintegralsalut.com"}
nuevas = 0
for path in sorted(set(gsc) | set(ahr)):
    if norm(path) in conocidas:
        continue
    g = gsc.get(path, {}); a = ahr.get(path, {})
    clics, impr, bl = int(g.get("clicks", 0) or 0), int(g.get("impressions", 0) or 0), a.get("backlinks", "")
    spam = bool(SPAM.search(unquote(path)))
    if spam and not bl:
        d, st, nota = "410", "410", "spam del hackeo (no está en la web actual)"
    else:
        d, st, nota = "REVISAR", "", ("SPAM con backlinks — decidir; " if spam else "") + "conocida por Google, fuera del inventario actual"
    nota += f"; GSC {clics} clics / {impr} impr" + (f"; Ahrefs {bl} dominios" if bl else "")
    rows.append({**{k: "" for k in rows[0]}, "url": path, "decision": d, "destino": "", "estado_esperado": st,
                 "tipo": "historica", "backlinks": bl, "trafico": clics, "notas": nota})
    nuevas += 1
# spam que sí está en inventario pero quedó REVISAR por tener clics en GSC: 410 explícito
for r in rows:
    if SPAM.search(unquote(r["url"])) and r["decision"] == "REVISAR" and not r.get("backlinks"):
        r["decision"], r["estado_esperado"] = "410", "410"
        r["notas"] = (r["notas"] + "; " if r["notas"] else "") + "spam del hackeo: 410 aunque tenga clics"
with open("migracion/urls.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
cnt = {}
for r in rows: cnt[r["decision"]] = cnt.get(r["decision"], 0) + 1
print(f"+{nuevas} URLs históricas · totales: {cnt}")
