#!/usr/bin/env python3
"""Portada con el diseño «Versión C» (maqueta The Lift Co, migracion/diseno/home-version-c.html).
Parte del contenido LITERAL ya extraído por build_home.py (src/content/pages/es/home.json con bloques mp-*)
y lo reordena en los bloques vc-* de la maqueta. Los textos nuevos de la maqueta están en NO_LITERAL.md.
Cifras de Google (nota y nº de reseñas) NO van aquí: salen de src/data/site.json -> rating (dato vivo de GBP).
Uso: python3 scripts/build_home.py && python3 scripts/build_home_vc.py"""
import json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wp_lib import local_image

LANG = sys.argv[1] if len(sys.argv) > 1 else "es"
SRC = f"src/content/pages/{LANG}/home.json"
# Textos NUEVOS de la maqueta (no existen en el WordPress). es = maqueta; resto = traducción propia (NO_LITERAL.md, revisar).
T = json.load(open("scripts/home_vc_textos.json"))[LANG]
page = json.load(open(SRC))
if page.get("theme") == "vc":
    sys.exit("home.json ya es vc: regenera antes con build_home.py")
B = {}
for b in page["blocks"]:
    B.setdefault(b["type"], []).append(b)
hero, = B["mp-hero"]
intro, medest = B["mp-split"]
cards, = B["mp-cards"]
units, = B["mp-units"]
videos, = B["mp-videos"]
bene, = B["mp-benefits"]
team, = B["mp-team"]
contact, = B["mp-contact"]
reviews, = B["mp-reviews"]
nap, = B["mp-nap"]
U = "https://www.medicsintegralsalut.com/wp-content/uploads/"
WA = "https://api.whatsapp.com/send?phone=34620892236"


def img(path, alt):
    li = local_image(U + path)
    li["alt"] = alt
    return li


def strong(h):  # la maqueta usa <b>; el contenido literal usa <strong>: se deja <strong>
    return h


# tildes corregidas en los nombres (maqueta; NO_LITERAL.md)
FIX = {"Dr. Valenti Puig Divi": "Dr. Valentí Puig Divi", "Dr. Alberto Gonzalez": "Dr. Alberto González"}


def big(im):
    """Retrato: intenta el original sin el sufijo -300x300 (la maqueta pide 3:4 grande); si no existe, el actual."""
    import re as _re
    src = im["src"].replace("/images/wp/", "")
    orig = _re.sub(r"-\d+x\d+(?=\.webp$)", "", src)
    if orig != src:
        for ext in (".jpg", ".png", ".jpeg", ".webp"):
            li = local_image(U + orig[:-5] + ext)
            if li and li["w"] > im["w"]:
                return li
    return im


I18N = json.load(open("migracion/i18n-map.json"))
from urllib.parse import unquote


def lp(es_path):
    """Ruta en este idioma de una página española (mapa de TranslatePress)."""
    for g in I18N.values():
        if g.get("es") == es_path:
            return unquote(g.get(LANG, es_path))
    return es_path


def html_title(t):
    w = t.split()
    return " ".join(w[:-3]) + " <em>" + " ".join(w[-3:]) + "</em>" if len(w) > 4 else t


cta_val = {"text": units["cta"]["text"], "href": "#info"}
cta_wa = {"text": "WhatsApp 620 892 236", "href": WA, "style": "linea"}
nums = iter(["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX"])
K = iter(T["k"])

blocks = []
# HERO (título literal del H2 de la portada; subtítulo, micro y cifras: maqueta)
blocks.append({"type": "vc-hero", "kicker": hero["kicker"], "titleHtml": T.get("title_html") or html_title(hero["title"]),
               "sub": T["sub"], "ctas": [cta_val, cta_wa], "micro": T["micro"],
               "image": intro["image"], "ratingLabel": T["reviews_n"],
               "stats": [{"rating": True, "lbl": T["reviews_n"]}, {"big": "{since}", "lbl": T["since"]},
                         {"big": "SECPRE", "lbl": T["secpre"]}, {"big": T["free"], "lbl": T["first"]}]})
# I · la clínica (H1 literal)
blocks.append({"type": "vc-editorial", "num": next(nums), "kicker": next(K), "headingTag": "h1", "heading": intro["heading"],
               "paras": intro["paras"], "cta": {**intro["cta"], "style": "linea"},
               "image": contact["image"]})  # la de la maqueta (clinica-estetica-Girona, 580px fondo negro) no aguanta 3:4
# II · tratamientos (fotos: la imagen destacada de cada página de tratamiento, por orden)
fotos = ["2025/11/aumento-de-pecho-en-girona.jpg", "2021/10/LIPOWEB.jpg", "2019/10/Ginecomastia.jpg",
         "2025/10/rinoplastia.jpg", "2026/07/Balon-gastrico-en-Girona.jpg", "2026/07/Blefaroplastia.jpg"]
blocks.append({"type": "vc-trat", "num": next(nums), "kicker": next(K), "heading": cards["heading"], "sub": cards["sub"],
               "text": cards["text"], "cards": [{**c, "href": unquote(c["href"]), "image": img(fotos[i], c["title"])} for i, c in enumerate(cards["cards"])]})
# III · unidades (4 columnas como la maqueta; corporal a lo ancho). Orden del WordPress:
# 0 facial · 1 corporal · 2 cosmética · 3 obesidad · 4 mamas · 5 cirugía facial · 6 cirugía corporal · 7 masculina
G = units["groups"]
for x in G:
    for l in x["links"]:
        l["href"] = unquote(l["href"])
