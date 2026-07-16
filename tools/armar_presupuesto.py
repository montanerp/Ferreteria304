"""Tool: armar_presupuesto.

Recibe el pedido del cliente (varios articulos con cantidades), busca cada
uno en el catalogo y devuelve un presupuesto detallado: cantidad x precio
unitario = subtotal, mas el total. Avisa faltantes y stock insuficiente.
"""

import re

from behemot_framework.tooling import tool, Param

from tools.stock_data import buscar, formato_precio


def _parsear_items(pedido: str):
    """Convierte el texto del pedido en una lista de (cantidad, descripcion).

    Cada item se separa por salto de linea o ';'. Formatos aceptados por item:
        '3 x martillo'   '3x martillo'   '3 martillo'
        'martillo x 3'   'martillo'      (cantidad por defecto = 1)
    """
    items = []
    partes = re.split(r"[;\n]+", pedido or "")
    for parte in partes:
        texto = parte.strip(" \t-•*")
        if not texto:
            continue

        cantidad = 1.0
        # Cantidad al inicio:  "3 x martillo" / "3x martillo" / "3 martillo"
        m = re.match(r"^(\d+(?:[.,]\d+)?)\s*[xX*]?\s+(.+)$", texto)
        if m:
            cantidad = float(m.group(1).replace(",", "."))
            desc = m.group(2).strip()
        else:
            # Cantidad al final:  "martillo x 3"
            m = re.match(r"^(.+?)\s*[xX]\s*(\d+(?:[.,]\d+)?)$", texto)
            if m:
                cantidad = float(m.group(2).replace(",", "."))
                desc = m.group(1).strip()
            else:
                desc = texto
        if desc:
            items.append((cantidad, desc))
    return items


@tool(
    name="armar_presupuesto",
    description=(
        "Arma un presupuesto detallado a partir del pedido del cliente. "
        "Pasá en 'pedido' cada articulo en una linea separada (o separados por ';') "
        "con el formato 'cantidad x descripcion', por ejemplo: "
        "'2 x martillo carpintero; 3 x pintura latex 4l; 1 x taladro'. "
        "Devuelve cada item con cantidad, precio unitario, subtotal y el total, "
        "avisando los que no se encontraron o no tienen stock suficiente."
    ),
    params=[
        Param(
            name="pedido",
            type_="string",
            description=(
                "Lista de articulos pedidos, uno por linea o separados por ';', "
                "en formato 'cantidad x descripcion'."
            ),
            required=True,
        )
    ],
)
async def armar_presupuesto(args: dict):
    pedido = (args.get("pedido") or "").strip()
    if not pedido:
        return "Indicá qué articulos querés presupuestar."

    items = _parsear_items(pedido)
    if not items:
        return "No pude interpretar el pedido. Escribí por ejemplo: '2 x martillo; 3 x tornillo 4x40'."

    lineas = ["🧾 *Presupuesto*", ""]
    total = 0.0
    no_encontrados = []
    sin_stock = []

    for cantidad, desc in items:
        resultados = buscar(desc, limite=1)
        if not resultados:
            no_encontrados.append(desc)
            lineas.append(f"❓ {desc} — no se encontró en el catálogo")
            continue

        p = resultados[0]
        subtotal = cantidad * p.precio
        total += subtotal
        cant_txt = f"{cantidad:g}"
        lineas.append(
            f"• {cant_txt} x [{p.codigo}] {p.detalle}\n"
            f"    {cant_txt} × {formato_precio(p.precio)} = {formato_precio(subtotal)}"
        )
        if p.stock <= 0:
            sin_stock.append(p.detalle)
            lineas.append("    ⚠️ Sin stock disponible (a pedido)")
        elif p.stock < cantidad:
            lineas.append(f"    ⚠️ Stock insuficiente: sólo hay {p.stock:g}")

    lineas.append("")
    lineas.append(f"*TOTAL: {formato_precio(total)}*")

    if no_encontrados:
        lineas.append("")
        lineas.append("No se encontraron: " + ", ".join(no_encontrados))
    if sin_stock:
        lineas.append("Sin stock (se pueden encargar): " + ", ".join(sin_stock))

    lineas.append("")
    lineas.append("_Presupuesto estimado sujeto a confirmación. Precios finales._")
    return "\n".join(lineas)
