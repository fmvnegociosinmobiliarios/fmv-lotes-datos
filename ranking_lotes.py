# -*- coding: utf-8 -*-
"""ranking_lotes.py — Ranking de lotes publicados por debajo de la referencia del barrio (mercado.json).
    python3 ranking_lotes.py relevamientos/AAAA-MM/lotes_avisos.csv [--n 25]"""
import csv, json, os, sys, argparse, unicodedata, re
HERE = os.path.dirname(os.path.abspath(__file__))
def norm(s): return re.sub(r"\s+", " ", unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().upper()).strip()
def f(x):
    try: return float(str(x).replace(".", "").replace(",", ".")) if "," in str(x) else float(x)
    except Exception: return None
ap = argparse.ArgumentParser(); ap.add_argument("csv"); ap.add_argument("--n", type=int, default=25); a = ap.parse_args()
M = json.load(open(os.path.join(HERE, "mercado.json"), encoding="utf-8")); ref = {norm(k): v for k, v in M["barrios"].items()}
rows = list(csv.DictReader(open(a.csv, encoding="utf-8"))); out = []; out_v = []; dudosos = []
for r in rows:
    b = ref.get(norm(r.get("barrio", ""))) or M["default"]; sup, pr = f(r.get("sup_m2")), f(r.get("precio_usd"))
    if not sup or not pr or sup < 80 or sup > 2000: continue
    usd_lote = pr / sup; dif = usd_lote / b["lote_m2"][1] - 1
    if dif < -0.6: dudosos.append((dif, r, usd_lote)); continue   # más de 60 % abajo: casi siempre m² o precio mal cargados
    out.append((dif, r, usd_lote))
    vend = f(r.get("vendibles_m2"))
    if vend and vend > 200:
        inc = pr / vend
        if inc < b["inc_vendible"][0]: out_v.append((inc / b["inc_vendible"][1] - 1, r, inc))
out.sort(key=lambda t: t[0]); out_v.sort(key=lambda t: t[0])
mes = os.path.basename(os.path.dirname(os.path.abspath(a.csv)))
L = [f"# Ranking de lotes — {mes}", "", f"Avisos válidos: {len(out)} de {len(rows)}. Referencia: USD/m² de lote mediana del barrio en mercado.json ({M['fecha_mercado']}).", "",
     "## Lotes publicados por debajo de la referencia del barrio", "", "| # | Barrio | Dirección | Sup. | Precio | USD/m² lote | Ref. barrio | Dif. | Link |", "|---|---|---|---|---|---|---|---|---|"]
for i, (dif, r, u) in enumerate(out[:a.n], 1):
    b = ref.get(norm(r.get("barrio", ""))) or M["default"]
    L.append(f"| {i} | {r.get('barrio')} | {r.get('direccion')} | {f(r.get('sup_m2')):.0f} m² | USD {f(r.get('precio_usd')):,.0f} | {u:,.0f} | {b['lote_m2'][1]:,} | {dif * 100:+.0f} % | {r.get('url')} |")
L += ["", "## Con m² vendibles publicados e incidencia por debajo del mínimo del barrio", "", "| Barrio | Dirección | Vendibles | Precio | USD/m² vendible | Mín. barrio | Link |", "|---|---|---|---|---|---|---|"]
for dif, r, inc in out_v[:a.n]:
    b = ref.get(norm(r.get("barrio", ""))) or M["default"]
    L.append(f"| {r.get('barrio')} | {r.get('direccion')} | {f(r.get('vendibles_m2')):.0f} m² | USD {f(r.get('precio_usd')):,.0f} | {inc:,.0f} | {b['inc_vendible'][0]:,} | {r.get('url')} |")
L += ["", f"Descartados por dato dudoso (más de 60 % bajo la referencia, casi siempre superficie o precio mal cargados): {len(dudosos)}; los 5 más llamativos por si vale la pena mirarlos: " + "; ".join(f"{r.get('barrio')} {r.get('direccion')} ({f(r.get('sup_m2')):.0f} m², USD {f(r.get('precio_usd')):,.0f})" for _, r, _ in sorted(dudosos, key=lambda t: t[0])[:5]) + ".",
      "", "Son candidatos para pedir un informe de lote; el precio pedido puede esconder problemas (ocupación, catalogación, manzana atípica, sucesión)."]
p = os.path.join(os.path.dirname(os.path.abspath(a.csv)), "ranking_lotes.md"); open(p, "w", encoding="utf-8").write("\n".join(L)); print(p); print("\n".join(L[:12]))
