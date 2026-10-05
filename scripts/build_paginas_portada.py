#!/usr/bin/env python3
"""Páginas interiores con el diseño de la portada «prototipo» (petición de dirección, 05/10/2026), en los 6 idiomas:
financiación, blog, contacto y las 7 unidades. Parte de los bloques actuales (guardados la primera vez en
migracion/paginas_vc/<grupo>/<lang>.json) y:
- cambia la cabecera de página (primer bloque con solo un encabezado) por pt-pagehero: el mismo H1, su texto y una foto
  en arco (la del primer tratamiento de la unidad, o una foto de la clínica);
- contacto: el formulario y la ficha pasan al bloque pt-contacto de la portada (mismos campos literales del CF7);
- financiación: el bloque final «¡Pero lo mejor para conocernos…!» pasa a la banda pt-cierre;
- columnas con un único enlace (p. ej. los tratamientos de Medicina estética corporal) pasan a tarjetas (vc-tarjetas);
- el resto de bloques se quedan (texto literal) y toman la piel de la portada (portada-extra.css) al ir dentro de .pt.
Uso: python scripts/build_paginas_portada.py"""
import glob, json, os, re
from urllib.parse import unquote
from bs4 import BeautifulSoup

GRUPOS = {"g0099": "financiacion", "g0031": "blog", "g0078": "contacto", "g0318": "unidad", "g0314": "unidad", "g0270": "unidad",
          "g0315": "unidad", "g0326": "unidad", "g0278": "unidad", "g0297": "unidad"}
T = json.load(open("scripts/portada_textos.json", encoding="utf-8"))
CHROME = json.load(open("src/data/vc-chrome.json", encoding="utf-8"))
WA = "https://api.whatsapp.com/send?phone=34620892236"
CLINICA = {"src": "/images/wp/2025/11/recepcion-medic-salut.webp", "w": 922, "h": 618}
LOGO = re.compile(r"/(mps|logo|financiera)[^/]*$", re.I)
ENCABEZADO = re.compile(r"^\s*<h([1-6])[^>]*>(.*?)</h\1>((?:\s*<p>.*?</p>)*)\s*$", re.S)
PAGINAS = {}
for f in glob.glob("src/content/pages/*/*.json"):
    j = json.load(open(f, encoding="utf-8"))
    PAGINAS[j["path"]] = (f, j)


def foto_de(path):
    """Foto de una página: su og:image (si no es un logo) o la primera foto grande de su contenido."""
    j = (PAGINAS.get(unquote(path)) or (None, None))[1]
    if not j:
        return None
    og = j["seo"].get("ogImage")
    if og and not LOGO.search(og):
        return og
    for m in re.finditer(r"<img\b[^>]*>", json.dumps(j["blocks"], ensure_ascii=False).replace('\\"', '"')):
        src, w = re.search(r'src="([^"]+)"', m.group(0)), re.search(r'width="(\d+)"', m.group(0))
        if src and w and int(w.group(1)) >= 300 and not LOGO.search(src.group(1)) and "vc-ico" not in m.group(0):
            return src.group(1)


def texto_plano(h):
    return BeautifulSoup(h, "html.parser").get_text(" ", strip=True)


UN_ENLACE = re.compile(r'^\s*<p><a href="([^"]+)">([^<]+)</a></p>\s*$')


def columnas_a_tarjetas(b):
    """vc-prosa cuyas columnas son, cada una, un único enlace -> vc-tarjetas (mismo texto y enlace)."""
    if b["type"] != "vc-prosa" or b.get("intro") or len(b.get("cols", [])) < 2:
        return b
    m = [UN_ENLACE.match(c.get("html") or "") for c in b["cols"]]
    if not all(m):
        return b
    return {"type": "vc-tarjetas", "items": [{"text": x.group(2), "href": x.group(1)} for x in m], **({"bg": b["bg"]} if b.get("bg") else {})}


def portada_contacto(L):
    home = json.load(open(PAGINAS[CHROME[L]["home"]][0], encoding="utf-8"))
    return next(b for b in home["blocks"] if b["type"] == "pt-contacto")


