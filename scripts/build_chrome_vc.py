#!/usr/bin/env python3
"""Cabecera y pie «Versión C» por idioma -> src/data/vc-chrome.json.
Etiquetas y enlaces LITERALES del menú y del pie de cada portada del WordPress (TranslatePress); solo la etiqueta
"Clínica" (en el WordPress "Medics Integral Salut") y los títulos de columna del pie son de la maqueta."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from urllib.parse import unquote
from wp_lib import soup, text, rel

LANGS = ["es", "ca", "en", "fr", "ru", "uk"]
I18N = json.load(open("migracion/i18n-map.json"))
lp = lambda es, L: unquote(next((g.get(L, es) for g in I18N.values() if g.get("es") == es), es))
slash = lambda h: h if not h.startswith("/") or h.endswith("/") or "#" in h else h + "/"
CLINICA = {"es": "Clínica", "ca": "Clínica", "en": "Clinic", "fr": "Clinique", "ru": "Клиника", "uk": "Клініка"}
out = {}
for L in LANGS:
    s = soup("https://www.medicsintegralsalut.com/" + ("" if L == "es" else L + "/"))
    ul = (s.select_one("nav.main_menu") or s.select_one("header nav")).find("ul")
    top = []
    for li in ul.find_all("li", recursive=False):
        a = li.find("a")
        top.append({"text": text(a), "href": unquote(rel(a.get("href")))})
    # orden del WordPress: 0 clínica · 1 equipo · 2 unidades (#) · 3 financiación · 4 blog · 5 contacto
    units_href = None
    sub = ul.find_all("li", recursive=False)[2].find("ul")
    first_sub = sub.find("a") if sub else None
    ft = s.find("footer")
    for x in ft(["script", "style", "noscript", "svg"]):
        x.decompose()
    st = [t for t in ft.stripped_strings]
    links = [{"text": text(a), "href": unquote(rel(a.get("href")))} for a in ft.find_all("a")]
    home = "/" if L == "es" else f"/{L}/"
    contact = top[5]["href"]
    out[L] = {
        "home": home,
        "menu": [{"text": CLINICA[L], "href": top[0]["href"]}, top[1], {"text": top[2]["text"], "href": "#unidades"}, top[3], top[4], top[5]],
        "cta": {"text": st[-1], "href": "#info"},
        "anchors": {"#info": contact.rstrip("/") + "/#form", "#unidades": lp("/unidades/", L)},
        "footer": {"brand": st[0], "addr": st[1], "legal": links[0:4], "contactTitle": st[7],
                   "phone": st[8], "wa": st[9], "email": st[10], "tratTitle": st[11], "trat": links[6:11],
                   "socialTitle": st[17], "finTitle": st[18], "fin": slash(links[14]["href"])},
    }
json.dump(out, open("src/data/vc-chrome.json", "w"), ensure_ascii=False, indent=1)
for L in LANGS:
    print(L, [m["text"] for m in out[L]["menu"]], out[L]["cta"], out[L]["footer"]["tratTitle"], out[L]["footer"]["legal"][0])
