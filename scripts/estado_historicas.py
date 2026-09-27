#!/usr/bin/env python3
"""Consulta el estado ACTUAL de las URLs históricas del contrato (sin seguir redirecciones)
y resuelve el destino final, para heredar las 301 que ya hace WordPress."""
import csv, json, time, urllib.request, urllib.error, sys, os
from urllib.parse import urljoin, quote, unquote
B = "https://www.medicsintegralsalut.com"
class NoRedir(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k): return None
op = urllib.request.build_opener(NoRedir)
def head(u):
    for i in range(4):
        try:
            r = op.open(urllib.request.Request(u, method="GET", headers={"User-Agent": "Mozilla/5.0 (TheLiftCo migration audit)"}), timeout=30)
            return r.status, None
        except urllib.error.HTTPError as e:
            return e.code, e.headers.get("Location")
        except Exception:
            time.sleep(3 * (i + 1))
    return 0, None
out = json.load(open("migracion/historicas_estado.json")) if os.path.exists("migracion/historicas_estado.json") else {}
rows = [r for r in csv.DictReader(open("migracion/urls.csv", encoding="utf-8")) if r["tipo"] == "historica"]
for n, r in enumerate(rows, 1):
    p = r["url"]
    if p in out: continue
    u = B + quote(unquote(p), safe="/%:@-._~!$&'()*+,;=")
    chain, st, loc = [], *head(u)
    cur = u
    while st in (301, 302, 307, 308) and loc and len(chain) < 6:
        cur = urljoin(cur, loc); chain.append((st, cur)); time.sleep(0.4)
        st, loc = head(cur)
    out[p] = {"status_inicial": chain[0][0] if chain else st, "final": cur if chain else None, "status_final": st, "saltos": len(chain)}
    if n % 25 == 0:
        json.dump(out, open("migracion/historicas_estado.json", "w"), ensure_ascii=False, indent=1); print(n, flush=True)
    time.sleep(0.5)
json.dump(out, open("migracion/historicas_estado.json", "w"), ensure_ascii=False, indent=1)
print("fin", len(out))
