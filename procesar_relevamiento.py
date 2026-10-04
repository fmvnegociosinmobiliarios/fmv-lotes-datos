# -*- coding: utf-8 -*-
"""procesar_relevamiento.py — Convierte el volcado del relevamiento de Zonaprop (window.__fmv) en
relevamiento_lotes.json y lotes_avisos.csv para actualizar_mercado.py y ranking_lotes.py.
    python3 procesar_relevamiento.py fmv_dump.json relevamientos/AAAA-MM/"""
import json, csv, sys, os, datetime, statistics as st
src, outd = sys.argv[1], sys.argv[2]; os.makedirs(outd, exist_ok=True)
D = json.load(open(src, encoding="utf-8")); hoy = datetime.date.today().isoformat()
def q(v, p):
    v = sorted(v); k = (len(v) - 1) * p; f = int(k); c = min(f + 1, len(v) - 1); return round(v[f] + (v[c] - v[f]) * (k - f))
R = {"fecha": hoy, "fuente": "Zonaprop (terrenos y departamentos hasta 5 años), m² totales", "barrios": {}}; rows = []; seen = set()
for b, L in D["lotes"].items():
    val = []; inc = []
    for a in L:
        if not a.get("url") or a["url"] in seen: continue
        seen.add(a["url"]); sup, usd = a.get("sup"), a.get("usd")
        if not sup or not usd or sup < 80 or sup > 2000 or usd / sup < 150 or usd / sup > 15000: continue
        val.append(usd / sup)
        if a.get("vend") and a["vend"] > 200 and 150 < usd / a["vend"] < 3000: inc.append(usd / a["vend"])
        rows.append(dict(barrio=b, direccion=(a.get("addr") or "").strip(), sup_m2=sup, precio_usd=usd, usd_m2_lote=round(usd / sup), vendibles_m2=a.get("vend") or "", usd_m2_vendible=round(usd / a["vend"]) if a.get("vend") else "", altura_declarada=a.get("alt") or "", portal="zonaprop", url="https://www.zonaprop.com.ar" + a["url"], fecha=hoy))
    E = [x["usd"] / x["sup"] for x in D["estrenar"].get(b, []) if x.get("usd") and x.get("sup") and 800 <= x["usd"] / x["sup"] <= 12000]
    R["barrios"][b] = {"estrenar": {"n": len(E), **({"p25": q(E, .25), "p50": q(E, .5), "p75": q(E, .75)} if len(E) >= 3 else {})},
                       "lotes": {"n": len(val), **({"lote_m2": [q(val, .25), q(val, .5), q(val, .75)]} if len(val) >= 3 else {}), **({"inc_vendible": [q(inc, .25), q(inc, .5), q(inc, .75)]} if len(inc) >= 3 else {})}}
json.dump(R, open(os.path.join(outd, "relevamiento_lotes.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
with open(os.path.join(outd, "lotes_avisos.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
for b, v in R["barrios"].items(): print(f"{b:18s} lotes n={v['lotes']['n']:3d} {v['lotes'].get('lote_m2', '-')}  inc={v['lotes'].get('inc_vendible', '-')}  estrenar n={v['estrenar']['n']:2d} p50={v['estrenar'].get('p50', '-')}")
print(len(rows), "avisos de lotes")
