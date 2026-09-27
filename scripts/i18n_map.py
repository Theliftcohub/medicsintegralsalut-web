#!/usr/bin/env python3
"""Reconstruye migracion/i18n-map.json desde los hreflang del HTML (TranslatePress, sin SQL).
Agrupa por la URL x-default/es de cada página; marca grupos incompletos."""
import json, sys
from urllib.parse import urlparse
inv = json.load(open("migracion/inventory.json"))
groups, incompletos = {}, []
norm = lambda l: l.split("-")[0].lower()
for it in inv["items"]:
    hm = (it.get("seo") or {}).get("hreflang_map") or {}
    if not hm or it.get("status") != 200:
        continue
    m = {norm(l): urlparse(u).path for l, u in hm.items() if l != "x-default"}
    key = m.get("es") or urlparse(hm.get("x-default", it["url"])).path
    g = groups.setdefault(key, {})
    for l, p in m.items():
        g.setdefault(l, p)
todos = {"es", "ca", "en", "fr", "ru", "uk"}
for k, g in groups.items():
    falta = todos - set(g)
    if falta:
        incompletos.append({"grupo": k, "faltan": sorted(falta)})
out = {f"g{i:04d}": g for i, (k, g) in enumerate(sorted(groups.items()))}
json.dump(out, open("migracion/i18n-map.json", "w"), ensure_ascii=False, indent=1)
json.dump(incompletos, open("migracion/i18n-incompletos.json", "w"), ensure_ascii=False, indent=1)
print(f"{len(out)} grupos de traducción · {len(incompletos)} incompletos")
