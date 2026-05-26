"""
Informe semanal de Maleu.
Lee Sheets via Service Account, genera MD + resumen WhatsApp.

Uso:
  python informe_semanal.py [--semanas-atras N] [--out FILE.md] [--solo-wa] [--json]

Ambientes:
  - Local: corre desde C:\\Users\\tadeu\\
  - Remote (cloud): clonado del repo, creds en ./creds/service-account.json
"""
import sys
import os
import io
import argparse
from pathlib import Path
from datetime import datetime, date, timedelta, timezone
from collections import defaultdict

try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")
except Exception:
    pass

import gspread
from google.oauth2.service_account import Credentials

SHEET_ID = "1ILXCc9ddbC_gJPNoUADBiSMXAWLM9v73ov2_xXb8YsY"

def find_creds():
    candidates = [
        Path(__file__).parent / "creds" / "service-account.json",
        Path(r"C:\Users\tadeu\maleu-service-account.json"),
        Path(os.environ.get("MALEU_SA_KEY", "")),
    ]
    for c in candidates:
        if c and c.exists():
            return str(c)
    raise FileNotFoundError("No se encontró service-account.json")

def now_ar():
    return datetime.now(timezone(timedelta(hours=-3)))

def get_semana_cerrada(semanas_atras=1):
    hoy = now_ar().date()
    lunes_actual = hoy - timedelta(days=hoy.weekday())
    lunes = lunes_actual - timedelta(weeks=semanas_atras)
    domingo = lunes + timedelta(days=6)
    return lunes, domingo

def parse_fecha(s):
    if s is None or s == "":
        return None
    if isinstance(s, (int, float)):
        try:
            return (datetime(1899, 12, 30) + timedelta(days=int(s))).date()
        except Exception:
            return None
    s = str(s).strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d/%m/%y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None

def parse_num(s):
    if s is None or s == "":
        return 0.0
    if isinstance(s, (int, float)):
        return float(s)
    s = str(s).replace("$", "").replace(" ", "").strip()
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    elif s.count(".") > 1:
        s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return 0.0

def fmt_money(n):
    return f"${n:,.0f}".replace(",", ".")

def cargar(sh, nombre):
    ws = sh.worksheet(nombre)
    rows = ws.get(f"A1:CA{ws.row_count}", value_render_option="UNFORMATTED_VALUE")
    if not rows:
        return [], {}
    headers = [str(h) for h in rows[0]]
    idx = {h: i for i, h in enumerate(headers)}
    return rows[1:], idx

def get(row, idx, key, default=""):
    i = idx.get(key)
    if i is None or i >= len(row):
        return default
    v = row[i]
    return default if v is None else v

def procesar(sh, nombre, barrio_key=None):
    rows, idx = cargar(sh, nombre)
    out = []
    for r in rows:
        f = parse_fecha(get(r, idx, "Fecha"))
        if not f:
            continue
        out.append({
            "hoja": nombre,
            "fecha": f,
            "estado": str(get(r, idx, "Estado de Entrega")).strip(),
            "estado_pago": str(get(r, idx, "Estado de Pago")).strip(),
            "facturado": parse_num(get(r, idx, "Facturado")),
            "costo": parse_num(get(r, idx, "Costo")),
            "margen": parse_num(get(r, idx, "Margen Bruto")),
            "cliente": str(get(r, idx, "Cliente")).strip(),
            "barrio": str(get(r, idx, barrio_key)).strip() if barrio_key else "",
        })
    return out

def filtrar(rows, ini, fin):
    return [r for r in rows if ini <= r["fecha"] <= fin]

def resumen(rows):
    entregados = [r for r in rows if r["estado"].lower() == "entregado"]
    fact = sum(r["facturado"] for r in entregados)
    margen = sum(r["margen"] for r in entregados)
    costo = sum(r["costo"] for r in entregados)
    sin_cobrar = [r for r in entregados if r["estado_pago"].lower() != "cobrado"]
    return {
        "pedidos": len(rows),
        "entregados": len(entregados),
        "cancelados": len([r for r in rows if r["estado"].lower() == "cancelado"]),
        "facturado": fact,
        "costo": costo,
        "margen": margen,
        "margen_pct": (margen / fact) if fact > 0 else 0,
        "ticket": fact / len(entregados) if entregados else 0,
        "sin_cobrar_monto": sum(r["facturado"] for r in sin_cobrar),
        "sin_cobrar_cant": len(sin_cobrar),
    }

