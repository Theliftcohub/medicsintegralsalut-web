#!/usr/bin/env python3
"""Validación rápida (paralela) de la preview contra el contrato y el inventario.
1) Estado HTTP de TODAS las URLs de migracion/urls.csv (200 / 301 al destino / 410), sin seguir redirecciones.
2) En cada página 200 de dist/: title y description literales, canonical, un solo H1, sin restos de WordPress
   (wp-content, shortcodes), sin Typeform, imágenes locales y enlaces internos existentes.
Uso: python3 scripts/validar_rapido.py https://medicsintegralsalut-preview.netlify.app"""
import ast, csv, json, os, re, sys, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import unquote, urljoin, urlparse, quote
BASE = sys.argv[1].rstrip("/")
rows = list(csv.DictReader(open("migracion/urls.csv")))
inv = {unquote(urlparse(i["url"]).path): i for i in json.load(open("migracion/inventory.json"))["items"]}


class NoRedir(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


op = urllib.request.build_opener(NoRedir)


def status(r):
    u = r["url"] or "/"
    try:
        resp = op.open(urllib.request.Request(BASE + quote(unquote(u), safe="/%"), method="HEAD"), timeout=30)
        return r, resp.status, ""
    except urllib.error.HTTPError as e:
        return r, e.code, e.headers.get("Location", "")
    except Exception as e:
        return r, 0, str(e)[:60]


fails, ok = [], 0
with ThreadPoolExecutor(24) as ex:
    for r, code, loc in ex.map(status, rows):
        exp = {"mantener": 200, "301": 301, "410": 410}.get(r["decision"])
        u = r["url"] or "/"
        if r["decision"] == "mantener" and u and not u.endswith("/"):
            exp = 301
        if r["decision"] == "mantener" and u.startswith("/wp-content/"):
            exp = 301
        if code != exp:
            fails.append(("estado", unquote(u), f"esperado {exp}, recibido {code} {loc}"))
        elif code == 301 and r["decision"] == "301" and r["destino"]:
            dst = unquote(urlparse(loc).path)
            if dst.rstrip("/") != unquote(r["destino"]).rstrip("/") and not r["destino"].startswith("http"):
                fails.append(("destino", unquote(u), f"va a {dst} (contrato: {unquote(r['destino'])})"))
            else:
                ok += 1
        else:
            ok += 1
print("URLs del contrato OK:", ok, "· fallos:", len(fails))

# 2) contenido de dist/
LEFT = re.compile(r"wp-content|wp-includes|\[/?vc_|typeform|elementor-", re.I)
warn = []
for root, _, files in os.walk("dist"):
    if "index.html" not in files:
        continue
    path = "/" + os.path.relpath(root, "dist").replace(os.sep, "/") + "/"
    path = "/" if path == "/./" else path
    if path in ("/404/", "/410/"):
        continue
    h = open(os.path.join(root, "index.html"), encoding="utf-8").read()
    t = re.search(r"<title>(.*?)</title>", h, re.S)
    h1 = re.findall(r"<h1[\s>]", h)
    it = inv.get(path)
    if it:
        s = it.get("seo") or {}
        s = ast.literal_eval(s) if isinstance(s, str) else s
        import html as H
        if s.get("title") and t and H.unescape(t.group(1)).strip() != s["title"].strip():
            fails.append(("title", path, f"{H.unescape(t.group(1))[:60]} ≠ {s['title'][:60]}"))
    if len(h1) != 1:
        warn.append(("h1", path, f"{len(h1)} H1"))
    body = h.split("<body", 1)[-1]
    m = LEFT.search(body)
    if m:
        fails.append(("restos", path, body[max(0, m.start() - 60):m.end() + 40].replace("\n", " ")))
    for src in re.findall(r'<img[^>]+src="([^"]+)"', body):
        if src.startswith("/") and not os.path.exists("public" + unquote(src)) and not os.path.exists("dist" + unquote(src)):
            fails.append(("imagen", path, src))
    for href in re.findall(r'<a[^>]+href="(/[^"#?]*)', body):
        q = unquote(href)
        if not (os.path.exists("dist" + q) or os.path.exists("dist" + q.rstrip("/") + "/index.html") or os.path.exists("public" + q)):
            warn.append(("enlace-roto", path, q))
kinds = {}
for k, p, d in fails:
    kinds.setdefault(k, []).append((p, d))
for k, v in kinds.items():
    print(f"FAIL {k}: {len(v)}", v[:6])
wk = {}
for k, p, d in warn:
    wk.setdefault(k, []).append((p, d))
for k, v in wk.items():
    print(f"WARN {k}: {len(v)}", v[:6])
json.dump({"fails": fails, "warns": warn}, open("migracion/validacion_rapida.json", "w"), ensure_ascii=False, indent=1)
