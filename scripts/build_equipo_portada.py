#!/usr/bin/env python3
"""Página del equipo (/cirugia-plastica-girona-equipo-medico/ y sus 5 traducciones) con el diseño de la portada «prototipo».
Lee el HTML literal de los bloques vc-prosa (guardados la primera vez en migracion/equipo_vc/<lang>.json) y monta:
  pt-pagehero (H1, texto, foto en arco con la cita del Dr. Dewever) · pt-listas («¿Por qué elegirnos?» / «¿Cómo trabajamos?»)
  pt-medicos (fichas por especialidad: nombre, especialidad, nº de colegiado, CV y asociaciones desplegables) · pt-cierre.
Textos literales del WordPress; las fotos de las fichas son los retratos actuales de la portada (mismos médicos).
Uso: python scripts/build_equipo_portada.py"""
import json, os, glob, re, unicodedata
from bs4 import BeautifulSoup, Tag

GRUPO = "g0064"
T = json.load(open("scripts/portada_textos.json", encoding="utf-8"))
CHROME = json.load(open("src/data/vc-chrome.json", encoding="utf-8"))
WA = "https://api.whatsapp.com/send?phone=34620892236"
CLAVES = ["dewever", "vera", "ramirez", "puig", "ibarzabal", "perez", "gonzalez"]


def llano(s):
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()


def retratos():
    """Retratos de la portada (vc-equipo) por apellido."""
    m = [b for b in json.load(open("migracion/home_vc/es.json", encoding="utf-8")) if b["type"] == "vc-equipo"][0]["members"]
    return {k: x["image"] for x in m for k in CLAVES if k in llano(x["name"]) or k in llano(x["image"]["src"])}


def medico(vin, fuera):
    cs = vin.find_all("div", class_="vc-in-c", recursive=False)
    datos = cs[1]
    nombre = datos.find("h3").get_text(" ", strip=True)
    campos = [{"k": h.get_text(" ", strip=True), "v": h.find_next_sibling("p").get_text(" ", strip=True)}
              for h in datos.find_all("h5") if h.find_next_sibling("p")]
    det = [{"summary": d.find("summary").get_text(" ", strip=True),
            "html": "".join(str(x) for x in d.contents if not (isinstance(x, Tag) and x.name == "summary")).strip()} for d in fuera]
    img = cs[0].find("img")
    clave = next((k for k in CLAVES if k in llano(nombre)), None)
    return {"name": nombre, "campos": campos, "details": det, "clave": clave,
            "image": {"src": img["src"], "alt": img.get("alt") or nombre} if img else None}


R = retratos()
for f in glob.glob("src/content/pages/*/*.json"):
    page = json.load(open(f, encoding="utf-8"))
    if page.get("i18nGroup") != GRUPO:
        continue
    L = page["lang"]
    copia = f"migracion/equipo_vc/{L}.json"
    if not os.path.exists(copia):
        os.makedirs("migracion/equipo_vc", exist_ok=True)
        json.dump(page["blocks"], open(copia, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    vc = json.load(open(copia, encoding="utf-8"))
    html = [b["cols"][0]["html"] for b in vc]
    C, t = CHROME[L], T[L]

    b0 = BeautifulSoup(html[0], "html.parser")
    ps = b0.find_all("p")
    autor, cita = ps[0].get_text(" ", strip=True), ps[1].decode_contents().replace("<br/>", " ").strip()
    b1 = BeautifulSoup(html[1], "html.parser")
    listas = [{"heading": c.find("h2").get_text(" ", strip=True), "items": [li.decode_contents().strip() for li in c.find_all("li")]}
              for c in b1.find_all("div", class_="vc-in-c")]

    grupos, intro = [], None
    for h in html[2:]:
        s = BeautifulSoup(h, "html.parser")
        raiz = s.find("div", class_="vc-solo-escritorio") or s  # en el WordPress esta ficha solo se veía en escritorio
        hijos = [x for x in raiz.contents if isinstance(x, Tag)]
        for k, el in enumerate(hijos):
            if el.name == "h3":
                grupos.append({"titulo": el.get_text(" ", strip=True), "medicos": []})
            elif el.name == "p" and intro is None:
                intro = el.decode_contents().strip()
            elif el.name == "div" and "vc-in" in (el.get("class") or []):
                det = []
                for x in hijos[k + 1:]:
                    if x.name != "details":
                        break
                    det.append(x)
                if not grupos:
                    grupos.append({"titulo": "", "medicos": []})
                grupos[-1]["medicos"].append(medico(el, det))
    for g in grupos:
        for m in g["medicos"]:
            if m["clave"] in R:
                m["image"] = {**R[m["clave"]], "alt": m["name"]}
            m.pop("clave")

    equipo_home = [b for b in json.load(open(f"migracion/home_vc/{L}.json", encoding="utf-8")) if b["type"] == "vc-equipo"][0]
    card = equipo_home["card"]
    page["theme"] = "portada"
    page["blocks"] = [
        {"type": "pt-pagehero", "kicker": b1.find("h2").get_text(" ", strip=True), "headingTag": "h1",
         "heading": b1.find("h1").get_text(" ", strip=True), "text": b1.find("p").decode_contents().strip(),
         "ctas": [{"text": t["hero"]["cta"], "href": C["anchors"]["#info"]}, {"text": t["hero"]["wa"], "href": WA, "style": "wa"}],
         "image": {"src": "/images/wp/2019/11/Dr-Mike-Dewever_ok.webp", "w": 1600, "h": 708, "alt": t["hero"]["alt"]},
         "quote": {"html": cita, "author": autor}},
        {"type": "pt-listas", "cols": listas},
        {"type": "pt-medicos", "id": "equipo", "kicker": equipo_home["kicker"], "text": intro, "grupos": grupos},
        {"type": "pt-cierre", "heading": card["title"], "html": card["text"],
         "ctas": [{"text": card["cta"]["text"], "href": C["anchors"]["#info"]}, {"text": "WhatsApp", "href": WA, "style": "linea"}]},
    ]
    json.dump(page, open(f, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(L, page["path"], "·", [(g["titulo"][:28], len(g["medicos"])) for g in grupos])
