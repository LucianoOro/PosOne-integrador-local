"""Declaraciones de funciones para Gemini Function Calling.

Define las funciones que el modelo Gemini puede invocar para
interactuar con el sistema POS: consultar stock, precios, clientes,
generar cotizaciones, etc.
"""

from google.genai import types


SYSTEM_INSTRUCTION = (
    "Sos un asistente de ventas para PosONE, un sistema POS argentino. "
    "Respondés en español rioplatense, de forma cordial pero profesional.\n\n"
    "REGLAS ABSOLUTAS:\n"
    "1. NUNCA inventes datos. SIEMPRE llamá a una función para obtener información real.\n"
    "2. SIEMPRE llamá a una función antes de responder. No respondas sin datos del sistema.\n"
    "3. Tenés acceso TOTAL a todos los datos through las funciones. NUNCA digas que no podés "
    "acceder a datos, que necesitás un número de teléfono, o que no tenés permisos.\n"
    "4. Si el cliente pide algo, ACTUÁ directamente. No pidas confirmación. Llamá la función y respondé con los datos reales.\n\n"
    "MAPEO DE CONSULTAS → FUNCIONES:\n"
    "- Buscar productos por nombre → buscar_articulos(query)\n"
    "- Stock de un artículo → consultar_stock(codigo)\n"
    "- Precio de un artículo → consultar_precio(codigo, lista)\n"
    "- Buscar cliente → buscar_clientes(query)\n"
    "- Cotizaciones pendientes → cotizaciones_pendientes()\n"
    "- Estado de caja → consultar_caja()\n"
    "- Facturas/comprobantes → listar_comprobantes(tipo, caja_id)\n"
    "- Detalle de un comprobante → ver_comprobante(comprobante_id)\n"
    "- Facturas de la caja actual → listar_facturas_caja()\n"
    "- Qué se vendió hoy → listar_facturas_caja()\n"
    "- Generar cotización → generar_cotizacion(cliente_id, items)\n"
    "- Convertir cotización a factura → convertir_cotizacion(cotizacion_id, tipo_factura)\n"
    "- Bloquear artículo → bloquear_articulo(codigo)\n"
    "- Desbloquear artículo → desbloquear_articulo(codigo)\n\n"
    "ESTILO:\n"
    "- Usá español rioplatense: 'vos', 'tenés', 'buscá', 'podés'.\n"
    "- Respondé con los datos exactos que devuelven las funciones, sin agregar información inventada.\n"
    "- Si una función devuelve error o sin resultados, decilo claramente al usuario.\n"
    "- Si el cliente pregunta por algo que no cubren las funciones, explicá qué sí podés hacer."
)

MODEL_NAME = "gemini-3.1-flash-lite-preview"

# Cadena de modelos fallback: si el principal falla (429/503/quota), prueba el siguiente
# Los modelos 3.x con thought_signature errors caen automáticamente al siguiente modelo.
MODEL_FALLBACK_CHAIN = [
    "gemini-3.1-flash-lite-preview",  # Cuota disponible, function calling
    "gemini-2.5-flash",               # Mejor function calling, cuota limitada
    "gemini-2.5-flash-lite",          # Más rápido, más cuota
    "gemini-2.0-flash",               # Estable, buena cuota gratuita
]


