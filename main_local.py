"""Prueba LOCAL de la demo (sin Telegram ni ngrok).

Levanta la interfaz Gradio del framework en http://localhost:7860 usando el
mismo asistente, config y tools que la versión de Telegram. Ideal para probar
las respuestas y los presupuestos rápido.

Ejecutar:
    .\.venv\Scripts\python main_local.py
Luego abrir http://localhost:7860 en el navegador.
"""

import logging
import os
import uvicorn

from behemot_framework.factory import create_behemot_app

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config", "config_telegram.yaml")

app = create_behemot_app(
    enable_telegram=False,     # sin webhook: no toca el bot ni requiere ngrok
    enable_test_local=True,    # interfaz Gradio en http://localhost:7860
    config_path=CONFIG_PATH,
    use_tools=["buscar_producto", "armar_presupuesto"],
)


if __name__ == "__main__":
    # uvicorn mantiene vivo el proceso mientras Gradio corre en su hilo (7860).
    uvicorn.run(app, host="0.0.0.0", port=8000)
