"""Tool: buscar_producto.

Permite al agente consultar el catalogo de la ferreteria (precio y stock)
antes de armar un presupuesto o cuando el cliente pregunta por un articulo.
"""

from behemot_framework.tooling import tool, Param

from tools.stock_data import buscar, formato_precio


@tool(
    name="buscar_producto",
    description=(
        "Busca articulos en el catalogo de la ferreteria por nombre/descripcion "
        "o por codigo. Devuelve codigo, descripcion, precio unitario y stock "
        "disponible. Usala cuando el cliente pregunta si hay un producto, por su "
        "precio, o cuando no estas seguro del articulo exacto antes de presupuestar."
    ),
    params=[
        Param(
            name="consulta",
            type_="string",
            description="Texto a buscar (ej. 'martillo', 'pintura latex 4l') o el codigo exacto.",
            required=True,
        )
    ],
)
async def buscar_producto(args: dict):
    consulta = (args.get("consulta") or "").strip()
    if not consulta:
        return "Indicá qué producto querés buscar."

    resultados = buscar(consulta, limite=8)
    if not resultados:
        return (
            f"No encontré productos que coincidan con '{consulta}'. "
            "Probá con otra descripción o un código."
        )

    lineas = [f"Encontré {len(resultados)} resultado(s) para '{consulta}':"]
    for p in resultados:
        disp = f"{p.stock:g} disp." if p.stock > 0 else "SIN STOCK"
        lineas.append(
            f"- [{p.codigo}] {p.detalle} — {formato_precio(p.precio)} ({disp})"
        )
    return "\n".join(lineas)
