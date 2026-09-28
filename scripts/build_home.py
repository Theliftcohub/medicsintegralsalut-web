#!/usr/bin/env python3
"""Portada (es) -> src/content/pages/es/home.json + menú y pie literales.
Renovación visual (línea de las páginas de tratamiento nuevas) con contenido literal.
Uso: python3 scripts/build_home.py [url] [lang] [out]"""
import json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wp_lib import soup, inline, text, rel, local_image
from bs4 import BeautifulSoup

URL = sys.argv[1] if len(sys.argv) > 1 else "https://www.medicsintegralsalut.com/"
LANG = sys.argv[2] if len(sys.argv) > 2 else "es"
OUT = sys.argv[3] if len(sys.argv) > 3 else "src/content/pages/es/home.json"

s = soup(URL)
inv = {i["url"]: i for i in json.load(open("migracion/inventory.json"))["items"]}
seo_src = inv.get(URL, {}).get("seo", {})
rows = s.select_one(".default_template_holder").find_all("div", class_="vc_row", recursive=False)
for r in rows:
    for x in r(["script", "style", "noscript"]):
        x.decompose()


def img_of(el):
    i = el.find("img")
    if not i:
        return None
    li = local_image(i.get("src"))
    if li:
        li["alt"] = i.get("alt") or ""
    return li


def btn(el):
    a = el.find("a", class_="qbutton")
    return {"text": text(a), "href": rel(a.get("href"))} if a else None


def paras(el):
    return [inline(p) for p in el.find_all("p") if inline(p)]


blocks = []
# 0 · hero
r = rows[0]
blocks.append({"type": "mp-hero", "kicker": text(r.find("p")), "titleTag": "h2",
               "title": " ".join(text(x) for x in r.find("h2").find_all("strong")) or text(r.find("h2")),
               "cta": btn(r), "note": text(r.find_all("p")[-1]), "image": img_of(r)})
# 1 · intro con H1
r = rows[1]
blocks.append({"type": "mp-split", "headingTag": "h1", "heading": text(r.find("h1")),
               "paras": paras(r), "cta": btn(r), "image": img_of(r), "media": "left"})
# 2-4 · intervenciones más solicitadas
r = rows[2]
cards = []
for rr in rows[3:5]:
    for h3 in rr.find_all("h3"):
        a = h3.find("a")
        b = h3.find_next("a", class_="qbutton")
        cards.append({"title": text(h3), "href": rel(a.get("href")), "cta": text(b)})
blocks.append({"type": "mp-cards", "heading": text(r.find("h2")), "sub": text(r.find("h3")),
               "text": paras(r), "cards": cards, "alt": True})
# 5-8 · unidades
r = rows[5]
groups = []
for rr in rows[6:8]:
    for h3 in rr.find_all("h3"):
        p = h3.find_next("p")
        links = []
        for a in p.find_all("a"):
            t = text(a)
            if t:
                links.append({"text": t, "href": rel(a.get("href"))})
        groups.append({"title": text(h3), "links": links})
blocks.append({"type": "mp-units", "heading": text(r.find("h2")), "text": paras(r), "groups": groups,
               "cta": btn(rows[8])})
# 9 · vídeos
r = rows[9]
items = []
for li in r.select("ul.portfolio_slides > li"):
    a = li.find("h3").find("a")
    v = li.find("a", class_="lightbox")
    items.append({"title": text(a), "href": rel(a.get("href")), "video": v.get("href") if v else "",
                  "image": img_of(li)})
blocks.append({"type": "mp-videos", "heading": text(r.find("h2")), "sub": text(r.find("p")), "items": items})
# 10 · medicina estética
r = rows[10]
blocks.append({"type": "mp-split", "headingTag": "h2", "heading": text(r.find("h2")), "paras": paras(r),
               "image": img_of(r), "media": "right", "alt": True})
# 11 · beneficios
r = rows[11]
blocks.append({"type": "mp-benefits", "heading": text(r.find("h2")), "items": [text(h) for h in r.find_all("h3")],
               "text": paras(r), "cta": btn(r)})
# 12 · equipo
r = rows[12]
members = []
for h3 in r.find_all("h3"):
    if h3.find("img") or not text(h3):
        continue
    ps = h3.find_all_next("p", limit=2)
    im = h3.find_previous("img")
    members.append({"name": text(h3), "role": text(ps[0]) if ps else "", "bio": inline(ps[1]) if len(ps) > 1 else "",
                    "image": (lambda li: (li.update(alt=im.get("alt") or text(h3)) or li) if li else None)(local_image(im.get("src"))) if im else None})
intro = r.find("h2").find_next("p")
blocks.append({"type": "mp-team", "id": "equipo", "heading": text(r.find("h2")), "text": [inline(intro)],
               "members": members, "alt": True})
# 13 · contacto (Typeform: se conserva el MISMO formulario, que ya alimenta Kommo)
r = rows[13]
tf = r.find(attrs={"data-tf-live": True})
blocks.append({"type": "mp-typeform", "id": "info", "heading": text(r.find("h3")), "text": paras(r),
               "typeform": tf.get("data-tf-live") if tf else "", "image": img_of(r)})
# 14 · opiniones (Trustindex: reseñas reales de Google, sin AggregateRating)
r = rows[14]
reviews = []
t = s.find("template", id="trustindex-google-widget-html")
if t:
    ts = BeautifulSoup(t.decode_contents(), "html.parser")
    for it in ts.select(".ti-review-item"):
        n = it.select_one(".ti-name")
        c = it.select_one(".ti-review-content") or it.select_one(".ti-review-text-container")
        if n and c:
            reviews.append({"name": text(n), "text": text(c)})
blocks.append({"type": "mp-reviews", "id": "opiniones", "heading": text(r.find("h2")), "source": "Google",
               "reviews": reviews})
# 15 · NAP literal
r = rows[15]
ps = [p for p in r.find_all("p") if text(p)]
maps = r.find("a")
blocks.append({"type": "mp-nap", "heading": text(r.find("h3")), "lines": [inline(p) for p in ps],
               "mapsHref": maps.get("href") if maps else ""})

page = {"path": "/" if LANG == "es" else f"/{LANG}/", "lang": LANG, "i18nGroup": "home",
        "seo": {"title": seo_src.get("title", ""), "description": seo_src.get("meta_description", ""),
                "canonical": seo_src.get("canonical") or None, "robots": seo_src.get("robots") or "index, follow",
                "ogTitle": seo_src.get("og_title") or None, "ogDescription": seo_src.get("og_description") or None},
        "schema": [], "blocks": blocks}
og = seo_src.get("og_image")
if og:
    li = local_image(og)
    if li:
        page["seo"]["ogImage"] = li["src"]
page["seo"] = {k: v for k, v in page["seo"].items() if v}
os.makedirs(os.path.dirname(OUT), exist_ok=True)
json.dump(page, open(OUT, "w"), ensure_ascii=False, indent=1)
print(OUT, len(blocks), "bloques ·", sum(len(json.dumps(b)) for b in blocks), "bytes")
