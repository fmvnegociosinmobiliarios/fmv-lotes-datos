# -*- coding: utf-8 -*-
"""
actualizar_mercado.py — Actualiza mercado.json (parámetros de mercado del informe de lote) una vez por mes.

    python3 actualizar_mercado.py --tasador data/mercado.json --lotes relevamiento_lotes.json [--mesh 1650] [--salida mercado.json]

Entradas:
  --tasador  JSON del relevamiento del Tasador M2 (repo fmv-web, data/mercado.json). Se usa para "usado_m2"
             (USD/m² de departamentos usados por barrio). El script busca por barrio una clave que contenga
             "venta" o "usd" y un valor plausible (300–9000). Si no encuentra, deja el valor anterior y lo marca.
  --lotes    JSON del relevamiento de a estrenar y terrenos (ver RELEVAMIENTO_LOTES.md):
             {"fecha": "2026-11-01", "barrios": {"Belgrano": {"estrenar": {"n": 38, "p25": 3100, "p50": 3400, "p75": 3900},
                                                              "lotes": {"n": 6, "lote_m2": [2200, 3100, 4800], "inc_vendible": [480, 590, 760]}}}}
  --mesh     costo directo MESH del mes (USD/m², obra terminada estándar-alta). Si falta, se mantiene el anterior.
UVA y dólar MEP se bajan solos (argentinadatos.com y dolarapi.com); si fallan, se mantienen.

Reglas: muestra chica (< 8 avisos a estrenar, < 3 lotes) => no se toca ese barrio y se anota en "pendientes".
Un salto mayor al 25 % respecto del mes anterior se aplica igual pero queda marcado en "alertas" para revisión.
Siempre escribe un resumen en actualizacion_resumen.md.
"""
import json, sys, os, datetime, argparse, urllib.request, unicodedata, re

HERE = os.path.dirname(os.path.abspath(__file__))

def norm(s): return re.sub(r"\s+", " ", unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().upper()).strip()

def fetch_json(url, timeout=25):
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "fmv-lotes/1.0"}), timeout=timeout) as r: return json.loads(r.read().decode())

def uva_mep():
    out = {}
    try:
        serie = fetch_json("https://api.argentinadatos.com/v1/finanzas/indices/uva/")
        hoy = datetime.date.today().isoformat(); vals = [x for x in serie if x["fecha"] <= hoy]
        out["UVA"] = float(vals[-1]["valor"]); out["UVA_fecha"] = vals[-1]["fecha"]
    except Exception as e: out["UVA_error"] = str(e)
    try:
        d = fetch_json("https://dolarapi.com/v1/dolares/bolsa"); out["MEP"] = round((float(d["compra"]) + float(d["venta"])) / 2, 2); out["MEP_fecha"] = d["fechaActualizacion"][:10]
    except Exception as e: out["MEP_error"] = str(e)
    return out