def get_function_declarations() -> list[types.Tool]:
    """Retorna las herramientas (tools) con las declaraciones de funciones
    para que Gemini pueda invocarlas durante la conversación.
    """
    funciones = [
        types.FunctionDeclaration(
            name="buscar_articulos",
            description=(
                "Busca artículos por nombre, código, código de barra o código rápido. "
                "Útil cuando el cliente pregunta por productos disponibles."
            ),
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "query": types.Schema(
                        type="STRING",
                        description="Texto a buscar (nombre, código, barra o rápido)",
                    ),
                },
                required=["query"],
            ),
        ),
        types.FunctionDeclaration(
            name="consultar_stock",
            description=(
                "Consulta el stock actual de un artículo específico por su código. "
                "Retorna información completa del artículo incluyendo stock y estado."
            ),
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "codigo": types.Schema(
                        type="STRING",
                        description="Código del artículo",
                    ),
                },
                required=["codigo"],
            ),
        ),
        types.FunctionDeclaration(
            name="consultar_precio",
            description=(
                "Consulta el precio de un artículo. Se puede consultar precio público "
                "o mayorista según la lista indicada."
            ),
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "codigo": types.Schema(
                        type="STRING",
                        description="Código del artículo",
                    ),
                    "lista": types.Schema(
                        type="STRING",
                        description=(
                            "Lista de precios: 'publico' o 'mayorista'. "
                            "Por defecto 'publico'."
                        ),
                    ),
                },
                required=["codigo"],
            ),
        ),
        types.FunctionDeclaration(
            name="buscar_clientes",
            description=(
                "Busca clientes por razón social o CUIT. "
                "Retorna lista de clientes que coinciden con la búsqueda."
            ),
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "query": types.Schema(
                        type="STRING",
                        description="Texto a buscar en razón social o CUIT",
                    ),
                },
                required=["query"],
            ),
        ),
        types.FunctionDeclaration(
            name="cotizaciones_pendientes",
            description=(
                "Lista cotizaciones pendientes (no convertidas a factura). "
                "Opcionalmente filtra por cliente."
            ),
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "cliente_id": types.Schema(
                        type="INTEGER",
                        description="ID del cliente para filtrar (opcional, null para todas)",
                    ),
                },
            ),
        ),
        types.FunctionDeclaration(
            name="convertir_cotizacion",
            description=(
                "Convierte una cotización en factura. "
                "Se debe indicar el tipo de factura (FACTURA_A, FACTURA_B, FACTURA_C)."
            ),
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "cotizacion_id": types.Schema(
                        type="INTEGER",
                        description="ID de la cotización a convertir",
                    ),
                    "tipo_factura": types.Schema(
                        type="STRING",
                        description=(
                            "Tipo de factura: FACTURA_A, FACTURA_B o FACTURA_C. "
                            "Por defecto FACTURA_B."
                        ),
                    ),
                },
                required=["cotizacion_id"],
            ),
        ),
        types.FunctionDeclaration(
            name="bloquear_articulo",
            description=(
                "Bloquea un artículo de emergencia. "
                "El artículo queda con estado BLOQUEADO y no se puede facturar."
            ),
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "codigo": types.Schema(
                        type="STRING",
                        description="Código del artículo a bloquear",
                    ),
                },
                required=["codigo"],
            ),
        ),
        types.FunctionDeclaration(
            name="desbloquear_articulo",
            description="Desbloquea un artículo previamente bloqueado para permitir su venta nuevamente.",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "codigo": types.Schema(
                        type="STRING",
                        description="Código del artículo a desbloquear",
                    ),
                },
                required=["codigo"],
            ),
        ),
        types.FunctionDeclaration(
            name="generar_cotizacion",
            description=(
                "Genera una cotización para un cliente con los items indicados. "
                "La cotización es un comprobante que NO afecta stock. "
                "Se necesita el ID del cliente y una lista de items con código y cantidad."
            ),
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "cliente_id": types.Schema(
                        type="INTEGER",
                        description="ID del cliente",
                    ),
                    "items": types.Schema(
                        type="ARRAY",
                        items=types.Schema(
                            type="OBJECT",
                            properties={
                                "codigo": types.Schema(
                                    type="STRING",
                                    description="Código del artículo",
                                ),
                                "cantidad": types.Schema(
                                    type="INTEGER",
                                    description="Cantidad solicitada",
                                ),
                            },
                            required=["codigo", "cantidad"],
                        ),
                        description="Lista de items con código y cantidad",
                    ),
                },
                required=["cliente_id", "items"],
            ),
        ),
        types.FunctionDeclaration(
            name="consultar_caja",
            description=(
                "Consulta el estado de la caja actual (si hay una abierta). "
                "Retorna información de la caja abierta o indica que no hay ninguna."
            ),
            parameters=types.Schema(
                type="OBJECT",
                properties={},
            ),
        ),
        types.FunctionDeclaration(
            name="listar_comprobantes",
            description=(
                "Lista comprobantes (facturas o cotizaciones) por tipo o por caja. "
                "Útil para ver qué se facturó hoy, ver facturas de un tipo específico, "
                "o consultar qué se vendió en la caja actual."
            ),
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "tipo": types.Schema(
                        type="STRING",
                        description=(
                            "Tipo de comprobante: FACTURA_A, FACTURA_B, FACTURA_C, COTIZACION. "
                            "Si no se especifica, lista facturas B por defecto."
                        ),
                    ),
                    "caja_id": types.Schema(
                        type="INTEGER",
                        description="ID de la caja para filtrar comprobantes de esa caja (opcional).",
                    ),
                },
            ),
        ),
        types.FunctionDeclaration(
            name="ver_comprobante",
            description=(
                "Obtiene el detalle completo de un comprobante (factura o cotización) por su ID. "
                "Muestra items, formas de pago, totales, cliente, etc."
            ),
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "comprobante_id": types.Schema(
                        type="INTEGER",
                        description="ID del comprobante a consultar",
                    ),
                },
                required=["comprobante_id"],
            ),
        ),
        types.FunctionDeclaration(
            name="listar_facturas_caja",
            description=(
                "Lista todas las facturas de la caja abierta actual. "
                "Útil para saber qué se vendió en la jornada y hacer cierre de caja."
            ),
            parameters=types.Schema(
                type="OBJECT",
                properties={},
            ),
        ),
    ]

    return [types.Tool(function_declarations=funciones)]