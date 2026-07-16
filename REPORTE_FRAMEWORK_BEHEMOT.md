# Reporte para el equipo de Behemot Framework

Hallazgos surgidos al construir la **demo Ferretería** (Telegram + presupuestos)
sobre `behemot-framework` **v0.6.26**. El framework **no fue modificado**; se
documentan acá para que el equipo evalúe las adecuaciones que correspondan.

---

## 1. (Bloqueante) No se puede enviar un PDF / documento por Telegram desde una tool

**Contexto:** la ferretería pide, como caso especial, poder recibir el presupuesto
en PDF por Telegram. Hoy no es posible sin modificar el framework, por dos motivos
combinados:

### 1.a — El webhook de Telegram no propaga `session_context` a las tools
En `behemot_framework/factory.py` (~línea 298) el flujo de Telegram llama:

```python
respuesta = await self.asistente.generar_respuesta(str(chat_id), texto, imagen_path)
```

…sin pasar `session_context`. En cambio, el flujo de **WhatsApp** (~líneas 808‑810) sí lo hace:

```python
respuesta = await self.asistente.generar_respuesta(
    phone_number, texto, imagen_path,
    session_context={ "phone_number": phone_number, "whatsapp_connector": self.whatsapp_connector, ... },
)
```

Como `tooling.call_tool` solo inyecta el `ToolContext` (`agente`) cuando hay
`session_context`, **una tool ejecutada desde Telegram nunca recibe el `chat_id`
ni el connector**. Tampoco es accesible por otra vía: `observability.get_current_trace()`
devuelve `None` salvo que Langfuse esté habilitado, así que no sirve como fuente
del `chat_id`.

**Fix sugerido:** en el webhook de Telegram, pasar `session_context` de forma
análoga a WhatsApp, por ejemplo:

```python
respuesta = await self.asistente.generar_respuesta(
    str(chat_id), texto, imagen_path,
    session_context={
        "chat_id": chat_id,
        "telegram_connector": self.telegram_connector,
    },
)
```

### 1.b — `TelegramConnector` no puede enviar documentos
`behemot_framework/connectors/telegram_connector.py` expone `enviar_mensaje`
(texto), `enviar_voz`, `enviar_accion`, pero **no un método para enviar archivos**
(equivalente a la Bot API `sendDocument`).

**Fix sugerido:** agregar un método, p.ej.:

```python
def enviar_documento(self, chat_id: int, file_path: str, caption: str = "") -> bool:
    endpoint = f"{self.base_url}/sendDocument"
    with open(file_path, "rb") as fh:
        files = {"document": fh}
        data = {"chat_id": chat_id, "caption": caption}
        resp = requests.post(endpoint, data=data, files=files, timeout=30)
    return resp.ok
```

**Impacto:** con 1.a + 1.b, una tool `presupuesto_pdf` podría declarar `agente`
como primer parámetro, obtener `agente.chat_id` + `agente.telegram_connector`,
generar el PDF y enviarlo. Hoy no es posible.

**Workaround en la demo:** el pedido de PDF se trata como *pedido especial* y se
**deriva a un asesor humano** (handoff), en lugar de generar/enviar el PDF el bot.

---

## 2. (Limitación) `Param` no soporta tipos compuestos (array / object / enum)

En `behemot_framework/tooling.py`, `Param.to_dict()` solo emite:

```python
def to_dict(self):
    return {"type": self.type, "description": self.description}
```

No permite describir `items` (de un `array`), propiedades de un `object`, ni
`enum`. Con `jsonschema` activo, declarar un parámetro `array` genera un JSON
Schema sin `items`, que algunos modelos/validadores de OpenAI rechazan.

**Impacto:** una tool que naturalmente recibiría una lista (p.ej. los ítems de un
presupuesto: `[{producto, cantidad}, ...]`) no puede declararla con tipos.

**Workaround en la demo:** las tools usan parámetros `string` y parsean adentro
(ej.: `armar_presupuesto(pedido="2 x martillo; 3 x pintura latex 4l")`).

**Sugerencia:** permitir en `Param` campos opcionales `items`, `properties`,
`enum` que se reflejen en `to_dict()`.

---

## 3. (Menor / UX) Aviso de SAFETY_LEVEL con el extra `[voice]`

Instalando `behemot-framework[voice]` (sin `[rag]`), al arrancar con
`SAFETY_LEVEL: "medium"` aparece:

```
⚠️  SAFETY_LEVEL='medium' pero langchain-openai no está instalado ... Filtro de seguridad DESACTIVADO.
```

Es decir, el filtro queda **silenciosamente desactivado** pese a pedir `medium`.
Sugerencia: documentar la dependencia (o incluir el requisito del filtro en más
extras), o fallar de forma más explícita si se pide un `SAFETY_LEVEL` activo sin
las dependencias necesarias.

---

## 4. (Robustez) El webhook de Telegram no de-duplica por `update_id`

`factory.py` ya hace ACK 200 inmediato y procesa en segundo plano (bien), pero no
guarda ni compara el `update_id`. Si Telegram reentrega un update (algo esperable
ante un blip de red / túnel inestable, o un reintento en vuelo), el handler lo
procesa de nuevo y el bot responde dos veces al mismo mensaje (observado en la demo
con ngrok: un `Read timeout expired` gatilló un `/start`/`Hola` duplicado).

**Sugerencia:** de-duplicar por `update_id` (p.ej. `SET NX EX` en Redis) y descartar
los ya vistos antes de procesar. Alternativamente, exponer un hook/middleware para
que la app lo haga sin parchear el framework.

**Nota:** en hosting estable (Railway) el disparador (read timeouts de ngrok)
desaparece, por lo que en la práctica casi no se observa; igual la de-duplicación
haría el webhook robusto ante cualquier reentrega.

---

_Versión analizada: behemot-framework 0.6.26. Demo: `mi_asistente2` (ferretería)._
