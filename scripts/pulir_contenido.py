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
13. tarjetas     Rejillas de enlaces a tratamientos (filas .vc-in con un enlace por celda) -> bloque `vc-tarjetas`
                 {heading, items[{text, href}]}: el componente añade foto y descripción de la página enlazada.
15. autor        La cuenta de la agencia («Nicols») figuraba como autora de una entrada: pasa a «Clínica Medics Integral Salut»,
                 como el resto de entradas (frontmatter y tarjeta del listado del blog).
16. respuesta    Etiqueta «Respuesta directa:» (y sus traducciones) al inicio de los resúmenes .mpost: se quita la etiqueta y
                 se conserva la frase, con mayúscula inicial.
17. canonical    Canonical a una URL que redirige -> a su destino final; a una URL que no existe o es 410 -> canonical propio
                 (rarezas de TranslatePress: p. ej. /en/team/... con canonical a /en/equip/..., que nunca existió).
18. migas rotas  Miga a una URL que no existe: si es la última, pasa a la propia página; si no, se quita.
14. sedes        Hospitales de /medics-integral-salut/ (título suelto + fila foto | mapa y datos, repetido) ->
                 una sección con una tarjeta por hospital (`variant: "tarjetas"`).
Uso: python scripts/pulir_contenido.py [--paginas]   (--paginas: no toca las entradas .md)"""
import csv, glob, json, os, re, sys
from bs4 import BeautifulSoup, Tag
from collections import Counter
from urllib.parse import unquote

SITE = "https://www.medicsintegralsalut.com"
M = {unquote(r[0]).rstrip("/"): unquote(r[1]) for r in csv.reader(open("migracion/url-map.csv", encoding="utf-8")) if len(r) >= 2}
GONE = {unquote(l.strip()).rstrip("/") for l in open("migracion/gone.txt", encoding="utf-8") if l.strip()}
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


def entidad(o):
    """MedicalClinic/MedicalOrganization de la clínica (también anidados, p. ej. publisher) -> misma entidad que el sitio."""
    if isinstance(o, dict):
        t = o.get("@type") or o.get("type")
        if t in ("MedicalClinic", "MedicalOrganization") and o.get("url", "").rstrip("/") == SITE and "@id" not in o:
            o["@id"] = f"{SITE}/#org"
            C["entidad"] += 1
        for v in o.values():
            entidad(v)
    elif isinstance(o, list):
        for v in o:
            entidad(v)
    return o


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


ETIQUETA = re.compile(r"<(b|strong)>\s*(?:Respuesta directa|Resposta directa|Direct answer|Réponse directe|Прямой ответ|Пряма відповідь)\s*:?\s*</\1>\s*(\S)")
AUTOR = ("Nicols", "Clínica Medics Integral Salut")


def texto(h):
    C["respuesta"] += len(ETIQUETA.findall(h))
    h = ETIQUETA.sub(lambda m: m.group(2).upper(), h)
    if f'"vc-bcard-meta">{AUTOR[0]}<' in h:
        C["autor"] += 1
        h = h.replace(f'"vc-bcard-meta">{AUTOR[0]}<', f'"vc-bcard-meta">{AUTOR[1]}<')
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


def rejilla_enlaces(h):
    """HTML con solo un título opcional y filas de enlaces -> (heading_html, tag, items) o None."""
    s = BeautifulSoup(h or "", "html.parser")
    heading, tag, items = None, "h2", []
    for el in s.contents:
        if not isinstance(el, Tag):
            if str(el).strip():
                return None
            continue
        if el.name in ("h2", "h3", "h4") and heading is None and not items:
            heading, tag = el.decode_contents().strip(), el.name
        elif (el.name == "p" and heading is None and not items and el.find("strong")
              and el.get_text(strip=True) == el.find("strong").get_text(strip=True)):
            heading = el.find("strong").decode_contents().strip()  # título en <p><strong> (WPBakery) -> h2
        elif el.name == "div" and "vc-in" in (el.get("class") or []):
            for c in el.find_all("div", class_="vc-in-c", recursive=False):
                kids = [k for k in c.contents if isinstance(k, Tag) or str(k).strip()]
                if not kids:
                    continue
                for k in kids:  # cada celda: uno o varios <p> con un enlace (o texto sin enlace)
                    if not isinstance(k, Tag) or k.name != "p":
                        return None
                    a = k.find_all("a")
                    if len(a) > 1 or (a and a[0].get_text(strip=True) != k.get_text(strip=True)):
                        return None
                    items.append({"text": k.get_text(" ", strip=True), **({"href": a[0]["href"]} if a else {})})
        elif el.name == "p" and el.find("a") and el.get_text(strip=True) == el.find("a").get_text(strip=True):
            items.append({"text": el.get_text(" ", strip=True), "href": el.find("a")["href"]})
        else:
            return None
    return (heading, tag, items) if len(items) >= 2 else None


SOLO_H = re.compile(r"^\s*<h[2-4][^>]*>.*?</h[2-4]>\s*$", re.S)


def sedes(blocks):
    """[h2+p] [h3] [foto | mapa+datos] [h3] [foto | mapa+datos]… -> intro + una tarjeta por sede."""
    titulo = lambda b: b["type"] == "vc-prosa" and len(b.get("cols", [])) == 1 and SOLO_H.match(b["cols"][0].get("html") or "")
    ficha = lambda b: b["type"] == "vc-prosa" and len(b.get("cols", [])) == 2 and "vc-embed--mapa" in (b["cols"][1].get("html") or "")
    out, i = [], 0
    while i < len(blocks):
        cards, j = [], i
        while j + 1 < len(blocks) and titulo(blocks[j]) and ficha(blocks[j + 1]):
            t, d = blocks[j], blocks[j + 1]
            cards.append({"html": d["cols"][0]["html"] + t["cols"][0]["html"] + d["cols"][1]["html"]})
            j += 2
        if len(cards) < 2:
            out.append(blocks[i])
            i += 1
            continue
        sec = {"type": "vc-prosa", "bg": "crema", "variant": "tarjetas", "cols": cards}
        prev = out[-1] if out else None
        if prev and prev["type"] == "vc-prosa" and len(prev.get("cols", [])) == 1 and (prev["cols"][0].get("html") or "").lstrip().startswith("<h2"):
            sec["intro"] = out.pop()["cols"][0]["html"]
        out.append(sec)
        C["sedes"] += 1
        i = j
    return out


def desequilibrado(h):
    return len(re.findall(r"<div[\s>]", h or "")) != (h or "").count("</div>")


# rutas existentes (páginas y entradas) para validar canonical y migas
EXISTEN = set()
for _f in glob.glob("src/content/pages/*/*.json"):
    EXISTEN.add(json.load(open(_f, encoding="utf-8"))["path"])
for _f in glob.glob("src/content/posts/*/*.md"):
    EXISTEN.add(json.loads(re.search(r"^path: (.*)$", open(_f, encoding="utf-8").read().split("---")[1], re.M).group(1)))


def canonical(path, can):
    if not can:
        return can
    cp = unquote(re.sub(r"^https?://[^/]+", "", can))
    if cp == path or cp in EXISTEN:
        return can
    fin = final(cp) if cp.rstrip("/") in M else None
    nuevo = fin if fin and fin in EXISTEN and fin.rstrip("/") not in GONE else path
    C["canonical"] += 1
    return SITE + nuevo


def migas_ok(path, bc):
    out = []
    for i, c in enumerate(bc or []):
        if c["path"] in EXISTEN:
            out.append(c)
        elif i == len(bc) - 1:
            out.append({**c, "path": path})
            C["migas rotas"] += 1
        else:
            C["migas rotas"] += 1
    return out


# ---- entradas (.md) ----
post_paths = set()
for md in glob.glob("src/content/posts/*/*.md"):
    raw = open(md, encoding="utf-8").read()
    _, fm, body = raw.split("---", 2)
    post_paths.add(json.loads(re.search(r"^path: (.*)$", fm, re.M).group(1)))
    if "--paginas" in sys.argv:
        continue
    m = re.search(r"^schema: (.*)$", fm, re.M)
    if m:
        fm = fm.replace(m.group(0), "schema: " + json.dumps(entidad(json.loads(m.group(1))), ensure_ascii=False))
    _p = json.loads(re.search(r"^path: (.*)$", fm, re.M).group(1))
    _c = re.search(r"^canonical: (.*)$", fm, re.M)
    if _c and canonical(_p, json.loads(_c.group(1))) != json.loads(_c.group(1)):
        fm = fm.replace(_c.group(0), "canonical: " + json.dumps(canonical(_p, json.loads(_c.group(1))), ensure_ascii=False))
    _b = re.search(r"^breadcrumbs: (.*)$", fm, re.M)
    if _b:
        _n = migas_ok(_p, json.loads(_b.group(1)))
        if _n != json.loads(_b.group(1)):
            fm = fm.replace(_b.group(0), "breadcrumbs: " + json.dumps(_n, ensure_ascii=False))
    if f'author: "{AUTOR[0]}"' in fm:
        fm = fm.replace(f'author: "{AUTOR[0]}"', f'author: "{AUTOR[1]}"')
        C["autor"] += 1
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
        j["breadcrumbs"] = migas_ok(j["path"], migas(j["breadcrumbs"]))
    if j["seo"].get("canonical"):
        j["seo"]["canonical"] = canonical(j["path"], j["seo"]["canonical"])
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
        j["title"] = re.sub(r"\s*[-–—|]\s*Medics\s*Integral\s*Salut\s*$", "", j["seo"]["title"], flags=re.I).strip()
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
    nuevos = []
    for b in blocks:
        r = rejilla_enlaces(b["cols"][0].get("html")) if b["type"] == "vc-prosa" and len(b.get("cols", [])) == 1 and not b.get("intro") else None
        if r:
            heading, tag, items = r
            nb = {"type": "vc-tarjetas", "items": items, **({"heading": heading, "headingTag": tag} if heading else {})}
            if b.get("bg"):
                nb["bg"] = b["bg"]
            nuevos.append(nb)
            C["tarjetas"] += 1
        else:
            nuevos.append(b)
    blocks = sedes(nuevos)
    j["blocks"] = blocks
    j["schema"] = entidad(json.loads(logo(json.dumps(j["schema"], ensure_ascii=False))))
    gracias(j["blocks"], j["lang"])
    if j["path"] in GRACIAS.values() and "noindex" not in j["seo"]["robots"]:
        j["seo"]["robots"] = "noindex, follow"
        C["noindex"] += 1
    if json.dumps(j, ensure_ascii=False) != antes:
        json.dump(j, open(f, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(dict(C))
