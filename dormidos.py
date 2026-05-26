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

    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text("\n".join(md), encoding="utf-8")
        print(f"\n[OK] Guardado: {args.out}", file=sys.stderr)

if __name__ == "__main__":
    main()
