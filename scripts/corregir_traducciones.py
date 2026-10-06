#!/usr/bin/env python3
"""Corrige traducciones defectuosas heredadas del WordPress (TranslatePress, traducción automática). Idempotente.
Se ejecuta después de pulir_contenido.py. Registro en NO_LITERAL.md (05/10/2026).

1. chrome     Menú, botón, pie y nombres de tratamientos destacados por idioma (scripts/chrome_traducciones.json):
              «units/funding/Request valuation», «Единицы/контакто/Запросить оценку», «Balla gàstrica»…
2. migas      Primera miga = «Inicio» en el idioma de la página (venía «Start», «Début», «Начало»).
3. teléfono   «0620 892 236» (solo en inglés) -> «620 892 236».
4. fechas     Fechas en español dentro de páginas en otro idioma («julio 2026», «20 may 2026», «4 jul 2026»)
              -> mes en el idioma de la página.
5. etiquetas  «Revisado por», «Autor:», «Actualizado:» en páginas que no son en español -> etiqueta traducida.
              Y palabras mal traducidas de forma sistemática: en «valuation» (tasación) -> «consultation», «hunch» -> «hump»;
              ru «Контакто» -> «Контакты».
6. textos     Fragmentos en el idioma equivocado (scripts/traducciones_contenido/<lang>.json: original -> traducción),
              sustituidos en los nodos de texto del HTML de cada página/entrada de ese idioma.
Uso: python scripts/corregir_traducciones.py"""
import glob, json, os, re
from collections import Counter

LANGS = ["ca", "en", "fr", "ru", "uk"]
C = Counter()
UI = json.load(open("src/i18n/ui.json", encoding="utf-8"))

# ---- 1) cabecera y pie ----
CH = json.load(open("scripts/chrome_traducciones.json", encoding="utf-8"))
chrome = json.load(open("src/data/vc-chrome.json", encoding="utf-8"))
for L, fix in CH.items():
    if L not in chrome:
        continue
    c = chrome[L]
    for i, txt in enumerate(fix.get("menu", [])):
        if txt and c["menu"][i]["text"] != txt:
            c["menu"][i]["text"] = txt; C["chrome"] += 1
    if fix.get("cta") and c["cta"]["text"] != fix["cta"]:
        c["cta"]["text"] = fix["cta"]; C["chrome"] += 1
    for k, v in fix.get("footer", {}).items():
        if c["footer"].get(k) != v:
            c["footer"][k] = v; C["chrome"] += 1
    for viejo, nuevo in fix.get("trat", {}).items():
        for t in c["footer"]["trat"]:
            if t["text"] == viejo:
                t["text"] = nuevo; C["chrome"] += 1
    for viejo, nuevo in fix.get("units", {}).items():
        def ren(xs):
            for u in xs:
                if u["text"] == viejo:
                    u["text"] = nuevo; C["chrome"] += 1
                ren(u.get("sub", []))
        ren(c.get("units", []))
