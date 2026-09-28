#!/usr/bin/env python3
"""Menú principal y pie LITERALES de la web actual -> src/data/menu.json y src/data/footer.json (por idioma)."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wp_lib import soup, text, rel, local_image

HOMES = {"es": "https://www.medicsintegralsalut.com/"}
menu, footer = {}, {}
for lang, url in HOMES.items():
    s = soup(url)
    ul = (s.select_one("nav.main_menu") or s.select_one("header nav")).find("ul")
    def items(ul):
        out = []
        for li in ul.find_all("li", recursive=False):
            a = li.find("a")
            it = {"text": text(a), "href": rel(a.get("href"))}
            sub = li.find("ul")
            if sub:
                it["children"] = items(sub)
            out.append(it)
        return out
    menu[lang] = items(ul)
    cta = s.select_one("header a[href*='contacto#form'], header a[href*='contacte#form']")
    menu[f"cta_{lang}"] = {"text": text(cta), "href": rel(cta.get("href"))} if cta else None
    ft = s.find("footer")
    for x in ft(["script", "style", "noscript", "svg"]): x.decompose()
    links = [{"text": text(a), "href": rel(a.get("href"))} for a in ft.find_all("a")]
    footer[lang] = {
        "strings": [t for t in ft.stripped_strings],
        "links": links,
        "logos": [dict(local_image(i.get("src")) or {}, alt=i.get("alt") or "") for i in ft.find_all("img") if "line.jpg" not in (i.get("src") or "")],
    }
json.dump(menu, open("src/data/menu.json", "w"), ensure_ascii=False, indent=1)
json.dump(footer, open("src/data/footer.json", "w"), ensure_ascii=False, indent=1)
print(json.dumps(footer["es"]["strings"], ensure_ascii=False))
print([l for l in footer["es"]["logos"]])