for f, page in list(PAGINAS.values()):
    tipo = GRUPOS.get(page.get("i18nGroup"))
    if not tipo:
        continue
    L, C, t = page["lang"], CHROME[page["lang"]], T[page["lang"]]
    copia = f"migracion/paginas_vc/{page['i18nGroup']}/{L}.json"
    if not os.path.exists(copia):
        os.makedirs(os.path.dirname(copia), exist_ok=True)
        json.dump(page["blocks"], open(copia, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    bloques = json.load(open(copia, encoding="utf-8"))

    # cabecera: primer bloque con solo un encabezado (y quizá un subtítulo); si no hay, el título de la página
    m = ENCABEZADO.match(bloques[0]["cols"][0].get("html") or "") if bloques[0]["type"] == "vc-prosa" and len(bloques[0].get("cols", [])) == 1 else None
    titulo, sub = (texto_plano(m.group(2)), m.group(3).strip()) if m else (page.get("title") or page["seo"]["title"], "")
    titulo = re.sub(r"\s*[-–—|]\s*Medics\s*Integral\s*Salut\s*$", "", titulo, flags=re.I)
    resto = [columnas_a_tarjetas(b) for b in (bloques[1:] if m else bloques)]
    imagen, kicker = None, {"financiacion": C["menu"][3]["text"], "blog": C["menu"][4]["text"],
                            "contacto": C["menu"][5]["text"], "unidad": C["menu"][2]["text"]}[tipo]
    if tipo == "unidad":
        primera = next((b["items"][0]["href"] for b in resto if b["type"] == "vc-tarjetas" and b["items"] and b["items"][0].get("href")), None)
        src = foto_de(primera) if primera else None
        if not src:  # unidades sin tarjetas: la primera foto grande de su propio contenido
            src = foto_de(page["path"])
        imagen = {"src": src, "w": 600, "h": 680, "alt": titulo} if src else {**CLINICA, "alt": titulo}
    elif tipo in ("financiacion", "contacto"):
        imagen = {**CLINICA, "alt": titulo}
    # financiación: los párrafos iniciales del bloque siguiente pasan a la cabecera
    if tipo == "financiacion" and not sub:
        s = BeautifulSoup(resto[0]["cols"][0]["html"], "html.parser")
        ps = [p for p in s.find_all("p", recursive=False)]
        sub = "".join(str(p) for p in ps)
        for p in ps:
            p.decompose()
        resto[0] = {**resto[0], "cols": [{"html": str(s).strip()}]}
    if tipo == "contacto":
        intro = resto[0]["cols"][0]["html"]  # «Pide una visita gratuita…»
        sub = sub or intro
    ctas = [] if tipo == "blog" else [{"text": t["hero"]["cta"], "href": C["anchors"]["#info"] if tipo != "contacto" else "#form"},
                                     {"text": t["hero"]["wa"], "href": WA, "style": "wa"}]
    nuevos = [{"type": "pt-pagehero", "kicker": kicker, "headingTag": "h1", "heading": titulo, "text": sub, "ctas": ctas,
               **({"image": imagen} if imagen else {})}]

    if tipo == "contacto":
        pc = json.loads(json.dumps(portada_contacto(L)))
        viejo = resto[0]["cols"][1]["form"]
        pc["form"]["name"], pc["form"]["thanks"] = viejo["name"], viejo["thanks"]
        pc.pop("kicker", None)
        pc["heading"], pc["sub"] = "", ""
        tabla = resto[0]["cols"][2]["html"]  # tabla de protección de datos (literal)
        nuevos += [pc, {"type": "vc-prosa", "cols": [{"html": tabla}]}]
        nuevos += [b for b in resto[1:] if "vc-embed--mapa" not in json.dumps(b)]  # «te llamamos»; el mapa ya va en pt-contacto
    elif tipo == "financiacion":
        cierre = resto[-1]["cols"][0]["html"]
        s = BeautifulSoup(cierre, "html.parser")
        h = s.find(["h2", "h3"])
        btn, tel = s.find("a", class_="btn"), s.find("a", href=re.compile("^tel:"))
        nuevos += resto[:-1] + [{"type": "pt-cierre", "heading": h.get_text(" ", strip=True), "html": "",
                                 "ctas": [{"text": btn.get_text(" ", strip=True), "href": btn["href"]},
                                          {"text": tel.get_text(" ", strip=True), "href": tel["href"], "style": "linea"}]}]
    else:
        nuevos += resto
    page["theme"] = "portada"
    page["blocks"] = nuevos
    json.dump(page, open(f, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(L, tipo, page["path"], "·", titulo[:40], "·", (imagen or {}).get("src"))
