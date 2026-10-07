#!/usr/bin/env python3
"""Arreglos de accesibilidad en el marcado heredado del WordPress (src/content), sin tocar ningún texto (07/10/2026):
- Filtros de las entradas .mpost (`<div class="mpp-filters" role="tablist">` con <button> dentro): un tablist exige
  hijos role="tab" (Lighthouse «aria-required-children»); son botones de filtro, así que pasan a role="group".
Idempotente. Uso: python scripts/accesibilidad_contenido.py   (después: regenerar el paquete de _datos)"""
import glob

CAMBIOS = [('<div class="mpp-filters" role="tablist">', '<div class="mpp-filters" role="group">')]
n_arch = n_camb = 0
for f in glob.glob("src/content/**/*.md", recursive=True) + glob.glob("src/content/**/*.json", recursive=True):
    t = open(f, encoding="utf-8").read()
    nuevo = t
    for a, b in CAMBIOS:
        n_camb += nuevo.count(a)
        nuevo = nuevo.replace(a, b)
    if nuevo != t:
        open(f, "w", encoding="utf-8").write(nuevo)
        n_arch += 1
print(f"{n_camb} cambios en {n_arch} archivos")
