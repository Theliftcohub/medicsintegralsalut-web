#!/usr/bin/env python3
"""CSS de la portada «Versión C» (maqueta The Lift, 28/09/2026) -> src/styles/vc.css
Copia LITERAL del <style> de la maqueta, solo con los selectores acotados a body.vc para que no choque
con el sistema .mpost de las páginas de tratamiento (todas las páginas comparten el mismo bundle de CSS).
- :root -> .vc   (variables solo dentro de la portada)
- body -> body.vc · html se deja · resto -> .vc <selector>
- .rv (animación de entrada) solo se oculta si hay JS (html.vc-js), para no dejar contenido invisible.
- Se eliminan las reglas .nota (notas internas del diseñador).
Uso: python3 scripts/build_vc_css.py <maqueta.html>"""
import re, sys
import tinycss2
from bs4 import BeautifulSoup

src = BeautifulSoup(open(sys.argv[1], encoding="utf-8").read(), "html.parser").find("style").get_text()


def pre(sel):
    sel = sel.strip()
    if not sel or sel.startswith("from") or sel.startswith("to") or re.match(r"^\d+%$", sel):
        return sel
    if sel == ":root":
        return ".vc"
    if sel == "html":
        return "html"
    if sel == "*":
        return ".vc,.vc *"
    if sel.startswith("body"):
        return "body.vc" + sel[4:]
    if sel.startswith(".rv"):
        return "html.vc-js .vc " + sel
    return ".vc " + sel


def rules(nodes, out, depth=0):
    for n in nodes:
        if n.type == "qualified-rule":
            sels = [s for s in tinycss2.serialize(n.prelude).split(",")]
            if any(re.search(r"\.nota(?![\w-])", s) for s in sels):
                continue
            out.append(",".join(pre(s) for s in sels) + "{" + tinycss2.serialize(n.content).strip() + "}")
        elif n.type == "at-rule":
            kw = n.at_keyword.lower()
            head = "@" + n.at_keyword + tinycss2.serialize(n.prelude)
            if kw == "keyframes":
                out.append(head + "{" + tinycss2.serialize(n.content) + "}")
            elif n.content is not None:
                inner = []
                rules(tinycss2.parse_rule_list(n.content, skip_comments=True, skip_whitespace=True), inner, depth + 1)
                out.append(head + "{" + "\n".join(inner) + "}")
            else:
                out.append(head + ";")


out = []
rules(tinycss2.parse_stylesheet(src, skip_comments=True, skip_whitespace=True), out)
hdr = "/* Portada «Versión C» · maqueta The Lift Co (28/09/2026). GENERADO por scripts/build_vc_css.py — no editar a mano;\n   los ajustes propios van en vc-extra.css */\n"
open("src/styles/vc.css", "w").write(hdr + "\n".join(out) + "\n")
print("src/styles/vc.css", len(out), "reglas")
