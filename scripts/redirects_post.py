#!/usr/bin/env python3
"""Ajustes finales de public/_redirects y public/.htaccess tras build_redirects.py (URLs con %xx: ru/uk, "·" catalán…).
- Netlify compara las reglas con la ruta codificada en MAYÚSCULAS (normaliza %d0 -> %D0 antes): se reescriben
  origen y destino en mayúsculas y se quitan duplicados y reglas que solo añaden/quitan la barra (bucle).
- Apache (.htaccess): RewriteRule compara con la ruta DECODIFICADA: patrones y destinos se escriben en UTF-8
  (Apache vuelve a codificar el destino al redirigir)."""
import re
from urllib.parse import unquote, quote

def up(p):
    return quote(unquote(p), safe="/-_.~!$&'()*+,;=:@")

# Netlify
out, seen = [], set()
for l in open("public/_redirects", encoding="utf-8"):
    if l.startswith("#") or not l.strip():
        out.append(l.rstrip("\n")); continue
    parts = l.split()
    src, dst, rest = parts[0], parts[1], parts[2:]
    s2 = up(src)
    d2 = dst if dst.startswith("http") else up(dst)
    if unquote(s2).rstrip("/") == unquote(d2).rstrip("/"):
        continue  # solo cambia la barra: Netlify ya lo hace y la regla haría bucle
    if s2 in seen:
        continue
    seen.add(s2)
    out.append("  ".join([s2, d2] + rest))
open("public/_redirects", "w", encoding="utf-8").write("\n".join(out) + "\n")

# Apache
lines, seen = [], set()
for l in open("public/.htaccess", encoding="utf-8"):
    m = re.match(r"^(RewriteRule\s+)(\S+)(\s+)(\S+)(.*)$", l.rstrip("\n"))
    if m and "%" in (m.group(2) + m.group(4)):
        pat = re.sub(r"(%[0-9A-Fa-f]{2})+", lambda x: re.escape(unquote(x.group(0))), m.group(2))
        dst = unquote(m.group(4)) if not m.group(4).startswith("http") else m.group(4)
        l = m.group(1) + pat + m.group(3) + dst + m.group(5)
        if pat in seen:
            continue
        seen.add(pat)
    l = l.replace("//?$", "/?$")  # build_redirects escribe "x//?$" en los 410 (no casaría nunca con "x/")
    lines.append(l.rstrip("\n"))
open("public/.htaccess", "w", encoding="utf-8").write("\n".join(lines) + "\n")
print("netlify:", sum(1 for x in out if x and not x.startswith("#")), "reglas · apache:", sum(1 for x in lines if x.startswith("RewriteRule")))
