#!/usr/bin/env python3
"""Páginas en catalán que viven en URLs sin /ca/ (árbol catalán antiguo del WordPress, con canonical propio).
Decisión del usuario (05/10/2026): ordenarlas.
- Si existe su gemela en /ca/ (misma traducción en su grupo i18n, o la misma ruta bajo /ca/): se elimina la de la raíz
  y la URL pasa a 301 -> gemela (urls.csv). Los enlaces internos los reescribe después enlaces_finales.py.
- Si no hay gemela: se queda en su URL pero declarada como catalán (`lang: ca`), para que <html lang>, hreflang y
  el resto de la plantilla digan la verdad.
- Los listados del blog en español dejan de mostrar esas entradas.
Entrada: lista de rutas en migracion/catalan_raiz.json (generada con el análisis de idioma). Idempotente.
Uso: python scripts/ordenar_catalan_raiz.py"""
import csv, glob, json, os, re
from collections import defaultdict
from urllib.parse import quote, unquote

enc = lambda p: re.sub(r"%[0-9A-F]{2}", lambda m: m.group(0).lower(), quote(p, safe="/"))
RUTAS = json.load(open("migracion/catalan_raiz.json", encoding="utf-8"))
grp, files, lang = {}, {}, {}
for f in glob.glob("src/content/pages/*/*.json"):
    j = json.load(open(f, encoding="utf-8")); grp[j["path"]] = j.get("i18nGroup"); files[j["path"]] = f; lang[j["path"]] = j["lang"]
for f in glob.glob("src/content/posts/*/*.md"):
    fm = open(f, encoding="utf-8").read().split("---")[1]
    g = lambda k: (json.loads(m.group(1)) if (m := re.search(rf"^{k}: (.*)$", fm, re.M)) else None)
    grp[g("path")] = g("i18nGroup"); files[g("path")] = f; lang[g("path")] = g("lang")
porgrupo = defaultdict(dict)
for p, g in grp.items():
    if g: porgrupo[g][lang[p]] = p


def gemela(p):
    t = porgrupo.get(grp.get(p), {}).get("ca")
    if t and t != p:
        return t
    for cand in ("/ca" + p, "/ca" + re.sub(r"-2/$", "/", p)):
        if cand in files and cand != p:
            return cand
    return None


RES = "migracion/catalan_raiz_resultado.json"
prev = json.load(open(RES, encoding="utf-8")) if os.path.exists(RES) else {"redirigidas": {}, "declaradas_catalan": []}
redirigidas, relabel = dict(prev["redirigidas"]), list(prev["declaradas_catalan"])
for p in RUTAS:
    if p not in files or p in relabel:   # ya ordenada en una ejecución anterior
        continue
    t = gemela(p)
    if t:
        redirigidas[p] = t
        os.remove(files[p])
    else:
        relabel.append(p)
        f = files[p]
        if f.endswith(".json"):
            j = json.load(open(f, encoding="utf-8"))
            j["lang"] = "ca"
            if "ca" in porgrupo.get(j.get("i18nGroup"), {}) and porgrupo[j["i18nGroup"]]["ca"] != p:
                j.pop("i18nGroup", None)   # el grupo ya tiene catalán: esta queda suelta
            json.dump(j, open(f, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        else:
            raw = open(f, encoding="utf-8").read()
            open(f, "w", encoding="utf-8").write(raw.replace('lang: "es"', 'lang: "ca"', 1))

# contrato
rows = list(csv.DictReader(open("migracion/urls.csv", encoding="utf-8")))
campos = list(rows[0].keys())
por_url = {unquote(r["url"]): r for r in rows}
nota = "catalán en la raíz con gemela en /ca/: 301 (decisión usuario 05/10/2026)"
for p, t in redirigidas.items():
    r = por_url.get(p)
    if r and r["decision"] != "301":
        r.update(decision="301", destino=enc(t), estado_esperado="301", notas=nota)
    elif not r:
        rows.append({**{k: "" for k in campos}, "url": enc(p), "decision": "301", "destino": enc(t), "estado_esperado": "301", "notas": nota})
with open("migracion/urls.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=campos); w.writeheader(); w.writerows(rows)

# listados del blog en español: fuera las tarjetas de entradas que ya no son españolas
fuera = set(redirigidas) | set(relabel)
CARD = re.compile(r'<div class="vc-bcard">.*?</div>(?=<div class="vc-bcard">|</div>)', re.S)
quitadas = 0
for f in glob.glob("src/content/pages/es/*.json"):
    j = json.load(open(f, encoding="utf-8"))
    cambiado = False
    for b in j["blocks"]:
        for c in b.get("cols", []):
            h = c.get("html") or ""
            if "vc-bloglist" not in h:
                continue
            def f_(m):
                global quitadas
                href = re.search(r'href="([^"]+)"', m.group(0))
                if href and unquote(href.group(1)) in fuera:
                    quitadas += 1
                    return ""
                return m.group(0)
            nuevo = CARD.sub(f_, h)
            if nuevo != h:
                c["html"] = nuevo; cambiado = True
    if cambiado:
        json.dump(j, open(f, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
json.dump({"redirigidas": redirigidas, "declaradas_catalan": relabel}, open(RES, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"301 a /ca/: {len(redirigidas)} · declaradas catalán: {len(relabel)} · tarjetas quitadas del blog es: {quitadas}")
