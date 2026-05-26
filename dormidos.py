"""
Detector de clientes dormidos de Maleu + generador de drafts personalizados.

Categorias:
  - TIBIO   (21-45 dias): cliente activo perdiendo ritmo
  - FRIO    (45-90 dias): perdiendolo
  - MUY FRIO (90-180 dias): riesgo de perdida total

Excluye:
  - Clientes con 1 sola compra historica si fue hace >60 dias (probaron y no volvieron)
  - Clientes con ultima compra < 21 dias (activos)
  - Clientes con ultima compra > 180 dias (perdidos definitivamente)

NO manda WhatsApp. Solo arma la lista + drafts para que Tadeo elija.

Uso:
  python dormidos.py [--out FILE.md] [--json]
"""
import sys, os, io, argparse, json
try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")
except Exception: pass

from pathlib import Path
from datetime import datetime, date, timedelta, timezone
from collections import defaultdict

import gspread
from google.oauth2.service_account import Credentials

SHEET_ID = "1ILXCc9ddbC_gJPNoUADBiSMXAWLM9v73ov2_xXb8YsY"

def find_creds():
    for c in [
        Path(__file__).parent / "creds" / "service-account.json",
        Path(r"C:\Users\tadeu\maleu-service-account.json"),
        Path(os.environ.get("MALEU_SA_KEY", "")),
    ]:
        if c and c.exists(): return str(c)
    raise FileNotFoundError("service-account.json no encontrado")

def now_ar():
    return datetime.now(timezone(timedelta(hours=-3)))

def parse_fecha(s):
    if s is None or s == "": return None
    if isinstance(s, (int, float)):
        try: return (datetime(1899,12,30)+timedelta(days=int(s))).date()
        except: return None
    s = str(s).strip()
    for f in ("%d/%m/%Y","%Y-%m-%d","%d/%m/%y"):
        try: return datetime.strptime(s,f).date()
        except: continue
    return None

def parse_num(v):
    if v is None or v == "": return 0.0
    if isinstance(v,(int,float)): return float(v)
    s = str(v).replace("$","").replace(" ","").strip()
    if "," in s and "." in s: s = s.replace(".","").replace(",",".")
    elif "," in s: s = s.replace(",",".")
    elif s.count(".") > 1: s = s.replace(".","")
    try: return float(s)
    except: return 0.0

def fmt_money(n):
    return f"${n:,.0f}".replace(",",".")

def normalize_tel(t):
    if not t: return ""
    s = "".join(ch for ch in str(t) if ch.isdigit())
    if not s: return ""
    if s.startswith("549"): return s
    if s.startswith("54"): return "549" + s[2:]
    if s.startswith("9"): return "54" + s
    if len(s) >= 10: return "549" + s[-10:]
    return s

def normalize_nombre(n):
    return " ".join(str(n).strip().lower().split())

# Excluir familia Tadeo (no se manda WhatsApp a si mismo ni a su flia)
EXCLUIR_TEL = {
    "5491136887500",  # Tadeo / Rodrigo
    "5491136887405",  # Alejandra Basualdo
    "5491144377405",  # Iñaki
}
EXCLUIR_NOMBRE_KEYS = {
    "tadeo ustariz",
    "rodrigo ustariz",
    "alejandra basualdo",
    "alejandra ustariz",
    "iñaki ustariz",
    "inaki ustariz",
}

def cargar_hoja(sh, nombre, layout):
    ws = sh.worksheet(nombre)
    rows = ws.get(f"A1:CA{ws.row_count}", value_render_option="UNFORMATTED_VALUE")
    if not rows: return [], {}
    headers = [str(h) for h in rows[0]]
    idx = {h: i for i, h in enumerate(headers)}
    return rows[1:], idx

def get(row, idx, key, default=""):
    i = idx.get(key)
    if i is None or i >= len(row): return default
    v = row[i]
    return default if v is None else v

