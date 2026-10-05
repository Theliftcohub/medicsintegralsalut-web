#!/usr/bin/env python3
"""Limpieza del contenido ya generado (src/content), sin cambiar textos. Idempotente: se puede repetir.
Se ejecuta después de vc_pages.py / schema_posts.py. Cada paso corrige un fallo de la migración:

1. duplicados   Entradas que además tenían un JSON de página con la misma URL (conflicto de rutas en Astro): se borra el JSON.
2. migas        Yoast + bloque .mpost publicaban dos BreadcrumbList y vc_pages las concatenaba: se queda la primera
                lista completa, con cada enlace en su URL final. La BreadcrumbList del schema se quita (la genera el layout).
3. entidad      El MedicalClinic del schema de cada página pasa a ser la misma entidad que la del sitio (@id …/#org).
4. titulo       `title` = título literal de la página (seo.title sin el sufijo de marca): H1 de las páginas que no tienen.
5. oculto       Párrafos ocultos con CSS (.mpp-ex / .mpost-ex, 1 px fuera de pantalla): texto oculto = riesgo SEO.
6. iconos       <img> de ≤72 px -> class="vc-ico" (icono + texto en línea, en vez de imagen suelta).
7. contacto     El formulario partía en tres columnas el bloque «te llamamos» (HTML sin cerrar): se rehace en dos columnas.
8. media        Texto visible de los enlaces al vídeo bariátrico: /wp-content/uploads/… -> /media/… (NO_LITERAL.md).
9. gracias      Los formularios de ca/en/fr/ru/uk enviaban a /xx/gracias/, que no existe (404 tras enviar): cada idioma
                va a su página de gracias real.
10. noindex     Las páginas de gracias (destino de los formularios) no se indexan.
11. logo         El schema recuperado del WordPress apunta al logo en /wp-content/: pasa a /icon-512.png (la misma imagen).
12. h1           Entradas con un <h1> dentro del cuerpo (además del título): pasa a <h2 class="h-as-h1"> (mismo aspecto).
                 En las páginas lo hace src/lib/paginas.ts al pintar.
Uso: python scripts/pulir_contenido.py [--paginas]   (--paginas: no toca las entradas .md)"""
import csv, glob, json, os, re, sys
from collections import Counter
from urllib.parse import unquote

SITE = "https://www.medicsintegralsalut.com"
M = {unquote(r[0]).rstrip("/"): unquote(r[1]) for r in csv.reader(open("migracion/url-map.csv", encoding="utf-8")) if len(r) >= 2}
C = Counter()


def final(p):
    k, seen = unquote(p).rstrip("/"), set()
    while k in M and k not in seen:
        seen.add(k)
        k = unquote(M[k]).rstrip("/")
    return k + "/"


OCULTO = re.compile(r'<p class="(?:mpp-ex|mpost-ex)"[^>]*>.*?</p>\s*', re.S)
IMG = re.compile(r"<img\b[^>]*>")
WPMEDIA = "https://www.medicsintegralsalut.com/wp-content/uploads/2022/02/Cirugia-Bariatrica-BYPASS.mp4"
WPLOGO = "https://www.medicsintegralsalut.com/wp-content/uploads/2021/11/cropped-Logo-MIS-cuadrado-02-300x300.png"
H1 = re.compile(r"<h1(\s[^>]*)?>(.*?)</h1>", re.S)


def logo(t):
    if WPLOGO in t:
        C["logo"] += 1
        return t.replace(WPLOGO, f"{SITE}/icon-512.png")
    return t


def h1_a_h2(h):
    def f(m):
        C["h1"] += 1
        attrs = m.group(1) or ""
        attrs = attrs.replace('class="', 'class="h-as-h1 ', 1) if 'class="' in attrs else attrs + ' class="h-as-h1"'
        return f"<h2{attrs}>{m.group(2)}</h2>"
    return H1.sub(f, h)


def iconos(h):
    def f(m):
        tag = m.group(0)
        w = re.search(r'\bwidth="(\d+)"', tag)
        if not w or int(w.group(1)) > 72 or "vc-ico" in tag:
            return tag
        C["iconos"] += 1
        return tag.replace('class="', 'class="vc-ico ', 1) if 'class="' in tag else tag.replace("<img", '<img class="vc-ico"', 1)
    return IMG.sub(f, h)


def texto(h):
    n = len(OCULTO.findall(h))
    C["oculto"] += n
    h = OCULTO.sub("", h)
    if f">{WPMEDIA}<" in h:
        C["media"] += 1
        h = h.replace(f">{WPMEDIA}<", f">{WPMEDIA.replace('/wp-content/uploads/2022/02/', '/media/')}<")
    return h


