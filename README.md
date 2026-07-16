# Demo Ferretería — Asistente de presupuestos (Behemot + Telegram)

Bot de Telegram construido con el **framework Behemot** que responde consultas de
precio/stock y **arma presupuestos** leyendo la planilla de stock de la ferretería.

> Basado en el proyecto `mi_asistente`, adaptado a una versión más nueva de Behemot.
> **El framework Behemot NO se modifica.** Si hace falta un cambio en el framework,
> se reporta al equipo de desarrollo (ver sección *Notas para el equipo de Behemot*).

## Cómo funciona

- La ferretería deja su planilla como un archivo **`stock*.csv`** en la carpeta del
  proyecto. El agente toma **siempre el más reciente** (por fecha de modificación).
  Se puede forzar una ruta con la variable `STOCK_CSV_PATH` en `.env`.
- Formato del CSV: delimitador `;`, columnas `Codigo;Detalle;Stock;Precio`,
  decimal `.`, encoding latin‑1/cp1252 (export de Excel en español). El stock puede
  ser fraccionario (venta por peso/medida).
- El stock se consulta con **tools** (búsquedas y cálculos exactos), no con RAG, para
  que los precios y totales sean precisos.

### Tools

| Tool | Qué hace |
|------|----------|
| `buscar_producto` | Busca por descripción o código; devuelve precio y stock. |
| `armar_presupuesto` | Toma el pedido (`cantidad x descripción`, separado por `;` o saltos de línea), arma el detalle con subtotales, total, y avisa faltantes / stock insuficiente. |

Los precios se toman **finales** (tal cual el CSV). El **presupuesto en PDF** es un
pedido especial: hoy el bot **deriva a un asesor** (handoff) para enviarlo, porque el
framework todavía no permite adjuntar archivos por Telegram (ver
`REPORTE_FRAMEWORK_BEHEMOT.md`).

La búsqueda normaliza texto (mayúsculas, sin acentos), ignora palabras vacías y exige
que coincida la **mayoría** de los términos, para evitar matches equivocados.

## Puesta en marcha

1. Crear el entorno e instalar dependencias:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\pip install -r requirements.txt
   ```
2. Completar `.env`:
   - `GPT_API_KEY` (OpenAI)
   - `TELEGRAM_TOKEN` (de @BotFather)
   - `TELEGRAM_WEBHOOK_SECRET` (recomendado)
   - `TELEGRAM_WEBHOOK_URL` (lo sincroniza `start.ps1` con ngrok)
3. Dejar la planilla `stock*.csv` en la carpeta del proyecto.
4. Arrancar:
   ```powershell
   .\start.ps1
   ```
   `start.ps1` levanta ngrok (y Redis si está presente), sincroniza el webhook en
   `.env` y corre `main.py` en el puerto 8000.

> Redis es **opcional**: sin él la app corre sin memoria persistente de conversación.

## Probar los tools sin Telegram

```powershell
$env:PYTHONUTF8=1
.\.venv\Scripts\python -c "import asyncio; from tools.armar_presupuesto import armar_presupuesto; print(asyncio.run(armar_presupuesto({'pedido':'2 x martillo carpintero; 3 x pintura latex 4l'})))"
```

## Estructura

```
mi_asistente2/
├─ main.py                     # create_behemot_app(...) con las 2 tools
├─ config/config_telegram.yaml # prompt de sistema orientado a presupuestos
├─ tools/
│  ├─ stock_data.py            # loader del CSV + búsqueda (helper compartido)
│  ├─ buscar_producto.py       # tool
│  └─ armar_presupuesto.py     # tool
├─ stock-*.csv                 # planilla de stock (la carga la ferretería)
├─ requirements.txt
├─ start.ps1
└─ .env                        # secretos (no commitear)
```

## Notas para el equipo de Behemot

Los hallazgos sobre el framework (no se modificó nada) están detallados en
**`REPORTE_FRAMEWORK_BEHEMOT.md`**:

1. **Bloqueante — PDF/documentos por Telegram:** el webhook de Telegram no propaga
   `session_context` a las tools (sí lo hace WhatsApp) y `TelegramConnector` no tiene
   método para enviar archivos. Por eso el PDF se resuelve por handoff.
2. **Limitación — `Param` no soporta tipos compuestos** (array/object/enum): las tools
   usan `string` y parsean internamente.
3. **Menor — aviso de `SAFETY_LEVEL`** con el extra `[voice]` (filtro desactivado).
