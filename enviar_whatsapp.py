"""
Cliente WATI para enviar mensajes a Tadeo.
Usa template aprobado 'informe_maleu' (param {{1}} = resumen).

Uso:
  python enviar_whatsapp.py --telefono 5491136887500 --resumen "..."
"""
import sys, os, io, argparse
from pathlib import Path
try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
except Exception:
    pass
import requests

WATI_BASE = "https://live-mt-server.wati.io/1034656"

def get_token():
    p = Path(__file__).parent / "creds" / "wati-token.txt"
    if p.exists():
        return p.read_text(encoding="utf-8").strip()
    return os.environ.get("WATI_TOKEN", "")

def enviar_template(telefono, template_name, params):
    """Envía template aprobado. params = lista de strings para {{1}}, {{2}}, etc."""
    token = get_token()
    if not token:
        raise RuntimeError("WATI_TOKEN no encontrado")
    url = f"{WATI_BASE}/api/v2/sendTemplateMessage"
    payload = {
        "template_name": template_name,
        "broadcast_name": f"{template_name}_auto",
        "parameters": [{"name": str(i+1), "value": v} for i, v in enumerate(params)],
    }
    r = requests.post(
        url,
        params={"whatsappNumber": telefono},
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=payload,
        timeout=30,
    )
    return r.status_code, r.text

def enviar_session(telefono, mensaje):
    """Envía mensaje de sesión (texto libre, requiere ventana 24hs abierta)."""
    token = get_token()
    url = f"{WATI_BASE}/api/v1/sendSessionMessage/{telefono}"
    r = requests.post(
        url,
        params={"messageText": mensaje},
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    return r.status_code, r.text

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--telefono", default="5491136887500")
    p.add_argument("--resumen", required=True)
    p.add_argument("--template", default="informe_maleu")
    p.add_argument("--fallback-session", action="store_true")
    args = p.parse_args()

    status, body = enviar_template(args.telefono, args.template, [args.resumen])
    print(f"Template send: {status}")
    print(body[:500])

    if status >= 400 and args.fallback_session:
        print("\nFallback a sessionMessage...")
        status2, body2 = enviar_session(args.telefono, args.resumen)
        print(f"Session send: {status2}")
        print(body2[:500])