# Layouts por canal: (nombre_col_tel, nombre_col_barrio_o_club)
LAYOUTS = {
    "Home":   {"tel": "Teléfono", "barrio": "Barrio", "subbarrio": "Sub Barrio"},
    "Pilar":  {"tel": "Teléfono", "barrio": "Barrio Privado / Dirección", "subbarrio": None},
    "Clubes": {"tel": "Teléfono", "barrio": "Club", "subbarrio": None},
}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", help="Path para guardar el MD")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--min-dias", type=int, default=21)
    parser.add_argument("--max-dias", type=int, default=180)
    args = parser.parse_args()

    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_file(find_creds(), scopes=scopes)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(SHEET_ID)

    hoy = now_ar().date()
    hoy_dt = datetime.combine(hoy, datetime.min.time())

    # Agregar por cliente único (por teléfono normalizado, fallback nombre)
    clientes = {}   # key -> dict
    productos_por_cliente = {}  # key -> {abrev: total_unidades}

    # Cargar Productos catalog para nombres
    ws_prod = sh.worksheet("Productos")
    prod_rows = ws_prod.get(f"A1:Z{ws_prod.row_count}", value_render_option="UNFORMATTED_VALUE")
    prod_catalog = {}
    for r in prod_rows[1:]:
        if len(r) >= 3:
            abr = str(r[2]).strip()
            nom = str(r[1]).strip()
            if abr: prod_catalog[abr] = nom

    for canal, layout in LAYOUTS.items():
        rows, idx = cargar_hoja(sh, canal, layout)
        # Detectar columnas de productos: cualquier header con abreviatura conocida
        prod_cols = {abr: idx[abr] for abr in prod_catalog if abr in idx}
        if not rows: continue
        for r in rows:
            f = parse_fecha(get(r, idx, "Fecha"))
            if not f: continue
            estado = str(get(r, idx, "Estado de Entrega")).strip().lower()
            if estado != "entregado": continue
            nombre = str(get(r, idx, "Cliente")).strip()
            tel_raw = get(r, idx, layout["tel"])
            tel = normalize_tel(tel_raw)
            facturado = parse_num(get(r, idx, "Facturado"))
            barrio = str(get(r, idx, layout["barrio"])).strip() if layout.get("barrio") else ""
            sub = str(get(r, idx, layout["subbarrio"])).strip() if layout.get("subbarrio") else ""

            if not nombre and not tel: continue
            key = tel if tel else "N:" + normalize_nombre(nombre)

            if key not in clientes:
                clientes[key] = {
                    "nombre": nombre,
                    "tel": tel or "",
                    "tel_raw": str(tel_raw or ""),
                    "barrio": barrio,
                    "subbarrio": sub,
                    "canal": canal,
                    "pedidos": 0,
                    "facturado": 0,
                    "primera": f,
                    "ultima": f,
                    "fechas": [],
                }
                productos_por_cliente[key] = defaultdict(int)
            c = clientes[key]
            c["pedidos"] += 1
            c["facturado"] += facturado
            c["fechas"].append(f)
            if f < c["primera"]: c["primera"] = f
            if f > c["ultima"]:
                c["ultima"] = f
                if barrio: c["barrio"] = barrio
                if sub: c["subbarrio"] = sub
            for abr, col_idx in prod_cols.items():
                if col_idx < len(r):
                    cant = parse_num(r[col_idx])
                    if cant > 0: productos_por_cliente[key][abr] += cant

    # Filtrar dormidos
    dormidos = []
    for key, c in clientes.items():
        # Excluir familia Tadeo
        if c["tel"] in EXCLUIR_TEL: continue
        if normalize_nombre(c["nombre"]) in EXCLUIR_NOMBRE_KEYS: continue

        dias_desde = (hoy - c["ultima"]).days
        if dias_desde < args.min_dias: continue
        if dias_desde > args.max_dias: continue
        # Excluir clientes con 1 sola compra si fue hace >60 dias
        if c["pedidos"] == 1 and dias_desde > 60: continue

        # Top productos
        prods = sorted(productos_por_cliente[key].items(), key=lambda x: -x[1])[:3]
        prods_nom = [(prod_catalog.get(abr, abr), int(q)) for abr, q in prods]

        # Categoria
        if dias_desde <= 45: cat = "TIBIO"
        elif dias_desde <= 90: cat = "FRIO"
        else: cat = "MUY FRIO"

        ticket = c["facturado"] / c["pedidos"] if c["pedidos"] > 0 else 0

        dormidos.append({
            "nombre": c["nombre"],
            "tel": c["tel"],
            "tel_display": c["tel_raw"],
            "barrio": c["barrio"],
            "subbarrio": c["subbarrio"],
            "canal": c["canal"],
            "pedidos": c["pedidos"],
            "facturado": c["facturado"],
            "ticket": ticket,
            "primera": c["primera"],
            "ultima": c["ultima"],
            "dias_desde": dias_desde,
            "categoria": cat,
            "productos_top": prods_nom,
        })

    # Generar drafts personalizados
    for d in dormidos:
        nombre_corto = d["nombre"].split()[0].title() if d["nombre"] else "Hola"
        prod_principal = d["productos_top"][0][0] if d["productos_top"] else "tu pedido habitual"
        semanas = d["dias_desde"] // 7
        meses = d["dias_desde"] // 30

        if d["categoria"] == "TIBIO":
            d["draft"] = (
                f"Hola {nombre_corto}! Hace {semanas} semanas que no nos pedís. "
                f"Esta semana repartimos en Estancias Mié/Vie/Sáb 19-21hs. "
                f"¿Te paso lo de siempre o querés sumar algo nuevo?"
            )
        elif d["categoria"] == "FRIO":
            d["draft"] = (
                f"Hola {nombre_corto}! ¿Cómo andás? Hace {semanas} semanas que no aparecemos por tu freezer. "
                f"Tu última {prod_principal.lower()} fue el {d['ultima'].strftime('%d/%m')}. "
                f"Esta semana arranco con todo, contame si te resuelvo algo."
            )
        else:  # MUY FRIO
            d["draft"] = (
                f"Hola {nombre_corto}! Soy Tadeo de Maleu. "
                f"Hace {meses} meses que no nos pedís — capaz cambió tu rutina. "
                f"Si querés, te paso qué hay nuevo y vemos si te resuelve algo esta semana."
            )

    # Ordenar: por categoria (Tibios primero) y dentro por facturado historico desc (mejores clientes primero)
    cat_order = {"TIBIO": 0, "FRIO": 1, "MUY FRIO": 2}
    dormidos.sort(key=lambda x: (cat_order[x["categoria"]], -x["facturado"]))

    # OUTPUT
    if args.json:
        out = {
            "fecha": hoy.strftime("%Y-%m-%d"),
            "total": len(dormidos),
            "por_categoria": {
                "TIBIO": sum(1 for d in dormidos if d["categoria"]=="TIBIO"),
                "FRIO": sum(1 for d in dormidos if d["categoria"]=="FRIO"),
                "MUY FRIO": sum(1 for d in dormidos if d["categoria"]=="MUY FRIO"),
            },
            "dormidos": [
                {**d,
                 "primera": d["primera"].strftime("%Y-%m-%d"),
                 "ultima": d["ultima"].strftime("%Y-%m-%d")}
                for d in dormidos
            ],
        }
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return

    # MD output
    md = []
    md.append(f"# 😴 Clientes Dormidos — {hoy.strftime('%d/%m/%Y')}\n")
    md.append(f"_Generado {now_ar().strftime('%d/%m/%Y %H:%M')} AR_\n")
    md.append(f"\n**Total: {len(dormidos)} dormidos detectados**")
    tibios = [d for d in dormidos if d['categoria']=='TIBIO']
    frios = [d for d in dormidos if d['categoria']=='FRIO']
    muyfrios = [d for d in dormidos if d['categoria']=='MUY FRIO']
    md.append(f"\n- 🟡 **Tibios** (21-45 días): {len(tibios)}")
    md.append(f"- 🟠 **Fríos** (45-90 días): {len(frios)}")
    md.append(f"- 🔴 **Muy fríos** (90-180 días): {len(muyfrios)}")
    md.append(f"\n> 💡 Empezá por los TIBIOS de mayor ticket histórico. Son los que más rápido vuelven.")

    for cat_lbl, cat_emoji, lista in [
        ("TIBIOS", "🟡", tibios),
        ("FRÍOS", "🟠", frios),
        ("MUY FRÍOS", "🔴", muyfrios),
    ]:
        if not lista: continue
        md.append(f"\n\n---\n\n## {cat_emoji} {cat_lbl} ({len(lista)})\n")
        for d in lista:
            md.append(f"\n### {d['nombre']} ({d['dias_desde']} días sin pedir)")
            extras = []
            if d['barrio']: extras.append(d['barrio'])
            if d['subbarrio']: extras.append(d['subbarrio'])
            extras_str = " · ".join(extras) if extras else "(sin barrio)"
            md.append(f"- **Canal:** {d['canal']} · {extras_str}")
            md.append(f"- **Tel:** {d['tel'] or '(sin tel)'}")
            md.append(f"- **Historial:** {d['pedidos']} pedidos · {fmt_money(d['facturado'])} facturado · ticket prom {fmt_money(d['ticket'])}")
            md.append(f"- **Primera compra:** {d['primera'].strftime('%d/%m/%Y')} · **Última:** {d['ultima'].strftime('%d/%m/%Y')}")
            if d['productos_top']:
                prods_str = ", ".join(f"{n} ({q})" for n, q in d['productos_top'])
                md.append(f"- **Productos top:** {prods_str}")
            md.append(f"\n**Draft WhatsApp:**")
            md.append(f"> {d['draft']}\n")
            if d['tel']:
                md.append(f"📱 [Abrir en WhatsApp](https://wa.me/{d['tel']}?text={d['draft'].replace(' ', '%20').replace('!', '%21').replace('?', '%3F')})")

    print("\n".join(md))

    # ─── HTML (formato bonito para Drive) ───
    import urllib.parse
    tibios = [d for d in dormidos if d['categoria']=='TIBIO']
    frios = [d for d in dormidos if d['categoria']=='FRIO']
    muyfrios = [d for d in dormidos if d['categoria']=='MUY FRIO']

    def card_dormido(d):
        nombre = d['nombre']
        dias = d['dias_desde']
        extras = []
        if d['barrio']: extras.append(d['barrio'])
        if d['subbarrio']: extras.append(d['subbarrio'])
        ubicacion = " · ".join(extras) if extras else "(sin barrio)"
        prods = ", ".join(f'{n} ({q})' for n, q in d['productos_top']) if d['productos_top'] else "—"
        wa_link = ""
        if d['tel']:
            txt = urllib.parse.quote(d['draft'])
            wa_link = f'<a href="https://wa.me/{d["tel"]}?text={txt}" target="_blank" class="wa-btn">💬 Abrir WhatsApp</a>'
        return f"""<div class="dorm-card cat-{d['categoria'].replace(' ','-').lower()}">
  <div class="dc-head">
    <div class="dc-name">{nombre}</div>
    <div class="dc-dias">{dias}d sin pedir</div>
  </div>
  <div class="dc-meta">
    <span>{d['canal']}</span><span>·</span><span>{ubicacion}</span>
    {f'<span>·</span><span>{d["tel"]}</span>' if d['tel'] else ''}
  </div>
  <div class="dc-stats">
    <div><b>{d['pedidos']}</b> pedidos</div>
    <div><b>{fmt_money(d['facturado'])}</b> facturado</div>
    <div>ticket <b>{fmt_money(d['ticket'])}</b></div>
    <div>última <b>{d['ultima'].strftime('%d/%m/%Y')}</b></div>
  </div>
  <div class="dc-prods"><b>Top productos:</b> {prods}</div>
  <div class="dc-draft">{d['draft']}</div>
  {wa_link}
</div>"""

    def seccion_html(label, emoji, lista, color):
        if not lista: return ""
        cards = "\n".join(card_dormido(d) for d in lista)
        return f"""<div class="cat-section">
  <h2 class="cat-h" style="border-left-color:{color}">{emoji} {label} <span class="cat-count">{len(lista)}</span></h2>
  <div class="dorm-grid">{cards}</div>
</div>"""

    html = f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Maleu · Dormidos {hoy.strftime('%d/%m/%Y')}</title>
