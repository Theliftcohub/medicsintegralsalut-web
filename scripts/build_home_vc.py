#!/usr/bin/env python3
"""Portada con el diseño «Versión C» (maqueta The Lift Co, migracion/diseno/home-version-c.html).
Parte del contenido LITERAL ya extraído por build_home.py (src/content/pages/es/home.json con bloques mp-*)
y lo reordena en los bloques vc-* de la maqueta. Los textos nuevos de la maqueta están en NO_LITERAL.md.
Cifras de Google (nota y nº de reseñas) NO van aquí: salen de src/data/site.json -> rating (dato vivo de GBP).
Uso: python3 scripts/build_home.py && python3 scripts/build_home_vc.py"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wp_lib import local_image

SRC = "src/content/pages/es/home.json"
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


cta_val = {"text": "Solicitar valoración", "href": "#info"}
cta_wa = {"text": "WhatsApp 620 892 236", "href": WA, "style": "linea"}
nums = iter(["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX"])

blocks = []
# HERO (título literal del H2 de la portada; subtítulo, micro y cifras: maqueta)
blocks.append({"type": "vc-hero", "kicker": hero["kicker"], "titleHtml": "Nuestros pacientes<br>son nuestra mejor<br><em>carta de presentación</em>",
               "sub": "Cirugía plástica y medicina estética en el centro de Girona. Resultados naturales, criterio médico y acompañamiento en cada paso.",
               "ctas": [cta_val, cta_wa], "micro": "Sin compromiso · Atención médica · Respuesta el mismo día laborable",
               "image": intro["image"], "ratingLabel": "{count} reseñas en Google",
               "stats": [{"rating": True, "lbl": "{count} reseñas en Google"}, {"big": "{since}", "lbl": "Atendiendo en Girona"},
                         {"big": "SECPRE", "lbl": "Cirujanos colegiados"}, {"big": "Gratuita", "lbl": "Primera valoración"}]})
# I · la clínica (H1 literal)
blocks.append({"type": "vc-editorial", "num": next(nums), "kicker": "La clínica", "headingTag": "h1", "heading": intro["heading"],
               "paras": intro["paras"], "cta": {**intro["cta"], "style": "linea"},
               "image": contact["image"]})  # la de la maqueta (clinica-estetica-Girona, 580px fondo negro) no aguanta 3:4
# II · tratamientos (fotos: la imagen destacada de cada página de tratamiento)
fotos = {"/unidades/cirugia-estetica-mamas/aumento-de-pecho-girona/": "2025/11/aumento-de-pecho-en-girona.jpg",
         "/unidades/cirugia-estetica-corporal/liposuccion/": "2021/10/LIPOWEB.jpg",
         "/unidades/cirugia-estetica-masculina/ginecomastia/": "2019/10/Ginecomastia.jpg",
         "/unidades/cirugia-estetica-facial/rinoplastia-girona/": "2025/10/rinoplastia.jpg",
         "/unidades/sobrepeso-y-obesidad/balon-gastrico-girona/": "2026/07/Balon-gastrico-en-Girona.jpg",
         "/unidades/cirugia-estetica-facial/blefaroplastia-girona/": "2026/07/Blefaroplastia.jpg"}
blocks.append({"type": "vc-trat", "num": next(nums), "kicker": "Tratamientos", "heading": cards["heading"], "sub": cards["sub"],
               "text": cards["text"], "cards": [{**c, "image": img(fotos[c["href"]], c["title"])} for c in cards["cards"]]})
# III · unidades (4 columnas como la maqueta; corporal a lo ancho)
g = {x["title"]: x for x in units["groups"]}
cols = [["Medicina estética facial"], ["Medicina estética corporal", "Medicina cosmética"],
        ["Sobrepeso y obesidad", "Cirugía estética masculina"], ["Cirugía estética mamas", "Cirugía estética facial"]]
used = {t for c in cols for t in c}
missing = [t for t in used if t not in g]
if missing:
    sys.exit(f"grupos no encontrados: {missing} · hay {list(g)}")
wide = [t for t in g if t not in used]
blocks.append({"type": "vc-unidades", "id": "unidades", "num": next(nums), "kicker": "Especialidades", "heading": units["heading"],
               "text": units["text"], "columns": [[g[t] for t in c] for c in cols], "wide": [g[t] for t in wide],
               "cta": units["cta"]})
# IV · opiniones (reseñas reales de Google del widget Trustindex; nota y total desde site.json)
blocks.append({"type": "vc-resenas", "num": next(nums), "kicker": "Opiniones", "heading": reviews["heading"],
               "sub": nap["heading"], "reviews": reviews["reviews"][:6], "source": "Reseña en Google",
               "summary": [{"rating": True, "lbl": "Valoración media"}, {"big": "{count}", "lbl": "Reseñas verificadas"},
                           {"big": "{since}", "lbl": "Atendiendo en Girona"}],
               "more": {"text": "Ver las {count} reseñas en Google", "href": "https://maps.google.com/maps?cid=4878100397339283721", "style": "linea"}})
# V · testimonios en vídeo (títulos propuestos por la maqueta: NO_LITERAL, pendiente de confirmar)
# OJO: la maqueta decía «Amador: su bypass…», pero Amador (García) es el MÉDICO; el paciente que sale en la miniatura es Emili.
# Los nombres de paciente son los que ya aparecen en cada miniatura publicada (Emili, Elizabeth, Judith, Lidia).
vt = ["Bypass gástrico: el testimonio de Emili", "Aumento de pecho: el testimonio de Elizabeth",
      "Rinoplastia: el testimonio de Judith", "Arrugas de expresión: el testimonio de Lidia"]
va = ["Testimonio bypass gástrico", "Testimonio aumento de pecho", "Testimonio rinoplastia", "Testimonio arrugas de expresión"]
items = []
for i, it in enumerate(videos["items"]):
    items.append({"title": vt[i], "video": it["video"].replace("&feature=youtu.be", ""), "image": {**it["image"], "alt": va[i]}, "label": "Testimonio"})
blocks.append({"type": "vc-videos", "num": next(nums), "kicker": "Testimonios", "heading": videos["heading"],
               "sub": "Los buenos resultados, nuestra principal motivación", "items": items})
# VI · Medicina Estética Girona (sección literal de la portada que la maqueta no incluía: se conserva por SEO)
blocks.append({"type": "vc-editorial", "num": next(nums), "kicker": "Medicina estética", "headingTag": "h2", "heading": medest["heading"],
               "paras": medest["paras"], "image": medest["image"], "reverse": True, "bg": "crema-2"})
# VII · ventajas
blocks.append({"type": "vc-ventajas", "num": next(nums), "heading": bene["heading"], "items": bene["items"], "text": bene["text"],
               "cta": bene["cta"], "bg": "crema"})
# VIII · equipo (bios literales completas; retratos actuales)
blocks.append({"type": "vc-equipo", "id": "equipo", "num": next(nums), "kicker": "El equipo", "heading": team["heading"], "text": team["text"],
               "members": [{**m, "name": FIX.get(m["name"], m["name"]), "image": {**big(m["image"]), "alt": FIX.get(m["name"], m["name"])} if m.get("image") else None} for m in team["members"]], "card": {"title": contact["heading"], "text": contact["text"][0], "cta": cta_val}})
# distintivos
blocks.append({"type": "vc-distintivos", "logos": [
    img("2025/11/secpre.png", "SECPRE"), img("2025/11/clinica-diagonal.png", "Clínica Diagonal"),
    img("2026/03/clinica-tres-torres.png", "Clínica Tres Torres"), img("2026/03/centro-teknon.png", "Centro Médico Teknon"),
    img("2026/03/sccpre.png", "SCCPRE")]})
# IX · contacto (formulario PROPIO -> n8n -> Kommo; nunca Typeform)
blocks.append({"type": "vc-contacto", "id": "info", "num": next(nums), "kicker": "Contacto", "heading": nap["heading"], "sub": "Clínica Cirugía Estética | Médics Integral Salut",
               "rows": [{"ic": "◈", "k": "Dirección", "v": "Plaça Poeta Marquina, 3<br>17002 Girona, España", "note": "A 5 minutos de la estación del AVE"},
                        {"ic": "✆", "k": "Teléfono", "v": '<a href="tel:+34972209086">+34 972 20 90 86</a>'},
                        {"ic": "✆", "k": "WhatsApp", "v": '<a href="https://wa.me/34620892236">620 892 236</a>'},
                        {"ic": "✉", "k": "Email", "v": '<a href="mailto:info@medicsintegralsalut.com">info@medicsintegralsalut.com</a>'},
                        {"ic": "◷", "k": "Horario", "v": "Lunes a viernes: 10:00h a 20:00h<br>Sábado y domingo: cerrado"}],
               "ctas": [{"text": "WhatsApp", "href": WA, "style": "linea"}],
               "formTitle": contact["heading"], "formText": contact["text"][0], "form": contact["form"],
               "map": {"q": "Plaça Poeta Marquina 3, 17002 Girona", "title": "Medics Integral Salut en Girona", "href": nap["mapsHref"]}})
# cierre local
blocks.append({"type": "vc-cierre", "kicker": "Girona y Costa Brava", "heading": "Clínica de cirugía y medicina estética para toda la provincia de Girona",
               "html": "Recibimos pacientes de <strong>Figueres, Olot, Banyoles, Salt, Blanes, Lloret de Mar, Palamós, Palafrugell</strong> y toda la <strong>Costa Brava</strong>. Estamos en el centro de Girona (Plaça Poeta Marquina, 3), a 5 minutos de la estación del AVE, con financiación disponible y primera valoración gratuita.",
               "ctas": [{**cta_val, "style": "oscuro"}, {"text": "Ver financiación", "href": "/financiacion/", "style": "linea"}]})

page["theme"] = "vc"
page["blocks"] = blocks
json.dump(page, open(SRC, "w"), ensure_ascii=False, indent=1)
print(SRC, len(blocks), "bloques vc")
