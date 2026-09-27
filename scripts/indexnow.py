#!/usr/bin/env python3
"""
Envía las URLs del sitemap de producción a la API de IndexNow (Bing, Yandex, Naver,
Seznam.cz, Yep la consumen directamente; Bing alimenta a su vez a Copilot y, en
parte, al índice que usa ChatGPT Search cuando no tiene su propio rastreo reciente
de la URL). Ver references/funciones-google-y-llm.md #24 y references/lanzamiento.md.

No usa dependencias externas (solo la librería estándar).

Uso:
  # generar la clave (una vez por proyecto) y el archivo <clave>.txt en public/
  python3 scripts/indexnow.py --generar-clave --out public/

  # enviar TODAS las URLs del sitemap tras un despliegue a producción
  python3 scripts/indexnow.py --sitemap https://dominio.com/sitemap.xml --key public/<clave>.txt

  # enviar solo las URLs que han cambiado en este despliegue (recomendado en CI)
  python3 scripts/indexnow.py --sitemap https://dominio.com/sitemap.xml --key public/<clave>.txt \
      --solo-cambiadas migracion/urls-cambiadas.txt

  # comprobar qué se enviaría sin llamar a la API
  python3 scripts/indexnow.py --sitemap https://dominio.com/sitemap.xml --key public/<clave>.txt --dry-run

La clave (una cadena hexadecimal de 32-128 caracteres) se genera una vez, se sirve
en https://dominio.com/<clave>.txt con ese contenido exacto (Astro la copia desde
public/ tal cual), y se reutiliza en cada envío. Documentado en lanzamiento.md.
"""
import argparse
import json
import os
import secrets
import sys
import urllib.error
import urllib.request
from urllib.parse import urlparse
from xml.etree import ElementTree

ENDPOINT = "https://api.indexnow.org/indexnow"
UA = "TheLiftCo-migracion-indexnow/1.0"


def generar_clave(out_dir):
    clave = secrets.token_hex(32)  # 64 caracteres hex, dentro del rango 8-128 que acepta la API
    os.makedirs(out_dir, exist_ok=True)
    ruta = os.path.join(out_dir, f"{clave}.txt")
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(clave)
    print(f"Clave generada: {clave}\nArchivo: {ruta}")
    print("Recuerda: debe quedar accesible en https://dominio.com/{clave}.txt tal cual (Astro "
          "copia public/ a la raíz de dist/, no hace falta moverlo).")
    return clave


def leer_clave(key_arg):
    """--key acepta la clave literal o la ruta a un archivo <clave>.txt (se usa el nombre
    del archivo sin extensión, que es la propia clave, para no depender de leer bien el
    contenido si alguien lo edita con un salto de línea final distinto)."""
    if os.path.exists(key_arg):
        nombre = os.path.splitext(os.path.basename(key_arg))[0]
        if nombre:
            return nombre
        return open(key_arg, encoding="utf-8").read().strip()
    return key_arg.strip()


def descargar(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def urls_de_sitemap(sitemap_url, vistos=None):
    """Soporta sitemap index (recursivo) y sitemaps normales. urlset/sitemapindex de
    https://www.sitemaps.org/schemas/sitemap/0.9."""
    vistos = vistos if vistos is not None else set()
    if sitemap_url in vistos:
        return []
    vistos.add(sitemap_url)
    ns = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
    try:
        cuerpo = descargar(sitemap_url)
    except (urllib.error.URLError, urllib.error.HTTPError) as e:
        print(f"⚠️  no se pudo descargar {sitemap_url}: {e}", file=sys.stderr)
        return []
    root = ElementTree.fromstring(cuerpo)
    urls = []
    if root.tag == f"{ns}sitemapindex":
        for loc in root.findall(f"{ns}sitemap/{ns}loc"):
            urls.extend(urls_de_sitemap(loc.text.strip(), vistos))
    else:
        for loc in root.findall(f"{ns}url/{ns}loc"):
            urls.append(loc.text.strip())
    return urls


def filtrar_por_lista(urls, lista_fn):
    if not lista_fn or not os.path.exists(lista_fn):
        return urls
    rutas = set()
    for line in open(lista_fn, encoding="utf-8"):
        line = line.strip()
        if line:
            rutas.add(urlparse(line).path.rstrip("/") or "/")
    return [u for u in urls if (urlparse(u).path.rstrip("/") or "/") in rutas]


def enviar(host, clave, urls, dry_run):
    if not urls:
        print("Nada que enviar (0 URLs tras el filtrado).")
        return 0
    payload = {
        "host": host,
        "key": clave,
        "keyLocation": f"https://{host}/{clave}.txt",
        "urlList": urls,
    }
    print(f"{len(urls)} URLs a enviar a {ENDPOINT} (host={host}):")
    for u in urls[:20]:
        print(f"  - {u}")
    if len(urls) > 20:
        print(f"  ... y {len(urls) - 20} más")
    if dry_run:
        print("\n--dry-run: no se ha llamado a la API. Payload que se habría enviado:")
        print(json.dumps(payload, ensure_ascii=False, indent=2)[:2000])
        return 0
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        ENDPOINT, data=data, method="POST",
        headers={"Content-Type": "application/json; charset=utf-8", "User-Agent": UA},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            print(f"\nIndexNow respondió {r.status}")
            return 0
    except urllib.error.HTTPError as e:
        # 200/202 = aceptado; 400/403/422/429 llevan cuerpo explicativo de la API
        print(f"\n⚠️  IndexNow respondió {e.code}: {e.read().decode('utf-8', 'ignore')[:500]}",
              file=sys.stderr)
        return 1
    except urllib.error.URLError as e:
        print(f"\n⚠️  No se pudo contactar con IndexNow: {e}", file=sys.stderr)
        return 1


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--generar-clave", action="store_true", help="genera una clave nueva y su archivo <clave>.txt")
    ap.add_argument("--out", default="public/", help="carpeta donde escribir <clave>.txt con --generar-clave (por defecto public/)")
    ap.add_argument("--sitemap", help="URL del sitemap de producción (o del índice de sitemaps)")
    ap.add_argument("--key", help="la clave de IndexNow, o la ruta al archivo <clave>.txt (se usa el nombre del archivo)")
    ap.add_argument("--host", help="host a reportar a la API (por defecto, se deduce de --sitemap)")
    ap.add_argument("--solo-cambiadas", help="archivo con una URL o ruta por línea; si se pasa, solo se envían esas")
    ap.add_argument("--dry-run", action="store_true", help="muestra qué se enviaría, sin llamar a la API")
    a = ap.parse_args()

    if a.generar_clave:
        generar_clave(a.out)
        return

    if not a.sitemap or not a.key:
        ap.error("--sitemap y --key son obligatorios (o usa --generar-clave)")

    clave = leer_clave(a.key)
    if not (8 <= len(clave) <= 128) or not all(c.isalnum() or c == "-" for c in clave):
        ap.error(f"la clave '{clave}' no tiene el formato de IndexNow (8-128 caracteres alfanuméricos/guion)")

    host = a.host or urlparse(a.sitemap).netloc
    urls = urls_de_sitemap(a.sitemap)
    urls = filtrar_por_lista(urls, a.solo_cambiadas)
    sys.exit(enviar(host, clave, urls, a.dry_run))


if __name__ == "__main__":
    main()
