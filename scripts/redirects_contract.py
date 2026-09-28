#!/usr/bin/env python3
"""Contrato de URLs (migracion/urls.csv) -> migracion/url-map.csv (301) y migracion/gone.txt (410) para build_redirects.py.
- 301 con destino; 410; "mantener" sin barra final -> 301 a la versión con barra.
- Medios /wp-content/ que se mantienen -> 301 a su copia local (imagen WebP o /media/)."""
import csv, os, re, sys
from urllib.parse import unquote
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wp_lib import original_upload
rows = list(csv.DictReader(open("migracion/urls.csv")))


def existe(p):
    q = unquote(p.split("#")[0]).strip("/")
    return os.path.isfile(os.path.join("dist", q, "index.html")) or os.path.isfile(os.path.join("public", q))


def vivo(d):
    """Si el destino no existe en la build, sube por la ruta hasta la primera página que exista (nunca 404)."""
    if d.startswith("http") or existe(d):
        return d
    parts = d.strip("/").split("/")
    while parts:
        parts.pop()
        c = "/" + "/".join(parts) + "/" if parts else "/"
        if existe(c):
            print("  destino inexistente", unquote(d), "->", unquote(c))
            return c
    return d
mp, gone, falta = [], [], []
R301 = {r["url"]: r["destino"] for r in rows if r["decision"] == "301" and r["destino"]}


def final(d):
    """Resuelve cadenas A->B->C con el propio contrato antes de comprobar que el destino existe."""
    seen = set()
    while d in R301 and d not in seen:
        seen.add(d)
        d = R301[d]
    return d
for r in rows:
    u, d = r["url"], r["destino"]
    if r["decision"] == "301" and d:
        mp.append((u, vivo(final(d))))
    elif r["decision"] == "410":
        gone.append(u)
    elif r["decision"] == "mantener":
        if u.startswith("/wp-content/"):
            m = re.search(r"/wp-content/(?:w3-webp/)?uploads/(.+)$", original_upload(u))
            rel = unquote(m.group(1)) if m else ""
            cands = [f"public/images/wp/{os.path.splitext(rel)[0]}.webp", f"public/media/{os.path.basename(rel)}"]
            hit = next((c for c in cands if os.path.exists(c)), None)
            (mp.append((u, hit[len("public"):])) if hit else falta.append(u))
        # "mantener" sin barra final: NO se genera regla. Netlify (pretty URLs) y Apache (mod_dir) ya hacen
        # /x -> /x/ solos, y en Netlify una regla /x -> /x/ casa también con /x/ (coincidencia laxa) = bucle.
with open("migracion/url-map.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerows(mp)
open("migracion/gone.txt", "w").write("\n".join(gone) + "\n")
print(len(mp), "301 ·", len(gone), "410 · medios sin copia local:", falta)
