"""Servicio de integración con Google Gemini AI.

Procesa mensajes de WhatsApp a través del modelo Gemini con
function calling, permitiendo al asistente virtual interactuar
con el sistema POS de forma natural.
"""

import json
import logging
import os
from dataclasses import dataclass, field

from google import genai
from google.genai import types

from app.infrastructure.ai.gemini_functions import (
    MODEL_NAME,
    MODEL_FALLBACK_CHAIN,
    SYSTEM_INSTRUCTION,
    get_function_declarations,
)

# Re-export para uso externo
__all__ = ["GeminiEmptyResponseError", "GeminiResult", "GeminiService"]
from app.infrastructure.database.connection import SessionLocal
from app.infrastructure.database.repositories.articulo_repo import (
    SqlAlchemyArticuloRepository,
)
from app.infrastructure.database.repositories.caja_repo import SqlAlchemyCajaRepository
from app.infrastructure.database.repositories.cliente_repo import (
    SqlAlchemyClienteRepository,
)
from app.infrastructure.database.repositories.comprobante_repo import (
    SqlAlchemyComprobanteRepository,
)
from app.infrastructure.database.repositories.forma_pago_repo import (
    SqlAlchemyFormaPagoRepository,
)
from app.infrastructure.database.repositories.rubro_repo import SqlAlchemyRubroRepository
from app.infrastructure.database.repositories.vendedor_repo import (
    SqlAlchemyVendedorRepository,
)
from app.application.use_cases.articulo_use_case import ArticuloUseCase
from app.application.use_cases.caja_use_case import CajaUseCase
from app.application.use_cases.cliente_use_case import ClienteUseCase
from app.application.use_cases.comprobante_use_case import ComprobanteUseCase
from app.domain.entities.entities import (
    Comprobante,
    DetalleComprobante,
    ComprobanteFormaPago,
)
from app.domain.value_objects.enums import TipoComprobante

logger = logging.getLogger(__name__)


class GeminiEmptyResponseError(Exception):
    """Raised when Gemini returns a response with no function calls and no text."""
    pass


@dataclass
class GeminiResult:
    """Resultado del procesamiento de un mensaje por Gemini."""
    text: str
    cotizacion_id: int | None = None
    comprobante_id: int | None = None


