#!/usr/bin/env python3
"""CSS propio de las entradas del blog maquetadas con .mpost (5 variantes en el WordPress, en <style> dentro del
contenido) -> src/styles/mpost-posts.css, acotado a .vc-post-mpost para no afectar a las páginas de tratamiento."""
import hashlib, sys, tinycss2
from bs4 import BeautifulSoup
B = "https://www.medicsintegralsalut.com"
urls = open(sys.argv[1]).read().split()
seen, out = set(), []


def pre(sel):
    sel = sel.strip()
    return sel if sel.startswith(("from", "to")) or sel.endswith("%") else ".vc-post-mpost " + sel


def walk(nodes, acc):
    for n in nodes:
        if n.type == "qualified-rule":
            sels = tinycss2.serialize(n.prelude).split(",")
            acc.append(",".join(pre(x) for x in sels) + "{" + tinycss2.serialize(n.content).strip() + "}")
        elif n.type == "at-rule" and n.content is not None:
            head = "@" + n.at_keyword + tinycss2.serialize(n.prelude)
            if n.at_keyword.lower() == "keyframes":
                acc.append(head + "{" + tinycss2.serialize(n.content) + "}")
            else:
                inner = []
                walk(tinycss2.parse_rule_list(n.content, skip_comments=True, skip_whitespace=True), inner)
                acc.append(head + "{" + "\n".join(inner) + "}")


for u in urls:
    fn = f"migracion/html_cache/{hashlib.md5((B + u).encode()).hexdigest()}.html"
    s = BeautifulSoup(open(fn, errors="ignore").read(), "html.parser")
    mp = s.select_one(".post_text_inner .mpost")
    if not mp:
        continue
    for st in mp.find_all("style"):
        css = st.get_text().replace("<p>", "").replace("</p>", "").replace("<br />", "").replace("<br>", "")
        acc = []
        walk(tinycss2.parse_stylesheet(css, skip_comments=True, skip_whitespace=True), acc)
        for r in acc:
            if r not in seen:
                seen.add(r)
                out.append(r)
open("src/styles/mpost-posts.css", "w").write("/* GENERADO por scripts/build_mpost_posts_css.py: CSS literal de las entradas .mpost del WordPress */\n" + "\n".join(out) + "\n")
print(len(out), "reglas")
