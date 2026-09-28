#!/usr/bin/env python3
"""Utilidades comunes para convertir páginas WPBakery/Bridge del WordPress de Medics en bloques JSON.
- Texto LITERAL: solo se limpia el marcado (clases, estilos, spans vacíos); nunca se cambian palabras.
- Enlaces internos a ruta relativa. Imágenes descargadas a public/images/wp/<año>/<mes>/<nombre-original>.webp
"""
import hashlib, os, re, time, urllib.request
from urllib.parse import urlparse, unquote
from bs4 import BeautifulSoup, NavigableString, Tag

BASE = "https://www.medicsintegralsalut.com"
CACHE = "migracion/html_cache"
IMG_DIR = "public/images/wp"
INLINE_OK = {"a", "strong", "b", "em", "i", "br"}


def html_of(url):
    fn = os.path.join(CACHE, hashlib.md5(url.encode()).hexdigest() + ".html")
    return open(fn, encoding="utf-8", errors="ignore").read()


def soup(url):
    return BeautifulSoup(html_of(url), "html.parser")


def rel(href):
    """URL absoluta del propio dominio -> ruta relativa. Deja anclas, mailto, tel y externas."""
    if not href:
        return href
    href = href.strip()
    p = urlparse(href)
    if p.netloc in ("www.medicsintegralsalut.com", "medicsintegralsalut.com"):
        out = p.path or "/"
        if p.fragment:
            out += "#" + p.fragment
        return out
    return href


def inline(el, top=True):
    """HTML en línea literal: conserva a/strong/b/em/br, quita el resto de etiquetas (dejando su texto)."""
    out = []
    for c in el.children:
        if isinstance(c, NavigableString):
            out.append(str(c).replace("\xa0", " "))
        elif isinstance(c, Tag):
            if c.name in ("script", "style", "noscript", "svg", "template", "img"):
                continue
            inner = inline(c, top=False)
            if c.name == "br":
                out.append("<br>")
            elif c.name in ("strong", "b"):
                out.append(f"<strong>{inner}</strong>" if inner.strip() else inner)
            elif c.name in ("em", "i"):
                out.append(f"<em>{inner}</em>" if inner.strip() else inner)
            elif c.name == "a":
                href = rel(c.get("href"))
                out.append(f'<a href="{href}">{inner}</a>' if href and inner.strip() else inner)
            else:
                out.append(inner)
    txt = "".join(out)
    txt = re.sub(r"[ \t\r\n]+", " ", txt)
    if top:
        # espacios que quedaron dentro de las etiquetas se sacan fuera (<strong> x </strong> -> ␣<strong>x</strong>␣)
        txt = re.sub(r"<(strong|em)> ", r" <\1>", txt)
        txt = re.sub(r" </(strong|em)>", r"</\1> ", txt)
        txt = re.sub(r"\s+", " ", txt).strip()
    return txt


def text(el):
    return re.sub(r"\s+", " ", el.get_text(" ", strip=True)).strip() if el else ""


def original_upload(src):
    """URL de uploads original (sin la copia w3-webp del plugin)."""
    src = src.split("?")[0]
    src = src.replace("/wp-content/w3-webp/uploads/", "/wp-content/uploads/")
    if src.endswith("w3.webp"):
        src = src[: -len("w3.webp")]
    return src


def fetch_bytes(url):
    for i in range(5):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (TheLiftCo migration)"})
            with urllib.request.urlopen(req, timeout=40) as r:
                return r.read()
        except Exception:
            time.sleep(3 * (i + 1))
    return None


def local_image(src, max_w=1600):
    """Descarga la imagen original y la guarda en WebP con su nombre original. Devuelve {src,w,h} o None."""
    from PIL import Image
    import io
    if not src:
        return None
    if src.startswith("/"):
        src = BASE + src
    orig = original_upload(src)
    m = re.search(r"/wp-content/uploads/(.+)$", orig)
    if not m:
        return None
    relpath = unquote(m.group(1))
    base_noext = os.path.splitext(relpath)[0]
    out_rel = f"{base_noext}.webp"
    out_fs = os.path.join(IMG_DIR, out_rel)
    if not os.path.exists(out_fs):
        data = fetch_bytes(orig) or fetch_bytes(src)
        if not data:
            return None
        os.makedirs(os.path.dirname(out_fs), exist_ok=True)
        im = Image.open(io.BytesIO(data))
        if im.mode not in ("RGB", "RGBA"):
            im = im.convert("RGBA" if "transparency" in im.info else "RGB")
        if im.width > max_w:
            im = im.resize((max_w, round(im.height * max_w / im.width)))
        im.save(out_fs, "WEBP", quality=80, method=6)
    from PIL import Image as I2
    with I2.open(out_fs) as im2:
        w, h = im2.size
    return {"src": f"/images/wp/{out_rel}", "w": w, "h": h}
