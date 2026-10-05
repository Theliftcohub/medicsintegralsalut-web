#!/usr/bin/env python3
"""CSS de la portada «prototipo» -> src/styles/portada.css (GENERADO: no editar a mano; los ajustes van en portada-extra.css).
Copia LITERAL del <style> de la maqueta (migracion/diseno/home-prototipo.html, The Lift Co, 05/10/2026) con:
- todo acotado a `.vc .pt` (la portada va dentro de <div class="pt">) y las clases con prefijo `pt-`, para no chocar con vc.css;
- fuera la cabecera, el pie, el menú móvil, la barra móvil, las notas del diseñador y el hero (la cabecera y el pie son los
  de toda la web y el hero es otro diseño, en portada-extra.css). La animación de entrada (.rv) es la de vc.css.
Uso: python scripts/build_portada_css.py"""
import re

FUENTE = "migracion/diseno/home-prototipo.html"
SALIDA = "src/styles/portada.css"
FUERA = re.compile(r"#hdr|header|footer|\bnav\b|\.(nota|panel|velo|burger|bar|logo|acc|lupa|bm|fg|fl|hero|circ|onda|rv|play|valor|chips-av|hueco|g[1-4])\b|body\.nv|^html|^\*$")
ELEMENTOS = re.compile(r"^(h[1-6]|p|a|img|section|ul|li|b|strong)(?=$|[\s,:.\[>+~])")


def bloques(css):
    """[(prelude, cuerpo)] de primer nivel; el cuerpo de un @media se devuelve sin procesar."""
    out, i, n = [], 0, len(css)
    while i < n:
        j = css.find("{", i)
        if j < 0:
            break
        pre, prof, k = css[i:j].strip(), 1, j + 1
        while k < n and prof:
            prof += {"{": 1, "}": -1}.get(css[k], 0)
            k += 1
        out.append((pre, css[j + 1:k - 1]))
        i = k
    return out


def selector(s):
    s = s.strip()
    if FUERA.search(s):
        return None
    if s in (":root", "body"):
        return ".vc .pt"
    s = re.sub(r"\.([A-Za-z][\w-]*)", r".pt-\1", s)
    return ".vc .pt " + s


def regla(pre, cuerpo):
    sels = [x for x in (selector(p) for p in pre.split(",")) if x]
    return f"{','.join(sels)}{{{cuerpo.strip()}}}" if sels else ""


def procesa(css):
    out = []
    for pre, cuerpo in bloques(css):
        if pre.startswith("@keyframes"):
            continue
        if pre.startswith("@media"):
            dentro = [r for r in (regla(p, c) for p, c in bloques(cuerpo)) if r]
            if dentro:
                out.append(pre + "{\n" + "\n".join(dentro) + "\n}")
        else:
            r = regla(pre, cuerpo)
            if r:
                out.append(r)
    return out


html = open(FUENTE, encoding="utf-8").read()
css = "\n".join(re.findall(r"<style[^>]*>(.*?)</style>", html, re.S))
css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
reglas = procesa(css)
cab = ("/* Portada «prototipo» (The Lift Co, 05/10/2026). GENERADO por scripts/build_portada_css.py desde "
       "migracion/diseno/home-prototipo.html — no editar a mano; los ajustes van en portada-extra.css */\n")
open(SALIDA, "w", encoding="utf-8").write(cab + "\n".join(reglas) + "\n")
print(len(reglas), "reglas ->", SALIDA)
