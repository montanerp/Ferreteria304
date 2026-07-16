"""Demo Ferreteria: asistente Behemot conectado a Telegram.

Responde consultas de precio/stock y arma presupuestos leyendo la planilla
de stock (stock*.csv) que carga la ferreteria.

Corre igual en local (con .env + ngrok) que en Railway:
  - En Railway usa el puerto que asigna la plataforma (variable PORT) y
    deriva la URL del webhook del dominio publico (RAILWAY_PUBLIC_DOMAIN),
    asi no hay que setear TELEGRAM_WEBHOOK_URL a mano.
  - En local usa el puerto 8000 y la TELEGRAM_WEBHOOK_URL del .env (que
    start.ps1 sincroniza con ngrok).

Local:   python main.py   (o start.ps1 en Windows)
Railway: se ejecuta via Procfile -> python main.py
"""

import logging
import os
import uvicorn

from behemot_framework.factory import create_behemot_app

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config", "config_telegram.yaml")

# En Railway: si no hay TELEGRAM_WEBHOOK_URL explicita, derivarla del dominio
# publico que asigna la plataforma. Debe hacerse ANTES de create_behemot_app,
# porque el framework lee la URL al construir la app y registrar el webhook.
_railway_domain = os.getenv("RAILWAY_PUBLIC_DOMAIN")
if _railway_domain:
    if not os.getenv("TELEGRAM_WEBHOOK_URL"):
        os.environ["TELEGRAM_WEBHOOK_URL"] = f"https://{_railway_domain}/webhook"
        logger.info("Webhook derivado de Railway: %s", os.environ["TELEGRAM_WEBHOOK_URL"])
    # Callback de handoff (derivacion a humano) contra el mismo dominio publico.
    if not os.getenv("HANDOFF_CALLBACK_URL"):
        os.environ["HANDOFF_CALLBACK_URL"] = f"https://{_railway_domain}"

app = create_behemot_app(
    enable_telegram=True,      # conector de Telegram (webhook)
    enable_whatsapp=True,      # conector de WhatsApp Cloud API (webhook /whatsapp-webhook)
    enable_voice=True,         # transcribe audios entrantes con Whisper
    config_path=CONFIG_PATH,
    use_tools=["buscar_producto", "armar_presupuesto"],
)


if __name__ == "__main__":
    # Railway inyecta PORT; en local caemos a 8000.
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
