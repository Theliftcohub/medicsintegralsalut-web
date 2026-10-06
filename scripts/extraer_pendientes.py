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
SEG = re.compile(rf"<(p|li|h[1-6]|td|th|summary|figcaption|dt|dd|div|span|blockquote|cite|label|button|option|a)(?:\s[^>]*)?>((?:[^<]|<{INLINE}(?:\s[^>]*)?/?>|</{INLINE}>)+?)</\1>", re.S)
# texto suelto al principio de un div que después tiene bloques (p. ej. el aviso legal .mpp-disc: texto + <p>…)
RUN = re.compile(rf"(<div(?:\s[^>]*)?>)((?:[^<]|<{INLINE}(?:\s[^>]*)?/?>|</{INLINE}>)+?)(?=<(?:p|div|ul|ol|h[1-6]|table)[\s>])", re.S)
# texto detrás de un icono: <span class="tl"><svg…></svg>Texto</span>
SVGRUN = re.compile(rf"(</svg>)((?:[^<]|<{INLINE}(?:\s[^>]*)?/?>|</{INLINE}>)+?)(?=</(?:span|div|p|li|a|button|h[1-6]|summary)>)", re.S)
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


# marcas de español (y de catalán) para segmentos cortos, donde langdetect no es fiable
ES = re.compile(r"(ción|ciones|miento|mientos|dad|dades|ética|ético|ática|ático|ología|ológic[ao]s?|ía|ías|ío|ado|ados|ico|icos|mente)\b|[ñ¿¡]|(?<![qgQG])ue|\b(y|los|las|del|con|sin|para|por|qué|cómo|cuánto|cuándo|dónde|unos|unas|muy|más|también|desde|hasta|sobre|entre|después|antes|durante|primer[ao]|segund[ao]|tod[ao]s?|nuestr[ao]s?|sus?|est[ae]s?|estos|es[eao]s?|hay|tienen?|pueden?|deben?|hacer|mejor|mayor|menor|cirugía|tratamientos?|pacientes?|resultados?)\b", re.I)
CA = re.compile(r"ció\b|cions\b|\b(amb|per|els|és|dels|nostr[ae]|troba|abans|després|també|això|aquest[ae]?s?|cirurgia|tractaments?|primer[ae]?s?|resultats|millor|durada|pacients?)\b", re.I)
ROMANCE = ("es", "ca", "pt", "gl", "it")


CORTE = re.compile(r"<[^>]+>|[.;:!?¿¡|•·]+\s+|\s[–—]\s|\n")


def partes(seg):
    """Trozos de un segmento (texto entre etiquetas, frases) con 4+ palabras: cazan mezclas de idiomas
    (TranslatePress tradujo medio párrafo y dejó el resto en español)."""
    return [MARCAS.sub(" ", x).strip() for x in CORTE.split(seg) if len(x.split()) >= 4]


def marcas_es_ca(x):
    return bool(ES.search(x) or CA.search(x))


def es_romance(x):
    """español/catalán de verdad: langdetect lo da por románico Y hay un marcador léxico (langdetect confunde
    frases cortas inglesas o francesas con ca/it/pt)"""
    return idioma(x) in ROMANCE and marcas_es_ca(x)


def mal(L, seg):
    """seg: HTML interior del segmento (o texto plano). ¿Está en el idioma equivocado, entero o en parte?"""
    t = plano(seg)
    t2 = MARCAS.sub(" ", t).strip()
    if len(t2) < 6 or not re.search(r"[A-Za-zÀ-ÿА-Яа-яІіЇїЄєҐґ]{3}", t2): return False
    if re.fullmatch(r"[\d\s.,:;€%+\-–—/()·|★☆✓✔→«»\"'ºª@]+", t2): return False
    if re.match(r"^(form-|/|https?:|#|\.|mailto:|tel:)", t2): return False
    if re.search(r"[А-Яа-яІіЇїЄєҐґ]", t2):
        if L not in ("ru", "uk") or idioma(t2) not in ("cyr", L): return True
        quitar = lambda s: re.sub(r"\S*[А-Яа-яІіЇїЄєҐґ]\S*", " ", s)   # parte latina de un segmento mixto
        lat = quitar(t2)
        return (len(re.findall(r"\w+", lat)) >= 4 and es_romance(lat)) or any(es_romance(x) for x in partes(quitar(seg)))
    palabras = len(re.findall(r"\w+", t2))
    if palabras < 4:                      # corto: solo con marcas inequívocas
        if L == "ca": return bool(ES.search(t2)) and not CA.search(t2)
        return marcas_es_ca(t2)
    d = idioma(t2)
    if L == "ca":
        if d == "es" and not CA.search(t2) and (detect_langs(t2)[0].prob > 0.9 or ES.search(t2)): return True
        if d == "?" and palabras < 10 and ES.search(t2) and not CA.search(t2): return True
        return any(idioma(x) == "es" and ES.search(x) and not CA.search(x) for x in partes(seg))
    if d in ROMANCE and marcas_es_ca(t2): return True
    if d == "?" and palabras < 8: return marcas_es_ca(t2)
    return any(es_romance(x) for x in partes(seg))


# claves de los bloques JSON que llevan texto visible (el resto son rutas, nombres internos, clases…)
TEXTO_KEYS = {"html", "intro", "after", "text", "heading", "sub", "title", "alt", "imageAlt", "description", "lbl", "label",
              "placeholder", "labelHtml", "submit", "options", "q", "a", "t", "d", "k", "v", "s", "note", "bullets", "author",
              "summary", "bio", "role", "kicker", "eyebrow", "badge", "reviews", "micro", "vacio", "paras", "items", "cta", "quote",
              "legal", "texto", "titulo", "lateral", "rows", "ventajas", "contadores", "cards", "members", "grupos", "medicos",
              "campos", "details", "cols", "unidades", "links", "columns", "wide", "filtros", "stats", "textos", "trat", "h", "r"}


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
            def rec(o, key=None):   # textos/HTML de los bloques, solo en claves de texto
                if isinstance(o, dict):
                    for k2, v in o.items():
                        if k2 in TEXTO_KEYS or isinstance(v, (dict, list)): rec(v, k2)
                elif isinstance(o, list):
                    for v in o: rec(v, key)
                elif isinstance(o, str) and len(o) >= 6 and key in TEXTO_KEYS:
                    trozos.append(o if "<" in o else f"<p>{o}</p>")
            rec(j["blocks"])
            html = "\n".join(trozos)
        for m in list(SEG.finditer(html)) + list(RUN.finditer(html)) + list(SVGRUN.finditer(html)):
            seg = m.group(2).strip()
            if seg and mal(L, seg):
                pend[seg]["n"] += 1; pend[seg]["ej"] = pend[seg]["ej"] or fn
    out = dict(sorted(pend.items(), key=lambda x: -x[1]["n"]))
    json.dump(out, open(f"scripts/traducciones_contenido/{L}.pendientes.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(L, "segmentos distintos:", len(out), "· apariciones:", sum(v["n"] for v in out.values()), "· palabras:", sum(len(plano(k).split()) * 1 for k in out), flush=True)
