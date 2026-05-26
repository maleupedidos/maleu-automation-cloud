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

    # ─── HTML (formato bonito para Drive) ───
    def html_card(label, value, sub="", color="#FF7A1A"):
        sub_html = f'<div class="sub">{sub}</div>' if sub else ""
        return f'<div class="kpi" style="border-left:4px solid {color}"><div class="lbl">{label}</div><div class="val">{value}</div>{sub_html}</div>'

    def delta_html(pct, kind="fact"):
        if pct is None: return ""
        cls = "up" if pct >= 0 else "down"
        sign = "+" if pct >= 0 else ""
        return f'<span class="delta {cls}">{sign}{pct:.0f}% vs sem ant</span>'

    canales_html = ""
    for k, r in res_sem.items():
        mpct = f"{r['margen_pct']*100:.0f}%" if r['facturado'] > 0 else "—"
        canales_html += f"""<tr>
            <td><b>{k}</b></td>
            <td class="num">{r['pedidos']}</td>
            <td class="num">{r['entregados']}</td>
            <td class="num">{fmt_money(r['facturado'])}</td>
            <td class="num">{fmt_money(r['margen'])}</td>
            <td class="num">{mpct}</td>
            <td class="num">{fmt_money(r['ticket'])}</td>
        </tr>"""
    canales_html += f"""<tr class="total">
        <td><b>TOTAL</b></td><td class="num">—</td>
        <td class="num"><b>{total_e}</b></td>
        <td class="num"><b>{fmt_money(total_f)}</b></td>
        <td class="num"><b>{fmt_money(total_m)}</b></td>
        <td class="num"><b>{margen_pct_total*100:.0f}%</b></td>
        <td class="num">—</td>
    </tr>"""

    tendencia_html = f"""
    <tr><td>Sem -2 ({lun_prev2.strftime('%d/%m')}–{dom_prev2.strftime('%d/%m')})</td><td class="num">{e_prev2}</td><td class="num">{fmt_money(f_prev2)}</td></tr>
    <tr><td>Sem -1 ({lun_prev.strftime('%d/%m')}–{dom_prev.strftime('%d/%m')})</td><td class="num">{e_prev}</td><td class="num">{fmt_money(f_prev)}</td></tr>
    <tr class="total"><td><b>Esta sem</b></td><td class="num"><b>{total_e}</b></td><td class="num"><b>{fmt_money(total_f)}</b></td></tr>
    """

    diaadia_html = ""
    for d in ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"]:
        if d in por_dia:
            x = por_dia[d]
            diaadia_html += f'<tr><td><b>{d}</b></td><td class="num">{x["p"]}</td><td class="num">{fmt_money(x["f"])}</td></tr>'

    clubes_html = ""
    if clubes_sem:
        for r in clubes_sem:
            clubes_html += f'<tr><td>{r["fecha"].strftime("%d/%m")}</td><td><b>{r["barrio"]}</b></td><td>{r["cliente"]}</td><td class="num">{fmt_money(r["facturado"])}</td></tr>'
    else:
        clubes_html = '<tr><td colspan="4" style="text-align:center;color:#9ca3af;font-style:italic">Sin pedidos esta semana ⚠️</td></tr>'

    silentes_html = ""
    if clubes_silentes:
        silentes_chips = " ".join(f'<span class="chip alert">{c}</span>' for c in clubes_silentes if c)
        silentes_html = f'<div class="silent-box"><div class="silent-h">⚠️ Clubes silentes (pidieron sem-1, no esta sem)</div>{silentes_chips}<div class="silent-tip">→ Contactalos mañana antes del partido del viernes.</div></div>'

    dormidos_html = ""
    if dormidos:
        dorm_list = ""
        for c in dormidos[:15]:
            dorm_list += f'<li>{c.title()}</li>'
        extra = f'<li class="more">...y {len(dormidos)-15} más</li>' if len(dormidos) > 15 else ""
        dormidos_html = f'<div class="dorm-box"><div class="dorm-h">😴 Dormidos potenciales — {len(dormidos)}</div><ul>{dorm_list}{extra}</ul><div class="dorm-tip">→ Corré <code>/dormidos</code> para drafts WhatsApp.</div></div>'

    flecha_up = "📈"
    flecha_down = "📉"

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Maleu · Informe Sem {sem_num}</title>
<style>
:root {{
  --o: #FF7A1A;
  --o-dark: #E66800;
  --bg: #FFFAF5;
  --ink: #1b1b1b;
  --ink2: #4b5563;
  --ink3: #9ca3af;
  --green: #16a34a;
  --red: #dc2626;
  --border: #e5e7eb;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  padding: 24px 16px;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background: var(--bg);
  color: var(--ink);
  line-height: 1.55;
  font-size: 14px;
}}
.wrap {{ max-width: 880px; margin: 0 auto; }}
.hdr {{
  background: linear-gradient(135deg, #1b1b1b 0%, #2d2d2d 100%);
  color: #fff;
  padding: 32px 28px;
  border-radius: 16px;
  margin-bottom: 20px;
  position: relative;
  overflow: hidden;
}}
.hdr::before {{
  content: "";
  position: absolute;
  top: -50%;
  right: -10%;
  width: 50%;
  height: 200%;
  background: radial-gradient(circle, rgba(255,122,26,0.25) 0%, transparent 70%);
}}
.hdr h1 {{ margin: 0 0 6px 0; font-size: 28px; font-weight: 800; letter-spacing: -0.5px; }}
.hdr .subt {{ color: #d1d5db; font-size: 13px; font-weight: 500; }}
.hdr .gen {{ color: #9ca3af; font-size: 11px; margin-top: 8px; }}

.kpis {{
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 20px;
}}
.kpi {{
  background: #fff;
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}}
.kpi .lbl {{
  font-size: 10px;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.7px;
  color: var(--ink3);
  margin-bottom: 8px;
}}
.kpi .val {{
  font-size: 22px;
  font-weight: 800;
  color: var(--ink);
  line-height: 1.1;
}}
.kpi .sub {{ font-size: 11px; color: var(--ink2); margin-top: 4px; font-weight: 600; }}
.delta {{
  display: inline-block;
  padding: 3px 10px;
  border-radius: 12px;
  font-size: 11px;
  font-weight: 800;
  margin-top: 8px;
}}
.delta.up {{ background: #dcfce7; color: #15803d; }}
.delta.down {{ background: #fee2e2; color: #b91c1c; }}

.card {{
  background: #fff;
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 16px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}}
.card h2 {{
  margin: 0 0 4px 0;
  font-size: 15px;
  font-weight: 800;
  color: var(--ink);
}}
.card .csub {{
  font-size: 11px;
  color: var(--ink3);
  margin-bottom: 14px;
}}
table {{
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}}
table thead th {{
  background: #f9fafb;
  color: var(--ink3);
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  font-size: 10px;
  padding: 10px 8px;
  text-align: left;
  border-bottom: 2px solid var(--border);
}}
table thead th.num {{ text-align: right; }}
table tbody td {{
  padding: 10px 8px;
  border-bottom: 1px solid #f3f4f6;
}}
table tbody td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
table tbody tr.total {{ background: linear-gradient(90deg, #FFF6F0 0%, transparent 100%); }}
table tbody tr.total td {{ border-top: 2px solid var(--o); font-size: 14px; }}

.silent-box, .dorm-box {{
  border-radius: 10px;
  padding: 14px 16px;
  margin-top: 12px;
}}
.silent-box {{ background: #fef3c7; border-left: 4px solid #f59e0b; }}
.dorm-box {{ background: #fce7f3; border-left: 4px solid #db2777; }}
.silent-h, .dorm-h {{ font-weight: 800; font-size: 13px; margin-bottom: 8px; }}
.silent-tip, .dorm-tip {{ font-size: 12px; color: var(--ink2); margin-top: 8px; font-style: italic; }}
.chip {{
  display: inline-block;
  background: #fff;
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 700;
  margin: 2px 4px 2px 0;
}}
.chip.alert {{ color: #9a3412; }}
.dorm-box ul {{ margin: 0; padding-left: 18px; columns: 2; column-gap: 20px; }}
.dorm-box li {{ font-size: 12px; padding: 2px 0; }}
.dorm-box li.more {{ font-style: italic; color: var(--ink2); }}
.dorm-box code {{ background: #fff; padding: 2px 6px; border-radius: 4px; font-size: 11px; }}

.foot {{
  text-align: center;
  color: var(--ink3);
  font-size: 11px;
  padding: 20px 0;
  margin-top: 10px;
}}

@media (max-width: 720px) {{
  .kpis {{ grid-template-columns: repeat(2, 1fr); }}
  .hdr h1 {{ font-size: 22px; }}
  body {{ font-size: 13px; padding: 12px 8px; }}
  .card {{ padding: 14px; }}
  .dorm-box ul {{ columns: 1; }}
  table {{ font-size: 11px; }}
}}
</style>
</head>
<body>
<div class="wrap">

  <div class="hdr">
    <h1>📊 Maleu · Sem {sem_num}</h1>
    <div class="subt">{lun.strftime('%d/%m')}–{dom.strftime('%d/%m/%Y')}</div>
    <div class="gen">Generado: {now_ar().strftime('%d/%m/%Y %H:%M')} AR</div>
  </div>

  <div class="kpis">
    {html_card("Entregados", str(total_e), delta_html(pct_e), "#FF7A1A")}
    {html_card("Facturado", fmt_money(total_f), delta_html(pct_f), "#16a34a")}
    {html_card("Margen bruto", fmt_money(total_m), f'{margen_pct_total*100:.0f}% · {"+" if pct_m>=0 else ""}{pct_m:.0f}% vs sem ant', "#a855f7")}
    {html_card("Ticket prom.", fmt_money(total_f/total_e if total_e else 0), f"{total_sc_cant} sin cobrar" if total_sc_cant else "Todo cobrado ✓", "#f59e0b")}
  </div>

  <div class="card">
    <h2>📈 Ventas por canal</h2>
    <div class="csub">Cómo se reparte la facturación de la semana</div>
    <table>
      <thead><tr><th>Canal</th><th class="num">Ped.</th><th class="num">Entreg.</th><th class="num">Facturado</th><th class="num">Margen $</th><th class="num">Margen %</th><th class="num">Ticket</th></tr></thead>
      <tbody>{canales_html}</tbody>
    </table>
  </div>

  <div class="card">
    <h2>📅 Tendencia (3 semanas)</h2>
    <div class="csub">Comparativa para ver si venís subiendo o bajando</div>
    <table>
      <thead><tr><th>Semana</th><th class="num">Entregados</th><th class="num">Facturado</th></tr></thead>
      <tbody>{tendencia_html}</tbody>
    </table>
  </div>

  <div class="card">
    <h2>🏠 Home — día a día</h2>
    <div class="csub">Para ver qué días vienen fuertes</div>
    <table>
      <thead><tr><th>Día</th><th class="num">Pedidos</th><th class="num">Facturado</th></tr></thead>
      <tbody>{diaadia_html if diaadia_html else '<tr><td colspan="3" style="text-align:center;color:#9ca3af">Sin entregas Home esta semana</td></tr>'}</tbody>
    </table>
  </div>

  <div class="card">
    <h2>👥 Clientes</h2>
    <div class="csub">Adquisición vs retención</div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px">
      <div style="background:#dcfce7;border-radius:10px;padding:14px"><div style="font-size:10px;font-weight:800;color:#166534;letter-spacing:.5px">NUEVOS</div><div style="font-size:24px;font-weight:800;color:#166534">{len(nuevos)}</div></div>
      <div style="background:#dbeafe;border-radius:10px;padding:14px"><div style="font-size:10px;font-weight:800;color:#1e40af;letter-spacing:.5px">REPETIDORES</div><div style="font-size:24px;font-weight:800;color:#1e40af">{len(repetidores)}</div></div>
    </div>
    {dormidos_html}
  </div>

  <div class="card">
    <h2>⚽ Clubes</h2>
    <div class="csub">Pedidos del canal Clubes esta semana</div>
    <table>
      <thead><tr><th>Fecha</th><th>Club</th><th>Cliente</th><th class="num">Facturado</th></tr></thead>
      <tbody>{clubes_html}</tbody>
    </table>
    {silentes_html}
  </div>

  <div class="foot">
    Maleu — Rico y listo en minutos. · Informe generado por Claude Code
  </div>

</div>
</body>
</html>"""

    flecha = flecha_up if pct_f >= 0 else flecha_down
    flecha_m = flecha_up if pct_m >= 0 else flecha_down
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
        "html": html,
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
        # Si --out termina en .html, escribir HTML; si no, MD
        content = info["html"] if args.out.lower().endswith(".html") else info["md"]
        Path(args.out).write_text(content, encoding="utf-8")
        print(f"\n[OK] Guardado: {args.out}", file=sys.stderr)
