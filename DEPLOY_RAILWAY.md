# Deploy en Railway — Demo Ferretería (FerreBot)

Guía paso a paso para publicar la demo en Railway (hosting estable, siempre
encendido, con Redis administrado). Reemplaza a ngrok: URL pública fija, sin
"Read timeout" ni mensajes duplicados.

> Requisitos ya cumplidos: Railway CLI instalada (`railway 5.26.0`) y sesión
> iniciada (`railway login`). Verificá con `railway whoami`.

Los archivos del proyecto ya están listos para Railway:
- `main.py` — usa el puerto `PORT` de Railway y deriva el webhook de
  `RAILWAY_PUBLIC_DOMAIN` (no hay que pegar la URL a mano).
- `Procfile` — comando de arranque: `web: python main.py`.
- `.python-version` — fija Python 3.12.
- `.railwayignore` — evita subir `.venv/`, `redis/` (binarios Windows), `.env`, etc.
- `requirements.txt` — `behemot-framework[voice]` + `uvicorn`.
- `stock-*.csv` — la planilla SÍ se sube (el loader toma la más nueva).

---

## Paso a paso

Parado en la carpeta del proyecto (`C:\Users\Pedro\Desktop\mi_asistente2`):

### 1. Crear el proyecto
```
railway init
```
Elegí un nombre, p.ej. `ferrebot-demo`. Esto vincula esta carpeta al proyecto.

### 2. Agregar Redis (memoria de conversación)
```
railway add
```
Elegí **Redis** (base de datos administrada). Queda en el mismo proyecto.

### 3. Primer deploy (crea el servicio)
```
railway up
```
Sube el código y construye. La primera vez puede quedar sin arrancar del todo
hasta cargar las variables (paso 5) y el dominio (paso 4). Es normal.

### 4. Generar el dominio público
```
railway domain
```
Te da algo como `https://ferrebot-demo-production.up.railway.app`.
Esto habilita `RAILWAY_PUBLIC_DOMAIN`, de donde `main.py` arma el webhook solo.

### 5. Cargar las variables de entorno
En el **panel web** de Railway (servicio → pestaña *Variables*) es lo más cómodo,
sobre todo para la referencia de Redis. Cargá:

| Variable | Valor |
|---|---|
| `GPT_API_KEY` | tu clave de OpenAI (la del `.env`) |
| `TELEGRAM_TOKEN` | el token del bot (@BotFather) |
| `TELEGRAM_WEBHOOK_SECRET` | el string aleatorio del `.env` |
| `REDIS_URL` | **referencia** → `${{Redis.REDIS_URL}}` (autocompleta en el panel) |
| `HANDOFF_API_KEY` | (opcional, si usás handoff) del `.env` |
| `HANDOFF_WEBHOOK_URL` | (opcional) `https://behemot.net/api/v1/handoff/` |
| `HANDOFF_WEBHOOK_SECRET` | (opcional) del `.env` |
| `HANDOFF_TRIGGERS` | (opcional) `quiero hablar con una persona,asesor,presupuesto en pdf,...` |

⚠️ **NO** setees `TELEGRAM_WEBHOOK_URL` ni `HANDOFF_CALLBACK_URL`: `main.py` las
deriva del dominio de Railway. (Si las ponés con la URL vieja de ngrok, el bot
apuntaría a un túnel muerto.)

Por CLI también se puede (una por una):
```
railway variables --set "GPT_API_KEY=..." --set "TELEGRAM_TOKEN=..." --set "TELEGRAM_WEBHOOK_SECRET=..."
```
La referencia `${{Redis.REDIS_URL}}` conviene hacerla desde el panel.

### 6. Re-deploy para que tome todo
```
railway up
```
Ahora arranca con las variables + dominio → **registra el webhook solo** contra
`https://<tu-dominio>/webhook`.

### 7. Verificar
```
railway logs
```
Buscá:
- `✅ Redis configurado y funcionando correctamente`
- `Webhook de Telegram configurado: https://<tu-dominio>/webhook`
- `Uvicorn running on http://0.0.0.0:<PORT>`

Y en Telegram, escribile a **@Behemot_ia_bot**: *"necesito 2 martillos y 3 dilurras bidón"*.

---

## Notas

- **Un solo webhook por bot:** al deployar en Railway, el bot deja de apuntar a
  ngrok y pasa a Railway. Si querés volver a probar en local, `start.ps1` vuelve a
  apuntarlo a ngrok (y viceversa).
- **Actualizar el stock:** subí un `stock*.csv` nuevo y volvé a `railway up`; el
  loader toma automáticamente el más reciente. (Más adelante se puede mejorar para
  cargarlo sin re-deploy, p.ej. desde un bucket.)
- **Seguridad del filtro:** para activar `SAFETY_LEVEL: medium` real, agregá el
  extra `behemot-framework[rag]` en `requirements.txt`.
- **Costos:** Railway cobra por uso; una demo chica entra en el plan gratuito/starter.
