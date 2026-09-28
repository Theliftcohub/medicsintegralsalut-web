#!/usr/bin/env python3
"""Compara cada página de la web nueva (dist/) con la original (HTML cacheado del WordPress, 27/09/2026).
Por página: % de palabras del contenido original presentes en la nueva, encabezados (H1-H3) que faltan,
imágenes de contenido (original vs nueva) y formularios. Salida: migracion/comparacion_original.json + resumen."""
import collections, csv, hashlib, json, os, re, sys
from urllib.parse import unquote
from bs4 import BeautifulSoup
sys.path.insert(0, "scripts")
import vc_pages as V

W = re.compile(r"[\wÀ-ÿĀ-žА-яЁёІіЇїЄєҐґ·']{3,}", re.U)
def words(t): return collections.Counter(w.lower() for w in W.findall(t))
def heads(el): return [re.sub(r"\s+", " ", h.get_text(" ", strip=True)).lower() for h in el.find_all(["h1", "h2", "h3"]) if h.get_text(strip=True)]

rows = [r for r in csv.DictReader(open("migracion/urls.csv")) if r["decision"] == "mantener" and r["url"].endswith("/")]
out = []
for r in rows:
    p = r["url"]; dp = unquote(p)
    fn = "dist" + dp + "index.html"
    if not os.path.exists(fn):
        out.append({"url": dp, "error": "no existe en dist"}); continue
    try:
        s = V.soup_of(p)
    except Exception:
        continue
    root = s.select_one(".mpost") or s.select_one(".blog_holder article .post_text_inner") or V.content_root(s)
    if root is None:
        continue
    root = BeautifulSoup(str(root), "html.parser")
    for x in root(["script", "style", "noscript", "form", "iframe"]): x.decompose()
    for sel in V.DROP_SEL: [x.decompose() for x in root.select(sel)]
    n = BeautifulSoup(open(fn, encoding="utf-8").read(), "html.parser")
    main = n.find("main")
    for x in main(["script", "style", "form"]): x.decompose()
    wo, wn = words(root.get_text(" ")), words(main.get_text(" "))
    tot = sum(wo.values()) or 1
    miss = sum(max(0, c - wn.get(w, 0)) for w, c in wo.items())
    ho, hn = heads(root), set(heads(main))
    io = len([i for i in root.find_all("img") if "/wp-content/uploads/" in (i.get("src") or i.get("data-src") or "") and "themes" not in (i.get("src") or "")])
    inew = len(main.find_all("img"))
    out.append({"url": dp, "tipo": r["tipo"], "cobertura": round(100 * (1 - miss / tot), 1), "palabras": tot,
                "faltan_palabras": [w for w, c in (wo - wn).most_common(12)], "encabezados_faltan": [h for h in ho if h not in hn][:6],
                "img_orig": io, "img_nueva": inew})
json.dump(out, open("migracion/comparacion_original.json", "w"), ensure_ascii=False, indent=1)
ok = [o for o in out if "cobertura" in o]
bajo = sorted([o for o in ok if o["cobertura"] < 95 and o["palabras"] > 30], key=lambda o: o["cobertura"])
print("páginas comparadas:", len(ok), "· cobertura media:", round(sum(o["cobertura"] for o in ok) / len(ok), 1))
print("≥99%:", sum(o["cobertura"] >= 99 for o in ok), "· 95-99%:", sum(95 <= o["cobertura"] < 99 for o in ok), "· <95%:", len(bajo))
print("con encabezados que faltan:", sum(bool(o["encabezados_faltan"]) for o in ok))
print("con menos imágenes que el original:", sum(o["img_nueva"] < o["img_orig"] for o in ok))
for o in bajo[:25]:
    print(f'{o["cobertura"]:5}% {o["url"][:70]} · faltan: {o["faltan_palabras"][:8]} · H: {o["encabezados_faltan"][:2]}')