json.dump(chrome, open("src/data/vc-chrome.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

# ---- 4) meses ----
MESES = {
    "es": ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"],
    "ca": ["de gener", "de febrer", "de març", "d'abril", "de maig", "de juny", "de juliol", "d'agost", "de setembre", "d'octubre", "de novembre", "de desembre"],
    "en": ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"],
    "fr": [(r"\bSel, Figueres\b", "Salt, Figueres"), "janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"],
    "ru": ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"],
    "uk": ["січня", "лютого", "березня", "квітня", "травня", "червня", "липня", "серпня", "вересня", "жовтня", "листопада", "грудня"],
}
ABREV_ES = {"ene": 0, "feb": 1, "mar": 2, "abr": 3, "may": 4, "jun": 5, "jul": 6, "ago": 7, "sep": 8, "oct": 9, "nov": 10, "dic": 11}
for m in MESES["es"]:
    ABREV_ES[m] = MESES["es"].index(m)
FECHA = re.compile(r"\b(?:(\d{1,2}) )?(" + "|".join(sorted(ABREV_ES, key=len, reverse=True)) + r")\b\.? (20\d\d)")


# nominativo del mes para fechas sin día en ruso/ucraniano
NOM = {"ru": ["январь", "февраль", "март", "апрель", "май", "июнь", "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь"],
       "uk": ["січень", "лютий", "березень", "квітень", "травень", "червень", "липень", "серпень", "вересень", "жовтень", "листопад", "грудень"]}


def fecha(L, txt):
    def f(m):
        dia, mes, anyo = m.group(1), ABREV_ES[m.group(2).lower()], m.group(3)
        if L in ("ru", "uk"):
            return f"{dia} {MESES[L][mes]} {anyo}" if dia else f"{NOM[L][mes]} {anyo}"
        if L == "ca":
            n = MESES["ca"][mes]
            return f"{dia} {n} de {anyo}" if dia else f"{n.split(' ', 1)[-1] if ' ' in n else n[2:]} {anyo}"
        return f"{dia + ' ' if dia else ''}{MESES[L][mes]} {anyo}"
    return FECHA.sub(f, txt)


# ---- 5) etiquetas ----
ETIQ = {
    "ca": {"Revisado por": "Revisat per", "Autor:": "Autor:", "Actualizado:": "Actualitzat:", "Tiempo de lectura": "Temps de lectura"},
    "en": {"Revisado por": "Reviewed by", "Autor:": "Author:", "Actualizado:": "Updated:", "Tiempo de lectura": "Reading time"},
    "fr": {"Revisado por": "Révisé par", "Autor:": "Auteur :", "Actualizado:": "Mis à jour :", "Tiempo de lectura": "Temps de lecture"},
    "ru": {"Revisado por": "Проверено:", "Autor:": "Автор:", "Actualizado:": "Обновлено:", "Tiempo de lectura": "Время чтения"},
    "uk": {"Revisado por": "Перевірено:", "Autor:": "Автор:", "Actualizado:": "Оновлено:", "Tiempo de lectura": "Час читання"},
}


PALABRAS = {
    "en": [(r"\bSal, Figueres\b", "Salt, Figueres"), (r"\bvaluations\b", "consultations"), (r"\bValuations\b", "Consultations"), (r"\bvaluation\b", "consultation"),
           (r"\bValuation\b", "Consultation"), (r"\bhunch\b", "hump"), (r"\bHunch\b", "Hump")],
    "fr": [(r"\bSel, Figueres\b", "Salt, Figueres")],
    "ru": [(r"\b[Кк]онтакто\b", "Контакты")],
}


def etiquetas(L, h):
    for rx, b in PALABRAS.get(L, []):
        h, n = re.subn(rx, b, h)
        C["palabras"] += n
    for a, b in ETIQ[L].items():
        if a != b and a in h:
            C["etiquetas"] += h.count(a)
            h = h.replace(a, b)
    return h


# ---- 6) textos en el idioma equivocado ----
# Misma segmentación que extraer_pendientes.py: HTML interior de elementos de texto (con sus etiquetas en línea) y campos
# de texto de los bloques JSON / frontmatter. Se sustituye el segmento ENTERO cuando coincide exactamente con una clave.
TRAD = {}
for L in LANGS:
    f = f"scripts/traducciones_contenido/{L}.json"
    TRAD[L] = json.load(open(f, encoding="utf-8")) if os.path.exists(f) else {}
INLINE = r"(?:a|b|strong|em|i|u|span|br|sup|sub|small|mark|abbr|time)"
SEG = re.compile(rf"<(p|li|h[1-6]|td|th|summary|figcaption|dt|dd|div|span|blockquote|cite|label|button|option|a)(\s[^>]*)?>((?:[^<]|<{INLINE}(?:\s[^>]*)?/?>|</{INLINE}>)+?)</\1>", re.S)
RUN = re.compile(rf"(<div(?:\s[^>]*)?>)((?:[^<]|<{INLINE}(?:\s[^>]*)?/?>|</{INLINE}>)+?)(?=<(?:p|div|ul|ol|h[1-6]|table)[\s>])", re.S)
SVGRUN = re.compile(rf"(</svg>)((?:[^<]|<{INLINE}(?:\s[^>]*)?/?>|</{INLINE}>)+?)(?=</(?:span|div|p|li|a|button|h[1-6]|summary)>)", re.S)
TEXTO_KEYS = {"html", "intro", "after", "text", "heading", "sub", "title", "alt", "imageAlt", "description", "lbl", "label",
              "placeholder", "labelHtml", "submit", "options", "q", "a", "t", "d", "k", "v", "s", "note", "bullets", "author",
              "summary", "bio", "role", "kicker", "eyebrow", "badge", "reviews", "micro", "vacio", "legal", "texto", "titulo", "h", "r"}


def textos(L, h):
    """HTML: cada segmento cuyo interior (sin espacios en los extremos) está en el diccionario se sustituye entero."""
    d = TRAD[L]
    if not d or not h:
        return h
    def f(m):
        inner = m.group(3)
        k = inner.strip()
        if k in d:
            C["textos"] += 1
            return f"<{m.group(1)}{m.group(2) or ''}>{inner.replace(k, d[k])}</{m.group(1)}>"
        return m.group(0)
    def f2(m):   # texto suelto al principio de un div con bloques detrás
        run = m.group(2); k = run.strip()
        if k and k in d:
            C["textos"] += 1
            return m.group(1) + run.replace(k, d[k])
        return m.group(0)
    return SVGRUN.sub(f2, RUN.sub(f2, SEG.sub(f, h)))


def traducir_valor(L, v):
    """Cadena de un campo JSON/frontmatter: entera si coincide; si lleva HTML, por segmentos."""
    d = TRAD[L]
    if not isinstance(v, str) or not d:
        return v
    k = v.strip()
    if k in d:
        C["textos"] += 1
        return v.replace(k, d[k])
    return textos(L, v) if "<" in v else v


def traducir_json(L, o, key=None):
    if isinstance(o, dict):
        return {k2: (traducir_json(L, v, k2) if (k2 in TEXTO_KEYS or isinstance(v, (dict, list))) else v) for k2, v in o.items()}
    if isinstance(o, list):
        return [traducir_json(L, v, key) for v in o]
    if isinstance(o, str) and key in TEXTO_KEYS:
        return traducir_valor(L, o)
    return o


def arreglar(L, h):
    if L == "en":
        n = h.count("0620 892 236"); C["telefono"] += n
        h = h.replace("0620 892 236", "620 892 236")
    h2 = fecha(L, h)
    C["fechas"] += int(h2 != h)
    return etiquetas(L, h2)


for f in glob.glob("src/content/pages/*/*.json"):
    j = json.load(open(f, encoding="utf-8"))
    L = j["lang"]
    antes = json.dumps(j, ensure_ascii=False)
    if j.get("breadcrumbs") and j["breadcrumbs"][0]["name"] != UI[L]["home"] and j["breadcrumbs"][0]["path"] in ("/", f"/{L}/"):
        j["breadcrumbs"][0]["name"] = UI[L]["home"]; C["migas"] += 1
    if L != "es":
        for b in j["blocks"]:
            for c in b.get("cols", []):
                for k in ("html", "after"):
                    if c.get(k):
                        c[k] = arreglar(L, c[k])
            if b.get("html"):
                b["html"] = arreglar(L, b["html"])
            if b.get("intro"):
                b["intro"] = arreglar(L, b["intro"])
    if L != "es" and TRAD[L]:
        j["blocks"] = traducir_json(L, j["blocks"])
        for k in ("title", "description"):
            if j["seo"].get(k): j["seo"][k] = traducir_valor(L, j["seo"][k])
        if j.get("title"): j["title"] = traducir_valor(L, j["title"])
    if json.dumps(j, ensure_ascii=False) != antes:
        json.dump(j, open(f, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
for f in glob.glob("src/content/posts/*/*.md"):
    L = f.replace("\\", "/").split("/")[3]
    if L == "es":
        continue
    raw = open(f, encoding="utf-8").read()
    _, fm, body = raw.split("---", 2)
    body = textos(L, arreglar(L, body))
    for k in ("title", "seoTitle", "description", "h1", "imageAlt", "category"):
        m = re.search(rf"^{k}: (.*)$", fm, re.M)
        if m:
            v = json.loads(m.group(1)); nv = traducir_valor(L, v)
            if nv != v: fm = fm.replace(m.group(0), f"{k}: " + json.dumps(nv, ensure_ascii=False))
    nuevo = "---" + fm + "---" + body
    if nuevo != raw:
        open(f, "w", encoding="utf-8").write(nuevo)
print(dict(C))
