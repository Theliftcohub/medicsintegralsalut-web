#!/usr/bin/env python3
"""Traducción por lotes de los segmentos pendientes (scripts/traducciones_contenido/<lang>.pendientes.json).
Los segmentos de origen (en español, casi siempre) son los mismos para ca/en/fr: se exportan una sola vez (unión) y
cada lote se traduce a los tres idiomas a la vez.

  python scripts/traducir_lotes.py export <desde> <cuantos>        imprime los segmentos numerados pendientes (unión ca/en/fr)
  python scripts/traducir_lotes.py import <archivo.json>           {"<n>": {"en": "...", "fr": "...", "ca": "..."}} -> <lang>.json
  python scripts/traducir_lotes.py export-cyr <lang> <desde> <n>   lo mismo para ru/uk (origen español -> un idioma)
  python scripts/traducir_lotes.py import-cyr <lang> <archivo.json>   {"<n>": "..."}
  python scripts/traducir_lotes.py estado                          cuántos quedan por idioma

Reglas de traducción: mismas etiquetas HTML en el mismo sitio (<b>, <a href=…>, <br/>), mismas cifras, nombres propios y
marcas sin tocar (Medics Integral Salut, SECPRE, Girona…), terminología médica correcta, registro profesional y cercano
(tú en es/ca/fr; «you» en en; «вы/ви» en ru/uk). Nada de explicaciones: solo la traducción."""
import json, os, sys

DIR = "scripts/traducciones_contenido"
LAT = ["ca", "en", "fr"]


def pend(L):
    f = f"{DIR}/{L}.pendientes.json"
    return json.load(open(f, encoding="utf-8")) if os.path.exists(f) else {}


def hechas(L):
    f = f"{DIR}/{L}.json"
    return json.load(open(f, encoding="utf-8")) if os.path.exists(f) else {}


def guardar(L, d):
    json.dump(d, open(f"{DIR}/{L}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def union():
    """Lista estable de segmentos de origen pendientes en ca, en o fr (ordenada por apariciones totales)."""
    peso = {}
    for L in LAT:
        for k, v in pend(L).items():
            peso[k] = peso.get(k, 0) + v["n"]
    return [k for k, _ in sorted(peso.items(), key=lambda x: (-x[1], x[0]))]


def falta(k):
    return [L for L in LAT if k in pend(L) and k not in hechas(L)]


cmd = sys.argv[1]
if cmd == "estado":
    for L in LAT + ["ru", "uk"]:
        p, h = pend(L), hechas(L)
        print(L, "pendientes:", len([k for k in p if k not in h]), "/", len(p), "· traducidos:", len(h))
elif cmd == "export":
    desde, n = int(sys.argv[2]), int(sys.argv[3])
    segs = [k for k in union() if falta(k)]
    for i, k in enumerate(segs[desde:desde + n], desde):
        print(f"### {i} [{''.join(falta(k))}]\n{k}\n")
    print(f"--- {min(desde + n, len(segs))}/{len(segs)} pendientes (unión ca/en/fr)")
elif cmd == "import":
    segs = [k for k in union() if falta(k)]
    datos = json.load(open(sys.argv[2], encoding="utf-8"))
    # el índice se refiere a la lista pendiente en el momento del export: se guarda la lista para no desplazar
    ref = json.load(open(f"{DIR}/_orden.json", encoding="utf-8"))
    out = {L: hechas(L) for L in LAT}
    n = 0
    for i, tr in datos.items():
        k = ref[int(i)]
        for L, t in tr.items():
            if L in LAT and t and k in pend(L):
                out[L][k] = t; n += 1
    for L in LAT:
        guardar(L, out[L])
    print("traducciones guardadas:", n)
elif cmd == "fijar":
    # congela el orden de la unión pendiente: los índices de export/import se refieren a este archivo
    segs = [k for k in union() if falta(k)]
    json.dump(segs, open(f"{DIR}/_orden.json", "w", encoding="utf-8"), ensure_ascii=False)
    print("orden fijado:", len(segs), "segmentos")
elif cmd == "export-cyr":
    L, desde, n = sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
    segs = [k for k in pend(L) if k not in hechas(L)]
    json.dump(segs, open(f"{DIR}/_orden_{L}.json", "w", encoding="utf-8"), ensure_ascii=False)
    for i, k in enumerate(segs[desde:desde + n], desde):
        print(f"### {i}\n{k}\n")
    print(f"--- {min(desde + n, len(segs))}/{len(segs)} pendientes ({L})")
elif cmd == "import-cyr":
    L = sys.argv[2]
    ref = json.load(open(f"{DIR}/_orden_{L}.json", encoding="utf-8"))
    out = hechas(L)
    datos = json.load(open(sys.argv[3], encoding="utf-8"))
    for i, t in datos.items():
        if t: out[ref[int(i)]] = t
    guardar(L, out)
    print(L, "traducciones guardadas:", len(datos))
