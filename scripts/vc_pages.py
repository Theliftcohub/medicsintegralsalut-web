#!/usr/bin/env python3
"""Constructor de páginas «Versión C» a partir del HTML cacheado del WordPress (todas las plantillas, todos los idiomas).

Principio: el CONTENIDO es literal (mismo texto, H1/H2, enlaces, imágenes con su alt, JSON-LD propio de la página);
solo cambia la plantilla. Cada página sale como src/content/pages/<lang>/<slug>.json con theme "vc".

- Páginas con componentes .mpost (tratamientos nuevos): el marcado .mpost se conserva tal cual (limpio) en un bloque
  `vc-mpost`; la piel «Versión C» se la da src/styles/vc-mpost.css.
- Resto (WPBakery/Bridge, entradas del blog, fichas): el contenido se reduce a HTML semántico (h1-h6, p, listas,
  tablas, imágenes, enlaces, énfasis) y va en bloques `vc-prosa` por fila de WPBakery.
Uso: python3 scripts/vc_pages.py <ruta> [<ruta> ...]   ·   --todas  (todas las filas "mantener" de migracion/urls.csv)
"""
import ast, csv, hashlib, io, json, os, re, sys, urllib.request
from urllib.parse import urlparse, unquote, parse_qs
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wp_lib import rel, local_image, fetch_bytes, BASE
from bs4 import BeautifulSoup, Comment, NavigableString, Tag

LANGS = ("ca", "en", "fr", "ru", "uk")
INV = {i["url"]: i for i in json.load(open("migracion/inventory.json"))["items"]}
I18N = json.load(open("migracion/i18n-map.json"))
PATH2GROUP = {p: g for g, m in I18N.items() for p in m.values()}
REPORT = {"imagenes_sin_local": [], "enlaces_wp_content": [], "iframes": [], "formularios": [], "typeform": []}


def lang_of(path):
    s = [x for x in path.split("/") if x]
    return s[0] if s and s[0] in LANGS else "es"


def soup_of(path):
    u = BASE + path
    fn = f"migracion/html_cache/{hashlib.md5(u.encode()).hexdigest()}.html"
    return BeautifulSoup(open(fn, encoding="utf-8", errors="ignore").read(), "html.parser")


def seo_of(path):
    it = INV.get(BASE + path, {})
    s = it.get("seo") or {}
    if isinstance(s, str):
        s = ast.literal_eval(s)
    out = {"title": s.get("title") or it.get("wp_title") or "", "description": s.get("meta_description") or "",
           "canonical": s.get("canonical") or None, "robots": s.get("robots") or "index, follow",
           "ogTitle": s.get("og_title") or None, "ogDescription": s.get("og_description") or None}
    og = s.get("og_image")
    if og:
        li = local_image(og)
        if li:
            out["ogImage"] = li["src"]
    return {k: v for k, v in out.items() if v}, it


def fix_mojibake(t):
    for _ in range(3):
        try:
            n = t.encode("latin1").decode("utf-8")
            if n == t:
                break
            t = n
        except Exception:
            break
    return t


def yoast(s):
    """BreadcrumbList del grafo de Yoast -> [{name, path}]; JSON-LD propio de la página (FAQPage, etc.)."""
    crumbs, own = [], []
    for sc in s.find_all("script", type="application/ld+json"):
        try:
            d = json.loads(sc.get_text())
        except Exception:
            continue
        graph = d.get("@graph") if isinstance(d, dict) else None
        if graph:
            for g in graph:
                if g.get("@type") == "BreadcrumbList":
                    for li in g.get("itemListElement", []):
                        item = li.get("item")
                        crumbs.append({"name": li.get("name"), "path": rel(item) if item else None})
        elif isinstance(d, dict) and d.get("@type") in ("FAQPage", "HowTo", "VideoObject", "MedicalProcedure", "Service", "Product", "Event"):
            own.append(d)
    if crumbs and not crumbs[-1]["path"]:
        crumbs[-1]["path"] = None
    return crumbs, own


def to_schema(d):
    if isinstance(d, list) or "@type" not in d:
        return None
    d = dict(d)
    d.pop("@context", None)
    t = d.pop("@type")
    return {"type": t, **d}


YT = re.compile(r"(?:youtube(?:-nocookie)?\.com/(?:embed/|watch\?v=)|youtu\.be/)([\w-]{11})")


