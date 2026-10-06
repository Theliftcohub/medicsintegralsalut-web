#!/usr/bin/env python3
"""Secciones nuevas de la portada (maqueta de dirección, 06/10/2026), en los 6 idiomas:
5 vídeos · 6 «la doctora responde» · 7 tratamientos más pedidos · 8 historias reales · 9 resultados en consulta ·
10 aviso celulitis/lipedema · 11 banda final.
Edita cada home.json EN SU SITIO (no regenera el resto: conserva lo que ya corrigieron pulir_contenido.py y
corregir_traducciones.py). Sustituye pt-trat, pt-pasos, pt-resenas y pt-faq; el texto literal de pt-trat pasa a la
introducción de «tratamientos más pedidos» y las reseñas de Google alimentan «historias reales». Lo quitado se guarda
la primera vez en migracion/home_secciones/<lang>.json (de ahí se lee siempre: idempotente).
Textos: scripts/home_secciones.json. Miniaturas 9:16 de los vídeos: public/images/home/reels/<id>.webp.
Uso: python scripts/home_secciones.py   (después: corregir_traducciones.py y npm run build)"""
import glob, io, json, os, re, urllib.request
from PIL import Image

LANGS = ["es", "ca", "en", "fr", "ru", "uk"]
T = json.load(open("scripts/home_secciones.json", encoding="utf-8"))
PORTADA = json.load(open("scripts/portada_textos.json", encoding="utf-8"))
WA = "https://api.whatsapp.com/send?phone=34620892236"
# pt-cierre: lo repite la banda final (11); pt-hero: sustituido por el carrusel (referencia clinicatintore.com)
QUITAR = ("pt-trat", "pt-pasos", "pt-resenas", "pt-faq", "pt-cierre", "pt-hero")
NUEVOS = ("ps-hero", "ps-reels", "ps-doctora", "ps-pedidos", "ps-historias", "ps-resultados", "ps-aviso", "ps-banda")
# hero: grupo i18n de la unidad de destino + foto en gris (public/images/home/hero/)
HERO = [("g0278", "/images/home/hero/facial.webp"), ("g0291", "/images/home/hero/pecho.webp"),
        ("g0270", "/images/home/hero/corporal.webp"), ("g0326", "/images/home/hero/peso.webp")]
ORDEN = ["ps-hero", "pt-clinica", "pt-unidades", "pt-equipo", "pt-distintivos", "ps-reels", "ps-doctora", "ps-pedidos",
         "ps-historias", "ps-resultados", "ps-aviso", "pt-texto", "pt-contacto", "ps-banda"]
# vídeos de testimonios del canal de la clínica (los de la portada del WordPress)
VIDEOS = ["AD2F_1nMRvY", "gKfqSRLzb8o", "ytuluT_sVg8", "5tMvNB00PSI"]
# fotograma de YouTube que se usa de miniatura (maxres1/2/3 = 25/50/75 % del vídeo): el que muestra a la paciente centrada.
# La miniatura por defecto es un cartel de texto que no sirve en vertical.
FOTOGRAMA = {"AD2F_1nMRvY": "maxres2", "gKfqSRLzb8o": "maxres2", "ytuluT_sVg8": "maxres2", "5tMvNB00PSI": "maxres3"}
# reseñas de Google que se usan (nombre tal cual en Google) y su etiqueta (orden de T[L]["historias"]["etiquetas"])
RESENAS = ["NATALIA MARTINEZ", "Alisson Mijas", "Camila Constanza Vélez Silva"]
# tarjetas y aviso: grupo i18n de la página de destino + foto
CARDS = [("g0294", "/images/wp/2024/03/mujer-vista-lateral-gotas-agua-piel-scaled-1024x683.webp"),
         ("g0326", "/images/wp/2026/07/Dietetica-y-nutricion-en-Girona.webp"),
         ("g0288", "/images/wp/2025/10/rinoplastia.webp")]
AVISO = "g0316"
FOTO_DOCTORA = "/images/wp/2024/02/doctor-su-paciente-escogiendo-protesis-mamaria-oficina-1-scaled-1024x683.webp"
FOTO_RESULTADOS = "/images/wp/2026/07/Hidreclat-hidratacion-facial-en-profundidad-en-Girona.webp"


def img(src, alt):
    w, h = Image.open("public" + src).size
    return {"src": src, "w": w, "h": h, "alt": alt}


