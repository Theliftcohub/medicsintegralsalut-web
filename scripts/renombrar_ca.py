#!/usr/bin/env python3
"""Quita el sufijo «-2» de las URLs catalanas (TranslatePress): /ca/unitats-2/… -> /ca/unitats/…, /ca/contacte-2/ -> /ca/contacte/.
Decisión del usuario (05/10/2026): limpieza completa. Solo «-2» al final de un segmento; «-50», «-110»… son parte del nombre.

- Choque: si la URL limpia ya era otra página o entrada (duplicado antiguo del WordPress), ese duplicado se elimina y la
  URL limpia pasa a servir la página actual (la del menú). La URL «-2» redirige (301) a la limpia.
- Se actualizan: path, canonical, migas, nombre interno de los formularios, enlaces internos de todo src/content, src/data/vc-chrome.json,
  migracion/i18n-map.json y el contrato migracion/urls.csv (vieja -> 301 a la nueva; nueva -> mantener; destinos que
  apuntaban a la vieja -> la nueva). Informe: migracion/renombrado_ca.json.
Uso:  python scripts/renombrar_ca.py             (solo informe, no cambia nada)
      python scripts/renombrar_ca.py --aplicar
Después: npm run build -> redirects_contract.py -> build_redirects.py … -> redirects_post.py -> npm run build (ver CLAUDE.md)."""
import csv, glob, json, os, re, sys
from urllib.parse import quote, unquote

SITE = "https://www.medicsintegralsalut.com"
SUF = re.compile(r"-2(?=/)")
APLICAR = "--aplicar" in sys.argv


def enc(p):
    """Ruta codificada como en urls.csv (%xx en minúsculas, como las genera WordPress)."""
    return re.sub(r"%[0-9A-F]{2}", lambda m: m.group(0).lower(), quote(p, safe="/"))


def fm_get(fm, k):
    m = re.search(rf"^{k}: (.*)$", fm, re.M)
    return json.loads(m.group(1)) if m else None


# ---- inventario de páginas y entradas ----
items = {}  # path -> (tipo, archivo)
for f in glob.glob("src/content/pages/*/*.json"):
    items[json.load(open(f, encoding="utf-8"))["path"]] = ("page", f)
for f in glob.glob("src/content/posts/*/*.md"):
    items[fm_get(open(f, encoding="utf-8").read().split("---")[1], "path")] = ("post", f)

M, omitidas = {}, []
destinos = {}
for p in sorted(items):
    if p.startswith("/ca/") and SUF.search(p):
        destinos.setdefault(SUF.sub("", p), []).append(p)
for nuevo, viejos in destinos.items():
    if len(viejos) > 1:
        omitidas += viejos  # dos URLs «-2» que acabarían en la misma: no se toca ninguna
    else:
        M[viejos[0]] = nuevo
duplicados = sorted(n for n in M.values() if n in items and n not in M)

informe = {"renombradas": [[o, n] for o, n in sorted(M.items())], "duplicados_eliminados": duplicados, "omitidas": omitidas}
print(f"{len(M)} URLs a renombrar · {len(duplicados)} duplicados antiguos que se eliminan · {len(omitidas)} omitidas")
if not APLICAR:
    for o, n in sorted(M.items())[:10]:
        print("  ", o, "->", n, "(sustituye a un duplicado)" if n in duplicados else "")
    print("Solo informe. Con --aplicar se ejecuta.")
    sys.exit(0)

# ---- 1) duplicados antiguos fuera ----
for n in duplicados:
    os.remove(items[n][1])

# ---- 2) rutas en cualquier texto: /ca/… (decodificadas o %xx, relativas o absolutas) ----
TOKEN = re.compile(r"(https://www\.medicsintegralsalut\.com)?(/ca/[^\s\"'<>#?\\]*)")


def cambia(txt):
    def f(m):
        dom, ruta = m.group(1) or "", m.group(2)
        clave = unquote(ruta) if unquote(ruta).endswith("/") else unquote(ruta) + "/"
        if clave not in M:
            return m.group(0)
        nueva = M[clave] if ruta.endswith("/") else M[clave].rstrip("/")
        return dom + (enc(nueva) if dom or "%" in ruta else nueva)
    return TOKEN.sub(f, txt)


def nombre(path):
    resto = path.strip("/").split("/", 1)[1] if path.count("/") > 2 else path.strip("/").split("/")[-1]
    return resto.replace("/", "__")


for f in glob.glob("src/content/pages/*/*.json") + glob.glob("src/content/posts/*/*.md"):
    raw = open(f, encoding="utf-8").read()
    nuevo = cambia(raw)
    destino = f
    if f.endswith(".json"):
        p = json.loads(raw)["path"]
        if p in M:
            destino = os.path.join(os.path.dirname(f), nombre(M[p]) + ".json")
            # nombre interno del formulario (va a GTM y a Kommo) sin el «-2» de la URL antigua
            nuevo = re.sub(r'"name": "(form-[^"]*)"', lambda m: '"name": "%s"' % re.sub(r"-2(?=-|$)", "", m.group(1)), nuevo)
    else:
        p = fm_get(raw.split("---")[1], "path")
        if p in M:
            destino = os.path.join(os.path.dirname(f), M[p].strip("/").split("/")[-1] + ".md")
    if nuevo != raw or destino != f:
        if destino != f and os.path.exists(destino):
            sys.exit(f"ABORTADO: {destino} ya existe y no es {f}")
        open(destino, "w", encoding="utf-8").write(nuevo)
        if destino != f:
            os.remove(f)

for f in ("src/data/vc-chrome.json", "migracion/i18n-map.json"):
    raw = open(f, encoding="utf-8").read()
    open(f, "w", encoding="utf-8").write(cambia(raw))

# ---- 3) contrato ----
rows = list(csv.DictReader(open("migracion/urls.csv", encoding="utf-8")))
campos = list(rows[0].keys())
por_url = {unquote(r["url"]): r for r in rows}
nota = "renombrada 05/10/2026: URL catalana sin «-2» (decisión usuario)"
for o, n in M.items():
    vieja = por_url.get(o)
    if vieja:
        vieja.update(decision="301", destino=enc(n), estado_esperado="301", notas=nota)
    nueva = por_url.get(n)
    if nueva:
        nueva.update(decision="mantener", destino=enc(n), estado_esperado="200", notas=f"antes {o} · {nota}")
    else:
        base = dict(vieja) if vieja else {k: "" for k in campos}
        base.update(url=enc(n), decision="mantener", destino=enc(n), estado_esperado="200", notas=f"antes {o} · {nota}")
        rows.append(base)
        por_url[n] = base
for r in rows:
    d = unquote(r["destino"] or "")
    if r["decision"] == "301" and (d if d.endswith("/") else d + "/") in M:
        r["destino"] = enc(M[d if d.endswith("/") else d + "/"])
with open("migracion/urls.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=campos)
    w.writeheader()
    w.writerows(rows)

json.dump(informe, open("migracion/renombrado_ca.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("Aplicado. Informe en migracion/renombrado_ca.json")
