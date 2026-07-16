"""Carga y busqueda sobre la planilla de stock de la ferreteria.

Este modulo NO es una tool en si mismo: contiene los helpers que usan
`buscar_producto` y `armar_presupuesto`. Se importa desde esos modulos.

Formato de la planilla (CSV exportado de la ferreteria):
    - Delimitador: ';'
    - Columnas:  Codigo ; Detalle ; Stock ; Precio
    - Decimal:   '.'  (ej. Precio=19359.04, Stock=19.37 -> stock fraccionario)
    - Encoding:  cp1252 / latin-1 (export de Excel en espanol)

La ferreteria puede "cargar una planilla nueva" simplemente dejando un
archivo `stock*.csv` en la carpeta del proyecto: se toma SIEMPRE el mas
reciente (por fecha de modificacion). Se puede forzar una ruta con la
variable de entorno STOCK_CSV_PATH.
"""

from __future__ import annotations

import csv
import glob
import logging
import os
import re
import time
import unicodedata
from dataclasses import dataclass
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

# Raiz del proyecto = carpeta padre de tools/
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@dataclass
class Producto:
    codigo: str
    detalle: str
    stock: float
    precio: float
    detalle_norm: str  # detalle normalizado (sin acentos, mayusculas) para buscar


# --- Cache simple en memoria; se recarga si cambia el archivo -----------------
_cache: List[Producto] = []
_cache_path: Optional[str] = None
_cache_mtime: float = 0.0


def _normalizar(texto: str) -> str:
    """Mayusculas, sin acentos, sin puntuacion, espacios colapsados."""
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = texto.upper()
    texto = re.sub(r"[^A-Z0-9 ]+", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def _to_float(valor: str) -> float:
    """Convierte '19359.04' / '14,00' / '' a float de forma tolerante."""
    if valor is None:
        return 0.0
    v = valor.strip()
    if not v:
        return 0.0
    # Soporta tanto '.' (formato de esta planilla) como ',' decimal por las dudas.
    if "," in v and "." in v:
        v = v.replace(".", "").replace(",", ".")  # 1.234,56 -> 1234.56
    elif "," in v:
        v = v.replace(",", ".")
    try:
        return float(v)
    except ValueError:
        return 0.0


def _resolver_ruta_csv() -> Optional[str]:
    """Ruta del CSV a usar: STOCK_CSV_PATH si esta seteada, si no el stock*.csv mas nuevo."""
    env_path = os.getenv("STOCK_CSV_PATH")
    if env_path and os.path.isfile(env_path):
        return env_path
    candidatos = glob.glob(os.path.join(_BASE_DIR, "stock*.csv"))
    candidatos += glob.glob(os.path.join(_BASE_DIR, "data", "stock*.csv"))
    if not candidatos:
        return None
    # El mas reciente por fecha de modificacion.
    return max(candidatos, key=os.path.getmtime)


def _leer_csv(ruta: str) -> List[Producto]:
    productos: List[Producto] = []
    # Cadena de encodings: utf-8 primero, luego latin-1 (nunca falla al decodificar).
    # 'cp1252' se evita como intermedio porque tiene bytes indefinidos que abortan
    # la lectura a mitad de archivo. Cada intento reinicia la lista.
    for enc in ("utf-8-sig", "latin-1"):
        try:
            productos = []
            with open(ruta, "r", encoding=enc, newline="") as fh:
                reader = csv.DictReader(fh, delimiter=";")
                for fila in reader:
                    detalle = (fila.get("Detalle") or "").strip()
                    if not detalle:
                        continue
                    productos.append(
                        Producto(
                            codigo=(fila.get("Codigo") or "").strip(),
                            detalle=detalle,
                            stock=_to_float(fila.get("Stock")),
                            precio=_to_float(fila.get("Precio")),
                            detalle_norm=_normalizar(detalle),
                        )
                    )
            logger.info("Stock cargado (%s productos) desde %s [%s]", len(productos), ruta, enc)
            return productos
        except UnicodeDecodeError:
            continue
    logger.error("No se pudo decodificar el CSV de stock: %s", ruta)
    return productos


def cargar_stock() -> List[Producto]:
    """Devuelve la lista de productos, recargando si el archivo cambio."""
    global _cache, _cache_path, _cache_mtime
    ruta = _resolver_ruta_csv()
    if not ruta:
        logger.warning("No se encontro ninguna planilla stock*.csv en %s", _BASE_DIR)
        return []
    mtime = os.path.getmtime(ruta)
    if ruta != _cache_path or mtime != _cache_mtime or not _cache:
        _cache = _leer_csv(ruta)
        _cache_path = ruta
        _cache_mtime = mtime
    return _cache


# Palabras muy comunes que no aportan a la busqueda (y generan falsos positivos).
_STOPWORDS = {
    "DE", "DEL", "LA", "EL", "LOS", "LAS", "PARA", "POR", "CON", "SIN",
    "Y", "A", "EN", "X", "UN", "UNA", "AL", "SU", "ARTICULO", "ARTICULOS",
}


def _tokens_utiles(texto: str) -> List[str]:
    """Tokens normalizados relevantes: descarta stopwords y tokens de 1 caracter."""
    return [
        t for t in _normalizar(texto).split()
        if len(t) >= 2 and t not in _STOPWORDS
    ]


def _puntuar(query_tokens: List[str], prod: Producto) -> int:
    """Score = cantidad de tokens de la consulta presentes en el detalle."""
    return sum(1 for t in query_tokens if t in prod.detalle_norm)


def buscar(consulta: str, limite: int = 8) -> List[Producto]:
    """Busca productos por codigo exacto o por coincidencia de texto en Detalle.

    Ranking: mas tokens coincidentes primero; a igualdad, prioriza los que
    tienen stock disponible y luego el detalle mas corto (match mas especifico).
    """
    productos = cargar_stock()
    if not productos:
        return []

    consulta = (consulta or "").strip()
    if not consulta:
        return []

    # 1) Match exacto por codigo.
    exactos = [p for p in productos if p.codigo == consulta]
    if exactos:
        return exactos[:limite]

    # 2) Match por texto (tokens).
    tokens = _tokens_utiles(consulta)
    if not tokens:
        return []

    # Para aceptar un producto exigimos que coincida la MAYORIA de los tokens
    # utiles de la consulta. Asi 'articulo inexistente xyz' (1 de 3) no matchea,
    # pero 'aceite madera 900' (3 de 3) si. Consultas de 1-2 tokens: basta 1.
    umbral = max(1, (len(tokens) + 1) // 2)

    candidatos: List[Tuple[int, Producto]] = []
    for p in productos:
        score = _puntuar(tokens, p)
        if score >= umbral:
            candidatos.append((score, p))

    candidatos.sort(
        key=lambda sp: (-sp[0], 0 if sp[1].stock > 0 else 1, len(sp[1].detalle))
    )
    return [p for _, p in candidatos[:limite]]


def formato_precio(valor: float) -> str:
    """Formatea 19359.04 -> '$19.359,04' (estilo AR)."""
    entero, dec = f"{valor:,.2f}".split(".")
    entero = entero.replace(",", ".")
    return f"${entero},{dec}"