def yt_thumb(vid):
    out = f"public/images/yt/{vid}.webp"
    if not os.path.exists(out):
        from PIL import Image
        data = fetch_bytes(f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg")
        if not data:
            return None
        os.makedirs(os.path.dirname(out), exist_ok=True)
        Image.open(io.BytesIO(data)).convert("RGB").save(out, "WEBP", quality=78)
    return f"/images/yt/{vid}.webp"


def yt_facade(soup, vid, title):
    """Vídeo de YouTube que solo se carga al pulsar (privacidad: sin cookies de Google hasta el clic)."""
    thumb = yt_thumb(vid)
    b = soup.new_tag("button", attrs={"type": "button", "class": "vc-yt", "data-yt": vid, "aria-label": f"▶ {title}".strip()})
    if thumb:
        b.append(soup.new_tag("img", attrs={"src": thumb, "alt": title, "loading": "lazy", "width": "480", "height": "360"}))
    sp = soup.new_tag("span", attrs={"class": "vc-yt-play", "aria-hidden": "true"})
    sp.string = "▶"
    b.append(sp)
    return b


def img_attrs(el, path):
    src = el.get("data-src") or el.get("data-lazy-src") or el.get("src") or ""
    if src.startswith("/images/"):
        return True  # ya local (miniaturas de vídeo)
    if src.startswith("data:"):
        src = el.get("data-src") or el.get("data-lazy-src") or ""
    if src and re.search(r"(medicstetics|medicsintegralsalut)\.com/wp-content/uploads/.+\.svg$", src):
        # SVG propios (algunos enlazados desde el dominio antiguo medicstetics.com, que redirige al actual)
        rel_ = re.search(r"/wp-content/uploads/(.+)$", src).group(1)
        out = f"public/images/wp/{unquote(rel_)}"
        if not os.path.exists(out):
            data = fetch_bytes(BASE + "/wp-content/uploads/" + rel_)
            if data and data.lstrip()[:5] in (b"<svg ", b"<?xml"):
                os.makedirs(os.path.dirname(out), exist_ok=True)
                open(out, "wb").write(data)
        if os.path.exists(out):
            keep = {k: el.get(k) for k in ("alt", "class", "title", "width", "height") if el.get(k) is not None}
            el.attrs = {**keep, "src": out[len("public"):], "loading": "lazy", "decoding": "async"}
            el.attrs.setdefault("alt", "")
            return True
    li = local_image(src) if src and "/wp-content/" in src else None
    if not li:
        if src and not src.startswith(("/images/", "data:")):
            REPORT["imagenes_sin_local"].append((path, src))
        return False
    keep = {k: el.get(k) for k in ("alt", "class", "title") if el.get(k) is not None}
    el.attrs = {**keep, "src": li["src"], "width": str(li["w"]), "height": str(li["h"])}
    el.attrs.setdefault("alt", "")
    if "fetchpriority" not in el.attrs:
        el["loading"] = "lazy"
    el["decoding"] = "async"
    return True


def clean_common(root, path, soup):
    for c in root.find_all(string=lambda x: isinstance(x, Comment)):
        c.extract()
    for x in root(["style", "noscript", "link", "meta"]):
        x.decompose()
    for x in root("script"):
        x.decompose()
    # iframes -> fachada de YouTube; otros se anotan
    for f in root.find_all("iframe"):
        src = f.get("data-src") or f.get("src") or ""
        m = YT.search(src)
        if m:
            title = fix_mojibake(f.get("title") or "")
            f.replace_with(yt_facade(soup, m.group(1), title))
        elif "google.com/maps" in src:
            d = soup.new_tag("div", attrs={"class": "vc-embed vc-embed--mapa", "data-embed": src, "data-title": f.get("title") or "Google Maps"})
            b = soup.new_tag("button", attrs={"type": "button", "class": "btn linea"})
            sp = soup.new_tag("span"); sp.string = "{{map_load}}"; b.append(sp); d.append(b)
            f.replace_with(d)
        else:
            REPORT["iframes"].append((path, src))
            if "typeform" in src:
                REPORT["typeform"].append(path)
            f.decompose()
    for el in root.find_all(True):
        for a in list(el.attrs):
            if a.startswith("data-") and a not in ("data-f", "data-cat", "data-yt", "data-embed", "data-title"):
                del el.attrs[a]
            elif a in ("onclick", "onload", "srcset", "sizes", "fetchpriority") and el.name != "img":
                del el.attrs[a]
    for el in root.find_all("img"):
        if el.attrs is None or el.parent is None:
            continue
        if "/wp-content/themes/" in (el.get("src") or ""):
            el.decompose()
            continue
        if el.get("fetchpriority"):
            el["fetchpriority"] = "high"
        if not img_attrs(el, path):
            el.decompose()
    for a in root.find_all("a", href=True):
        h = a["href"].strip()
        if "typeform" in h:
            REPORT["typeform"].append(path)
        if "/wp-content/uploads/" in h:
            if re.search(r"\.(jpe?g|png|webp|gif)$", h.split("?")[0], re.I):
                li = local_image(h)
                if li:
                    a["href"] = li["src"]
                    continue
            loc = "public/media/" + os.path.basename(unquote(h.split("?")[0]))
            if os.path.exists(loc):
                a["href"] = loc[len("public"):]
                continue
            REPORT["enlaces_wp_content"].append((path, h))
        a["href"] = rel(h)
    # estilos en línea con url(...) de uploads -> imagen local
    for el in root.find_all(style=True):
        st = el["style"]
        for u in re.findall(r"url\((['\"]?)([^)'\"]+)\1\)", st):
            if "/wp-content/" in u[1]:
                li = local_image(u[1])
                st = st.replace(u[1], li["src"]) if li else st
        el["style"] = st
    # párrafos vacíos y <br> sueltos que añadió wpautop
    for p in root.find_all("p"):
        if not p.get_text(strip=True) and not p.find(["img", "button", "svg", "a"]):
            p.decompose()
    for br in root.select(".mpost-filters > br, .mpost-cta > br, .mpost-grid > br"):
        br.decompose()


def mpost_block(s, path):
    mp = s.select_one(".mpost")
    own = []
    for sc in mp.find_all("script", type="application/ld+json"):
        try:
            d = json.loads(sc.get_text())
            own.extend(d if isinstance(d, list) else d.get("@graph", [d]))
        except Exception:
            pass
    clean_common(mp, path, s)
    for f in mp.find_all("form"):
        REPORT["formularios"].append(path)
    html = "".join(str(c) for c in mp.children).strip()
    return {"type": "vc-mpost", "html": html}, own



# ---------------------------------------------------------------- prosa (WPBakery / Bridge / entradas / fichas)
KEEP = {"div", "h1", "h2", "h3", "h4", "h5", "h6", "p", "ul", "ol", "li", "a", "strong", "b", "em", "i", "br", "img",
        "figure", "figcaption", "table", "thead", "tbody", "tr", "th", "td", "blockquote", "hr", "button", "span",
        "details", "summary", "dl", "dt", "dd", "sup", "sub", "u"}
DROP_SEL = [".title_holder", ".post_info", ".blog_like", ".post_comments", ".portfolio_social_holder", ".social_share_holder",
            ".comment_holder", "#respond", ".comments_holder", ".blog_share", ".portfolio_navigation", ".qode_print",
            ".post_more", ".single_tags", "aside", ".column2", ".sidebar", ".widget", "nav", ".wpcf7-response-output",
            ".screen-reader-response", ".trp-language-switcher", ".ht-ctc", "#ht-ctc-chat", ".vc_separator", ".separator", ".vc_empty_space"]
BLOCK_TAGS = {"div", "h1", "h2", "h3", "h4", "h5", "h6", "p", "ul", "ol", "table", "blockquote", "hr", "figure", "details", "dl", "img", "button"}


def cf7_form(f, path):
    """CF7 -> definición del formulario propio (mismos campos, placeholders y textos)."""
    REPORT["formularios"].append(path)
    fields = []
    names = {"your-name": ("nombre", "name"), "your-tel": ("telefono", "tel"), "your-email": ("email", "email"),
             "your-message": ("mensaje", None), "your-subject": ("asunto", None)}
    for el in f.find_all(["input", "textarea", "select"]):
        n = el.get("name") or ""
        t = el.get("type") or el.name
        if t in ("hidden", "submit") or n.startswith("_") or not n:
            continue
        key, ac = names.get(n, (re.sub(r"[^a-z0-9]+", "_", n.lower()).strip("_") or "campo", None))
        if n.startswith("acceptance") or t == "checkbox":
            from wp_lib import inline
            lab = el.find_parent("label")
            lbl = lab.find(class_="wpcf7-list-item-label") if lab else None
            html = inline(lbl) if lbl else ""
            if not html:  # texto de aceptación escrito DESPUÉS del control (p. ej. "He leído la <a>Política…</a>")
                wrap = el.find_parent(class_="wpcf7-form-control-wrap")
                tmp = BeautifulSoup("<span></span>", "html.parser").span
                sib = wrap.next_sibling if wrap else None
                while sib is not None and not (isinstance(sib, Tag) and (sib.name == "br" or "wpcf7-form-control-wrap" in (sib.get("class") or []) or sib.find("input"))):
                    nxt = sib.next_sibling
                    tmp.append(sib.extract() if isinstance(sib, Tag) else NavigableString(str(sib)))
                    sib = nxt
                html = inline(tmp)
            fields.append({"name": "privacidad" if n.startswith("acceptance") else key, "type": "checkbox", "required": True,
                           "labelHtml": html or (el.get("value") or "")})
            continue
        if el.name == "select":
            fields.append({"name": key, "type": "select", "required": "wpcf7-validates-as-required" in (el.get("class") or []),
                           "options": [o.get_text(strip=True) for o in el.find_all("option")]})
            continue
        if t == "radio":
            if any(x["name"] == key for x in fields):
                continue
            grp = el.find_parent(class_="wpcf7-radio")
            opts = [x.get_text(strip=True) for x in grp.find_all(class_="wpcf7-list-item-label")] if grp else []
            fields.append({"name": key, "type": "radio", "required": True, "options": opts})
            continue
        f2 = {"name": key, "type": "textarea" if el.name == "textarea" else ("tel" if t == "tel" else "email" if t == "email" else "text"),
              "placeholder": el.get("placeholder") or "", "required": "wpcf7-validates-as-required" in (el.get("class") or []) or el.has_attr("aria-required")}
        if ac:
            f2["autocomplete"] = ac
        fields.append(f2)
    sub = f.find(["input", "button"], attrs={"type": "submit"})
    label = (sub.get("value") if sub and sub.name == "input" else sub.get_text(strip=True) if sub else "") or "Enviar"
    slug = re.sub(r"[^a-z0-9]+", "-", path.strip("/").lower()).strip("-")[:40] or "home"
    return {"name": f"form-{slug}", "thanks": ("/" if lang_of(path) == "es" else f"/{lang_of(path)}/") + "gracias/",
            "submit": label, "fields": fields}


def sanitize(node, path):
    """Deja solo HTML semántico literal: etiquetas permitidas, atributos mínimos."""
    for el in list(node.find_all(True)):
        if el.parent is None:
            continue
        cls = el.get("class") or []
        if el.name == "div":
            if "vc-embed" in cls:
                el.attrs = {"class": "vc-embed vc-embed--mapa", "data-embed": el.get("data-embed"), "data-title": el.get("data-title")}
            elif "vc-in" in cls:
                el.attrs = {"class": "vc-in", "style": el.get("style")}
            elif "vc-bloglist" in cls or "vc-bcard" in cls:
                el.attrs = {"class": cls[0]}
            elif "vc-in-c" in cls:
                el.attrs = {"class": "vc-in-c"}
            else:
                el.unwrap()
            continue
        if el.name not in KEEP:
            el.unwrap()
            continue
        keep = {}
        if el.name == "a":
            keep = {k: el.get(k) for k in ("href", "target", "rel") if el.get(k)}
            if "qbutton" in cls or "vc_btn3" in cls or "btn" in cls:
                keep["class"] = "btn"
        elif el.name == "img":
            keep = {k: el.get(k) for k in ("src", "alt", "width", "height", "loading", "decoding") if el.get(k) is not None}
        elif el.name in ("td", "th"):
            keep = {k: el.get(k) for k in ("colspan", "rowspan", "scope") if el.get(k)}
        elif el.name == "button":
            keep = {k: el.get(k) for k in ("type", "class", "data-yt", "aria-label") if el.get(k)}
            if "vc-yt" not in (el.get("class") or []) and not (el.parent and "vc-embed" in (el.parent.get("class") or [])):
                el.unwrap()
                continue
        elif el.name == "span":
            if el.parent is not None and el.parent.name == "button":
                keep = {}
            elif "vc-yt-play" in cls:
                keep = {"class": "vc-yt-play", "aria-hidden": "true"}
            else:
                el.unwrap()
                continue
        elif el.name == "p" and "vc-bcard-meta" in cls:
            keep = {"class": "vc-bcard-meta"}
        elif el.name == "details" and el.has_attr("open"):
            keep = {"open": ""}
        el.attrs = keep
    # texto suelto a nivel de bloque -> <p>
    html = str(node) if node.name != "[document]" else "".join(str(c) for c in node.contents)
    return html


def wrap_loose_text(soup_frag):
    out, buf = [], []
    def flush():
        t = "".join(str(x) for x in buf).strip()
        if t and re.sub(r"<br\s*/?>", "", t).strip():
            out.append(f"<p>{t}</p>")
        buf.clear()
    for c in list(soup_frag.contents):
        if isinstance(c, Tag) and c.name in BLOCK_TAGS:
            flush()
            out.append(str(c))
        else:
            buf.append(c)
    flush()
    return "\n".join(out)


CONTACTO = {"es": "/contacto/", "en": "/en/contact/", "fr": "/fr/contact/", "ca": "/ca/contacte-2/",
            "ru": "/ru/%d0%ba%d0%be%d0%bd%d1%82%d0%b0%d0%ba%d1%82%d0%be/", "uk": "/uk/%d0%ba%d0%be%d0%bd%d1%82%d0%b0%d0%ba%d1%82/"}
_CF = {}


def contact_form(path):
    """Formulario propio con los campos literales del CF7 de /contacto/ del idioma (sustituye a Typeform)."""
    L = lang_of(path)
    if L not in _CF:
        cs = soup_of(CONTACTO[L])
        _CF[L] = cf7_form(cs.select_one("form.wpcf7-form"), CONTACTO[L])
    f = json.loads(json.dumps(_CF[L]))
    f["name"] = "form-" + (re.sub(r"[^a-z0-9]+", "-", unquote(path).strip("/").lower()).strip("-")[:40] or "home")
    return f


def landing_hero(frag):
    """Antes de clean_common (que quita los style)."""
    # landings propias (troo-*): la foto del hero es un fondo CSS en línea -> <img> decorativa al principio de la sección
    for sec in frag.select("section.troo-banner-sec[style*=url]"):
        m = re.search(r"url\(['\"]?([^'\")]+)", sec["style"])
        li = local_image(m.group(1)) if m else None
        if li:
            sec.insert(0, BeautifulSoup('<img src="%s" alt="" width="%s" height="%s" loading="eager" decoding="async"/>' % (li["src"], li["w"], li["h"]), "html.parser"))


def structure_widgets(frag):
    """Conserva la estructura visible del WordPress que sanitize aplanaría:
    - acordeones/toggles de Bridge (qode-accordion-holder: h4 título + contenido) -> <details><summary> cerrados, como en el original;
    - filas internas de WPBakery (.vc_row.vc_inner con columnas vc_col-sm-N) -> rejilla .vc-in con las mismas proporciones."""
    # numeritos sueltos de carruseles/pasos (1 2 3 4) sin contenido asociado: fuera
    for x in frag.select(".rounded-circle, .carousel-indicators, .owl-dots, .slick-dots"):
        if re.fullmatch(r"[\d\s]*", x.get_text()):
            x.decompose()
    # listado de entradas (plugin «mega post» de Bridge: .grid > .mason-item) -> rejilla de tarjetas como el original
    for grid in frag.select(".grid"):
        items = grid.select(":scope > .mason-item")
        if not items:
            continue
        box = frag.new_tag("div", attrs={"class": "vc-bloglist"})
        for it in items:
            t = it.select_one(".mega-post-title a")
            if not t:
                continue
            card = frag.new_tag("div", attrs={"class": "vc-bcard"})
            im = it.select_one(".mega-post-image img")
            if im:
                a = frag.new_tag("a", href=t.get("href"))
                a.append(im.extract())
                card.append(a)
            h = frag.new_tag("h3")
            h.append(t.extract())
            card.append(h)
            ex = it.select_one(".mega-post-para")
            txt = re.sub(r"\s+", " ", ex.get_text(" ", strip=True)) if ex else ""
            # el WordPress mete en el extracto el CSS de las entradas .mpost ("mpost{--accent…", "body{margin…"): se corta ahí
            txt = re.split(r"\s*(?:\.?mpost\S*\{|body\{|\S+\{[-\w]+:)", txt)[0].strip()
            if txt:
                p_ = frag.new_tag("p")
                p_.string = txt
                card.append(p_)
            au = it.select_one(".mega-post-meta")
            if au and au.get_text(strip=True):
                m = frag.new_tag("p", attrs={"class": "vc-bcard-meta"})
                m.string = au.get_text(" ", strip=True)
                card.append(m)
            box.append(card)
        grid.replace_with(box)
    for hold in frag.select(".qode-accordion-holder"):
        out = []
        for t in hold.find_all(class_="qode-title-holder"):
            c = t.find_next_sibling(class_="qode-accordion-content")
            for m in t.select(".qode-accordion-mark"):
                m.decompose()
            d = frag.new_tag("details")
            sm = frag.new_tag("summary")
            sm.string = t.get_text(" ", strip=True)
            d.append(sm)
            if c:
                inner = c.select_one(".qode-accordion-content-inner") or c
                d.append(BeautifulSoup(wrap_loose_text(BeautifulSoup(inner.decode_contents(), "html.parser")), "html.parser"))
            out.append(d)
        for d in reversed(out):
            hold.insert_after(d)
        hold.decompose()
    for row in reversed(frag.select(".vc_row.vc_inner, .vc_row_inner")):
        cols = [c for c in row.select(".wpb_column") if c.find_parent(class_="wpb_column") in (None, row.find_parent(class_="wpb_column"))]
        cols = [c for c in cols if c.get_text(strip=True) or c.find("img")]
        if len(cols) < 2:
            continue
        grid = frag.new_tag("div", attrs={"class": "vc-in"})
        spans = []
        for c in cols:
            m = re.search(r"vc_col-sm-(\d+)", " ".join(c.get("class") or []))
            spans.append(m.group(1) if m else "1")
            cell = frag.new_tag("div", attrs={"class": "vc-in-c"})
            cell.append(BeautifulSoup(wrap_loose_text(BeautifulSoup(c.decode_contents(), "html.parser")), "html.parser"))
            grid.append(cell)
        grid["style"] = "--g:" + " ".join(f"{s}fr" for s in spans)
        row.replace_with(grid)


def prose_html(el, path, s):
    frag = BeautifulSoup(str(el), "html.parser")
    for tf in frag.select("[data-tf-widget], [data-tf-popup], [data-tf-live]"):
        REPORT["typeform"].append(path)
        box = tf.find_parent(id="landing-form") or tf
        box.replace_with(BeautifulSoup("<p>{{FORM}}</p>", "html.parser"))
    for sel in DROP_SEL:
        for x in frag.select(sel):
            x.decompose()
    landing_hero(frag)
    clean_common(frag, path, s)
    for f in frag.find_all("form"):  # el formulario propio va en el MISMO sitio que el CF7 (antes/después del texto como en el original)
        f.replace_with(BeautifulSoup("<p>{{CF7}}</p>", "html.parser"))
    structure_widgets(frag)
    sanitize(frag, path)
    html = wrap_loose_text(frag)
    # shortcodes de WPBakery que el WordPress deja VISIBLES como texto (fallo del sitio actual): fuera
    html = re.sub(r"\[vc_raw_html\][A-Za-z0-9+/=%\s]*\[/vc_raw_html\]", "", html)
    html = re.sub(r"\[/?(vc_|qode_|mkd_|rev_slider)[^\]]*\]", "", html)
    html = re.sub(r"(<p>\s*</p>|<p>(\s|&nbsp;|<br/?>|\.\.\.)*</p>)", "", html)
    # <p> que envuelve un bloque (tabla, lista, rejilla…): HTML inválido, el navegador lo parte y deja párrafos vacíos
    html = re.sub(r"<p>\s*(<(?:table|ul|ol|h[1-6]|div|blockquote|details|figure)[\s>])", r"\1", html)
    html = re.sub(r"(</(?:table|ul|ol|h[1-6]|div|blockquote|details|figure)>)\s*</p>", r"\1", html)
    return html.strip()


def content_root(s):
    for sel in [".sptp-single-post", ".blog_holder article .post_text_inner", ".portfolio_single", ".full_width_inner",
                ".default_template_holder", ".container_inner.default_template_holder", ".content_inner .container_inner", ".content_inner"]:
        for el in s.select(sel):
            if el.find_parent(["header", "footer"]) or el.find_parent(lambda t: t.name not in ("body", "html") and any(re.search("header|side_menu|sticky", c) for c in (t.get("class") or []))):
                continue
            if el.get_text(strip=True):
                return el
    # plantillas propias (landings) o contenido fuera de los contenedores de Bridge: el <body> sin cabecera ni pie
    b = BeautifulSoup(str(s.body), "html.parser").body
    for x in b.select("header, footer, nav, .side_menu, .header_top, .page_header, .title_holder, #back_to_top, .ht-ctc, .ct-ultimate-gdpr-container, .cookie-notice-container, script, style, noscript"):
        x.decompose()
    return b if b.get_text(strip=True) else None


def prosa_blocks(s, path):
    root = content_root(s)
    if root is None:  # página sin contenido en el WordPress (p. ej. fichas de portfolio vacías)
        REPORT.setdefault("vacias", []).append(path)
        it = INV.get(BASE + path, {})
        sd = it.get("seo") or {}
        sd = ast.literal_eval(sd) if isinstance(sd, str) else sd
        t = it.get("wp_title") or sd.get("h1") or (sd.get("title") or "").split(" - ")[0].split(" | ")[0]
        return [{"type": "vc-prosa", "cols": [{"html": f"<h1>{t}</h1>"}]}] if t else []
    rows = root.select(":scope > .vc_row, :scope > div > .vc_row") if root else []
    rows = [r for r in rows if not r.find_parent(class_="vc_row") or r.find_parent(class_="vc_row") is None]
    units = rows if rows else [root]
    blocks = []
    for i, r in enumerate(units):
        cols = r.select(":scope .wpb_column") if rows else []
        cols = [c for c in cols if c.find_parent(class_="wpb_column") is None] or [r]
        out = []
        for c in cols:
            forms = [cf7_form(f, path) for f in c.select("form")]
            if "typeform" in str(c):
                REPORT["typeform"].append(path)
            h = prose_html(c, path, s)
            # CF7 ({{CF7}}) y Typeform ({{FORM}}) -> formulario propio en el mismo sitio del original
            parts = re.split(r"<p>\{\{(CF7|FORM)\}\}</p>", h)
            for k in range(0, len(parts), 2):
                if parts[k].strip():
                    out.append({"html": parts[k].strip()})
                if k + 1 < len(parts):
                    out.append({"form": forms.pop(0) if parts[k + 1] == "CF7" and forms else contact_form(path)})
            for f in forms:  # formularios cuyo marcador se perdió (no debería): al final
                out.append({"form": f})
        if out:
            b = {"type": "vc-prosa", "cols": out, "bg": "crema" if i % 2 else None}
            if len(cols) == 1 and len(out) > 1:
                b["stack"] = True  # una sola columna del WordPress partida por el formulario: se apila, no rejilla
            blocks.append(b)
    for b in blocks:
        if not b["bg"]:
            b.pop("bg")
    return blocks


def slug_file(path, lang):
    p = unquote(path).strip("/")
    if lang != "es":
        p = p[len(lang):].strip("/")
    f = (p.replace("/", "__") or "home")
    if len(f.encode()) > 150:
        f = f[:40] + "-" + hashlib.md5(f.encode()).hexdigest()[:10]
    return f + ".json"


def build_post(path, s, seo, it):
    """Entrada del blog -> src/content/posts/<lang>/<slug>.md (cuerpo HTML literal, frontmatter completo)."""
    lang = lang_of(path)
    art = s.select_one(".blog_holder article") or s
    h1 = art.select_one("h1.entry_title") or s.find("h1")
    for d in h1.select(".date"):
        d.decompose()
    title = re.sub(r"\s+", " ", h1.get_text(" ", strip=True)).strip()
    info = art.select_one(".post_info")
    author, category = "", ""
    if info:
        a = info.select_one(".post_author a, .post_author_link") or info.find("a", href=re.compile("/author/"))
        author = a.get_text(strip=True) if a else ""
        c = info.find("a", rel=re.compile("category")) or info.find("a", href=re.compile("/category/"))
        category = c.get_text(strip=True) if c else ""
    body_el = art.select_one(".post_text_inner") or art
    for x in body_el.select("h1.entry_title, .post_info"):
        x.decompose()
    mp = body_el.select_one(".mpost")
    if mp:  # entrada maquetada con componentes .mpost: se conserva el marcado y SU CSS literal (mpost-posts.css, por variante)
        vid = hashlib.md5("".join(st.get_text() for st in mp.find_all("style")).encode()).hexdigest()[:8]
        blk, _ = mpost_block(BeautifulSoup(str(mp), "html.parser"), path)
        html = f'<div class="mpv-{vid}"><div class="mpost">' + re.sub(r"\n\s*\n", "\n", blk["html"]) + "</div></div>"
        # las entradas comparten nombres de clase con las páginas de tratamiento (mpost.css, piel vc-mpost.css) pero su
        # CSS literal es otro: se renombran mpost* -> mpp* para que SOLO les aplique mpost-posts.css (se ven como el original)
        html = re.sub(r'class="([^"]*)"', lambda m: 'class="' + re.sub(r"(?<![\w-])mpost", "mpp", m.group(1)) + '"', html)
    else:
        html = prose_html(body_el, path, s)
    meta = lambda prop: (s.find("meta", property=prop) or {}).get("content")
    img = seo.get("ogImage")
    fm = {"path": unquote(path), "lang": lang, "title": title, "seoTitle": seo.get("title") or title,
          "description": seo.get("description", ""), "date": (it.get("date") or meta("article:published_time") or "")[:19],
          "modified": (it.get("modified") or meta("article:modified_time") or "")[:19], "mpost": bool(mp),
          "author": author or "Clínica Medics Integral Salut", "category": category, "image": img, "imageAlt": title,
          "canonical": seo.get("canonical"), "robots": seo.get("robots", "index, follow")}
    g = PATH2GROUP.get(path)
    if g:
        fm["i18nGroup"] = g
    fm = {k: v for k, v in fm.items() if v not in (None, "", False)}
    out = f"src/content/posts/{lang}/{slug_file(path, lang)[:-5]}.md"
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        f.write("---\n" + "".join(f"{k}: {json.dumps(v, ensure_ascii=False)}\n" for k, v in fm.items()) + "---\n\n" + html + "\n")
    return out


def build(path):
    s = soup_of(path)
    lang = lang_of(path)
    seo, it = seo_of(path)
    crumbs, own = yoast(s)
    if "single-post" in (s.body.get("class") or []):
        return build_post(path, s, seo, it), "post"
    if PATH2GROUP.get(path) == PATH2GROUP.get("/unidades/"):
        # /unidades/ está VACÍA en el WordPress (solo el botón flotante de WhatsApp): se le da el índice de unidades
        # literal de la portada del mismo idioma, con su título como H1 (NO_LITERAL.md)
        home = json.load(open(f"src/content/pages/{lang}/home.json"))
        u = next(b for b in home["blocks"] if b["type"] == "vc-unidades")
        blocks = [{**u, "headingTag": "h1", "num": None, "id": None}]
        kind = "unidades"
    elif s.select_one(".mpost"):
        block, own2 = mpost_block(s, path)
        blocks = [block]
        own = own or own2
        kind = "mpost"
    else:
        blocks = prosa_blocks(s, path)
        kind = "prosa"
        if not blocks:
            return None, "vacia"
    dpath = unquote(path)
    page = {"path": dpath if dpath.endswith("/") else dpath + "/", "lang": lang, "theme": "vc", "seo": seo,
            "schema": [x for x in (to_schema(d) for d in own) if x], "blocks": blocks}
    g = PATH2GROUP.get(path)
    if g:
        page["i18nGroup"] = g
    if len(crumbs) > 1:
        page["breadcrumbs"] = [{"name": c["name"], "path": c["path"] or page["path"]} for c in crumbs]
    out = f"src/content/pages/{lang}/{slug_file(path, lang)}"
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(page, open(out, "w"), ensure_ascii=False, indent=1)
    return out, kind


if __name__ == "__main__":
    args = sys.argv[1:]
    if args == ["--todas"]:
        args = [r["url"] for r in csv.DictReader(open("migracion/urls.csv"))
                if r["decision"] == "mantener" and r["url"].endswith("/") and not r["url"].startswith("/wp-content") and r["url"] not in ("/", "/ca/", "/en/", "/fr/", "/ru/", "/uk/")]
    stats = {}
    for n, p in enumerate(args):
        print(n, p, flush=True)
        try:
            out, kind = build(p)
        except Exception as e:
            out, kind = None, f"ERROR {e.__class__.__name__}: {e}"
        stats.setdefault(kind, []).append(p)
    json.dump(REPORT, open("migracion/vc_pages_report.json", "w"), ensure_ascii=False, indent=1)
    for k, v in stats.items():
        print(k, len(v), v[:5] if k != "mpost" else "")
    print({k: len(v) for k, v in REPORT.items()})
