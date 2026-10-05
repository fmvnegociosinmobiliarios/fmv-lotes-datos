# -*- coding: utf-8 -*-
"""
informe_fmv.py — Plantilla negro y dorado del Informe de factibilidad y tasación de lotes (FMV Soluciones Inmobiliarias).

    python3 informe_fmv.py modelo.json [textos.json] [salida.pdf]

modelo.json: salida de motor_fmv.py.  textos.json (opcional): textos y datos que el redactor quiere imponer:
  numero, fecha, cliente, titulo, subtitulo, resumen, entorno, veredicto, normativa_nota, mercado_nota, comps_fuente,
  conclusiones (lista de párrafos), recomendacion, uso_nota, ocupacion, cub_exist, tipo_actual, comprador, pasos (lista de [titulo, texto]).
"""
import json, sys, os, datetime, qrcode
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (BaseDocTemplate, PageTemplate, Frame, Paragraph, Table, TableStyle, Spacer, PageBreak, Image, KeepTogether, NextPageTemplate, Flowable)
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

HERE = os.path.dirname(os.path.abspath(__file__))
for cand in ["/usr/share/fonts/truetype/dejavu", HERE, os.path.join(HERE, "fonts")]:
    if os.path.exists(os.path.join(cand, "DejaVuSans.ttf")):
        pdfmetrics.registerFont(TTFont("DV", os.path.join(cand, "DejaVuSans.ttf"))); pdfmetrics.registerFont(TTFont("DVB", os.path.join(cand, "DejaVuSans-Bold.ttf")))
        pdfmetrics.registerFont(TTFont("DVI", os.path.join(cand, "DejaVuSans-Oblique.ttf"))); break
from reportlab.pdfbase.pdfmetrics import registerFontFamily
registerFontFamily("DV", normal="DV", bold="DVB", italic="DVI", boldItalic="DVB")

W, H = A4
BLACK = colors.HexColor("#0b0b0c"); INK = colors.HexColor("#141416"); GOLD = colors.HexColor("#c9a227"); GOLD2 = colors.HexColor("#e6c766"); GOLD_D = colors.HexColor("#8f7119")
PAPER = colors.HexColor("#f7f5f0"); GREY = colors.HexColor("#6b6b6b"); LINE = colors.HexColor("#d9d4c7"); TEXT = colors.HexColor("#1a1a1a"); CREAM = colors.HexColor("#efe9d8"); SOFT = colors.HexColor("#f1ede3")
FIRMA = "Fernando M. Veiga"; CARGO = "Corredor Inmobiliario y Martillero Público · CUCICBA 9981"; EMPRESA = "FMV SOLUCIONES INMOBILIARIAS"
TEL = "+54 9 11 6851-1494"; MAIL = "info@fmvbrokers.com.ar"; WEB = "fmvbrokers.com.ar"; WA = "https://wa.me/5491168511494?text=Hola%20Fernando,%20le%C3%AD%20el%20informe%20de%20factibilidad"
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]

def fmt(x, d=0):
    s = f"{x:,.{d}f}"; return s.replace(",", "X").replace(".", ",").replace("X", ".")
def usd(x, r=None):
    if r: x = round(x, r)
    return "USD " + fmt(x)
def usdk(x):  # redondeado a miles
    return "USD " + fmt(round(x, -3))
def rango(a, b, r=-3): return f"{usd(a, r)} – {usd(b, r)}"
def fecha_larga(d): return f"{d.day} de {MESES[d.month - 1]} de {d.year}"

B = ParagraphStyle("B", fontName="DV", fontSize=9.4, leading=13.6, textColor=TEXT, spaceAfter=5, alignment=4)
BL = ParagraphStyle("BL", parent=B, alignment=0)
SM = ParagraphStyle("SM", parent=B, fontSize=7.3, leading=9.6, textColor=GREY, spaceAfter=4)
H1 = ParagraphStyle("H1", fontName="DVB", fontSize=17, leading=21, textColor=TEXT, spaceBefore=6, spaceAfter=8, keepWithNext=True)
H2 = ParagraphStyle("H2", fontName="DVB", fontSize=11.2, leading=14, textColor=GOLD_D, spaceBefore=8, spaceAfter=4, keepWithNext=True)
TC = ParagraphStyle("TC", fontName="DV", fontSize=8.1, leading=10.2, textColor=TEXT)
TCB = ParagraphStyle("TCB", parent=TC, fontName="DVB")
TCH = ParagraphStyle("TCH", parent=TC, fontName="DVB", textColor=GOLD)

def P(t, st=B): return Paragraph(t, st)

class Titulo(Flowable):
    """Número dorado + título + línea corta."""
    def __init__(self, num, txt):
        Flowable.__init__(self); self.num, self.txt = num, txt; self.height = 15 * mm; self.width = W - 40 * mm
    def wrap(self, aw, ah): return self.width, self.height
    def draw(self):
        c = self.canv; c.setFillColor(GOLD); c.setFont("DV", 9); c.drawString(0, 6 * mm, self.num)
        c.setFillColor(TEXT); c.setFont("DVB", 17); c.drawString(8 * mm, 6 * mm, self.txt)
        c.setStrokeColor(GOLD); c.setLineWidth(1); c.line(0, 2 * mm, 28 * mm, 2 * mm)

def titulo(num, txt): return KeepTogether([Spacer(1, 4), Titulo(num, txt)])

