#!/usr/bin/env python3
"""Cierra las filas REVISAR del contrato de URLs (migracion/urls.csv) con criterios explícitos (28/09/2026):
1. PROPUESTA con destino -> se aplica (301 al destino; "PROPUESTA: 410" -> 410).
2. Archivos de blog (category/tag/author/page/N/feed) -> 301 al listado padre o al blog del idioma.
3. Portfolio (categorías, paginación) -> 301 al portfolio del idioma.
4. Slug en español bajo /uk/ (hoy 403) -> 301 a la versión uk de esa entrada (mapa TranslatePress).
5. Errores 500 de WordPress -> 301 a la misma página en el árbol correcto.
6. Medios /wp-content/ -> 301 a la imagen local si existe; si no, 410.
Cada decisión queda en la columna notas ("RESUELTO 28/09: ...")."""
import csv, json, os, re, sys
from urllib.parse import unquote
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
rows = list(csv.DictReader(open("migracion/urls.csv")))
I18N = json.load(open("migracion/i18n-map.json"))
by_es = {v["es"]: v for v in I18N.values() if "es" in v}
BLOG = {"es": "/blog-2/", "ca": "/ca/blog-2/", "en": "/en/blog-2/", "fr": "/fr/blog-2/", "ru": by_es["/blog-2/"]["ru"], "uk": by_es["/blog-2/"]["uk"]}
PORT = by_es["/portfolio_page/"]
MANUAL = {  # destinos elegidos por contenido
    "/5268/": ("301", "/como-eliminar-ojeras/", "ID de WordPress 5268 = /como-eliminar-ojeras/"),
    "/cuanto-cuesta-una-rinoplastia-espana/": ("301", "/unidades/cirugia-estetica-facial/rinoplastia-girona/", "tema rinoplastia (precio) -> página de rinoplastia"),
    "/en/units-2/cosmetic-facial-surgery/": ("301", by_es["/unidades/cirugia-estetica-facial/"]["en"], "árbol duplicado units-2 -> unidad en inglés"),
    "/ca/portfolio_page/botoox-mike-lidia/": ("301", by_es["/portfolio_page/video-prueba-4/"]["ca"], "mismo vídeo en el portfolio catalán"),
    "/ca/category/uncategorized-ca/": ("301", BLOG["ca"], "categoría vacía -> blog"),
}
lang = lambda p: (p.split("/")[1] if p.split("/")[1:2] and p.split("/")[1] in ("ca", "en", "fr", "ru", "uk") else "es")
ES_SLUG = {p.strip("/").split("/")[-1]: v for p, v in by_es.items()}
done = []
for r in rows:
    if r["decision"] != "REVISAR":
        continue
    u, n, d = r["url"], r["notas"], r["destino"]
    L = lang(u)
    dec = None
    if u in MANUAL:
        dec = MANUAL[u]
    elif "PROPUESTA: 410" in n:
        dec = ("410", "", "propuesta aplicada")
    elif "PROPUESTA" in n and d:
        dec = ("301", d, "propuesta aplicada")
    elif re.search(r"/(category|tag|author)/|/page/\d+/|/feed/$|/pagina/\d+/|/страница/\d+/", unquote(u)) and "portfoli" not in u and "портфолио" not in unquote(u):
        dec = ("301", d or BLOG[L], "archivo del blog -> listado")
    elif "portfolio" in u or "portfoli" in u or "портфолио" in unquote(u):
        dec = ("301", PORT[L], "portfolio -> portfolio del idioma")
    elif L == "uk" and "403" in n:
        slug = u.strip("/").split("/")[-1]
        v = ES_SLUG.get(slug)
        if v and v.get("uk"):
            dec = ("301", v["uk"], f"slug español bajo /uk/ -> versión uk de /{slug}/")
    elif "500" in n and "ru" == L:
        dec = ("301", by_es["/unidades/gabinete-de-estetica/reduccion-de-volumen-girona/"]["ru"], "árbol duplicado -> unidad en ruso")
    elif u.startswith("/wp-content/"):
        from wp_lib import original_upload
        m = re.search(r"/wp-content/(?:w3-webp/)?uploads/(.+)$", original_upload(u))
        rel = unquote(m.group(1)) if m else ""
        base = re.sub(r"-\d+x\d+$", "", os.path.splitext(rel)[0].replace(".jpg", ""))
        cand = [f"public/images/wp/{os.path.splitext(rel)[0]}.webp", f"public/images/wp/{base}.webp"]
        hit = next((c for c in cand if os.path.exists(c)), None)
        dec = ("301", hit[len("public"):], "medio -> imagen local") if hit else ("410", "", "medio sin equivalente en la web nueva")
    if dec:
        r["decision"], r["destino"] = dec[0], dec[1]
        r["estado_esperado"] = dec[0]
        r["notas"] = (n + " · " if n else "") + f"RESUELTO 28/09: {dec[2]}"
        done.append((u, dec))
w = csv.DictWriter(open("migracion/urls.csv", "w", newline=""), fieldnames=rows[0].keys())
w.writeheader(); w.writerows(rows)
left = [r["url"] for r in rows if r["decision"] == "REVISAR"]
print("resueltas", len(done), "· quedan", len(left), left)
