#!/usr/bin/env python3
"""Segmentos en el idioma equivocado dentro del contenido de cada idioma -> scripts/traducciones_contenido/<lang>.pendientes.json
({segmento: {"n": veces, "ej": archivo}}). Un segmento es el HTML interior de un elemento de texto (p, li, h1-h6, td, th,
summary, figcaption, dt, dd, div/span sin bloques dentro), con sus etiquetas en línea (<b>, <a>, <br>…), para traducir
frases enteras y no trozos. También los campos de SEO (title/seoTitle/description/h1/imageAlt) si están en otro idioma.
Las traducciones se escriben en <lang>.json (segmento -> traducción, mismas etiquetas) y las aplica corregir_traducciones.py.
Uso: python scripts/extraer_pendientes.py [ca en fr ru uk]"""
import glob, json, re, sys
from collections import defaultdict
from langdetect import detect_langs, DetectorFactory
DetectorFactory.seed = 0
LANGS = sys.argv[1:] or ["ca", "en", "fr", "ru", "uk"]
INLINE = r"(?:a|b|strong|em|i|u|span|br|sup|sub|small|mark|abbr|time)"
SEG = re.compile(rf"<(p|li|h[1-6]|td|th|summary|figcaption|dt|dd|div|span|blockquote|cite|label|button|option)(?:\s[^>]*)?>((?:[^<]|<{INLINE}(?:\s[^>]*)?/?>|</{INLINE}>)+?)</\1>", re.S)
MARCAS = re.compile(r"\b(Medics Integral Salut|Médics|SECPRE|SCCPRE|WhatsApp|Girona|Barcelona|Biologique Recherche|EBOPRAS|SEME|SECO|Vaser|Váser|MEGA|AMI|Elipse|Allurion|Motiva|Mentor|Teknon|Tres Torres|Diagonal|Instagram|Facebook|YouTube|Google|TikTok)\b", re.I)


def plano(seg):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", seg)).strip()


def idioma(t):
    if re.search(r"[іїєґІЇЄҐ]", t): return "uk"
    if re.search(r"[ыэъЫЭЪ]", t): return "ru"
    if re.search(r"[А-Яа-я]", t): return "cyr"
    try:
        r = detect_langs(t)[0]
        return r.lang if r.prob > 0.85 else "?"
    except Exception:
        return "?"


def mal(L, t):
    t2 = MARCAS.sub("", t)
    if len(t2) < 12 or not re.search(r"[A-Za-zÀ-ÿА-Яа-яІіЇїЄєҐґ]{3}", t2): return False
    if re.fullmatch(r"[\d\s.,:;€%+\-–—/()·|★☆✓✔→«»\"'ºª]+", t2): return False
    d = idioma(t2)
    if d == "?": return False
    if L in ("ru", "uk"):
        if d in ("cyr", L): return False
        return len(t2) >= 25 and d in ("es", "ca", "en", "fr", "pt", "it", "gl")   # frases enteras en latino dentro de cirílico
    if d == "cyr": return True
    if L == "ca" and d == "es": return len(t2) > 40 and detect_langs(t2)[0].prob > 0.92
    if L == "fr" and d in ("ca", "es") and len(t2) < 30: return False
    if L == "en" and d in ("ca", "es") and len(t2) < 25: return False
    return d != L


for L in LANGS:
    pend = defaultdict(lambda: {"n": 0, "ej": "", "campo": ""})
    for f in glob.glob(f"src/content/pages/{L}/*.json") + glob.glob(f"src/content/posts/{L}/*.md"):
        raw = open(f, encoding="utf-8").read()
        fn = f.replace("\\", "/")
        if f.endswith(".md"):
            fm, body = raw.split("---", 2)[1:]
            for k in ("title", "seoTitle", "description", "h1", "imageAlt", "category"):
                m = re.search(rf"^{k}: (.*)$", fm, re.M)
                if m:
                    v = json.loads(m.group(1))
                    if isinstance(v, str) and mal(L, v):
                        pend[v]["n"] += 1; pend[v]["ej"] = pend[v]["ej"] or fn; pend[v]["campo"] = k
            html = body
        else:
            j = json.loads(raw)
            for k in ("title", "description"):
                v = j["seo"].get(k) or ""
                if v and mal(L, v):
                    pend[v]["n"] += 1; pend[v]["ej"] = pend[v]["ej"] or fn; pend[v]["campo"] = "seo." + k
            if j.get("title") and mal(L, j["title"]):
                pend[j["title"]]["n"] += 1; pend[j["title"]]["ej"] = pend[j["title"]]["ej"] or fn; pend[j["title"]]["campo"] = "title"
            trozos = []
            def rec(o):   # todos los textos/HTML de los bloques, estén donde estén
                if isinstance(o, dict):
                    for v in o.values(): rec(v)
                elif isinstance(o, list):
                    for v in o: rec(v)
                elif isinstance(o, str) and len(o) >= 12:
                    trozos.append(o if "<" in o else f"<p>{o}</p>")
            rec(j["blocks"])
            html = "\n".join(trozos)
        for m in SEG.finditer(html):
            seg = m.group(2).strip()
            if seg and mal(L, plano(seg)):
                pend[seg]["n"] += 1; pend[seg]["ej"] = pend[seg]["ej"] or fn
    out = dict(sorted(pend.items(), key=lambda x: -x[1]["n"]))
    json.dump(out, open(f"scripts/traducciones_contenido/{L}.pendientes.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(L, "segmentos distintos:", len(out), "· apariciones:", sum(v["n"] for v in out.values()), "· palabras:", sum(len(plano(k).split()) * 1 for k in out), flush=True)