<style>
:root {{ --o:#FF7A1A; --bg:#FFFAF5; --ink:#1b1b1b; --ink2:#4b5563; --ink3:#9ca3af; --border:#e5e7eb; }}
*{{box-sizing:border-box}}
body{{margin:0;padding:24px 16px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:var(--bg);color:var(--ink);line-height:1.55;font-size:14px}}
.wrap{{max-width:1100px;margin:0 auto}}
.hdr{{background:linear-gradient(135deg,#1b1b1b 0%,#2d2d2d 100%);color:#fff;padding:32px 28px;border-radius:16px;margin-bottom:20px;position:relative;overflow:hidden}}
.hdr::before{{content:"";position:absolute;top:-50%;right:-10%;width:50%;height:200%;background:radial-gradient(circle,rgba(255,122,26,0.25) 0%,transparent 70%)}}
.hdr h1{{margin:0 0 6px 0;font-size:28px;font-weight:800;letter-spacing:-.5px}}
.hdr .subt{{color:#d1d5db;font-size:13px;font-weight:500}}
.hdr .gen{{color:#9ca3af;font-size:11px;margin-top:8px}}
.kpis{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:20px}}
.kpi{{background:#fff;border-radius:12px;padding:16px;box-shadow:0 1px 3px rgba(0,0,0,.04)}}
.kpi .lbl{{font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:.7px;color:var(--ink3);margin-bottom:8px}}
.kpi .val{{font-size:28px;font-weight:800;color:var(--ink);line-height:1}}
.kpi.tibio{{border-left:4px solid #facc15}}
.kpi.frio{{border-left:4px solid #fb923c}}
.kpi.muyfrio{{border-left:4px solid #dc2626}}
.kpi.total{{border-left:4px solid var(--o)}}
.tip{{background:#fef3c7;border-left:4px solid #f59e0b;padding:12px 16px;border-radius:8px;margin-bottom:20px;font-size:13px}}
.cat-section{{margin-bottom:32px}}
.cat-h{{font-size:18px;font-weight:800;padding-left:12px;border-left:4px solid var(--o);margin:0 0 14px 0}}
.cat-count{{display:inline-block;background:#1b1b1b;color:#fff;padding:2px 9px;border-radius:10px;font-size:12px;margin-left:6px}}
.dorm-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:12px}}
.dorm-card{{background:#fff;border-radius:12px;padding:16px;box-shadow:0 1px 3px rgba(0,0,0,.04);border-left:4px solid #facc15;display:flex;flex-direction:column;gap:8px}}
.dorm-card.cat-frio{{border-left-color:#fb923c}}
.dorm-card.cat-muy-frio{{border-left-color:#dc2626}}
.dc-head{{display:flex;justify-content:space-between;align-items:baseline;gap:8px}}
.dc-name{{font-weight:800;font-size:15px;color:var(--ink)}}
.dc-dias{{background:#fef3c7;color:#92400e;padding:3px 8px;border-radius:6px;font-size:11px;font-weight:700;white-space:nowrap}}
.dorm-card.cat-frio .dc-dias{{background:#fed7aa;color:#9a3412}}
.dorm-card.cat-muy-frio .dc-dias{{background:#fecaca;color:#991b1b}}
.dc-meta{{font-size:12px;color:var(--ink2);display:flex;gap:6px;flex-wrap:wrap}}
.dc-meta span{{white-space:nowrap}}
.dc-stats{{display:grid;grid-template-columns:repeat(2,1fr);gap:6px 12px;font-size:12px;color:var(--ink2);padding:8px;background:#f9fafb;border-radius:8px}}
.dc-prods{{font-size:12px;color:var(--ink2)}}
.dc-draft{{background:#FFFAF5;border-left:3px solid var(--o);padding:10px 12px;border-radius:6px;font-size:13px;color:var(--ink);font-style:italic;line-height:1.4}}
.wa-btn{{display:inline-block;background:#25D366;color:#fff;text-align:center;padding:10px 14px;border-radius:8px;text-decoration:none;font-weight:700;font-size:13px;margin-top:4px}}
.wa-btn:hover{{background:#1ebd5a}}
.foot{{text-align:center;color:var(--ink3);font-size:11px;padding:20px 0}}
@media (max-width:720px){{ .kpis{{grid-template-columns:repeat(2,1fr)}} .hdr h1{{font-size:22px}} body{{font-size:13px;padding:12px 8px}} .dorm-grid{{grid-template-columns:1fr}} }}
</style></head>
<body><div class="wrap">
  <div class="hdr">
    <h1>😴 Clientes Dormidos</h1>
    <div class="subt">Detectados al {hoy.strftime('%d/%m/%Y')}</div>
    <div class="gen">Generado: {now_ar().strftime('%d/%m/%Y %H:%M')} AR</div>
  </div>
  <div class="kpis">
    <div class="kpi total"><div class="lbl">Total</div><div class="val">{len(dormidos)}</div></div>
    <div class="kpi tibio"><div class="lbl">🟡 Tibios (21-45d)</div><div class="val">{len(tibios)}</div></div>
    <div class="kpi frio"><div class="lbl">🟠 Fríos (45-90d)</div><div class="val">{len(frios)}</div></div>
    <div class="kpi muyfrio"><div class="lbl">🔴 Muy fríos (90-180d)</div><div class="val">{len(muyfrios)}</div></div>
  </div>
  <div class="tip">💡 <b>Empezá por los TIBIOS de mayor ticket histórico.</b> Son los que más rápido vuelven y los que más mueven la aguja.</div>
  {seccion_html("TIBIOS", "🟡", tibios, "#facc15")}
  {seccion_html("FRÍOS", "🟠", frios, "#fb923c")}
  {seccion_html("MUY FRÍOS", "🔴", muyfrios, "#dc2626")}
  <div class="foot">Maleu — Rico y listo en minutos. · Detector de dormidos · Tadeo elige a quién contactar</div>
</div></body></html>"""

    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        content = html if args.out.lower().endswith(".html") else "\n".join(md)
        Path(args.out).write_text(content, encoding="utf-8")
        print(f"\n[OK] Guardado: {args.out}", file=sys.stderr)

if __name__ == "__main__":
    main()
