#!/usr/bin/env python3
"""Cabecera de las páginas del menú como una banda de foto a todo el ancho (referencia de dirección, 06/10/2026:
clinicatintore.com/clinica-rinoplastia-ultrasonica-barcelona/): foto en gris y el H1 grande en mayúsculas, centrado.
El texto y los botones que llevaba la cabecera pasan justo debajo (mismo texto; lo pinta PageHero.astro).
- Fotos: de la propia web (public/images), en gris, a 800 y 1600 px (o su ancho, si es menor) en public/images/paginas/.
- Edita el bloque pt-pagehero de cada página EN SU SITIO (los 6 idiomas): image = la foto de su grupo, alt = el H1.
Uso: python scripts/cabeceras_paginas.py   (idempotente; después de build_paginas_portada.py / build_equipo_portada.py)"""
import glob, json, os
from PIL import Image, ImageChops, ImageOps

# grupo i18n -> (nombre, foto de origen, encuadre object-position)
FOTOS = {
    "g0126": ("clinica", "wp/2022/01/DSC_0092-scaled.webp", "50% 40%"),
    "g0064": ("equipo", "wp/2024/03/IMG_3467-scaled.webp", "50% 35%"),
    "g0269": ("unidades", "wp/2024/01/mujer-marcada-cirugia-estetica.webp", "50% 50%"),
    "g0099": ("financiacion", "wp/2024/08/freepik-export-20240821110921SSys-scaled.webp", "50% 28%"),
    "g0031": ("blog", "wp/2022/03/shutterstock_612568868-scaled.webp", "50% 50%"),
    "g0078": ("contacto", "wp/2019/11/Dr-Mike-Dewever_ok.webp", "62% 30%"),
    "g0318": ("medicina-estetica-facial", "wp/2023/02/Diseno-sin-titulo-3.webp", "50% 40%", "recortar"),
    "g0278": ("cirugia-estetica-facial", "home/hero/facial.webp", "50% 28%"),
    "g0270": ("cirugia-estetica-corporal", "home/hero/corporal.webp", "50% 40%"),
    "g0315": ("medicina-estetica-corporal", "wp/2024/02/shutterstock_753507415-scaled.webp", "50% 40%"),
    "g0326": ("sobrepeso-y-obesidad", "home/hero/peso.webp", "50% 30%"),
    "g0314": ("medicina-cosmetica", "wp/2024/03/mujer-vista-lateral-gotas-agua-piel-scaled.webp", "50% 40%"),
    "g0297": ("cirugia-estetica-masculina", "wp/2022/06/Rectangle-4-1.webp", "62% 35%"),
}
DEST = "public/images/paginas"


def banda(nombre, origen, recortar=False):
    """versiones en gris a 800 y 1600 px de ancho (sin ampliar): devuelve src, srcset, ancho y alto de la mayor"""
    os.makedirs(DEST, exist_ok=True)
    im = ImageOps.grayscale(Image.open("public/images/" + origen).convert("RGB"))
    # fuera las bandas lisas de los lados (solo las fotos marcadas: otras tienen un fondo de estudio que es parte de la foto)
    fondo = Image.new("L", im.size, im.getpixel((0, 0)))
    caja = ImageChops.difference(im, fondo).point(lambda v: 255 if v > 12 else 0).getbbox()
    if recortar and caja and (caja[2] - caja[0]) < im.width * 0.97:
        im = im.crop((caja[0], 0, caja[2], im.height))
    anchos = sorted({min(800, im.width), min(1600, im.width)})
    out = []
    for w in anchos:
        f = f"{DEST}/{nombre}-{w}.webp"
        h = round(im.height * w / im.width)
        if not os.path.exists(f):
            im.resize((w, h), Image.LANCZOS).save(f, "WEBP", quality=68, method=6)
        out.append((f[len("public"):], w, h))
    src, w, h = out[-1]
    return {"src": src, "srcset": ", ".join(f"{s} {x}w" for s, x, _ in out), "w": w, "h": h}


img = {g: banda(n, o, *x) | {"pos": p} for g, (n, o, p, *x) in FOTOS.items()}
n = 0
for f in glob.glob("src/content/pages/*/*.json"):
    j = json.load(open(f, encoding="utf-8"))
    g = j.get("i18nGroup")
    if g not in FOTOS or j.get("theme") != "portada":
        continue
    b = next((b for b in j["blocks"] if b["type"] == "pt-pagehero"), None)
    if not b:
        print("SIN CABECERA", j["lang"], j["path"])
        continue
    b["image"] = {**img[g], "alt": b["heading"]}
    json.dump(j, open(f, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    n += 1
print(n, "cabeceras ·", ", ".join(f"{v['src'].split('/')[-1]}" for v in img.values()))
