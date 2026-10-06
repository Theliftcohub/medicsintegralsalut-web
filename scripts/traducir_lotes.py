#!/usr/bin/env python3
"""Traducción por lotes de los segmentos pendientes (scripts/traducciones_contenido/<lang>.pendientes.json).
Los segmentos de origen (en español, casi siempre) son los mismos en los 5 idiomas: se exportan una sola vez (unión) y
cada lote se traduce a los cinco idiomas a la vez (solo a los que lo tienen pendiente, marcados tras el número).

  python scripts/traducir_lotes.py fijar                           congela el orden (_orden.json); los índices se refieren a él
  python scripts/traducir_lotes.py export <desde> <cuantos> [palabras]   imprime los segmentos pendientes desde ese índice
  python scripts/traducir_lotes.py validar <archivo.json>          comprueba un lote (idiomas, etiquetas, cifras)
  python scripts/traducir_lotes.py import <archivo.json>           {"<n>": {"ca": "...", "en": "...", "fr": "...", "ru": "...", "uk": "..."}} -> <lang>.json
  python scripts/traducir_lotes.py estado                          cuántos quedan por idioma

Reglas de traducción: mismas etiquetas HTML en el mismo sitio (<b>, <a href=…>, <br/>), mismas cifras, nombres propios y
marcas sin tocar (Medics Integral Salut, SECPRE, Girona…), terminología médica correcta, registro profesional y cercano
(tú en es/ca/fr; «you» en en; «вы/ви» en ru/uk). Nada de explicaciones: solo la traducción."""
import json, os, re, sys

DIR = "scripts/traducciones_contenido"
LAT = ["ca", "en", "fr", "ru", "uk"]   # el origen (español) es común: cada lote se traduce a los 5 idiomas


_CACHE = {}


def _carga(f):
    if f not in _CACHE:
        _CACHE[f] = json.load(open(f, encoding="utf-8")) if os.path.exists(f) else {}
    return _CACHE[f]


def pend(L):
    return _carga(f"{DIR}/{L}.pendientes.json")


def hechas(L):
    return _carga(f"{DIR}/{L}.json")


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
    for L in LAT:
        p, h = pend(L), hechas(L)
        print(L, "pendientes:", len([k for k in p if k not in h]), "/", len(p), "· traducidos:", len(h))
elif cmd == "export":
    # índices de _orden.json (fijos): se saltan los ya traducidos; opcional tope de palabras de origen por lote
    desde, n = int(sys.argv[2]), int(sys.argv[3])
    tope = int(sys.argv[4]) if len(sys.argv) > 4 else 10 ** 9
    ref = json.load(open(f"{DIR}/_orden.json", encoding="utf-8"))
    i, c, palabras = desde, 0, 0
    while i < len(ref) and c < n and palabras < tope:
        k = ref[i]
        if falta(k):
            print(f"### {i} [{''.join(falta(k))}]\n{k}\n"); c += 1
            palabras += len(re.sub(r"<[^>]+>", " ", k).split())
        i += 1
    print(f"--- siguiente: {i} · segmentos: {c} · palabras: {palabras} · pendientes (unión): {len([k for k in ref if falta(k)])}")
elif cmd == "validar":
    # comprueba un lote antes de importar: índices, idiomas marcados, mismas etiquetas HTML (en orden) y mismas cifras
    ref = json.load(open(f"{DIR}/_orden.json", encoding="utf-8"))
    datos = json.load(open(sys.argv[2], encoding="utf-8"))
    tags = lambda s: [re.sub(r"\s+", " ", t.strip()) for t in re.findall(r"<[^>]+>", s)]
    cifras = lambda s: re.findall(r"\d+", s)
    errores = 0
    for i, tr in datos.items():
        k = ref[int(i)]
        for L in falta(k):
            if L not in tr or not tr[L]:
                print(f"{i} {L}: falta"); errores += 1
        for L, t in tr.items():
            if L not in LAT or not t: continue
            if tags(t) != tags(k):
                print(f"{i} {L}: etiquetas distintas"); errores += 1
            elif sorted(cifras(t)) != sorted(cifras(k)):
                print(f"{i} {L}: cifras distintas {cifras(k)} -> {cifras(t)}"); errores += 1
            elif t.strip() == k.strip() and L in ("ru", "uk") and len(re.sub(r"<[^>]+>", " ", k).split()) >= 5:
                print(f"{i} {L}: sin traducir"); errores += 1
    print("errores:", errores)
    sys.exit(1 if errores else 0)
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