blocks.append({"type": "vc-unidades", "id": "unidades", "num": next(nums), "kicker": next(K), "heading": units["heading"],
               "text": units["text"], "columns": [[G[0]], [G[1], G[2]], [G[3], G[7]], [G[4], G[5]]], "wide": [G[6]],
               "cta": units["cta"]})
# IV · opiniones (reseñas reales de Google del widget Trustindex; nota y total desde site.json)
blocks.append({"type": "vc-resenas", "num": next(nums), "kicker": next(K), "heading": reviews["heading"],
               "sub": nap["heading"], "reviews": reviews["reviews"][:6], "source": T["review_src"],
               "summary": [{"rating": True, "lbl": T["avg"]}, {"big": "{count}", "lbl": T["verified"]},
                           {"big": "{since}", "lbl": T["since"]}],
               "more": {"text": T["more"], "href": "https://maps.google.com/maps?cid=4878100397339283721", "style": "linea"}})
# V · testimonios en vídeo (títulos nuevos: NO_LITERAL). OJO: Amador (García) es el MÉDICO; los pacientes son
# los que salen en cada miniatura (Emili, Elizabeth, Judith, Lidia).
YT4 = ["https://www.youtube.com/watch?v=AD2F_1nMRvY", "https://www.youtube.com/watch?v=gKfqSRLzb8o",
       "https://www.youtube.com/watch?v=ytuluT_sVg8", "https://www.youtube.com/watch?v=5tMvNB00PSI"]
items = []
for i, it in enumerate(videos["items"]):
    it["video"] = it.get("video") or YT4[i]  # en uk el enlace del vídeo falta en el WordPress: el mismo vídeo que en es
    items.append({"title": T["vt"][i], "video": it["video"].replace("&feature=youtu.be", ""), "image": {**it["image"], "alt": T["va"][i]}, "label": T["vlabel"]})
blocks.append({"type": "vc-videos", "num": next(nums), "kicker": next(K), "heading": videos["heading"],
               "sub": T.get("vsub") or videos["sub"], "items": items})
# VI · Medicina Estética Girona (sección literal de la portada que la maqueta no incluía: se conserva por SEO)
blocks.append({"type": "vc-editorial", "num": next(nums), "kicker": next(K), "headingTag": "h2", "heading": medest["heading"],
               "paras": medest["paras"], "image": medest["image"], "reverse": True, "bg": "crema-2"})
# VII · ventajas
blocks.append({"type": "vc-ventajas", "num": next(nums), "heading": bene["heading"], "items": bene["items"], "text": bene["text"],
               "cta": bene["cta"], "bg": "crema"})
# VIII · equipo (bios literales completas; retratos actuales)
blocks.append({"type": "vc-equipo", "id": "equipo", "num": next(nums), "kicker": next(K), "heading": team["heading"], "text": team["text"],
               "members": [{**m, "name": FIX.get(m["name"], m["name"]), "image": {**big(m["image"]), "alt": FIX.get(m["name"], m["name"])} if m.get("image") else None} for m in team["members"]],
               "card": {"title": contact["heading"], "text": contact["text"][0], "cta": cta_val}})
# distintivos
blocks.append({"type": "vc-distintivos", "logos": [
    img("2025/11/secpre.png", "SECPRE"), img("2025/11/clinica-diagonal.png", "Clínica Diagonal"),
    img("2026/03/clinica-tres-torres.png", "Clínica Tres Torres"), img("2026/03/centro-teknon.png", "Centro Médico Teknon"),
    img("2026/03/sccpre.png", "SCCPRE")]})
# IX · contacto (formulario PROPIO -> n8n -> Kommo; nunca Typeform)
R = T["rows"]
blocks.append({"type": "vc-contacto", "id": "info", "num": next(nums), "kicker": next(K), "heading": nap["heading"], "sub": re.sub(r"<[^>]+>", "", nap["lines"][0]),
               "rows": [{"ic": "◈", "k": R[0], "v": "Plaça Poeta Marquina, 3<br>" + T["country"], "note": T["ave"]},
                        {"ic": "✆", "k": R[1], "v": '<a href="tel:+34972209086">+34 972 20 90 86</a>'},
                        {"ic": "✆", "k": R[2], "v": '<a href="https://wa.me/34620892236">620 892 236</a>'},
                        {"ic": "✉", "k": R[3], "v": '<a href="mailto:info@medicsintegralsalut.com">info@medicsintegralsalut.com</a>'},
                        {"ic": "◷", "k": R[4], "v": T["hours"]}],
               "ctas": [{"text": "WhatsApp", "href": WA, "style": "linea"}],
               "formTitle": contact["heading"], "formText": contact["text"][0], "form": contact["form"],
               "map": {"q": "Plaça Poeta Marquina 3, 17002 Girona", "title": T["map"], "href": nap["mapsHref"]}})
# cierre local (sección nueva de la maqueta)
blocks.append({"type": "vc-cierre", "kicker": next(K), "heading": T["cierre_h"], "html": T["cierre"],
               "ctas": [{**cta_val, "style": "oscuro"}, {"text": T["fin"], "href": lp("/financiacion/"), "style": "linea"}]})

page["theme"] = "vc"
page["blocks"] = blocks
json.dump(page, open(SRC, "w"), ensure_ascii=False, indent=1)
print(SRC, len(blocks), "bloques vc")