def miniatura(vid):
    """miniatura de YouTube recortada a 9:16 (360x640, WebP): ligera y local (sin pedir nada a YouTube al cargar)"""
    dest = f"public/images/home/reels/{vid}.webp"
    if not os.path.exists(dest):
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        n = FOTOGRAMA.get(vid, "maxres2")[-1]
        for calidad in (f"maxres{n}", f"sd{n}", f"hq{n}"):
            try:
                datos = urllib.request.urlopen(f"https://i.ytimg.com/vi/{vid}/{calidad}.jpg", timeout=20).read()
                im = Image.open(io.BytesIO(datos)).convert("RGB")
                if im.size[0] >= 480:
                    break
            except Exception:
                continue
        w, h = im.size
        ancho = round(h * 9 / 16)
        im = im.crop(((w - ancho) // 2, 0, (w - ancho) // 2 + ancho, h)).resize((360, 640), Image.LANCZOS)
        im.save(dest, "WEBP", quality=72, method=6)
    return {"src": dest[len("public"):], "w": 360, "h": 640}


def cita(texto):
    """primeras frases de la reseña (literal), entre 60 y 190 caracteres"""
    frases = re.split(r"(?<=[.!?])\s+", texto.strip())
    out = ""
    for f in frases:
        if out and (len(out) >= 60 or len(out) + len(f) > 190):
            break
        out = (out + " " + f).strip()
    return out if len(out) <= 200 else out[:190].rsplit(" ", 1)[0] + "…"


def nombre(n):
    partes = n.title().split()
    return f"{partes[0]} {partes[-2]}" if len(partes) >= 4 else " ".join(partes)


# páginas por grupo i18n e idioma
DESTINO = {}
for f in glob.glob("src/content/pages/*/*.json"):
    j = json.load(open(f, encoding="utf-8"))
    if j.get("i18nGroup"):
        DESTINO[(j["i18nGroup"], j["lang"])] = j["path"]
enlace = lambda g, L: DESTINO.get((g, L)) or DESTINO.get((g, "es")) or ("/" if L == "es" else f"/{L}/")

reels_img = [miniatura(v) for v in VIDEOS]
for L in LANGS:
    f = next(p for p in glob.glob(f"src/content/pages/{L}/*.json") if json.load(open(p, encoding="utf-8")).get("i18nGroup") == "home")
    page = json.load(open(f, encoding="utf-8"))
    copia = f"migracion/home_secciones/{L}.json"
    guardado = json.load(open(copia, encoding="utf-8")) if os.path.exists(copia) else []
    nuevos_q = [b for b in page["blocks"] if b["type"] in QUITAR and b["type"] not in {g["type"] for g in guardado}]
    if nuevos_q or not os.path.exists(copia):
        os.makedirs(os.path.dirname(copia), exist_ok=True)
        json.dump(guardado + nuevos_q, open(copia, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    quitado = {b["type"]: b for b in json.load(open(copia, encoding="utf-8"))}
    t = T[L]
    resenas = {r["name"]: r["text"] for r in quitado["pt-resenas"]["reviews"]}

    h = t["hero"]
    nuevos = {
        "ps-hero": {"type": "ps-hero", "kicker": h["kicker"], "label": h["label"], "prev": h["prev"], "next": h["next"], "ir": h["ir"],
                    "slides": [{"title": tit, "sub": sub, "href": enlace(g, L), "ver": h["ver"], "cta": {"text": h["cta"], "href": "#info"},
                                "image": img(src, tit)} for (tit, sub), (g, src) in zip(h["slides"], HERO)]},
        "ps-reels": {"type": "ps-reels", "heading": t["reels"]["heading"], "sub": t["reels"]["sub"], "ver": t["reels"]["ver"], "cerrar": t["reels"]["cerrar"],
                     "perfil": {"text": "@medicsintegralsalut", "href": "https://www.instagram.com/medicsintegralsalut/"},
                     "items": [{"title": tit, "video": f"https://www.youtube.com/watch?v={v}", "image": im, "label": t["reels"]["chip"]}
                               for tit, v, im in zip(t["reels"]["titulos"], VIDEOS, reels_img)]},
        "ps-doctora": {"type": "ps-doctora", "kicker": t["doctora"]["kicker"], "heading": t["doctora"]["heading"],
                       "image": img(FOTO_DOCTORA, t["doctora"]["alt"]), "items": t["doctora"]["items"]},
        "ps-pedidos": {"type": "ps-pedidos", "heading": t["pedidos"]["heading"], "intro": quitado["pt-trat"].get("text", []),
                       "cards": [{**c, "href": enlace(g, L), "image": img(src, c["title"])} for c, (g, src) in zip(t["pedidos"]["cards"], CARDS)]},
        "ps-historias": {"type": "ps-historias", "heading": t["historias"]["heading"],
                         "items": [{"name": nombre(n), "label": et, "quote": cita(resenas[n]), "source": t["historias"]["fuente"]}
                                   for n, et in zip(RESENAS, t["historias"]["etiquetas"]) if n in resenas]},
        "ps-resultados": {"type": "ps-resultados", "kicker": t["resultados"]["kicker"], "heading": t["resultados"]["heading"],
                          "text": t["resultados"]["text"], "image": img(FOTO_RESULTADOS, t["resultados"]["alt"])},
        "ps-aviso": {"type": "ps-aviso", "heading": t["aviso"]["heading"], "text": t["aviso"]["text"], "cta": {"text": t["aviso"]["cta"], "href": enlace(AVISO, L)}},
        "ps-banda": {"type": "ps-banda", "heading": t["banda"]["heading"],
                     "linea": t["banda"]["linea"].replace("{wa}", f'<a href="{WA}" rel="noopener" target="_blank">620 892 236</a>'),
                     "cta": {"text": PORTADA[L]["hero"]["cta"] + " →", "href": "#info"}},
    }
    actuales = {b["type"]: b for b in page["blocks"] if b["type"] not in QUITAR and b["type"] not in NUEVOS}
    todos = {**actuales, **nuevos}
    sobran = [k for k in todos if k not in ORDEN]
    page["blocks"] = [todos[k] for k in ORDEN if k in todos] + [todos[k] for k in sobran]
    json.dump(page, open(f, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(L, f, [b["type"] for b in page["blocks"]])
