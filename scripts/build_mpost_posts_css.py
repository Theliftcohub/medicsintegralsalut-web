#!/usr/bin/env python3
"""CSS propio de las entradas del blog maquetadas con .mpost (5 variantes en el WordPress, en <style> dentro del
contenido) -> src/styles/mpost-posts.css, acotado a .vc-post-mpost para no afectar a las páginas de tratamiento."""
import hashlib, re, sys, tinycss2
from bs4 import BeautifulSoup
B = "https://www.medicsintegralsalut.com"
urls = open(sys.argv[1]).read().split()
seen, out = set(), []


def variant_id(mp):
    """Mismo cálculo que vc_pages.build_post: huella del <style> propio de la entrada."""
    return hashlib.md5("".join(st.get_text() for st in mp.find_all("style")).encode()).hexdigest()[:8]


def pre(sel, vid):
    sel = sel.strip()
    if sel.startswith(("from", "to")) or sel.endswith("%"):
        return sel
    return f".vc-post-mpost .mpv-{vid} " + re.sub(r"\.mpost(?![\w])", ".mpp", re.sub(r"\.mpost-", ".mpp-", sel))  # mismas clases que en vc_pages.build_post


def walk(nodes, acc, vid):
    for n in nodes:
        if n.type == "qualified-rule":
            sels = tinycss2.serialize(n.prelude).split(",")
            acc.append(",".join(pre(x, vid) for x in sels) + "{" + tinycss2.serialize(n.content).strip() + "}")
        elif n.type == "at-rule" and n.content is not None:
            head = "@" + n.at_keyword + tinycss2.serialize(n.prelude)
            if n.at_keyword.lower() == "keyframes":
                acc.append(head + "{" + tinycss2.serialize(n.content) + "}")
            else:
                inner = []
                walk(tinycss2.parse_rule_list(n.content, skip_comments=True, skip_whitespace=True), inner, vid)
                acc.append(head + "{" + "\n".join(inner) + "}")


for u in urls:
    fn = f"migracion/html_cache/{hashlib.md5((B + u).encode()).hexdigest()}.html"
    s = BeautifulSoup(open(fn, errors="ignore").read(), "html.parser")
    mp = s.select_one(".post_text_inner .mpost")
    if not mp:
        continue
    vid = variant_id(mp)  # cada variante de entrada lleva SU CSS (en el WordPress cada entrada solo carga el suyo)
    if vid in seen:
        continue
    seen.add(vid)
    for st in mp.find_all("style"):
        css = st.get_text().replace("<p>", "").replace("</p>", "").replace("<br />", "").replace("<br>", "")
        acc = []
        walk(tinycss2.parse_stylesheet(css, skip_comments=True, skip_whitespace=True), acc, vid)
        out.extend(acc)
open("src/styles/mpost-posts.css", "w").write("/* GENERADO por scripts/build_mpost_posts_css.py: CSS literal de las entradas .mpost del WordPress */\n" + "\n".join(out) + "\n")
print(len(out), "reglas")