def generar_informe(semanas_atras=1):
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_file(find_creds(), scopes=scopes)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(SHEET_ID)

    lun, dom = get_semana_cerrada(semanas_atras)
    lun_prev = lun - timedelta(days=7)
    dom_prev = lun - timedelta(days=1)
    lun_prev2 = lun - timedelta(days=14)
    dom_prev2 = lun - timedelta(days=8)
    sem_num = lun.isocalendar()[1]

    home   = procesar(sh, "Home",   barrio_key="Barrio")
    pilar  = procesar(sh, "Pilar",  barrio_key="Barrio Privado / Dirección")
    clubes = procesar(sh, "Clubes", barrio_key="Club")
    red    = procesar(sh, "Red",    barrio_key="Barrio Privado")

    canales = {"Home": home, "Pilar": pilar, "Clubes": clubes, "Red": red}
    res_sem = {k: resumen(filtrar(v, lun, dom)) for k, v in canales.items()}
    total_e = sum(r["entregados"] for r in res_sem.values())
    total_f = sum(r["facturado"] for r in res_sem.values())
    total_m = sum(r["margen"] for r in res_sem.values())
    total_c = sum(r["costo"] for r in res_sem.values())
    margen_pct_total = (total_m / total_f) if total_f > 0 else 0
    total_sc = sum(r["sin_cobrar_monto"] for r in res_sem.values())
    total_sc_cant = sum(r["sin_cobrar_cant"] for r in res_sem.values())

    # Margen sem anterior para comparar
    res_prev = {k: resumen(filtrar(v, lun_prev, dom_prev)) for k, v in canales.items()}
    m_prev = sum(r["margen"] for r in res_prev.values())
    pct_m = ((total_m - m_prev) / m_prev * 100) if m_prev else 0

    f_prev  = sum(resumen(filtrar(v, lun_prev,  dom_prev ))["facturado"] for v in canales.values())
    e_prev  = sum(resumen(filtrar(v, lun_prev,  dom_prev ))["entregados"] for v in canales.values())
    f_prev2 = sum(resumen(filtrar(v, lun_prev2, dom_prev2))["facturado"] for v in canales.values())
    e_prev2 = sum(resumen(filtrar(v, lun_prev2, dom_prev2))["entregados"] for v in canales.values())

    pct_f = ((total_f - f_prev) / f_prev * 100) if f_prev else 0
    pct_e = ((total_e - e_prev) / e_prev * 100) if e_prev else 0

    home_e = [r for r in filtrar(home, lun, dom) if r["estado"].lower() == "entregado"]
    dia_map = {0:"Lunes",1:"Martes",2:"Miércoles",3:"Jueves",4:"Viernes",5:"Sábado",6:"Domingo"}
    por_dia = defaultdict(lambda: {"p": 0, "f": 0})
    for r in home_e:
        d = dia_map[r["fecha"].weekday()]
        por_dia[d]["p"] += 1
        por_dia[d]["f"] += r["facturado"]

    hist = set()
    for r in (home + pilar + clubes):
        if r["fecha"] < lun and r["estado"].lower() == "entregado" and r["cliente"]:
            hist.add(r["cliente"].lower())
    sem_e = [r for r in (home + pilar + clubes) if lun <= r["fecha"] <= dom and r["estado"].lower() == "entregado"]
    nuevos, repetidores = set(), set()
    for r in sem_e:
        c = r["cliente"].lower()
        if not c: continue
        (repetidores if c in hist else nuevos).add(c)

    compraron_prev = set()
    for r in (home + pilar + clubes):
        if lun_prev <= r["fecha"] <= dom_prev and r["estado"].lower() == "entregado" and r["cliente"]:
            compraron_prev.add(r["cliente"].lower())
    compraron_act = {r["cliente"].lower() for r in sem_e if r["cliente"]}
    dormidos = sorted(compraron_prev - compraron_act)

    clubes_sem = [r for r in filtrar(clubes, lun, dom) if r["estado"].lower() == "entregado"]
    clubes_silentes = set()
    for r in clubes:
        if lun_prev <= r["fecha"] <= dom_prev and r["estado"].lower() == "entregado":
            clubes_silentes.add(r["barrio"])
    for r in clubes_sem:
        clubes_silentes.discard(r["barrio"])

    md = []
    md.append(f"# Informe Semanal Maleu — Sem {sem_num} ({lun.strftime('%d/%m')}–{dom.strftime('%d/%m/%Y')})\n")
    md.append(f"_Generado: {now_ar().strftime('%d/%m/%Y %H:%M')} AR_\n")
    md.append(f"\n## Resumen\n")
    md.append(f"- Total entregados: **{total_e}** ({pct_e:+.0f}% vs sem ant)")
    md.append(f"- Facturado: **{fmt_money(total_f)}** ({pct_f:+.0f}% vs sem ant)")
    md.append(f"- **Margen bruto: {fmt_money(total_m)} ({margen_pct_total*100:.1f}%)** ({pct_m:+.0f}% vs sem ant)")
    md.append(f"- Costo mercadería: {fmt_money(total_c)}")
    md.append(f"- Ticket promedio: {fmt_money(total_f/total_e if total_e else 0)}")
    md.append(f"- Sin cobrar: {fmt_money(total_sc)} ({total_sc_cant} pedidos)")

    md.append(f"\n## Ventas por canal\n")
    md.append("| Canal | Pedidos | Entregados | Facturado | Margen $ | Margen % | Ticket |")
    md.append("|---|---|---|---|---|---|---|")
    for k, r in res_sem.items():
        mpct = f"{r['margen_pct']*100:.0f}%" if r['facturado'] > 0 else "—"
        md.append(f"| {k} | {r['pedidos']} | {r['entregados']} | {fmt_money(r['facturado'])} | {fmt_money(r['margen'])} | {mpct} | {fmt_money(r['ticket'])} |")
    md.append(f"| **TOTAL** | — | **{total_e}** | **{fmt_money(total_f)}** | **{fmt_money(total_m)}** | **{margen_pct_total*100:.0f}%** | — |")

    md.append(f"\n## Tendencia (3 semanas)\n")
    md.append("| Semana | Entregados | Facturado |")
    md.append("|---|---|---|")
    md.append(f"| Sem -2 ({lun_prev2.strftime('%d/%m')}–{dom_prev2.strftime('%d/%m')}) | {e_prev2} | {fmt_money(f_prev2)} |")
    md.append(f"| Sem -1 ({lun_prev.strftime('%d/%m')}–{dom_prev.strftime('%d/%m')}) | {e_prev} | {fmt_money(f_prev)} |")
    md.append(f"| **Esta sem** | **{total_e}** | **{fmt_money(total_f)}** |")

    md.append(f"\n## Home — día a día\n")
    for d in ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"]:
        if d in por_dia:
            x = por_dia[d]
            md.append(f"- **{d}**: {x['p']} ped · {fmt_money(x['f'])}")

    md.append(f"\n## Clientes\n")
    md.append(f"- Nuevos: **{len(nuevos)}**")
    md.append(f"- Repetidores: **{len(repetidores)}**")
    if dormidos:
        md.append(f"\n### Dormidos potenciales (compraron sem-1, no esta sem) — {len(dormidos)}")
        for c in dormidos[:15]:
            md.append(f"- {c.title()}")
        if len(dormidos) > 15:
            md.append(f"- _...y {len(dormidos)-15} más_")

    md.append(f"\n## Clubes\n")
    if clubes_sem:
        for r in clubes_sem:
            md.append(f"- {r['fecha'].strftime('%d/%m')} · {r['barrio']} · {r['cliente']} · {fmt_money(r['facturado'])}")
    else:
        md.append("- Sin pedidos esta semana")
    if clubes_silentes:
        md.append(f"\n### Clubes silentes (pidieron sem-1, no esta sem)")
        for c in clubes_silentes:
            if c: md.append(f"- {c}")

    flecha = "📈" if pct_f >= 0 else "📉"
    flecha_m = "📈" if pct_m >= 0 else "📉"
    wa_lines = [
        f"📊 Maleu — Sem {sem_num}",
        f"",
        f"{total_e} entregados ({pct_e:+.0f}%)",
        f"{fmt_money(total_f)} facturado ({pct_f:+.0f}%) {flecha}",
        f"{fmt_money(total_m)} margen ({margen_pct_total*100:.0f}%) ({pct_m:+.0f}%) {flecha_m}",
        f"Ticket: {fmt_money(total_f/total_e if total_e else 0)}",
    ]
    if total_sc_cant:
        wa_lines.append(f"Sin cobrar: {fmt_money(total_sc)} ({total_sc_cant})")
    if dormidos:
        wa_lines.append(f"")
        wa_lines.append(f"😴 {len(dormidos)} dormidos nuevos")
    if clubes_silentes:
        silentes_str = ", ".join(c for c in clubes_silentes if c)
        wa_lines.append(f"⚠️ Clubes silentes: {silentes_str}")

    return {
        "md": "\n".join(md),
        "wa": "\n".join(wa_lines),
        "sem_num": sem_num,
        "lun": lun.strftime("%Y-%m-%d"),
        "dom": dom.strftime("%Y-%m-%d"),
        "total_entregados": total_e,
        "total_facturado": total_f,
        "total_margen": total_m,
        "total_costo": total_c,
        "margen_pct": margen_pct_total,
        "pct_facturado": pct_f,
        "pct_margen": pct_m,
        "dormidos_count": len(dormidos),
        "clubes_silentes": list(clubes_silentes),
    }

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--semanas-atras", type=int, default=1)
    p.add_argument("--out", help="Path para guardar MD")
    p.add_argument("--solo-wa", action="store_true")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    info = generar_informe(args.semanas_atras)

    if args.json:
        import json
        print(json.dumps(info, ensure_ascii=False, indent=2))
    elif args.solo_wa:
        print(info["wa"])
    else:
        print(info["md"])
        print("\n---\n=== RESUMEN WHATSAPP ===\n")
        print(info["wa"])

    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(info["md"], encoding="utf-8")
        print(f"\n[OK] Guardado: {args.out}", file=sys.stderr)
