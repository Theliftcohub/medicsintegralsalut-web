#!/usr/bin/env python3
"""Comprueba que ningún enlace interno de las 6 portadas (dist/index.html y dist/<lang>/index.html) da 404.

Un destino es válido si existe dist/<ruta>/index.html (o el archivo exacto), o si dist/_redirects
tiene una regla 301/302 para esa ruta (se sigue hasta 5 saltos). Uso: python3 scripts/comprobar_enlaces_portadas.py [dist]
"""
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

DIST = Path(sys.argv[1] if len(sys.argv) > 1 else 'dist')
LANGS = ['', 'ca', 'en', 'fr', 'ru', 'uk']


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hrefs = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'a' and a.get('href'):
            self.hrefs.append(a['href'])
        if tag in ('img', 'script', 'source', 'video') and a.get('src'):
            self.hrefs.append(a['src'])
        if tag == 'link' and a.get('href') and a.get('rel') in ('stylesheet', 'preload'):
            self.hrefs.append(a['href'])


def cargar_redirecciones():
    r = {}
    f = DIST / '_redirects'
    if not f.exists():
        return r
    for linea in f.read_text(encoding='utf-8').splitlines():
        p = linea.split()
        if len(p) >= 3 and p[0].startswith('/') and p[2] in ('301', '302', '308'):
            r[unquote(p[0]).rstrip('/') or '/'] = p[1]
    return r


REDIR = cargar_redirecciones()


def existe(ruta, saltos=0):
    ruta = unquote(ruta)
    base = DIST / ruta.lstrip('/')
    if ruta.endswith('/') or ruta == '':
        if (base / 'index.html').is_file():
            return True
    elif base.is_file():
        return True
    elif (base / 'index.html').is_file():
        return True
    if saltos < 5:
        destino = REDIR.get(ruta.rstrip('/') or '/')
        if destino in ('/410.html', '/404.html'):
            return False
        if destino and not destino.startswith('http'):
            return existe(urlsplit(destino).path, saltos + 1)
    return False


total = 0
rotos = []
unicos = set()
for l in LANGS:
    f = DIST / l / 'index.html' if l else DIST / 'index.html'
    parser = Links()
    parser.feed(f.read_text(encoding='utf-8'))
    for h in parser.hrefs:
        if re.match(r'^(https?:|mailto:|tel:|javascript:|data:|//)', h) or h.startswith('#'):
            continue
        ruta = urlsplit(h).path
        if not ruta:
            continue
        total += 1
        unicos.add(ruta)
        if not existe(ruta):
            rotos.append((l or 'es', h))

print(f'enlaces internos comprobados: {total} ({len(unicos)} únicos)')
print(f'rotos: {len(rotos)}')
for l, h in sorted(set(rotos)):
    print(f'  [{l}] {h}')
sys.exit(1 if rotos else 0)