def tabla(rows, widths, header=True, zebra=True, bold_rows=(), gold_rows=(), align_right_from=1, size=8.1):
    data = [[(Paragraph(str(c), TCH if (header and i == 0) else (TCB if i in bold_rows else TC)) if not isinstance(c, Flowable) else c) for c in r] for i, r in enumerate(rows)]
    t = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    st = [("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 3.2), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.2), ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
          ("LINEBELOW", (0, 0), (-1, -1), 0.3, LINE)]
    if header: st += [("BACKGROUND", (0, 0), (-1, 0), BLACK), ("LINEBELOW", (0, 0), (-1, 0), 0.6, GOLD)]
    if zebra: st += [("BACKGROUND", (0, i), (-1, i), SOFT) for i in range(1 if header else 0, len(rows)) if i % 2 == 0]
    for i in gold_rows: st += [("BACKGROUND", (0, i), (-1, i), CREAM), ("LINEBELOW", (0, i), (-1, i), 0.8, GOLD)]
    t.setStyle(TableStyle(st)); return t

class KPIs(Flowable):
    def __init__(self, items, h=26 * mm):
        Flowable.__init__(self); self.items = items; self.h = h; self.width = W - 40 * mm
    def wrap(self, aw, ah): return self.width, self.h + 3 * mm
    def draw(self):
        c = self.canv; n = len(self.items); tw = (self.width - 3 * mm * (n - 1)) / n
        for i, (l, v, note) in enumerate(self.items):
            x = i * (tw + 3 * mm); y0 = 1.5 * mm
            c.setFillColor(BLACK); c.roundRect(x, y0, tw, self.h, 2 * mm, fill=1, stroke=0); c.setFillColor(GOLD); c.rect(x, y0, 1.2 * mm, self.h, fill=1, stroke=0)
            c.setFillColor(colors.HexColor("#bdbdbd")); c.setFont("DV", 6.2); c.drawString(x + 4 * mm, y0 + self.h - 6 * mm, l.upper())
            fs = 12.5
            while fs > 7 and pdfmetrics.stringWidth(v, "DVB", fs) > tw - 7 * mm: fs -= 0.5
            c.setFillColor(GOLD2); c.setFont("DVB", fs); c.drawString(x + 4 * mm, y0 + self.h - 14.5 * mm, v)
            ns = 6.3
            while ns > 4.5 and pdfmetrics.stringWidth(note, "DV", ns) > tw - 7 * mm: ns -= 0.25
            c.setFillColor(colors.HexColor("#9a9a9a")); c.setFont("DV", ns); c.drawString(x + 4 * mm, y0 + self.h - 21 * mm, note)

class Caja(Flowable):
    """Caja crema con barra dorada (veredicto / nota destacada)."""
    def __init__(self, texto, titulo=None):
        Flowable.__init__(self); self.p = Paragraph((f"<b><font color='#8f7119'>{titulo}</font></b><br/>" if titulo else "") + texto, ParagraphStyle("v", parent=B, fontSize=9.1, leading=13, spaceAfter=0)); self.width = W - 40 * mm
    def wrap(self, aw, ah):
        _, h = self.p.wrap(self.width - 12 * mm, ah); self.h = h + 8 * mm; return self.width, self.h + 2 * mm
    def draw(self):
        c = self.canv; c.setFillColor(CREAM); c.roundRect(0, 1 * mm, self.width, self.h, 2 * mm, fill=1, stroke=0); c.setFillColor(GOLD); c.rect(0, 1 * mm, 1.5 * mm, self.h, fill=1, stroke=0)
        self.p.drawOn(c, 7 * mm, 1 * mm + 4 * mm)

# ----------------------------------------------------------------------------- portada / contratapa
def hacer_qr(path):
    qr = qrcode.QRCode(box_size=10, border=1); qr.add_data(WA); qr.make(); qr.make_image(fill_color="#c9a227", back_color="#0b0b0c").convert("RGB").save(path)

def contacto(c, x, y, w, h, big=False):
    c.setFillColor(colors.HexColor("#1c1c1f")); c.roundRect(x, y, w, h, 3 * mm, fill=1, stroke=0); c.setStrokeColor(GOLD); c.setLineWidth(0.6); c.roundRect(x, y, w, h, 3 * mm, fill=0, stroke=1)
    q = h - 6 * mm; c.drawImage(ImageReader(contacto.qr), x + w - q - 3 * mm, y + 3 * mm, width=q, height=q)
    c.setFillColor(colors.white); c.setFont("DVB", 16 if big else 12.5); c.drawString(x + 7 * mm, y + h - (12 if big else 9) * mm, FIRMA)
    c.setFillColor(GOLD); c.setFont("DV", 9.5 if big else 8.5); c.drawString(x + 7 * mm, y + h - (19 if big else 14.5) * mm, CARGO)
    c.setFillColor(colors.HexColor("#d6d6d6")); c.setFont("DV", 10 if big else 9)
    if big:
        c.drawString(x + 7 * mm, y + h - 30 * mm, "WhatsApp  " + TEL); c.drawString(x + 7 * mm, y + h - 36.5 * mm, MAIL); c.drawString(x + 7 * mm, y + h - 43 * mm, WEB)
    else:
        c.drawString(x + 7 * mm, y + h - 21.5 * mm, "WhatsApp " + TEL); c.drawString(x + 7 * mm, y + h - 26.5 * mm, MAIL + "   ·   " + WEB)
    c.setFillColor(GREY); c.setFont("DV", 6.5); c.drawRightString(x + w - q - 5 * mm, y + 4 * mm, "Escaneá para escribirme por WhatsApp")

def marca(c, dark=True):
    c.setStrokeColor(GOLD); c.setLineWidth(0.8); c.line(22 * mm, H - 22 * mm, W - 22 * mm, H - 22 * mm)
    c.setFillColor(GOLD); c.setFont("DVB", 10); c.drawString(22 * mm, H - 18 * mm, "FMV"); c.setFont("DV", 8.5); c.setFillColor(GOLD2); c.drawString(33 * mm, H - 18 * mm, "SOLUCIONES INMOBILIARIAS")

def portada(c, doc):
    R, T = doc.R, doc.T; c.saveState()
    c.setFillColor(BLACK); c.rect(0, 0, W, H, fill=1, stroke=0); c.setFillColor(INK); c.rect(0, 0, W, H * 0.46, fill=1, stroke=0)
    try:
        from PIL import Image as PILImage
        im = PILImage.open(R["mapas"]["oro"]); ar = im.height / im.width; mw = W * 0.36; mh = min(mw * ar, H * 0.21); mw = mh / ar
        c.drawImage(ImageReader(R["mapas"]["oro"]), W - 22 * mm - mw, H * 0.475, width=mw, height=mh, mask=None)
    except Exception: pass
    marca(c); c.setFont("DV", 7.5); c.setFillColor(GREY); c.drawRightString(W - 22 * mm, H - 18 * mm, f"{T['tipo_informe'].upper()} · N° {T['numero']}")
    c.setFillColor(colors.white); c.setFont("DV", 12); c.drawString(22 * mm, H * 0.80, T["tipo_informe"].upper())
    y = H * 0.80 - 14 * mm; c.setFont("DVB", 30 if len(T["titulo"]) < 20 else 24)
    for line in T["titulo_lineas"]: c.drawString(22 * mm, y, line); y -= 12.5 * mm
    c.setFillColor(GOLD); c.setFont("DV", 10.5); c.drawString(22 * mm, y - 1 * mm, T["subtitulo"])
    c.setStrokeColor(GOLD); c.setLineWidth(1.2); c.line(22 * mm, y - 7 * mm, 60 * mm, y - 7 * mm)
    kp = T["kpis_portada"]; xw = (W - 44 * mm) / 2; y0 = H * 0.40
    for i, (l, v) in enumerate(kp):
        x = 22 * mm + (i % 2) * xw; yy = y0 - (i // 2) * 24 * mm
        c.setFillColor(GREY); c.setFont("DV", 7.5); c.drawString(x, yy, l.upper())
        fs = 15
        while fs > 8 and pdfmetrics.stringWidth(v, "DVB", fs) > xw - 12 * mm: fs -= 0.5
        c.setFillColor(GOLD2); c.setFont("DVB", fs); c.drawString(x, yy - 7 * mm, v)
        c.setStrokeColor(GOLD_D); c.setLineWidth(0.4); c.line(x, yy - 10 * mm, x + xw - 10 * mm, yy - 10 * mm)
    contacto(c, 22 * mm, 20 * mm, W - 44 * mm, 34 * mm)
    fs = 6.8
    while fs > 5 and pdfmetrics.stringWidth(T["pie_portada"], "DV", fs) > W - 44 * mm: fs -= 0.2
    c.setFillColor(GREY); c.setFont("DV", fs); c.drawString(22 * mm, 12 * mm, T["pie_portada"]); c.restoreState()

def cuerpo(c, doc):
    T = doc.T; c.saveState()
    c.setFillColor(PAPER); c.rect(0, 0, W, H, fill=1, stroke=0); c.setFillColor(BLACK); c.rect(0, H - 16 * mm, W, 16 * mm, fill=1, stroke=0)
    c.setFillColor(GOLD); c.setFont("DVB", 8); c.drawString(20 * mm, H - 10 * mm, "FMV  ·  " + T["tipo_informe"].upper())
    c.setFillColor(colors.HexColor("#cfcfcf")); c.setFont("DV", 8); c.drawRightString(W - 20 * mm, H - 10 * mm, T["cabecera"])
    c.setStrokeColor(GOLD); c.setLineWidth(0.5); c.line(20 * mm, 16 * mm, W - 20 * mm, 16 * mm)
    c.setFillColor(GREY); c.setFont("DV", 7); c.drawString(20 * mm, 11 * mm, f"{FIRMA} · {CARGO} · WhatsApp {TEL}"); c.drawRightString(W - 20 * mm, 11 * mm, str(doc.page)); c.restoreState()

def contratapa(c, doc):
    T = doc.T; c.saveState(); c.setFillColor(BLACK); c.rect(0, 0, W, H, fill=1, stroke=0); marca(c)
    c.setFillColor(colors.white); c.setFont("DVB", 26); c.drawString(22 * mm, H * 0.74, "Próximos pasos")
    c.setStrokeColor(GOLD); c.setLineWidth(1.2); c.line(22 * mm, H * 0.74 - 6 * mm, 50 * mm, H * 0.74 - 6 * mm)
    yy = H * 0.74 - 18 * mm
    for i, (t1, t2) in enumerate(T["pasos"]):
        c.setFillColor(GOLD); c.setFont("DVB", 16); c.drawString(22 * mm, yy, f"{i + 1:02d}")
        c.setFillColor(colors.white); c.setFont("DVB", 11); c.drawString(36 * mm, yy + 1 * mm, t1)
        c.setFillColor(colors.HexColor("#bdbdbd")); c.setFont("DV", 8.8)
        p = Paragraph(t2, ParagraphStyle("s", fontName="DV", fontSize=8.8, leading=11.5, textColor=colors.HexColor("#bdbdbd"))); _, h = p.wrap(W - 60 * mm, 40 * mm); p.drawOn(c, 36 * mm, yy - 1.5 * mm - h)
        yy -= 11 * mm + h
    contacto(c, 22 * mm, 40 * mm, W - 44 * mm, 52 * mm, big=True)
    c.setFillColor(GREY); c.setFont("DV", 6.8)
    p = Paragraph(T["descargo"], ParagraphStyle("d", fontName="DV", fontSize=6.8, leading=9, textColor=GREY)); _, h = p.wrap(W - 44 * mm, 30 * mm); p.drawOn(c, 22 * mm, 34 * mm - h)
    c.restoreState()

# ----------------------------------------------------------------------------- textos por defecto
def preparar_textos(R, T):
    N, g, m, E = R["normativa"], R["geometria"], R["modelo"], R["modelo"]["esc"]["Estándar"]
    T = dict(T or {}); hoy = datetime.date.today(); T.setdefault("fecha", fecha_larga(hoy)); T.setdefault("fecha_corta", f"{MESES[hoy.month - 1].capitalize()} {hoy.year}")
    T.setdefault("numero", hoy.strftime("%Y-%m%d")); T.setdefault("fecha_mercado", R["mercado"].get("fecha_mercado") or R["global_"].get("fecha_mercado") or T["fecha"])
    viable = R["viable"]; T.setdefault("viable", viable)
    T.setdefault("tipo_informe", "Informe de factibilidad" if viable else "Informe de factibilidad y tasación")
    T.setdefault("titulo", R["direccion"]); tl = T["titulo"]
    T.setdefault("titulo_lineas", [tl] if len(tl) < 22 else [tl.split(" esq. ")[0], "esq. " + tl.split(" esq. ")[1]] if " esq. " in tl else [tl[:tl.rfind(" ", 0, 24)], tl[tl.rfind(" ", 0, 24) + 1:]])
    T.setdefault("subtitulo", f"{R['barrio']} · Comuna {R['comuna']} · Ciudad Autónoma de Buenos Aires")
    T.setdefault("cabecera", f"{tl} · {R['barrio']} · {T['fecha_corta']}")
    T.setdefault("cliente", "Documento para el propietario")
    T.setdefault("pie_portada", f"Emitido el {T['fecha']} · Código Urbanístico vigente · Datos abiertos GCBA · Mercado relevado el {T['fecha_mercado']} · {T['cliente']}")
    cap = f"PB + {N['n_tipo']}" + (f" + {N['retiros']} retiro{'s' if N['retiros'] > 1 else ''}" if N["retiros"] else "") + f" · {N['unidad'].split(' – ')[0]}"
    T.setdefault("retiros_txt", (f"{N['retiros']} retiros admitidos; en este lote el segundo queda por debajo de 25 m² útiles y se proyecta como terraza / SUM" if N["retiros"] > m["retiros_utiles"] else f"{N['retiros']} retiro{'s' if N['retiros'] > 1 else ''} útil{'es' if N['retiros'] > 1 else ''}") if N["retiros"] else "sin retiros")
    if viable:
        T.setdefault("kpis_portada", [("Metros vendibles", f"{fmt(m['vend_cub'])} m²"), ("Valor estimado del lote", rango(m["precio_real"]["piso"], m["precio_real"]["techo"], -4)), ("Capacidad", cap), ("Plazo del negocio", f"{E['plazo']} meses")])
    else:
        u = R["uso_actual"]
        T.setdefault("kpis_portada", [("Tasación estimada (uso actual)", rango(u["rango"][0], u["rango"][1], -4)), ("Si estuviera ocupado", rango(u["rango_ocupado"][0], u["rango_ocupado"][1], -4)), ("Capacidad constructiva", f"{fmt(m['vend_cub'])} m² vendibles · {cap.split(' · ')[1]}"), ("Residual para desarrollador", usdk(E["terreno_residual"]) if E["terreno_residual"] > 0 else "negativo")])
    T.setdefault("pasos", [("Reunión", "Repasamos juntos el informe y definimos la estrategia: venta, permuta o mixta." if viable else "Repasamos juntos el informe y definimos la estrategia de venta y el precio de salida."),
                           ("Verificaciones", "Informe de dominio, situación del inmueble" + (", liquidación preliminar de plusvalía" if viable and m["plusv_usd"] > 0 else "") + " y medición de la superficie cubierta."),
                           ("Salida al mercado", "Presentación directa a desarrolladoras seleccionadas, sin publicar hasta que lo decidas." if viable else "Publicación en portales y presentación directa a los compradores naturales del inmueble."),
                           ("Negociación y cierre", "Acompañamiento hasta la escritura, con respaldo legal y técnico.")])
    T.setdefault("descargo", "Evaluación preliminar de factibilidad con fines de tasación y comercialización. No sustituye el anteproyecto de un profesional matriculado, la consulta catastral, el informe de dominio ni la liquidación oficial de plusvalía. Precios de mercado de publicación, variables mes a mes. Valores expresados en dólares estadounidenses billete.")
    return T

# ----------------------------------------------------------------------------- cuerpo del informe
def construir(R, T, out):
    N, g, m, esc, E, A, Pm = R["normativa"], R["geometria"], R["modelo"], R["modelo"]["esc"], R["modelo"]["esc"]["Estándar"], R["modelo"]["esc"]["Alto"], R["modelo"]["esc"]["Premium"]
    viable = T["viable"]; u = R["uso_actual"]; eng = R["englobamiento"]; M = R["mercado"]; GL = R["global_"]
    qrp = os.path.join(os.path.dirname(os.path.abspath(out)), "qr_wa.png"); hacer_qr(qrp); contacto.qr = qrp
    doc = BaseDocTemplate(out, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=24 * mm, bottomMargin=22 * mm, title=f"{T['tipo_informe']} – {T['titulo']}", author=EMPRESA)
    doc.R, doc.T = R, T
    fr = Frame(20 * mm, 22 * mm, W - 40 * mm, H - 46 * mm, id="f", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates([PageTemplate(id="portada", frames=[fr], onPage=portada), PageTemplate(id="cuerpo", frames=[fr], onPage=cuerpo), PageTemplate(id="contra", frames=[fr], onPage=contratapa)])
    S = [NextPageTemplate("cuerpo"), PageBreak()]
    unidad_corta = N["unidad"].split(" – ")[0]; dirs = " / ".join(R["direcciones"])
    frentes_txt = " y ".join(f"{fmt(fr_['largo'], 1)} m sobre {fr_['calle']}" for fr_ in g["frentes"]) if g["frentes"] else f"{fmt(g['frente'], 1)} m"
    usos = sorted({(r["tipo1"] or "").capitalize() + (" · " + r["tipo2"].lower() if r.get("tipo2") else "") + (f" · {r['pisos']} planta{'s' if int(r['pisos'] or 1) > 1 else ''}" if r.get("pisos") else "") for r in R["rus"]})
    uso_txt = T.get("uso_actual_txt") or ("; ".join(usos) if usos else "sin relevar")
    pisos_act = u["pisos"]
    # ---- 01 resumen
    S.append(titulo("01", "Resumen ejecutivo"))
    resumen = T.get("resumen") or (f"<b>{dirs}</b> es una parcela {'de esquina ' if g['esquina'] else 'entre medianeras '}de <b>{fmt(g['sup'])} m²</b> ({frentes_txt}; fondo {fmt(g['fondo'], 1)} m) en {R['barrio']}, "
                                   f"hoy ocupada por {uso_txt.lower()}. Bajo el Código Urbanístico está en <b>{N['unidad']}</b>: {N['nota'][0].lower() + N['nota'][1:]} "
                                   + ("Está catalogada o dentro de un Área de Protección Histórica, lo que condiciona cualquier demolición. " if (N["catalogado"] or N["aph"]) else "Sin catalogación ni protección patrimonial. ")
                                   + ("La parcela figura en el área de riesgo hídrico del Código, lo que exige retardo pluvial y suma plazo de aprobación. " if N["riesgo_hidrico"] else "")
                                   + (f"La huella edificable dentro de la Línea de Frente Interno es de <b>{fmt(g['huella'])} m²</b>" + (f" (quedan {fmt(g['fuera_lfi'])} m² de fondo sólo para planta baja)" if g["fuera_lfi"] > 5 else "") + "."))
    S.append(P(resumen))
    if viable:
        S.append(KPIs([("Metros vendibles", f"{fmt(m['vend_cub'])} m²", f"+ {fmt(m['exp_total'])} m² de expansiones"), ("Valor del lote", rango(m['precio_real']['piso'], m['precio_real']['techo'], -4).replace("USD ", "", 1).replace(" – USD", " –"), "residual con margen 22 % a 15 %"),
                       ("Margen a valor de mercado", f"{E['margen_lote_pub'] * 100:.0f} %", "nivel estándar, lote a precio de publicación"), ("Plazo total", f"{E['plazo']} meses", f"{E['plazo_aprob']} aprobación + {E['plazo_obra']} obra + 6 venta")]))
        ver_t = "VEREDICTO · NEGOCIO VIABLE" if E["margen_lote_pub"] >= 0.15 else "VEREDICTO · NEGOCIO AJUSTADO"
        ver = T.get("veredicto") or (f"A los precios a estrenar que absorbe {R['barrio']} el proyecto estándar deja un margen del <b>{E['margen_lote_pub'] * 100:.0f} %</b> pagando el lote al valor de publicación "
                                     f"({usdk(m['vml_pub'])}), y el valor residual del terreno ({usdk(E['terreno_residual'])}) {'supera' if E['terreno_residual'] > m['vml_pub'] else 'queda por debajo de'} lo que pide el mercado. "
                                     f"Precio real de cierre esperable: <b>{rango(m['precio_real']['piso'], m['precio_real']['techo'], -4)}</b>, con publicación sugerida en {usd(m['precio_real']['techo'] * 1.05, -4)} "
                                     f"o permuta por el {E['permuta_pct'] * 100:.0f} % de los metros vendibles.")
    else:
        S.append(KPIs([("Tasación estimada", rango(u['rango'][0], u['rango'][1], -4).replace("USD ", "", 1).replace(" – USD", " –"), "valor por su uso actual · no confirmada"), ("Si tuviera ocupantes", rango(u['rango_ocupado'][0], u['rango_ocupado'][1], -4).replace("USD ", "", 1).replace(" – USD", " –"), "descuento del 35-40 % por posesión"),
                       ("Valor como lote", rango(u['rango_lote'][0], u['rango_lote'][1], -4).replace("USD ", "", 1).replace(" – USD", " –"), f"USD {u['lote_m2'][0]}-{u['lote_m2'][1]}/m² · referencias del barrio"), ("Capacidad constructiva", f"{fmt(m['vend_cub'])} m² vend.", f"{fmt(m['cub_total'])} m² cubiertos · {unidad_corta}")]))
        ver_t = "VEREDICTO · VALE MÁS POR SU USO QUE COMO LOTE"
        ver = T.get("veredicto") or (f"La capacidad constructiva ({unidad_corta}, {fmt(m['vend_cub'])} m² vendibles) y los precios a estrenar de la zona ({usd(M['precio_venta'][0])} a {usd(M['precio_venta'][2])} por m²) dejan un valor residual "
                                     f"{'negativo' if E['terreno_residual'] <= 0 else 'de sólo ' + usdk(E['terreno_residual'])} para un desarrollador con margen del 22 %. Ningún desarrollador va a pagar por este lote más de lo que vale por su uso actual. "
                                     f"Por eso la tasación se apoya en el uso: <b>{rango(u['rango'][0], u['rango'][1], -4)}</b> libre de ocupantes, con publicación sugerida en {usd(u['rango'][1] * 1.08, -4)}. "
                                     + (f"El comprador natural es {T['comprador']}. " if T.get("comprador") else "") + "Es una estimación de gabinete sobre datos oficiales y de mercado; para confirmarla hacen falta la visita, la medición de la superficie cubierta, el estado constructivo, el título y la situación de ocupación.")
    S.append(Spacer(1, 4)); S.append(Caja(ver, ver_t))
    # ---- 02 ubicación
    S.append(titulo("02", "Ubicación, parcela y entorno"))
    try:
        from PIL import Image as PILImage
        im = PILImage.open(R["mapas"]["manzana"]); ar = im.height / im.width; iw = (W - 40 * mm) * 0.9; ih = iw * ar
        if ih > 95 * mm: ih = 95 * mm; iw = ih / ar
        S.append(Image(R["mapas"]["manzana"], width=iw, height=ih))
    except Exception: pass
    S.append(P("Fuente: elaboración propia sobre la capa de parcelas (Catastro GCBA, jul-2026) y el Relevamiento de Usos del Suelo 2022-2024 (pisos existentes por parcela). La huella edificable se dibuja a la distancia de la Línea de Frente Interno (25 % del ancho de manzana).", SM))
    aph_txt = ("Sí · " + "; ".join(f"{a.get('denominacion') or a.get('direccion') or ''} ({a.get('proteccion') or a.get('catalogacion') or ''}, {a.get('estado') or ''})" for a in R["aph"] if "DESESTIM" not in ((a.get("estado") or "") + (a.get("proteccion") or "")).upper())[:2]) if N["aph"] else ("No" + (" (hubo una propuesta de catalogación desestimada)" if R["aph"] else ""))
    obras_txt = "; ".join(f"{o['fecha'][:10]} · {o['descripcio'].capitalize()}" for o in R["obras"][:3]) if R["obras"] else "Ninguna desde 2021"
    datos = [["Dato", "Valor", "Fuente"], ["Nomenclatura catastral (SMP)", R["smp"], "Catastro GCBA"], ["Partida matriz", f"{R['partida']}", "Catastro GCBA"],
             ["Superficie de parcela (geometría catastral)", f"{fmt(g['sup'], 1)} m²" + (f" · ochava {fmt(g['ochava_area'], 1)} m²" if g["ochava_area"] else ""), "Parcelas GCBA / cálculo"],
             ["Frente / fondo", f"{frentes_txt} · fondo {fmt(g['fondo'], 1)} m" + (" · esquina" if g["esquina"] else ""), "Geometría de parcela"],
             ["Manzana", f"{R['sm']} · {(N['tipo_mza'] or '').lower()} · ancho {fmt(g['ancho_mz'])} m entre líneas oficiales · {R['manzana_resumen']['parcelas']} parcelas", "Catastro + Código Urbanístico"],
             ["Área de Protección Histórica / catalogación", aph_txt + " · " + ("Catalogada" if N["catalogado"] else "No catalogada"), "CU + capa APH GCBA"],
             ["Riesgo hídrico · LEP · ensanche · rivolta", f"{'Sí' if N['riesgo_hidrico'] else 'No'} · {'Sí' if N['lep'] else 'No'} · {'Sí' if N['ensanche'] else 'No'} · {'Sí' if N['rivolta'] else 'No'}", "Código Urbanístico GCBA"],
             ["Área de Desarrollo Prioritario Sur", "Sí" if N["adps"] else "No", "Código Urbanístico GCBA"], ["Uso actual relevado", uso_txt, "RUS 2022-2024"],
             ["Obras registradas en la parcela", obras_txt, "Obras registradas DGROC"],
             ["Manzana: obras registradas desde 2021", f"{R['manzana_resumen']['obras_recientes']} expedientes · altura máxima existente {R['manzana_resumen']['pisos_max']} pisos · promedio {R['manzana_resumen']['pisos_prom']:.1f}", "DGROC + RUS"]]
    S.append(tabla(datos, [52 * mm, 86 * mm, 32 * mm]))
    if g["linderos"]:
        S.append(P("Linderos", H2))
        rows = [["Parcela", "Dirección", "Sup.", "Pisos", "Uso relevado", "Situación (art. 6.4.2.3 / 6.5.5)"]]
        for l in g["linderos"]:
            sit = ("Catalogado" if l.get("catalogado") else "Consolidado (fachada ≥ 75 % de su unidad)") if l.get("consolidado") else ("Edificio: no englobable" if l["edificio"] else ("Lindero de fondo" if l["de_fondo"] else "Englobable en principio"))
            if l.get("supera_unidad"): sit += " · supera la altura de la unidad: completamiento de tejido posible"
            rows.append([l["smp"], l["direccion"], f"{fmt(l['area'])} m²", str(l["pisos"]), l["uso"].replace("/", " · ").title()[:48], sit])
        S.append(tabla(rows, [24 * mm, 42 * mm, 17 * mm, 12 * mm, 45 * mm, 30 * mm]))
    S.append(P(T.get("entorno") or f"<b>Lectura del entorno.</b> La manzana tiene {R['manzana_resumen']['parcelas']} parcelas con una altura promedio de {R['manzana_resumen']['pisos_prom']:.1f} pisos y un máximo de {R['manzana_resumen']['pisos_max']}; "
               f"{'hay ' + str(R['manzana_resumen']['obras_recientes']) + ' expedientes de obra registrados desde 2021, señal de que el tejido está en renovación' if R['manzana_resumen']['obras_recientes'] else 'no hay obras registradas desde 2021 en la manzana'}. "
               + ("Los linderos con edificios en altura ya consolidaron la medianera, lo que simplifica el proyecto pero elimina la opción de englobar por ese lado. " if any(l["edificio"] for l in g["linderos"]) else "")))
    # ---- 03 normativa
    S.append(titulo("03", "Encuadre normativo"))
    c3 = {c["tipo"]: c for c in N["cur3d"]}
    vol = " · ".join(f"{c['tipo']} {fmt(c['h_ini'], 1)}–{fmt(c['h_fin'], 1)} m" for c in N["cur3d"]) or "sin volumetría oficial publicada"
    norm = [["Concepto", "Código de Planeamiento (derogado)", "Código Urbanístico (vigente, norma 31/12/2024)"],
            ["Distrito / unidad", N.get("dist_cpu") or "–", N["unidad"]], ["Altura (art. " + N.get("art", "6.2") + ")", f"Según FOT {fmt(N['fot_cpu'], 2) if N['fot_cpu'] else '–'} y altura de distrito", f"{fmt(N['cuerpo'], 1)} m de altura máxima (PB + {N['n_tipo']})" + (f" · {N['retiros']} retiros habitables (2 m y 4 m desde la L.O.) hasta el plano límite de {fmt(N['plano'], 1)} m" if N["retiros"] else " · altura máxima = plano límite, sin retiros")],
            ["Volumetría oficial (CUR3D)", "–", vol], ["Capacidad", f"{fmt(m['cap_cpu'])} m² (FOT × superficie)" if m["cap_cpu"] else "–", f"{fmt(m['cub_total'])} m² cubiertos según huella × plantas"],
            ["Mixtura de usos", "–", N["mixtura_txt"]], ["Área edificable (art. 6.4.2 / 6.4.3)", "Centro libre de manzana", f"L.F.I. a {fmt(g['lfi'], 1)} m de la línea oficial (¼ de {fmt(g['ancho_mz'])} m" + ("; banda mínima de 16 m" if g['lfi'] <= 16.05 else "") + f"): huella {fmt(g['huella'])} m² de {fmt(g['sup'])} m²" + (f" · L.I.B. a {fmt(g['lib'], 1)} m (⅓): basamento hasta {fmt(g['huella_lib'])} m²" if N.get("basamento") else f" · L.I.B. a {fmt(g['lib'], 1) } m (⅓) sólo para subsuelos")],
            ["Parcela alcanzada por la L.F.I.", "–", ("Sí: " + fmt(g['fuera_lfi']) + " m² de fondo quedan fuera del área edificable (sólo planta baja / absorbente)") if g.get("alcanzada_lfi") else ("No: toda la parcela es edificable" + ("; al no ser esquina debe dejar espacio urbano de fondo (art. 6.4.2.4) para ventilar el contrafrente" if not g["esquina"] and N["n_tipo"] >= 3 else ""))],
            ["Proximidad a esquina (art. 6.4.2.3)", "–", (f"A {fmt(g['dist_esquina'], 1)} m del vértice de manzana, dentro de ¼ + 9 m: puede corresponder tronera o separación de 3 m del lindero con área descubierta; verificar en la plancheta" if g.get("proxima_esquina") else ("Parcela de esquina: el perfil de la calle mayor se vuelca sobre la menor sólo en la franja de la L.F.I. (art. 6.4.6)" if g["esquina"] else "No aplica"))],
            ["Plusvalía (Ley 6.062)", "No existía", f"Alícuota {N['alicuota'] * 100:.0f} % · incidencia {fmt(N['inc_uva'])} UVA/m² sobre el excedente de FOT {fmt(N['fot_cpu'], 2) if N['fot_cpu'] else 0}"]]
    S.append(tabla(norm, [40 * mm, 55 * mm, 75 * mm]))
    if T.get("normativa_nota"): S.append(P(T["normativa_nota"]))
    S.append(P("Franja edificable y contrafrente", H2))
    fondo_txt = T.get("fondo_nota") or (f"La franja edificable pertenece a la manzana, no a cada lote: todo lo que está a menos de {fmt(g['lfi'], 1)} m de cualquier línea oficial puede construirse a la altura de la unidad. "
                 + (f"El contrafrente de este lote queda a {fmt(g['dist_fondo_banda_opuesta'], 1)} m de la franja edificable de la calle opuesta" + (": ninguna torre de la calle de atrás puede pegarse a la medianera de fondo." if g["dist_fondo_banda_opuesta"] > 3 else ": los lotes de la calle de atrás pueden levantar hasta la altura de la unidad contra la medianera de fondo, y hay que proyectar las vistas hacia el frente o hacia el patio propio.") if g["dist_fondo_banda_opuesta"] is not None else "")
                 + (f" Linderos de fondo: " + "; ".join(f"{l['direccion']} ({l['pisos']} pisos, {l['uso'].lower()})" for l in g["fondo_vecinos"]) + "." if g["fondo_vecinos"] else ""))
    S.append(P(fondo_txt))
    # ---- 04 potencial
    S.append(titulo("04", "Potencial edificable y balance de superficies"))
    rows = [["Nivel", "Plantas", "Cubierto común", "Cubierto vendible", "Expansiones", "Total cubierto", "Vendible total"]]
    for p in m["plantas"]: rows.append([p["nivel"], str(p["n"]), f"{fmt(p['cub_comun'])} m²", f"{fmt(p['cub_vend'])} m²", f"{fmt(p['exp'])} m²", f"{fmt(p['cub_total'])} m²", f"{fmt(p['vend_total'])} m²"])
    rows.append(["Total", str(m["n_plantas"]), f"{fmt(m['comun'])} m²", f"{fmt(m['vend_cub'])} m²", f"{fmt(m['exp_total'])} m²", f"{fmt(m['cub_total'])} m²", f"{fmt(m['vend_cub'])} m²"])
    S.append(tabla(rows, [44 * mm, 15 * mm, 22 * mm, 24 * mm, 21 * mm, 22 * mm, 22 * mm], bold_rows=(len(rows) - 1,), gold_rows=(len(rows) - 1,)))
    S.append(P(f"Hipótesis: edificio {'de esquina' if g['esquina'] else 'entre medianeras'} con {'dos núcleos' if m['comun'] / max(m['n_plantas'], 1) > 40 else 'un núcleo'} de circulación de {fmt(M.get('nucleo_m2', 26))} m² por planta, planta baja con {fmt(m['plantas'][0]['cub_comun'])} m² de comunes (hall, medidores, bicicletero), "
               f"expansiones del 16 % de la huella en plantas tipo (se valúan al 50 %), retiros de 2 m y 4 m desde {'ambas líneas oficiales' if g['esquina'] else 'la línea oficial'} (art. 6.3.1)" + (f" y ochava de {fmt(g['ochava_area'], 1)} m²" if g["ochava_area"] else "") +
               f". Retiros: {T['retiros_txt']}. Eficiencia vendible/cubierto: <b>{m['eficiencia'] * 100:.0f} %</b>. Vendible ponderado (expansiones al 50 %): <b>{fmt(m['vend_pond'])} m²</b>. El balance es una aproximación de gabinete; el anteproyecto de un profesional matriculado puede variar ± 5 %.", SM))
    # ---- 05 plusvalía
    S.append(titulo("05", "Contribución por plusvalía urbana (Ley 6.062)"))
    if m["plusv_usd"] > 0:
        rows = [["Criterio", "Superficie adicional", "UVA", "USD (UVA " + fmt(m["UVA"], 2) + " · MEP " + fmt(m["MEP"], 2) + ")"],
                ["Ley 6.062: superficie sobre rasante sin balcones − 20 % − FOT del CPU", f"{fmt(m['adicional'])} m²", fmt(m["plusv_uva"]), usd(m["plusv_usd"])],
                ["Sin la deducción del 20 % (techo prudente)", f"{fmt(m['adicional_vend'])} m²", fmt(m["plusv_usd_v"] * m["MEP"] / m["UVA"]), usd(m["plusv_usd_v"])]]
        S.append(tabla(rows, [72 * mm, 32 * mm, 26 * mm, 40 * mm], gold_rows=(1,)))
        S.append(P(f"Fórmula: (m² construibles − FOT del código anterior {fmt(N['fot_cpu'], 2)} × {fmt(g['sup'])} m²) × {fmt(N['inc_uva'])} UVA/m² × {N['alicuota'] * 100:.0f} %. La base imponible es la superficie total sobre rasante (sin balcones ni construcciones sobre el plano límite) menos el 20 %, menos lo que admitía el Código de Planeamiento (A1 − A2), por el valor de incidencia en UVA y la alícuota del polígono. La paga quien registra los planos, antes del permiso de obra; el modelo la carga íntegra como costo. Sin la deducción del 20 % el monto subiría a {usdk(m['plusv_usd_v'])}."))
    else:
        S.append(P("No hay excedente respecto de la capacidad del código anterior" + (f" (FOT {fmt(N['fot_cpu'], 2)})" if N["fot_cpu"] else "") + ": el proyecto no paga contribución por plusvalía."))
    # ---- 06 mercado
    S.append(titulo("06", "Mercado: precios de venta, costos y valor del suelo"))
    rows = [["Variable", "Estándar", "Alto", "Premium"], ["Precio de venta a estrenar (USD/m²)", *[usd(x) for x in M["precio_venta"]]], ["Local / planta baja (USD/m²)", *[usd(x) for x in M["precio_local_pb"]]],
            ["Costo directo de obra (USD/m² cubierto)", *[usd(x) for x in M["costo_directo"]]], ["Plazo de obra (meses)", *[str(esc[k]["plazo_obra"]) for k in ("Estándar", "Alto", "Premium")]]]
    S.append(tabla(rows, [70 * mm, 33 * mm, 33 * mm, 34 * mm]))
    S.append(P(T.get("mercado_nota") or f"Precios de publicación relevados el {T['fecha_mercado']} para unidades a estrenar en {R['barrio']}; costo directo según índice MESH (jul-2026: USD 1.629/m² para obra terminada de calidad estándar-alta) ajustado por nivel. "
               f"Indirectos: proyecto y dirección 8 %, derechos y tasas 2,5 %, imprevistos 5 % sobre costo directo; comercialización 4 %, publicidad 1,5 % y legales 2 % sobre ventas. Demolición USD {GL['demolicion_usd_m2']}/m² existente" + (f"; retardo pluvial {usd(GL['retardo_pluvial_usd'])}" if N["riesgo_hidrico"] else "") + ".", SM))
    if m["comps"]:
        S.append(P("Lotes comparables en oferta", H2))
        rows = [["Lote", "Sup.", "Precio pedido", "m² vendibles", "USD/m² lote", "USD/m² vendible"]]
        for c in m["comps"]: rows.append([c["nombre"], f"{fmt(c['sup'])} m²", usd(c["precio"]), fmt(c["vendibles"]) if c.get("vendibles") else "–", usd(c["precio"] / c["sup"]) if c.get("sup") else "–", usd(c["precio"] / c["vendibles"]) if c.get("vendibles") else "–"])
        rows.append(["Mediana", "", "", "", usd(m["vml"]["lote_m2_med"]), usd(m["vml"]["inc_vend_med"])])
        S.append(tabla(rows, [62 * mm, 18 * mm, 28 * mm, 22 * mm, 20 * mm, 20 * mm], bold_rows=(len(rows) - 1,), gold_rows=(len(rows) - 1,)))
        S.append(P(T.get("comps_fuente") or f"Fuente: Zonaprop / Argenprop, relevado el {T['fecha_mercado']}. Precios pedidos, no de cierre.", SM))
    S.append(P(f"<b>Valor de mercado del lote (publicación):</b> por incidencia sobre vendible {usd(m['vml']['inc_vend_med'])}/m² × {fmt(m['vend_cub'])} m² = {usdk(m['vml']['por_vendible'])}; por m² de lote {usd(m['vml']['lote_m2_med'])}/m² × {fmt(g['sup'])} m² = {usdk(m['vml']['por_m2_lote'])}. "
               f"Promedio: <b>{usdk(m['vml_pub'])}</b> ({m['vml']['fuente']})."))
    # ---- 07 factibilidad
    S.append(titulo("07", "Factibilidad económica por nivel constructivo"))
    K = ("Estándar", "Alto", "Premium")
    rows = [["Concepto", *K], ["Ventas totales", *[usd(esc[k]["ventas"]) for k in K]], ["Costo directo de obra", *[usd(esc[k]["directo"]) for k in K]], ["Indirectos (proyecto, derechos, imprevistos)", *[usd(esc[k]["indirectos"]) for k in K]],
            ["Comercialización, publicidad y legales", *[usd(esc[k]["comercial"]) for k in K]], ["Demolición" + (" + retardo pluvial" if N["riesgo_hidrico"] else "") + (" + otros" if m["extras"] else ""), *[usd(esc[k]["demolicion"] + esc[k]["extras"]) for k in K]],
            ["Plusvalía", *[usd(esc[k]["plusvalia"]) for k in K]], ["Costo total sin terreno", *[usd(esc[k]["costo_sin_terreno"]) for k in K]],
            ["Valor residual del terreno · margen 22 %", *[usd(esc[k]["terreno_residual"]) for k in K]], ["Valor residual del terreno · margen 15 %", *[usd(esc[k]["residual_m15"]) for k in K]],
            ["Punto de equilibrio (lote sin ganancia)", *[usd(esc[k]["breakeven_lote"]) for k in K]], ["Incidencia por m² vendible (margen 22 %)", *[usd(esc[k]["inc_m2_vend"]) for k in K]], ["Valor por m² de lote (margen 22 %)", *[usd(esc[k]["precio_lote_m2"]) for k in K]],
            ["Margen pagando el lote a valor de publicación", *[f"{esc[k]['margen_lote_pub'] * 100:.0f} %" for k in K]], ["Permuta: % de vendibles que paga el lote", *[f"{esc[k]['permuta_pct'] * 100:.0f} %" for k in K]],
            ["Plazo total (aprobación + obra + venta)", *[f"{esc[k]['plazo']} meses" for k in K]]]
    S.append(tabla(rows, [70 * mm, 33 * mm, 33 * mm, 34 * mm], bold_rows=(7, 8), gold_rows=(8,)))
    S.append(P(f"El valor residual es lo máximo que un desarrollador puede pagar por el lote conservando el margen objetivo sobre costos totales. Las unidades premium exigen mayor costo y plazo y no siempre mejoran el residual: la lectura comparada muestra qué nivel maximiza el valor del lote en este terreno "
               f"({max(K, key=lambda k: esc[k]['terreno_residual'])}, {usdk(max(esc[k]['terreno_residual'] for k in K))}).", SM))
    S.append(P("Sensibilidad del valor residual (nivel estándar, margen 22 %)", H2))
    rows = [["Precio venta \\ costo directo", *[usd(c) + "/m²" for c in m["sens_cols"]]]]
    for pv, row in m["sens"]: rows.append([usd(pv) + "/m²", *[usd(v) for v in row]])
    S.append(tabla(rows, [46 * mm, 31 * mm, 31 * mm, 31 * mm, 31 * mm], gold_rows=(2,)))
    S.append(P("Cronograma", H2))
    rows = [["Etapa", "Estándar", "Alto", "Premium", "Qué incluye"], ["Aprobación y demolición", *[f"{esc[k]['plazo_aprob']} meses" for k in K], "Plusvalía, registro de plano, permiso de obra, demolición" + (", retardo pluvial" if N["riesgo_hidrico"] else "") + (", intervención patrimonial" if (N["aph"] or N["catalogado"]) else "")],
            ["Obra", *[f"{esc[k]['plazo_obra']} meses" for k in K], f"Según {fmt(m['cub_total'])} m² cubiertos y nivel de terminación"], ["Comercialización final", "6 meses", "6 meses", "6 meses", "Posventa y escrituras; la preventa corre durante la obra"],
            ["Total", *[f"{esc[k]['plazo']} meses" for k in K], ""]]
    S.append(tabla(rows, [40 * mm, 22 * mm, 22 * mm, 22 * mm, 64 * mm], bold_rows=(4,), gold_rows=(4,)))
    # ---- 08 valor y estrategia
    if viable:
        S.append(titulo("08", "Valor real del lote y estrategia de venta"))
        rows = [["Escenario", "Valor", "Lectura"], ["Piso: residual con margen 22 % (estándar)", usdk(E["terreno_residual"]), "Lo que paga un desarrollador que no cede margen"],
                ["Techo: residual con margen 15 %", usdk(E["residual_m15"]), "Desarrollador con financiamiento propio o estructura de costos ajustada"], ["Valor de publicación (comparables)", usdk(m["vml_pub"]), "Lo que piden lotes similares en oferta hoy"],
                ["Mejor nivel constructivo", f"{max(K, key=lambda k: esc[k]['terreno_residual'])} · {usdk(max(esc[k]['terreno_residual'] for k in K))}", "Residual máximo entre niveles"],
                ["Permuta sugerida", f"{E['permuta_pct'] * 100:.0f} % de los m² vendibles ≈ {fmt(E['permuta_pct'] * m['vend_cub'])} m²", "Equivalente al valor residual, cobrado en unidades terminadas"]]
        S.append(tabla(rows, [62 * mm, 48 * mm, 60 * mm], gold_rows=(1,)))
        S.append(P(T.get("estrategia") or f"<b>Precio real de venta a desarrolladores: {rango(m['precio_real']['piso'], m['precio_real']['techo'], -4)}.</b> Publicación sugerida en {usd(m['precio_real']['techo'] * 1.05, -4)} para dejar margen de negociación. "
                   f"La permuta conviene si el propietario puede esperar {E['plazo']} meses: recibe unidades por un valor nominal mayor, pero asume el riesgo de obra y de precio; exige garantía (hipoteca sobre el lote o fideicomiso con cláusulas de resguardo). "
                   "La venta en efectivo conviene si prioriza liquidez y certeza. Una vía intermedia es la venta con parte de pago en unidades (30-40 %)."))
    # ---- 09 englobamiento
    reco = [o for o in eng["opciones"] if o["recomendado"]]
    S.append(titulo("08" if not viable else "09", "Englobamiento con linderos" if reco else "Englobamiento evaluado y descartado"))
    if eng["opciones"]:
        rows = [["Alternativa", "Superficie", "Huella", "Frente", "Vendibles", "Vend. separadas", "Ganancia", "Residual 22 %"]]
        for o in eng["opciones"][:4]: rows.append(["Con " + " + ".join(c["direccion"] for c in o["con"]), f"{fmt(o['sup'])} m²", f"{fmt(o['huella'])} m²", f"{fmt(o['frente'], 1)} m", f"{fmt(o['vend'])} m²", f"{fmt(o['vend_separadas'])} m²", f"{o['ganancia_pct'] * 100:+.1f} %", usdk(o["residual"])])
        S.append(tabla(rows, [46 * mm, 19 * mm, 17 * mm, 15 * mm, 19 * mm, 22 * mm, 16 * mm, 22 * mm], gold_rows=tuple(i + 1 for i, o in enumerate(eng["opciones"][:4]) if o["recomendado"])))
    if reco:
        o = reco[0]
        S.append(P(T.get("englobe_nota") or f"Englobar con <b>{' + '.join(c['direccion'] for c in o['con'])}</b> ({', '.join(str(c['pisos']) + ' pisos, ' + c['uso'].lower() for c in o['con'])}) rinde un <b>{o['ganancia_pct'] * 100:.0f} %</b> más de metros vendibles que las parcelas por separado "
                   f"({fmt(o['vend'])} contra {fmt(o['vend_separadas'])} m²), porque comparte núcleo y suma frente para los retiros. Es un argumento de valor concreto para el desarrollador y para el vecino: conviene sondear al propietario lindero antes de salir al mercado, sin condicionar la venta a su decisión."))
    else:
        S.append(P(T.get("englobe_nota") or ("Se evaluó el englobamiento con cada lindero apto y " + ("ninguna combinación mejora el rendimiento en más del 10 %: " + "; ".join(f"con {' + '.join(c['direccion'] for c in o['con'])} {o['ganancia_pct'] * 100:+.1f} %" for o in eng["opciones"]) + ". " if eng["opciones"] else "no hay linderos aptos. ")
                   + ("Quedan excluidos " + "; ".join(f"{e['direccion']} ({e['motivo']})" for e in eng["excluidos"]) + ". " if eng["excluidos"] else "") + "El lote se valúa y se vende por sí solo; el englobamiento no se usa como argumento de precio.")))
    # ---- completamiento de tejido
    en = R.get("enrase") or {}
    if en.get("aplica"):
        S.append(P("Completamiento de tejido (art. 6.5.5)", H2))
        rows = [["Escenario", "Vendibles", "Cubiertos", "Residual 22 %", "Plusvalía"], ["Caso base (unidad)", f"{fmt(m['vend_cub'])} m²", f"{fmt(m['cub_total'])} m²", usdk(E["terreno_residual"]), usdk(m["plusv_usd"])],
                [f"Con enrase · caso {en['caso']} · +{en['plantas_extra']} plantas hasta {fmt(en['altura_objetivo'], 1)} m", f"{fmt(en['vend'])} m²", f"{fmt(en['cub'])} m²", usdk(en["residual"]), usdk(en["plusv_usd"])]]
        S.append(tabla(rows, [66 * mm, 24 * mm, 24 * mm, 28 * mm, 28 * mm], gold_rows=(2,)))
        S.append(P(T.get("enrase_nota") or (f"El lindero {' y '.join(x['direccion'] for x in en['linderos'])} es un edificio consolidado que supera el plano límite de la unidad ({', '.join(fmt(x['h_fachada'], 1) + ' m' for x in en['linderos'])}), por lo que el Código admite completar el tejido adosándose a él: "
                   f"+{fmt(en['ganancia_vend'])} m² vendibles. {en['nota']} No se usa como argumento de precio hasta que la consulta esté hecha; es el plus que un desarrollador experimentado va a ver.")))
    elif en.get("linderos") or (en.get("motivo") and any(l.get("supera_unidad") for l in g["linderos"])):
        S.append(P("Completamiento de tejido (art. 6.5.5)", H2)); S.append(P(T.get("enrase_nota") or f"Hay linderos que superan la altura de la unidad, pero {en.get('motivo')}."))
    # ---- 10 uso actual
    S.append(titulo("09" if not viable else "10", "Tasación por su uso actual" + ("" if not viable else " (valor de piso)")))
    rows = [["Concepto", "Mínimo", "Máximo", "Base"], ["Construcción existente (estimada)", f"{fmt(u['cub_exist'])} m²", "", f"{pisos_act} planta{'s' if pisos_act > 1 else ''} · {uso_txt[:50]}"],
            ["Valor por m² cubierto usado", usd(u["usado_m2"][0]), usd(u["usado_m2"][1]), f"Usados en {R['barrio']} (USD {u['usado_m2_bruto'][0]}–{u['usado_m2_bruto'][1]}) con {100 - u['factor_estado'] * 100:.0f} % de descuento por estado"], ["Valor por uso actual", usdk(u["rango_uso"][0]), usdk(u["rango_uso"][1]), "m² × valor usado"],
            ["Valor como lote (referencias del barrio)", usdk(u["rango_lote"][0]), usdk(u["rango_lote"][1]), f"USD {u['lote_m2'][0]}–{u['lote_m2'][1]}/m² de lote"], ["Tasación estimada libre de ocupantes", usdk(u["rango"][0]), usdk(u["rango"][1]), "mayor valor entre uso y lote"],
            ["Con ocupantes o inquilinos", usdk(u["rango_ocupado"][0]), usdk(u["rango_ocupado"][1]), "descuento del 35-40 %"]]
    S.append(tabla(rows, [58 * mm, 30 * mm, 30 * mm, 52 * mm], bold_rows=(5,), gold_rows=(5,)))
    S.append(P(T.get("uso_nota") or ("Este es el valor de piso del inmueble: lo que vale aunque ningún desarrollador lo compre. " if viable else "") + "La superficie cubierta existente se estima a partir de los pisos relevados y la huella; hay que confirmarla con la medición, el estado constructivo, el título y la situación de ocupación, que no fueron relevados.", SM))
    # ---- conclusiones
    S.append(titulo("10" if not viable else "11", "Conclusiones y recomendación comercial"))
    concl = T.get("conclusiones") or ([f"<b>Capacidad.</b> {N['unidad']}: {fmt(m['cub_total'])} m² cubiertos y {fmt(m['vend_cub'])} m² vendibles sobre una huella de {fmt(g['huella'])} m², en PB + {N['n_tipo']}" + (f" + {N['retiros']} retiro{'s' if N['retiros'] > 1 else ''} ({T['retiros_txt']})" if N["retiros"] else "") + ".",
                                       (f"<b>Valor.</b> Precio real de cierre {rango(m['precio_real']['piso'], m['precio_real']['techo'], -4)}; publicación sugerida {usd(m['precio_real']['techo'] * 1.05, -4)}; permuta por el {E['permuta_pct'] * 100:.0f} % de los vendibles." if viable else
                                        f"<b>Valor.</b> El desarrollo no cierra a los precios de la zona; tasación estimada por uso actual {rango(u['rango'][0], u['rango'][1], -4)} libre de ocupantes, publicación sugerida {usd(u['rango'][1] * 1.08, -4)}."),
                                       f"<b>Plusvalía.</b> {usdk(m['plusv_usd']) + ' con el criterio conservador; conviene liquidarla antes de negociar porque el comprador la descuenta del precio.' if m['plusv_usd'] > 0 else 'No aplica.'}",
                                       f"<b>Englobamiento.</b> {'Recomendado con ' + ' + '.join(c['direccion'] for c in reco[0]['con']) + ' (+%.0f %% de vendibles).' % (reco[0]['ganancia_pct'] * 100) if reco else 'Evaluado y descartado: no mejora el rendimiento en más del 10 %.'}",
                                       f"<b>Plazos.</b> {E['plazo_aprob']} meses de aprobación" + (" (riesgo hídrico y plusvalía suman tiempo)" if N["riesgo_hidrico"] else "") + f", {E['plazo_obra']} a {Pm['plazo_obra']} meses de obra según nivel, y 6 de comercialización final."])
    for t in concl: S.append(P(t))
    if T.get("recomendacion"): S.append(Caja(T["recomendacion"], "RECOMENDACIÓN"))
    # ---- fuentes
    S.append(titulo("11" if not viable else "12", "Fuentes, supuestos y alcance"))
    S.append(P("Datos abiertos del Gobierno de la Ciudad de Buenos Aires (data.buenosaires.gob.ar): parcelas catastrales (jul-2026), Código Urbanístico por parcela (norma al 31/12/2024, jun-2026), Relevamiento de Usos del Suelo 2022-2024, obras registradas DGROC (jul-2026), Áreas de Protección Histórica (jun-2026) y volumetría CUR3D (nov-2024). "
               f"Precios de mercado: publicaciones en portales inmobiliarios relevadas el {T['fecha_mercado']}. Costo de obra: índice MESH. UVA {fmt(m['UVA'], 2)} y dólar MEP {fmt(m['MEP'], 2)} a la fecha del relevamiento.", SM))
    S.append(P("Supuestos del modelo: núcleo de circulación de 26 m² por planta (22 m² en lotes chicos), expansiones del 16 % de la huella valuadas al 50 %, retiros de 2 m y 4 m desde la línea oficial, margen objetivo del 22 % sobre costos (15 % como techo), demolición USD 70/m², plusvalía liquidada sobre superficie cubierta total. "
               "La huella edificable se calcula con la Línea de Frente Interno al 25 % del ancho de manzana; en manzanas atípicas la plancheta oficial puede fijar otra franja.", SM))
    S.append(P("Régimen impositivo de la venta para personas humanas no habitualistas (verificado): el Impuesto a la Transferencia de Inmuebles fue derogado por la Ley 27.743 (2024) y el impuesto cedular del 15 % fue eliminado por el art. 192 de la Ley de Modernización Laboral (vigente desde el 1-ene-2026); subsiste el impuesto de sellos de la Ciudad (3,6 %, en general a cargo de ambas partes por mitades). Confirmar con el escribano según la situación particular.", SM))
    S.append(P("Alcance: evaluación preliminar con fines de tasación y comercialización, elaborada sobre información pública y de mercado sin visita al inmueble. No sustituye el anteproyecto de un profesional matriculado, la consulta catastral, el informe de dominio ni la liquidación oficial de plusvalía.", SM))
    S.append(NextPageTemplate("contra")); S.append(PageBreak()); S.append(Spacer(1, 1))
    # títulos pegados al primer elemento que sigue (evita títulos huérfanos al pie de página)
    S2 = []; i = 0
    while i < len(S):
        if isinstance(S[i], KeepTogether) and i + 1 < len(S) and not isinstance(S[i + 1], (PageBreak, NextPageTemplate)): S2.append(KeepTogether(S[i]._content + [S[i + 1]])); i += 2
        else: S2.append(S[i]); i += 1
    doc.build(S2)
    return out

def generar(modelo_json, textos_json=None, out=None):
    R = json.load(open(modelo_json, encoding="utf-8")); T = json.load(open(textos_json, encoding="utf-8")) if textos_json and os.path.exists(textos_json) else {}
    T = preparar_textos(R, T)
    out = out or f"Informe_{'factibilidad' if T['viable'] else 'tasacion'}_{R['direccion'].replace(' ', '_').replace('/', '-')}.pdf"
    return construir(R, T, out)

if __name__ == "__main__":
    a = sys.argv[1:]
    print(generar(a[0], a[1] if len(a) > 1 else None, a[2] if len(a) > 2 else None))