class GeminiService:
    """Servicio de IA que procesa mensajes usando Gemini con function calling.

    Flujo:
    1. Recibe mensaje del usuario
    2. Envía a Gemini con las declaraciones de funciones
    3. Si Gemini invoca una función → ejecuta el caso de uso correspondiente
    4. Envía el resultado de vuelta a Gemini para formatear la respuesta
    5. Retorna la respuesta en lenguaje natural
    """

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        self._client: genai.Client | None = None
        self._tools = get_function_declarations()
        self._config = types.GenerateContentConfig(
            tools=self._tools,
            system_instruction=SYSTEM_INSTRUCTION,
        )

    @property
    def client(self) -> genai.Client:
        """Lazy initialization del cliente Gemini."""
        if self._client is None:
            if not self._api_key:
                raise ValueError("GEMINI_API_KEY no configurado")
            self._client = genai.Client(api_key=self._api_key)
        return self._client

    @property
    def is_configured(self) -> bool:
        """Verifica si la API key de Gemini está configurada."""
        return bool(self._api_key)

    def process_message(
        self, phone_number: str, message: str, context: dict | None = None
    ) -> GeminiResult:
        """Procesa un mensaje a través de Gemini AI con cadena de modelos fallback.

        Si el modelo principal falla con 429 (quota), intenta con el siguiente
        modelo en la cadena. Si todos fallan, lanza excepción.

        Args:
            phone_number: Número de teléfono del remitente.
            message: Texto del mensaje recibido.
            context: Contexto adicional (historial, preferencias, etc.).

        Returns:
            GeminiResult con el texto de respuesta y metadata de side effects.
        """
        # Construir el historial de conversación
        contents = self._build_contents(phone_number, message, context)

        # Probar modelos en cadena hasta que uno funcione
        last_error = None
        for model in MODEL_FALLBACK_CHAIN:
            try:
                logger.info("Intentando con modelo: %s", model)
                return self._process_with_model(model, contents)
            except GeminiEmptyResponseError as e:
                logger.warning("Modelo %s devolvió respuesta vacía, probando siguiente...", model)
                last_error = e
                continue
            except Exception as e:
                error_msg = str(e)
                is_retryable = (
                    "429" in error_msg
                    or "RESOURCE_EXHAUSTED" in error_msg
                    or "quota" in error_msg.lower()
                    or "503" in error_msg
                    or "UNAVAILABLE" in error_msg
                    or "high demand" in error_msg.lower()
                    or "INVALID_ARGUMENT" in error_msg
                    or "thought_signature" in error_msg
                    or "403" in error_msg
                    or "PERMISSION_DENIED" in error_msg
                )
                if is_retryable:
                    logger.warning("Error retryable en modelo %s, probando siguiente... (%s)", model, error_msg[:80])
                    last_error = e
                    continue  # Try next model
                else:
                    # Error no retryable → relanzar
                    raise

        # Todos los modelos fallaron
        if last_error:
            raise last_error

    def _process_with_model(
        self, model: str, contents: list[types.Content]
    ) -> GeminiResult:
        """Procesa un mensaje con un modelo específico.

        Args:
            model: Nombre del modelo Gemini a usar.
            contents: Historial de conversación ya construido.

        Returns:
            GeminiResult con el texto de respuesta y metadata de side effects.
        """
        # Side effects tracker
        side_effects: dict = {}

        # Primera llamada a Gemini (con manejo de errores de cuota)
        try:
            response = self.client.models.generate_content(
                model=model,
                contents=contents,
                config=self._config,
            )
        except Exception as e:
            error_msg = str(e)
            # Errors that should trigger fallback to next model
            if any(k in error_msg for k in [
                "429", "RESOURCE_EXHAUSTED", "quota", "503", "UNAVAILABLE", "high demand",
                "INVALID_ARGUMENT", "thought_signature", "403", "PERMISSION_DENIED",
            ]):
                # Re-lanzar para que process_message pruebe el siguiente modelo
                raise
            logger.exception("Error inicial en Gemini AI: %s", error_msg)
            return GeminiResult(
                text="Disculpá, tuve un problema para procesar tu mensaje. Intentá de nuevo en un momento."
            )

        # Loop de function calling (máximo 5 iteraciones)
        max_iterations = 5
        for _ in range(max_iterations):
            function_calls, text_parts = self._parse_response(response)

            if not function_calls:
                # No hay llamadas a funciones → respuesta final
                if text_parts:
                    text = "".join(text_parts)
                else:
                    # Empty response — treat as model failure, try next model in fallback chain
                    raise GeminiEmptyResponseError("Gemini devolvió respuesta vacía")
                return GeminiResult(
                    text=text,
                    cotizacion_id=side_effects.get("cotizacion_id"),
                    comprobante_id=side_effects.get("comprobante_id"),
                )

            # Ejecutar funciones y recolectar respuestas
            function_response_parts = []
            for fc in function_calls:
                logger.info("Gemini invocó función: %s(%s)", fc.name, fc.args)
                result = self._execute_function(fc.name, dict(fc.args))
                # Trackear side effects
                if "cotizacion_id" in result:
                    side_effects["cotizacion_id"] = result["cotizacion_id"]
                if "comprobante_id" in result:
                    side_effects["comprobante_id"] = result["comprobante_id"]

                function_response_parts.append(
                    types.Part.from_function_response(
                        name=fc.name,
                        response=result,
                    )
                )

            # Agregar respuesta del modelo y resultados de funciones al historial
            contents.append(response.candidates[0].content)
            contents.append(
                types.Content(role="function", parts=function_response_parts)
            )

            # Llamada siguiente con los resultados
            try:
                response = self.client.models.generate_content(
                    model=model,
                    contents=contents,
                    config=self._config,
                )
            except Exception as e:
                error_msg = str(e)
                if any(k in error_msg for k in [
                    "429", "RESOURCE_EXHAUSTED", "quota", "503", "UNAVAILABLE", "high demand",
                    "INVALID_ARGUMENT", "thought_signature", "403", "PERMISSION_DENIED",
                ]):
                    # Re-lanzar para que process_message pruebe el siguiente modelo
                    raise
                logger.exception("Error en iteración de Gemini: %s", error_msg)
                return GeminiResult(
                    text="Disculpá, tuve un problema intermitente. Intentá de nuevo."
                )

        # Si llegamos aquí, demasiadas iteraciones
        text_parts = self._parse_response(response)[1]
        text = "".join(text_parts) if text_parts else "No pude completar la consulta."
        return GeminiResult(
            text=text,
            cotizacion_id=side_effects.get("cotizacion_id"),
            comprobante_id=side_effects.get("comprobante_id"),
        )

    def _build_contents(
        self, phone_number: str, message: str, context: dict | None
    ) -> list[types.Content]:
        """Construye el historial de conversación para Gemini."""
        contents = []

        # Agregar contexto previo si existe
        if context and context.get("history"):
            for msg in context["history"]:
                role = msg.get("role", "user")
                text = msg.get("text", "")
                contents.append(
                    types.Content(
                        role=role,
                        parts=[types.Part.from_text(text=text)],
                    )
                )

        # Agregar mensaje actual con contexto del número
        prefixed_message = (
            f"[Numero: {phone_number}] {message}" if phone_number else message
        )
        contents.append(
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=prefixed_message)],
            )
        )

        return contents

    def _parse_response(
        self, response
    ) -> tuple[list[types.FunctionCall], list[str]]:
        """Parsea la respuesta de Gemini y separa function calls de texto.

        Returns:
            Tupla (function_calls, text_parts).
        """
        function_calls = []
        text_parts = []

        if not response.candidates:
            logger.warning("Gemini: respuesta sin candidates")
            return function_calls, text_parts

        candidate = response.candidates[0]

        finish_reason = getattr(candidate, "finish_reason", None)
        if finish_reason and str(finish_reason) not in ("STOP", "FinishReason.STOP", "1"):
            logger.warning("Gemini: finish_reason=%s (bloqueado o incompleto)", finish_reason)

        if not candidate.content or not candidate.content.parts:
            logger.warning("Gemini: respuesta sin content.parts")
            return function_calls, text_parts

        for part in candidate.content.parts:
            if hasattr(part, "function_call") and part.function_call:
                function_calls.append(part.function_call)
            elif hasattr(part, "text") and part.text:
                text_parts.append(part.text)

        if not function_calls and not text_parts:
            logger.warning(
                "Gemini: respuesta vacía — 0 function_calls, 0 text_parts, %d parts total. "
                "finish_reason=%s",
                len(candidate.content.parts),
                finish_reason,
            )

        return function_calls, text_parts

    def _execute_function(self, function_name: str, args: dict) -> dict:
        """Ejecuta una función del sistema basada en la llamada de Gemini.

        Cada función crea su propia sesión de BD para garantizar
        transacciones independientes.

        Args:
            function_name: Nombre de la función a ejecutar.
            args: Argumentos de la función (viene de Gemini).

        Returns:
            Dict con el resultado serializable para devolver a Gemini.
        """
        db = SessionLocal()
        try:
            result = self._dispatch_function(function_name, args, db)
            db.commit()
            return result
        except Exception as e:
            db.rollback()
            logger.exception("Error ejecutando función %s: %s", function_name, e)
            return {"error": True, "mensaje": f"Error al ejecutar {function_name}: {str(e)}"}
        finally:
            db.close()

    def _dispatch_function(self, function_name: str, args: dict, db) -> dict:
        """Despacha la ejecución de la función correspondiente.

        Args:
            function_name: Nombre de la función.
            args: Argumentos de la función.
            db: Sesión de base de datos activa.

        Returns:
            Dict con resultado serializable.
        """
        dispatchers = {
            "buscar_articulos": self._buscar_articulos,
            "consultar_stock": self._consultar_stock,
            "consultar_precio": self._consultar_precio,
            "buscar_clientes": self._buscar_clientes,
            "cotizaciones_pendientes": self._cotizaciones_pendientes,
            "convertir_cotizacion": self._convertir_cotizacion,
            "bloquear_articulo": self._bloquear_articulo,
            "desbloquear_articulo": self._desbloquear_articulo,
            "generar_cotizacion": self._generar_cotizacion,
            "consultar_caja": self._consultar_caja,
            "listar_comprobantes": self._listar_comprobantes,
            "ver_comprobante": self._ver_comprobante,
            "listar_facturas_caja": self._listar_facturas_caja,
        }

        handler = dispatchers.get(function_name)
        if not handler:
            return {"error": True, "mensaje": f"Función desconocida: {function_name}"}

        return handler(args, db)

    # ─── Implementaciones de funciones ─────────────────────────────

    def _buscar_articulos(self, args: dict, db) -> dict:
        """Busca artículos por nombre, código, barra o rápido."""
        uc = ArticuloUseCase(
            SqlAlchemyArticuloRepository(db), SqlAlchemyRubroRepository(db)
        )
        query = args.get("query", "")
        articulos = uc.search(query)

        if not articulos:
            return {"resultados": [], "mensaje": f"No encontré artículos para '{query}'."}

        resultados = []
        for a in articulos[:10]:  # Limitar a 10 resultados
            resultados.append({
                "codigo": a.codigo,
                "descripcion": a.descripcion,
                "precio_publico": a.precio_publico,
                "precio_mayorista": a.precio_mayorista,
                "stock_actual": a.stock_actual,
                "inventario_estado": a.inventario_estado.value,
            })

        return {"resultados": resultados, "total": len(articulos)}

    def _consultar_stock(self, args: dict, db) -> dict:
        """Consulta el stock de un artículo específico."""
        uc = ArticuloUseCase(
            SqlAlchemyArticuloRepository(db), SqlAlchemyRubroRepository(db)
        )
        codigo = args.get("codigo", "")
        try:
            articulo = uc.get_by_codigo(codigo)
            return {
                "codigo": articulo.codigo,
                "descripcion": articulo.descripcion,
                "stock_actual": articulo.stock_actual,
                "stock_minimo": articulo.stock_minimo,
                "inventario_estado": articulo.inventario_estado.value,
                "precio_publico": articulo.precio_publico,
                "precio_mayorista": articulo.precio_mayorista,
            }
        except Exception:
            return {"error": True, "mensaje": f"Artículo '{codigo}' no encontrado."}

    def _consultar_precio(self, args: dict, db) -> dict:
        """Consulta el precio de un artículo."""
        uc = ArticuloUseCase(
            SqlAlchemyArticuloRepository(db), SqlAlchemyRubroRepository(db)
        )
        codigo = args.get("codigo", "")
        lista = args.get("lista", "publico").lower()

        try:
            articulo = uc.get_by_codigo(codigo)
            es_mayorista = lista == "mayorista"
            precio = articulo.calcular_precio(es_mayorista)
            return {
                "codigo": articulo.codigo,
                "descripcion": articulo.descripcion,
                "lista": lista,
                "precio": precio,
                "precio_publico": articulo.precio_publico,
                "precio_mayorista": articulo.precio_mayorista,
            }
        except Exception:
            return {"error": True, "mensaje": f"Artículo '{codigo}' no encontrado."}

    def _buscar_clientes(self, args: dict, db) -> dict:
        """Busca clientes por razón social o CUIT."""
        uc = ClienteUseCase(SqlAlchemyClienteRepository(db))
        query = args.get("query", "")
        clientes = uc.search(query)

        if not clientes:
            return {"resultados": [], "mensaje": f"No encontré clientes para '{query}'."}

        resultados = []
        for c in clientes[:10]:
            resultados.append({
                "id": c.id,
                "razon_social": c.razon_social,
                "cuit": c.cuit,
                "condicion_iva": c.condicion_iva.value,
                "telefono": c.telefono,
                "email": c.email,
            })

        return {"resultados": resultados, "total": len(clientes)}

    def _cotizaciones_pendientes(self, args: dict, db) -> dict:
        """Lista cotizaciones pendientes, opcionalmente filtradas por cliente."""
        uc = ComprobanteUseCase(
            repo=SqlAlchemyComprobanteRepository(db),
            caja_repo=SqlAlchemyCajaRepository(db),
            articulo_repo=SqlAlchemyArticuloRepository(db),
            cliente_repo=SqlAlchemyClienteRepository(db),
            vendedor_repo=SqlAlchemyVendedorRepository(db),
            forma_pago_repo=SqlAlchemyFormaPagoRepository(db),
        )
        cotizaciones = uc.listar_cotizaciones_pendientes()

        cliente_id = args.get("cliente_id")
        if cliente_id:
            cotizaciones = [c for c in cotizaciones if c.cliente_id == cliente_id]

        # Resolver nombres para cada cotización
        resultados = []
        for c in cotizaciones[:10]:
            cliente = SqlAlchemyClienteRepository(db).get_by_id(c.cliente_id)
            resultados.append({
                "id": c.id,
                "numero": c.numero,
                "fecha": c.fecha.isoformat() if c.fecha else None,
                "cliente_id": c.cliente_id,
                "cliente_nombre": cliente.razon_social if cliente else "Desconocido",
                "total": c.total,
                "estado": "pendiente",
            })

        return {"resultados": resultados, "total": len(cotizaciones)}

    def _convertir_cotizacion(self, args: dict, db) -> dict:
        """Convierte una cotización en factura."""
        cotizacion_id = args.get("cotizacion_id")
        tipo_factura_str = args.get("tipo_factura", "FACTURA_B")

        if not cotizacion_id:
            return {"error": True, "mensaje": "Se requiere cotizacion_id."}

        # Parsear tipo de factura
        try:
            tipo = TipoComprobante(tipo_factura_str)
        except ValueError:
            tipo = TipoComprobante.FACTURA_B

        uc = ComprobanteUseCase(
            repo=SqlAlchemyComprobanteRepository(db),
            caja_repo=SqlAlchemyCajaRepository(db),
            articulo_repo=SqlAlchemyArticuloRepository(db),
            cliente_repo=SqlAlchemyClienteRepository(db),
            vendedor_repo=SqlAlchemyVendedorRepository(db),
            forma_pago_repo=SqlAlchemyFormaPagoRepository(db),
        )

        try:
            factura = uc.convertir_cotizacion_a_factura(cotizacion_id, tipo)
            cliente = SqlAlchemyClienteRepository(db).get_by_id(factura.cliente_id)
            return {
                "comprobante_id": factura.id,
                "tipo": factura.tipo.value,
                "numero": f"{factura.punto_venta:04d}-{factura.numero:08d}",
                "cliente_nombre": cliente.razon_social if cliente else "Desconocido",
                "total": factura.total,
                "mensaje": (
                    f"Cotización {cotizacion_id} convertida a "
                    f"{factura.tipo.value} N° {factura.punto_venta:04d}-{factura.numero:08d}"
                ),
            }
        except Exception as e:
            return {"error": True, "mensaje": f"Error al convertir cotización: {str(e)}"}

    def _bloquear_articulo(self, args: dict, db) -> dict:
        """Bloquea un artículo de emergencia."""
        uc = ArticuloUseCase(
            SqlAlchemyArticuloRepository(db), SqlAlchemyRubroRepository(db)
        )
        codigo = args.get("codigo", "")

        try:
            articulo = uc.bloquear(codigo)
            return {
                "codigo": articulo.codigo,
                "descripcion": articulo.descripcion,
                "estado": articulo.inventario_estado.value,
                "mensaje": f"Artículo '{articulo.descripcion}' bloqueado exitosamente.",
            }
        except Exception as e:
            return {"error": True, "mensaje": f"Error al bloquear artículo: {str(e)}"}

    def _desbloquear_articulo(self, args: dict, db) -> dict:
        """Desbloquea un artículo previamente bloqueado."""
        uc = ArticuloUseCase(
            SqlAlchemyArticuloRepository(db), SqlAlchemyRubroRepository(db)
        )
        codigo = args.get("codigo", "")

        try:
            articulo = uc.desbloquear(codigo)
            return {
                "codigo": articulo.codigo,
                "descripcion": articulo.descripcion,
                "estado": articulo.inventario_estado.value,
                "stock_actual": articulo.stock_actual,
                "mensaje": f"Artículo '{articulo.descripcion}' desbloqueado exitosamente.",
            }
        except Exception as e:
            return {"error": True, "mensaje": f"Error al desbloquear artículo: {str(e)}"}

    def _generar_cotizacion(self, args: dict, db) -> dict:
        """Genera una cotización para un cliente con los items indicados."""
        cliente_id = args.get("cliente_id")
        items = args.get("items", [])

        if not cliente_id:
            return {"error": True, "mensaje": "Se requiere cliente_id."}
        if not items:
            return {"error": True, "mensaje": "Se requiere al menos un item."}

        uc = ComprobanteUseCase(
            repo=SqlAlchemyComprobanteRepository(db),
            caja_repo=SqlAlchemyCajaRepository(db),
            articulo_repo=SqlAlchemyArticuloRepository(db),
            cliente_repo=SqlAlchemyClienteRepository(db),
            vendedor_repo=SqlAlchemyVendedorRepository(db),
            forma_pago_repo=SqlAlchemyFormaPagoRepository(db),
        )

        # Construir detalles
        detalles = []
        for item in items:
            detalles.append(DetalleComprobante(
                articulo_codigo=item.get("codigo", ""),
                cantidad=int(item.get("cantidad", 1)),
            ))

        # Construir comprobante tipo COTIZACION
        cotizacion = Comprobante(
            tipo=TipoComprobante.COTIZACION,
            cliente_id=int(cliente_id),
            vendedor_id=1,  # Vendedor default
            lista_mayorista=False,
            consumidor_final=(int(cliente_id) == 1),
            canal="WHATSAPP",
            detalles=detalles,
            formas_pago=[],  # Cotización no requiere formas de pago
        )

        try:
            result = uc.crear_comprobante(cotizacion)
            cliente = SqlAlchemyClienteRepository(db).get_by_id(result.cliente_id)
            return {
                "cotizacion_id": result.id,
                "comprobante_id": result.id,
                "numero": f"{result.punto_venta:04d}-{result.numero:08d}",
                "cliente_nombre": cliente.razon_social if cliente else "Desconocido",
                "total": result.total,
                "items_count": len(result.detalles),
                "mensaje": (
                    f"Cotización N° {result.punto_venta:04d}-{result.numero:08d} "
                    f"generada para {cliente.razon_social if cliente else 'Desconocido'}. "
                    f"Total: ${result.total:,.2f}"
                ),
            }
        except Exception as e:
            return {"error": True, "mensaje": f"Error al generar cotización: {str(e)}"}

    def _consultar_caja(self, args: dict, db) -> dict:
        """Consulta el estado de la caja actual."""
        uc = CajaUseCase(
            SqlAlchemyCajaRepository(db), SqlAlchemyVendedorRepository(db)
        )

        try:
            caja = uc.get_abierta()
            vendedor = SqlAlchemyVendedorRepository(db).get_by_id(caja.vendedor_id)
            return {
                "abierta": True,
                "caja_id": caja.id,
                "vendedor": vendedor.nombre if vendedor else "Desconocido",
                "fecha_apertura": (
                    caja.fecha_apertura.isoformat() if caja.fecha_apertura else None
                ),
                "saldo_inicial": caja.saldo_inicial,
                "estado": caja.estado.value,
            }
        except Exception:
            return {
                "abierta": False,
                "mensaje": "No hay ninguna caja abierta.",
            }

    def _listar_comprobantes(self, args: dict, db) -> dict:
        """Lista comprobantes por tipo o por caja."""
        tipo_str = args.get("tipo", "FACTURA_B")
        caja_id = args.get("caja_id")

        uc = ComprobanteUseCase(
            repo=SqlAlchemyComprobanteRepository(db),
            caja_repo=SqlAlchemyCajaRepository(db),
            articulo_repo=SqlAlchemyArticuloRepository(db),
            cliente_repo=SqlAlchemyClienteRepository(db),
            vendedor_repo=SqlAlchemyVendedorRepository(db),
            forma_pago_repo=SqlAlchemyFormaPagoRepository(db),
        )

        try:
            tipo = TipoComprobante(tipo_str)
        except ValueError:
            tipo = TipoComprobante.FACTURA_B

        if caja_id:
            comprobantes = uc.listar_por_caja(caja_id)
        else:
            comprobantes = uc.listar_por_tipo(tipo)

        resultados = []
        for c in comprobantes[:15]:  # Limitar a 15 resultados
            cliente = SqlAlchemyClienteRepository(db).get_by_id(c.cliente_id)
            resultados.append({
                "id": c.id,
                "tipo": c.tipo.value,
                "numero": f"{c.punto_venta:04d}-{c.numero:08d}",
                "fecha": c.fecha.isoformat() if c.fecha else None,
                "cliente_id": c.cliente_id,
                "cliente_nombre": cliente.razon_social if cliente else "Desconocido",
                "total": c.total,
                "estado_sincronizacion": c.estado_sincronizacion.value,
                "cotizacion_origen_id": c.cotizacion_origen_id,
            })

        return {"resultados": resultados, "total": len(comprobantes)}

    def _ver_comprobante(self, args: dict, db) -> dict:
        """Obtiene el detalle completo de un comprobante."""
        comprobante_id = args.get("comprobante_id")
        if not comprobante_id:
            return {"error": True, "mensaje": "Se requiere comprobante_id."}

        uc = ComprobanteUseCase(
            repo=SqlAlchemyComprobanteRepository(db),
            caja_repo=SqlAlchemyCajaRepository(db),
            articulo_repo=SqlAlchemyArticuloRepository(db),
            cliente_repo=SqlAlchemyClienteRepository(db),
            vendedor_repo=SqlAlchemyVendedorRepository(db),
            forma_pago_repo=SqlAlchemyFormaPagoRepository(db),
        )

        try:
            c = uc.get_by_id(comprobante_id)
        except Exception as e:
            return {"error": True, "mensaje": f"Comprobante no encontrado: {str(e)}"}

        cliente = SqlAlchemyClienteRepository(db).get_by_id(c.cliente_id)

        detalles = []
        for d in c.detalles:
            art = SqlAlchemyArticuloRepository(db).get_by_codigo(d.articulo_codigo)
            detalles.append({
                "articulo_codigo": d.articulo_codigo,
                "articulo_descripcion": art.descripcion if art else d.articulo_codigo,
                "cantidad": d.cantidad,
                "precio_unitario": d.precio_unitario,
                "porc_dto": d.porc_dto,
                "subtotal": d.subtotal,
            })

        formas_pago = []
        for fp in c.formas_pago:
            fp_obj = SqlAlchemyFormaPagoRepository(db).get_by_id(fp.forma_pago_id)
            formas_pago.append({
                "forma_pago": fp_obj.nombre if fp_obj else f"ID {fp.forma_pago_id}",
                "monto": fp.monto,
                "cuotas": fp.cuotas,
            })

        return {
            "id": c.id,
            "tipo": c.tipo.value,
            "numero": f"{c.punto_venta:04d}-{c.numero:08d}",
            "fecha": c.fecha.isoformat() if c.fecha else None,
            "cliente": cliente.razon_social if cliente else "Desconocido",
            "consumidor_final": c.consumidor_final,
            "total": c.total,
            "subtotal": c.subtotal,
            "descuento_pie": c.descuento_pie,
            "estado_sincronizacion": c.estado_sincronizacion.value,
            "cotizacion_origen_id": c.cotizacion_origen_id,
            "detalles": detalles,
            "formas_pago": formas_pago,
        }

    def _listar_facturas_caja(self, args: dict, db) -> dict:
        """Lista facturas de la caja abierta actual."""
        caja_uc = CajaUseCase(
            SqlAlchemyCajaRepository(db), SqlAlchemyVendedorRepository(db)
        )

        try:
            caja = caja_uc.get_abierta()
        except Exception:
            return {"error": True, "mensaje": "No hay ninguna caja abierta."}

        comp_uc = ComprobanteUseCase(
            repo=SqlAlchemyComprobanteRepository(db),
            caja_repo=SqlAlchemyCajaRepository(db),
            articulo_repo=SqlAlchemyArticuloRepository(db),
            cliente_repo=SqlAlchemyClienteRepository(db),
            vendedor_repo=SqlAlchemyVendedorRepository(db),
            forma_pago_repo=SqlAlchemyFormaPagoRepository(db),
        )

        comprobantes = comp_uc.listar_por_caja(caja.id)

        # Solo facturas (no cotizaciones)
        facturas = [c for c in comprobantes if c.es_factura]

        total_facturado = sum(f.total for f in facturas)

        resultados = []
        for c in facturas:
            cliente = SqlAlchemyClienteRepository(db).get_by_id(c.cliente_id)
            resultados.append({
                "id": c.id,
                "tipo": c.tipo.value,
                "numero": f"{c.punto_venta:04d}-{c.numero:08d}",
                "cliente_nombre": cliente.razon_social if cliente else "Desconocido",
                "total": c.total,
            })

        return {
            "caja_id": caja.id,
            "fecha_apertura": caja.fecha_apertura.isoformat() if caja.fecha_apertura else None,
            "total_facturas": len(facturas),
            "total_facturado": total_facturado,
            "facturas": resultados,
        }