def buscar_usado(tasador, barrio):
    """Devuelve USD/m² de departamento usado para el barrio dentro del JSON del tasador (estructura flexible)."""
    nb = norm(barrio)
    def walk(o, ctx):
        if isinstance(o, dict):
            for k, v in o.items():
                yield from walk(v, ctx + [str(k)])
        elif isinstance(o, list):
            for i, v in enumerate(o): yield from walk(v, ctx + [str(i)])
        else: yield ctx, o
    cands = []
    for ctx, v in walk(tasador, []):
        c = " ".join(norm(x) for x in ctx)
        if nb in c and isinstance(v, (int, float)) and 300 <= v <= 9000 and ("VENTA" in c or "USD" in c) and "ALQ" not in c:
            peso = 2 if ("DEPTO" in c or "DEPARTAMENTO" in c or "2" in c.split()) else 1
            cands.append((peso, float(v), c))
    if not cands: return None, None
    med = sorted(x[1] for x in cands)[len(cands) // 2]
    cands.sort(key=lambda t: (-t[0], abs(t[1] - med)))
    return cands[0][1], cands[0][2]

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--tasador"); ap.add_argument("--lotes"); ap.add_argument("--mesh", type=float); ap.add_argument("--salida", default=os.path.join(HERE, "mercado.json")); ap.add_argument("--base", default=os.path.join(HERE, "mercado.json"))
    a = ap.parse_args()
    M = json.load(open(a.base, encoding="utf-8")); prev = json.loads(json.dumps(M))
    hoy = datetime.date.today().isoformat(); resumen = [f"# Actualización de mercado.json — {hoy}", ""]; alertas = []; pendientes = []; cambios = []
    # 1. índices
    ix = uva_mep()
    for k in ("UVA", "MEP"):
        if k in ix:
            cambios.append(f"{k}: {M['global'][k]} → {ix[k]} ({ix[k + '_fecha']})"); M["global"][k] = ix[k]
        else: pendientes.append(f"{k} no se pudo bajar ({ix.get(k + '_error')}); se mantiene {M['global'][k]}")
    if a.mesh:
        M["global"]["mesh_usd_m2"] = a.mesh; cambios.append(f"MESH: {a.mesh} USD/m²")
        # costo directo: estándar = 0,80 × MESH, alto = 0,95 × MESH, premium = 1,17 × MESH, con piso por zona (nunca menos que el 92 % del anterior)
        for b, v in list(M["barrios"].items()) + [("default", M["default"])]:
            nuevo = [round(a.mesh * f / 10) * 10 for f in (0.80, 0.95, 1.17)]
            viejo = v["costo_directo"]; v["costo_directo"] = [max(n, round(o * 0.92)) for n, o in zip(nuevo, viejo)]
    # 2. usados desde el tasador
    if a.tasador and os.path.exists(a.tasador):
        T = json.load(open(a.tasador, encoding="utf-8")); n_ok = 0
        for b, v in M["barrios"].items():
            u, ctx = buscar_usado(T, b)
            if u is None: pendientes.append(f"{b}: usado no encontrado en el tasador, se mantiene {v['usado_m2']}"); continue
            lo, hi = round(u * 0.85, -1), round(u * 1.10, -1)
            if abs(lo / v["usado_m2"][0] - 1) > 0.25: alertas.append(f"{b}: usado salta {v['usado_m2']} → [{lo}, {hi}] (fuente {ctx})")
            v["usado_m2"] = [lo, hi]; n_ok += 1
        cambios.append(f"Usados actualizados desde el tasador en {n_ok} barrios")
    else: pendientes.append("Sin JSON del tasador: usados sin cambio")
    # 3. a estrenar y lotes
    if a.lotes and os.path.exists(a.lotes):
        L = json.load(open(a.lotes, encoding="utf-8")); n_e = n_l = 0
        for b, v in M["barrios"].items():
            d = next((x for k, x in L.get("barrios", {}).items() if norm(k) == norm(b)), None)
            if not d: pendientes.append(f"{b}: sin relevamiento de a estrenar/lotes, se mantiene"); continue
            e = d.get("estrenar") or {}
            if e.get("n", 0) >= 8 and e.get("p50"):
                p50 = e["p50"]; nuevo = [round(p50 * 0.93, -1), round(p50 * 1.02, -1), round(p50 * 1.15, -1)]  # estándar / alto / premium sobre la mediana de publicación
                if abs(nuevo[0] / v["precio_venta"][0] - 1) > 0.25: alertas.append(f"{b}: a estrenar salta {v['precio_venta']} → {nuevo} (n={e['n']})")
                v["precio_venta"] = nuevo; v["precio_local_pb"] = [round(x * 1.12, -1) for x in nuevo]; n_e += 1
            else: pendientes.append(f"{b}: a estrenar muestra chica (n={e.get('n', 0)}), se mantiene")
            l = d.get("lotes") or {}
            if l.get("n", 0) >= 3 and l.get("lote_m2"):
                if abs(l["lote_m2"][1] / v["lote_m2"][1] - 1) > 0.25: alertas.append(f"{b}: lote salta {v['lote_m2']} → {l['lote_m2']} (n={l['n']})")
                v["lote_m2"] = [round(x, -1) for x in l["lote_m2"]]
                if l.get("inc_vendible"): v["inc_vendible"] = [round(x, -1) for x in l["inc_vendible"]]
                n_l += 1
            else: pendientes.append(f"{b}: lotes muestra chica (n={l.get('n', 0)}), se mantiene")
        cambios.append(f"A estrenar actualizados en {n_e} barrios; lotes en {n_l} barrios")
    else: pendientes.append("Sin relevamiento de lotes/a estrenar: precios de venta y lotes sin cambio")
    M["fecha_mercado"] = hoy; M["_historial"] = (M.get("_historial") or [])[-11:] + [dict(fecha=hoy, cambios=cambios, alertas=len(alertas), pendientes=len(pendientes))]
    json.dump(M, open(a.salida, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    resumen += ["## Cambios", *[f"- {c}" for c in cambios], "", "## Alertas (saltos > 25 %, revisar)", *([f"- {x}" for x in alertas] or ["- ninguna"]), "", "## Pendientes (sin dato suficiente, se mantuvo el valor anterior)", *([f"- {x}" for x in pendientes] or ["- ninguno"])]
    open(os.path.join(os.path.dirname(os.path.abspath(a.salida)), "actualizacion_resumen.md"), "w", encoding="utf-8").write("\n".join(resumen))
    print("\n".join(resumen))
    return 0

if __name__ == "__main__": sys.exit(main())
