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
    "fr": ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"],
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
    "en": [(r"valuations", "consultations"), (r"Valuations", "Consultations"), (r"valuation", "consultation"),
           (r"Valuation", "Consultation"), (r"hunch", "hump"), (r"Hunch", "Hump")],
    "ru": [(r"[Кк]онтакто", "Контакты")],
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
TRAD = {}
for L in LANGS:
    f = f"scripts/traducciones_contenido/{L}.json"
    TRAD[L] = json.load(open(f, encoding="utf-8")) if os.path.exists(f) else {}
TEXTO = re.compile(r">([^<>]+)<")


def textos(L, h):
    d = TRAD[L]
    if not d:
        return h
    def f(m):
        t = m.group(1)
        k = t.strip()
        if k in d:
            C["textos"] += 1
            return ">" + t.replace(k, d[k]) + "<"
        return m.group(0)
    return TEXTO.sub(f, h)


def arreglar(L, h):
    if L == "en":
        n = h.count("0620 892 236"); C["telefono"] += n
        h = h.replace("0620 892 236", "620 892 236")
    h2 = fecha(L, h)
    C["fechas"] += int(h2 != h)
    return textos(L, etiquetas(L, h2))


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
    if json.dumps(j, ensure_ascii=False) != antes:
        json.dump(j, open(f, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
for f in glob.glob("src/content/posts/*/*.md"):
    L = f.replace("\\", "/").split("/")[3]
    if L == "es":
        continue
    raw = open(f, encoding="utf-8").read()
    _, fm, body = raw.split("---", 2)
    nuevo = "---" + fm + "---" + arreglar(L, body)
    if nuevo != raw:
        open(f, "w", encoding="utf-8").write(nuevo)
print(dict(C))
