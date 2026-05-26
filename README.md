# Maleu Automation (cloud)

Scripts **públicos** para rutinas cloud de Maleu. Las credenciales NO viven acá — se inyectan vía prompt de cada rutina antes de ejecutar.

Repo privado original con histórico: `maleupedidos/maleu-automation` (no usar para cloud).

## Estructura

- `informe_semanal.py` — informe Lun-Dom de la semana cerrada
- `enviar_whatsapp.py` — cliente WATI
- `dormidos.py` — detector clientes dormidos + drafts WhatsApp
- `cerebro/` — vision/identidad/avatar para generar contenido
- `requirements.txt` — deps Python (gspread, google-auth, requests)

## Antes de ejecutar (en cloud)

```bash
pip install -r requirements.txt
mkdir -p creds
# Las rutinas crean ./creds/service-account.json y ./creds/wati-token.txt antes de correr scripts
```