def migas(bc):
    if not bc:
        return bc
    # dos listas concatenadas: cada una empieza en la portada
    starts = [i for i, c in enumerate(bc) if c["path"] in ("/", "/ca/", "/en/", "/fr/", "/ru/", "/uk/")]
    if len(starts) > 1:
        C["migas"] += 1
        bc = bc[starts[0]:starts[1]]
    return [{"name": c["name"], "path": final(c["path"])} for c in bc]


def contacto(b):
    """[intro + inicio de .vc-in] [formulario] [nota legal + cierre + llamada] -> intro + 2 columnas."""
    c1, c2, c3 = b["cols"]
    intro, _, resto = c1["html"].partition('<div class="vc-in"')
    etiqueta = re.sub(r'^[^>]*>\s*<div class="vc-in-c">', "", resto).strip()
    nota, _, llamada = c3["html"].partition('</div><div class="vc-in-c">')
    llamada = re.sub(r"(</div>\s*)+$", "", llamada).strip()
    C["contacto"] += 1
    out = {k: v for k, v in b.items() if k not in ("cols", "stack")}
    out["intro"] = intro.strip()
    out["cols"] = [{"html": etiqueta, "form": c2["form"], "after": nota.strip()}, {"html": llamada}]
    return out


# página de gracias de cada idioma (las /xx/gracias/ de TranslatePress no existen)
GRACIAS = {"es": "/gracias/", "ca": "/ca/gracies/", "en": "/en/thank-you/", "fr": "/fr/merci/", "ru": "/ru/спасибо/", "uk": "/uk/дякую/"}


def gracias(o, lang):
    if isinstance(o, dict):
        if "thanks" in o and o["thanks"] != GRACIAS[lang]:
            o["thanks"] = GRACIAS[lang]
            C["gracias"] += 1
        for v in o.values():
            gracias(v, lang)
    elif isinstance(o, list):
        for v in o:
            gracias(v, lang)


def desequilibrado(h):
    return len(re.findall(r"<div[\s>]", h or "")) != (h or "").count("</div>")


# ---- entradas (.md) ----
post_paths = set()
for md in glob.glob("src/content/posts/*/*.md"):
    raw = open(md, encoding="utf-8").read()
    _, fm, body = raw.split("---", 2)
    post_paths.add(json.loads(re.search(r"^path: (.*)$", fm, re.M).group(1)))
    if "--paginas" in sys.argv:
        continue
    nuevo = "---" + logo(fm) + "---" + h1_a_h2(texto(iconos(body)))
    if nuevo != raw:
        open(md, "w", encoding="utf-8").write(nuevo)

# ---- páginas (.json) ----
for f in glob.glob("src/content/pages/*/*.json"):
    j = json.load(open(f, encoding="utf-8"))
    if j["path"] in post_paths:
        os.remove(f)
        C["duplicados"] += 1
        continue
    antes = json.dumps(j, ensure_ascii=False)
    if j.get("breadcrumbs"):
        j["breadcrumbs"] = migas(j["breadcrumbs"])
    sch = []
    for s in j.get("schema", []):
        if s.get("type") == "BreadcrumbList":
            continue
        if s.get("type") in ("MedicalClinic", "MedicalOrganization") and s.get("url", "").rstrip("/") == SITE and "@id" not in s:
            s = {"type": s["type"], "@id": f"{SITE}/#org", **{k: v for k, v in s.items() if k != "type"}}
            C["entidad"] += 1
        sch.append(s)
    j["schema"] = sch
    if not j.get("title"):
        j["title"] = re.sub(r"\s*[-–|]\s*Medics\s*Integral\s*Salut\s*$", "", j["seo"]["title"], flags=re.I).strip()
    blocks = []
    for b in j["blocks"]:
        if b["type"] == "vc-prosa" and len(b.get("cols", [])) == 3 and b["cols"][1].get("form") and desequilibrado(b["cols"][0].get("html")):
            b = contacto(b)
        for c in b.get("cols", []):
            for k in ("html", "after"):
                if c.get(k):
                    c[k] = texto(iconos(c[k]))
        if b["type"] == "vc-mpost" and b.get("html"):
            b["html"] = texto(iconos(b["html"]))
        blocks.append(b)
    j["blocks"] = blocks
    j["schema"] = json.loads(logo(json.dumps(j["schema"], ensure_ascii=False)))
    gracias(j["blocks"], j["lang"])
    if j["path"] in GRACIAS.values() and "noindex" not in j["seo"]["robots"]:
        j["seo"]["robots"] = "noindex, follow"
        C["noindex"] += 1
    if json.dumps(j, ensure_ascii=False) != antes:
        json.dump(j, open(f, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(dict(C))
