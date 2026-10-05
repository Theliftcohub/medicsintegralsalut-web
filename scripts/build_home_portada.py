#!/usr/bin/env python3
"""Portada «prototipo» (The Lift Co, 05/10/2026; maqueta en migracion/diseno/home-prototipo.html) para los 6 idiomas.
Convierte los bloques vc-* de src/content/pages/<lang>/home.json (textos literales del WordPress y de «Versión C»)
en bloques pt-*, en el orden de la maqueta, y añade los textos nuevos de scripts/portada_textos.json.
- Hero: el diseño del pantallazo de dirección (foto a sangre con el Dr. Mike Dewever, foto real de la clínica).
- Se conserva el texto literal de «Medicina Estética Girona» (peso SEO) aunque la maqueta no lo traía.
- Sin la sección de vídeos (la maqueta no la trae). Notas del diseñador: fuera.
Idempotente: la primera vez guarda los bloques vc-* en migracion/home_vc/<lang>.json y después siempre parte de ahí.
Uso: python scripts/build_home_portada.py"""
import json, os

LANGS = ["es", "ca", "en", "fr", "ru", "uk"]
T = json.load(open("scripts/portada_textos.json", encoding="utf-8"))
CHROME = json.load(open("src/data/vc-chrome.json", encoding="utf-8"))
WA = "https://api.whatsapp.com/send?phone=34620892236"
HERO_IMG = {"src": "/images/wp/2019/11/Dr-Mike-Dewever_ok.webp", "w": 1600, "h": 708}
COLLAGE = ["/images/wp/2025/11/recepcion-medic-salut.webp", "/images/wp/2026/07/Lifting-facial-en-Girona.webp",
           "/images/wp/2026/07/Abdominoplastia-en-Girona.webp", "/images/wp/2026/07/Balon-gastrico-en-Girona.webp"]
# unidades: orden de la portada del WordPress (columnas + ancha) -> filtro, y orden de la maqueta
CATS = ["facial", "corporal", "cosmetica", "obesidad", "masculina", "mamas", "facial", "corporal"]
ORDEN = [0, 6, 1, 7, 5, 4, 3, 2]


def ruta(lang, f):
    for n in os.listdir(f"src/content/pages/{lang}"):
        p = f"src/content/pages/{lang}/{n}"
        if json.load(open(p, encoding="utf-8")).get("i18nGroup") == "home":
            return p


def vars_(s, L, C):
    fin = C["footer"]["fin"]
    return (s.replace("{fin}", fin).replace("{tel}", "tel:+34972209086").replace("{wa}", WA)
             .replace("{contacto}", C["anchors"]["#info"]).replace("{equipo}", C["menu"][1]["href"]))


for L in LANGS:
    f = ruta(L, None)
    page = json.load(open(f, encoding="utf-8"))
    copia = f"migracion/home_vc/{L}.json"
    if not os.path.exists(copia):
        os.makedirs("migracion/home_vc", exist_ok=True)
        json.dump(page["blocks"], open(copia, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    vc = json.load(open(copia, encoding="utf-8"))
    t, C = T[L], CHROME[L]
    tipo = lambda x, n=0: [b for b in vc if b["type"] == x][n]
    hero, ed1, trat, uni, res = tipo("vc-hero"), tipo("vc-editorial"), tipo("vc-trat"), tipo("vc-unidades"), tipo("vc-resenas")
    ed2, ven, equ, dis, con, cie = tipo("vc-editorial", 1), tipo("vc-ventajas"), tipo("vc-equipo"), tipo("vc-distintivos"), tipo("vc-contacto"), tipo("vc-cierre")

    planos = [u for col in uni["columns"] for u in col] + list(uni.get("wide", []))
    unidades = [{**planos[i], "c": CATS[i]} for i in ORDEN if i < len(planos)]
    form = json.loads(json.dumps(con["form"]))
    for c in form["fields"]:
        if c["type"] != "checkbox":
            c["label"] = c.pop("placeholder")
        c["ancho"] = c["name"] not in ("nombre", "telefono")
    i = next(k for k, c in enumerate(form["fields"]) if c["name"] == "mensaje")
    form["fields"].insert(i, {"name": "tratamiento", "type": "select", "label": t["form"]["tratamiento"], "required": False, "ancho": True,
                              "options": [""] + [u["title"] for u in unidades], "vacio": t["form"]["tratamientoVacio"]})
    form["submit"] = t["form"]["submit"]

    page["theme"] = "portada"
    page["blocks"] = [
        {"type": "pt-hero", "eyebrow": t["hero"]["eyebrow"], "titleHtml": t["hero"].get("titulo") or hero["titleHtml"].replace("<br>", " "), "sub": t["hero"]["sub"],
         "ctas": [{"text": t["hero"]["cta"], "href": "#info"}, {"text": t["hero"]["wa"], "href": WA, "style": "wa"}],
         "reviews": t["hero"]["reviews"], "badge": t["hero"]["badge"], "image": {**HERO_IMG, "alt": t["hero"]["alt"]}},
        {"type": "pt-clinica", "kicker": ed1["kicker"], "headingTag": "h1", "heading": ed1["heading"], "paras": ed1["paras"],
         "sub": ven["heading"], "ventajas": [{**v, "d": vars_(v["d"], L, C)} for v in t["ventajas"]], "extra": ven.get("text", []),
         "contadores": t["contadores"], "equipo": len(equ["members"]), "collage": [{"src": s, "alt": ed1["heading"]} for s in COLLAGE]},
        {"type": "pt-trat", "kicker": trat["kicker"], "heading": trat["heading"], "sub": trat["sub"], "text": trat["text"],
         "cards": [{**c, "bullets": t["vinetas"][k]} for k, c in enumerate(trat["cards"])]},
        {"type": "pt-unidades", "id": "unidades", "kicker": uni["kicker"], "heading": uni["heading"], "text": uni["text"],
         "filtros": t["filtros"], "unidades": unidades, "cta": uni.get("cta")},
        {"type": "pt-texto", "kicker": ed2["kicker"], "heading": ed2["heading"], "paras": ed2["paras"], "image": ed2.get("image")},
        {"type": "pt-pasos", **{k: v for k, v in t["pasos"].items() if k != "items"},
         "items": [{**p, "d": vars_(p["d"], L, C)} for p in t["pasos"]["items"]]},
        {"type": "pt-equipo", "id": "equipo", "kicker": equ["kicker"], "heading": equ["heading"], "text": equ["text"],
         "members": equ["members"], "card": equ["card"], "mas": {"text": t["equipoMas"], "href": C["menu"][1]["href"]}},
        {"type": "pt-distintivos", "logos": dis["logos"]},
        {"type": "pt-resenas", **{k: v for k, v in res.items() if k not in ("type", "num")}},
        {"type": "pt-faq", "kicker": t["faq"]["kicker"], "heading": t["faq"]["heading"],
         "items": [{"q": x["q"], "a": vars_(x["a"], L, C)} for x in t["faq"]["items"]]},
        {"type": "pt-contacto", "id": "info", "kicker": con["kicker"], "heading": con["heading"], "sub": con["sub"],
         "titulo": t["form"]["titulo"], "texto": t["form"]["sub"], "legal": t["form"]["legal"], "form": form,
         "lateral": t["lateral"], "rows": con["rows"], "ctas": [{"text": C["cta"]["text"], "href": "#info"}, *con.get("ctas", [])], "map": con.get("map")},
        {"type": "pt-cierre", **{k: v for k, v in cie.items() if k != "type"}},
    ]
    json.dump(page, open(f, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(L, f, len(page["blocks"]), "bloques")
