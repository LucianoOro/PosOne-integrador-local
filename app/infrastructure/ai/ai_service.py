"""Servicio de IA con soporte multi-provider (OpenAI, GitHub Models, Groq).

Procesa mensajes de WhatsApp a través de modelos de IA con function calling,
permitiendo al asistente virtual interactuar con el sistema POS de forma natural.

Proveedores soportados:
- openai: OpenAI API (GPT-4o-mini, etc.)
- github: GitHub Models (GPT-4o-mini vía GitHub token)
- groq: Groq API (Llama 3.3 70B, etc.)

Configuración vía .env:
- AI_PROVIDER: openai | github | groq (default: openai)
- OPENAI_API_KEY / AI_API_KEY: API key del provider
- AI_MODEL: modelo a usar (default: gpt-4o-mini para openai/github, llama-3.3-70b-versatile para groq)
"""

import json
import logging
import os
from dataclasses import dataclass

from openai import OpenAI

from app.infrastructure.ai.ai_functions import MODEL_NAME, SYSTEM_MESSAGE, get_tools
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

__all__ = ["AIServiceEmptyResponseError", "AIResult", "AIService"]


class AIServiceEmptyResponseError(Exception):
    """Raised when the AI returns a response with no function calls and no text."""
    pass


@dataclass
class AIResult:
    """Resultado del procesamiento de un mensaje por IA."""
    text: str
    cotizacion_id: int | None = None
    comprobante_id: int | None = None


# ─── Configuración de providers ──────────────────────────────────

PROVIDER_CONFIGS = {
    "openai": {
        "base_url": None,  # Usa el default de OpenAI
        "env_key": "OPENAI_API_KEY",
        "default_model": "gpt-4o-mini",
        "fallback_models": ["gpt-4o-mini", "gpt-4o"],
    },
    "github": {
        "base_url": "https://models.inference.ai.azure.com",  # URL operativa (github.models.ai/inference no conecta aún)
        "env_key": "AI_API_KEY",  # GitHub token (ghp_xxx o gho_xxx)
        "default_model": "gpt-4o-mini",
        # Fallback chain: gpt-4o-mini → gpt-4o
        # NOTA: o4-mini solo tiene 12 req/día en el free tier.
        # Cuando se activen student benefits, agregar "o4-mini" entre los dos.
        "fallback_models": ["gpt-4o-mini", "gpt-4o"],
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "env_key": "GROQ_API_KEY",
        # qwen3-32b: mejor function calling en Groq free tier.
        # Llama 3.3 70B como fallback (intermitente con XML).
        # Llama 4 Scout y Llama 3.1 8B tienen bugs con function calling.
        "default_model": "qwen/qwen3-32b",
        "fallback_models": ["qwen/qwen3-32b", "llama-3.3-70b-versatile"],
    },
}


class AIService:
    """Servicio de IA que procesa mensajes usando OpenAI-compatible APIs con function calling.

    Flujo:
    1. Recibe mensaje del usuario
    2. Envía al modelo de IA con las declaraciones de funciones
    3. Si la IA invoca una función → ejecuta el caso de uso correspondiente
    4. Envía el resultado de vuelta a la IA para formatear la respuesta
    5. Retorna la respuesta en lenguaje natural
    """

    def __init__(self, api_key: str | None = None):
        provider = os.environ.get("AI_PROVIDER", "openai").lower()
        config = PROVIDER_CONFIGS.get(provider, PROVIDER_CONFIGS["openai"])

        self._provider = provider
        self._api_key = api_key or os.environ.get(config["env_key"], "")
        self._model = os.environ.get("AI_MODEL", config["default_model"])
        self._base_url = config["base_url"]
        self._fallback_models = config.get("fallback_models", [self._model])
        self._client: OpenAI | None = None

    @property
    def client(self) -> OpenAI:
        """Lazy initialization del cliente OpenAI-compatible."""
        if self._client is None:
            if not self._api_key:
                raise ValueError("API key no configurada")
            kwargs = {"api_key": self._api_key}
            if self._base_url:
                kwargs["base_url"] = self._base_url
            self._client = OpenAI(**kwargs)
        return self._client

    @property
    def is_configured(self) -> bool:
        """Verifica si la API key está configurada."""
        return bool(self._api_key)

    def process_message(
        self, phone_number: str, message: str, context: dict | None = None
    ) -> AIResult:
        """Procesa un mensaje a través del modelo de IA con function calling.

        Si el modelo principal falla (rate limit, model not found), prueba
        con el siguiente modelo en la cadena de fallback.

        Args:
            phone_number: Número de teléfono del remitente.
            message: Texto del mensaje recibido.
            context: Contexto adicional (historial, preferencias, etc.).

        Returns:
            AIResult con el texto de respuesta y metadata de side effects.
        """
        # Construir mensajes
        messages = self._build_messages(phone_number, message, context)

        # Probar modelos en cadena de fallback
        last_error = None
        for model in self._fallback_models:
            try:
                logger.info("Intentando con modelo: %s", model)
                return self._process_with_model(model, messages)
            except AIServiceEmptyResponseError as e:
                logger.warning("Modelo %s devolvió respuesta vacía, probando siguiente...", model)
                last_error = e
                continue
            except Exception as e:
                error_msg = str(e)
                # Rate limit, model not found, o otros errores reintenables
                is_retriable = any(k in error_msg.lower() for k in [
                    "429", "rate_limit", "rate limit", "quota",
                    "model_not_found", "model not found",
                    "503", "server_error", "server error",
                    "timeout", "connection",
                    "tool_use_failed", "tool call validation failed",
                    "invalid_request_error",
                ])
                if is_retriable:
                    logger.warning("Error reintenable en modelo %s: %s — probando siguiente", model, error_msg[:100])
                    last_error = e
                    continue
                # Error no reintenable → relanzar
                raise

        # Todos los modelos fallaron
        if last_error:
            raise last_error
        raise RuntimeError("No hay modelos disponibles")

    def _process_with_model(
        self, model: str, messages: list[dict]
    ) -> AIResult:
        """Procesa un mensaje con un modelo específico.

        Args:
            model: Nombre del modelo a usar.
            messages: Historial de conversación ya construido.

        Returns:
            AIResult con el texto de respuesta y metadata de side effects.
        """
        # Side effects tracker
        side_effects: dict = {}

        # Loop de function calling (máximo 5 iteraciones)
        max_iterations = 5
        for _ in range(max_iterations):
            try:
                response = self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    tools=get_tools(),
                )
            except Exception as e:
                error_msg = str(e)
                # Groq/Llama a veces manda strings en vez de numbers en tool calls.
                # Ejemplo: diferencia: "0" en vez de diferencia: 0
                # Groq rechaza con 400 tool_use_failed y nos da el failed_generation.
                # Intentamos reintentar con type coercion del JSON fallido.
                if "tool_use_failed" in error_msg or "tool call validation failed" in error_msg:
                    coerced = self._try_coerce_failed_tool_call(error_msg)
                    if coerced:
                        logger.info("Reintentando con type coercion para modelo %s", model)
                        # Agregar los tool calls corregidos como mensaje del asistente
                        corrected_tool_calls = []
                        for tc in coerced:
                            corrected_tool_calls.append(tc)
                        messages.append({
                            "role": "assistant",
                            "tool_calls": corrected_tool_calls,
                        })
                        # Ejecutar las funciones corregidas
                        for tc in coerced:
                            func_name = tc["function"]["name"]
                            try:
                                args = json.loads(tc["function"]["arguments"])
                            except json.JSONDecodeError:
                                args = {}
                            args = self._coerce_tool_arguments(func_name, args)
                            result = self._execute_function(func_name, args)
                            if "cotizacion_id" in result:
                                side_effects["cotizacion_id"] = result["cotizacion_id"]
                            if "comprobante_id" in result:
                                side_effects["comprobante_id"] = result["comprobante_id"]
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tc["id"],
                                "content": json.dumps(result, ensure_ascii=False),
                            })
                        continue  # Volver a pedir respuesta al modelo
                logger.exception("Error llamando a IA (%s/%s): %s", self._provider, model, e)
                raise

            choice = response.choices[0]
            message = choice.message

            # Si hay tool_calls, ejecutar y continuar
            if message.tool_calls:
                # Agregar el mensaje del asistente al historial
                messages.append(message)

                for tool_call in message.tool_calls:
                    function_name = tool_call.function.name
                    try:
                        arguments = json.loads(tool_call.function.arguments)
                    except json.JSONDecodeError:
                        arguments = {}

                    # Coerción de tipos: algunos modelos (Llama) mandan strings
                    # donde el schema indica numbers/integers. Corregimos aquí.
                    arguments = self._coerce_tool_arguments(function_name, arguments)

                    logger.info("IA invocó función: %s(%s)", function_name, arguments)
                    result = self._execute_function(function_name, arguments)

                    # Trackear side effects
                    if "cotizacion_id" in result:
                        side_effects["cotizacion_id"] = result["cotizacion_id"]
                    if "comprobante_id" in result:
                        side_effects["comprobante_id"] = result["comprobante_id"]

                    # Agregar resultado de la herramienta
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(result, ensure_ascii=False),
                    })

                # Continuar el loop para obtener la respuesta final
                continue

            # Sin tool_calls estructurados — verificar si el texto tiene
            # formato XML de function call (Llama a veces hace esto)
            if message.content:
                xml_tool_calls = self._parse_xml_tool_calls(message.content)
                if xml_tool_calls:
                    logger.info("XML function calls detectados: %s", [tc["function"]["name"] for tc in xml_tool_calls])
                    # Agregar el mensaje del asistente al historial
                    messages.append(message)

                    for tc in xml_tool_calls:
                        func_name = tc["function"]["name"]
                        try:
                            arguments = json.loads(tc["function"]["arguments"])
                        except json.JSONDecodeError:
                            arguments = {}
                        arguments = self._coerce_tool_arguments(func_name, arguments)

                        logger.info("IA invocó función (XML): %s(%s)", func_name, arguments)
                        result = self._execute_function(func_name, arguments)

                        # Trackear side effects
                        if "cotizacion_id" in result:
                            side_effects["cotizacion_id"] = result["cotizacion_id"]
                        if "comprobante_id" in result:
                            side_effects["comprobante_id"] = result["comprobante_id"]

                        # Agregar resultado de la herramienta
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "content": json.dumps(result, ensure_ascii=False),
                        })

                    # Continuar el loop para obtener la respuesta final
                    continue

                # Texto normal sin function calls
                return AIResult(
                    text=message.content,
                    cotizacion_id=side_effects.get("cotizacion_id"),
                    comprobante_id=side_effects.get("comprobante_id"),
                )
            else:
                # Respuesta vacía sin function calls
                raise AIServiceEmptyResponseError("IA devolvió respuesta vacía")

        # Si llegamos aquí, demasiadas iteraciones
        if message.content:
            return AIResult(
                text=message.content,
                cotizacion_id=side_effects.get("cotizacion_id"),
                comprobante_id=side_effects.get("comprobante_id"),
            )
        return AIResult(text="No pude completar la consulta.")

    def _try_coerce_failed_tool_call(self, error_msg: str) -> list[dict] | None:
        """Intenta parsear y corregir tool calls que Groq rechazó por type mismatch.

        Groq devuelve el JSON fallido en 'failed_generation'.
        Ejemplo de error: diferencia: "0" (string) en vez de diferencia: 0 (number).
        Corregimos los tipos según el schema y devolvemos los tool calls listos para ejecutar.
        """
        import re
        # Extraer el JSON del campo 'failed_generation'
        match = re.search(r"'failed_generation':\s*'(\[.*?\])'", error_msg, re.DOTALL)
        if not match:
            # Formato alternativo: "failed_generation": "[...]"
            match = re.search(r'"failed_generation":\s*"(\[.*?\])"', error_msg, re.DOTALL)
        if not match:
            return None

        raw_json = match.group(1)
        # Unescape: Groq puede tener \\n, \\", etc.
        raw_json = raw_json.replace('\\n', '\n').replace('\\"', '"')

        try:
            tool_calls_raw = json.loads(raw_json)
        except json.JSONDecodeError:
            logger.warning("No se pudo parsear failed_generation: %s", raw_json[:200])
            return None

        if not isinstance(tool_calls_raw, list) or len(tool_calls_raw) == 0:
            return None

        # Corregir tipos y generar IDs ficticios
        import uuid
        corrected = []
        for tc in tool_calls_raw:
            if not isinstance(tc, dict) or "name" not in tc:
                continue
            func_name = tc["name"]
            params = tc.get("parameters", tc.get("arguments", {}))
            # Coercer tipos
            params = self._coerce_tool_arguments(func_name, params)
            corrected.append({
                "id": f"call_{uuid.uuid4().hex[:24]}",
                "type": "function",
                "function": {
                    "name": func_name,
                    "arguments": json.dumps(params, ensure_ascii=False),
                },
            })

        logger.info("Tool calls corregidos por type coercion: %s", [tc["function"]["name"] for tc in corrected])
        return corrected

    @classmethod
    def _parse_xml_tool_calls(cls, text: str) -> list[dict] | None:
        """Parsea function calls en formato XML que algunos modelos Llama generan.

        Formatos soportados:
        - <function=name>params_json</function>
        - <function=name params_json/>
        - <function=name>{"key": "value"}</function>

        Returns lista de tool call dicts con id, type, function.name, function.arguments
        o None si no se encontraron XML function calls.
        """
        import re
        import uuid

        # Patrón 1: <function=name>{"params": "value"}</function>
        pattern1 = r'<function\s*=\s*(\w+)\s*>(.*?)</function>'
        # Patrón 2: <function=name {"params": "value"} />
        pattern2 = r'<function\s*=\s*(\w+)\s+(\{[^}]+\})\s*/?>'

        tool_calls = []

        # Intentar patrón 1
        matches = re.findall(pattern1, text, re.DOTALL)
        if matches:
            for func_name, args_str in matches:
                args_str = args_str.strip()
                try:
                    if args_str:
                        arguments = json.loads(args_str)
                    else:
                        arguments = {}
                except json.JSONDecodeError:
                    arguments = {}
                tool_calls.append({
                    "id": f"call_{uuid.uuid4().hex[:24]}",
                    "type": "function",
                    "function": {
                        "name": func_name,
                        "arguments": json.dumps(arguments, ensure_ascii=False),
                    },
                })

        # Si no encontró con patrón 1, intentar patrón 2
        if not tool_calls:
            matches = re.findall(pattern2, text, re.DOTALL)
            if matches:
                for func_name, args_str in matches:
                    try:
                        arguments = json.loads(args_str)
                    except json.JSONDecodeError:
                        arguments = {}
                    tool_calls.append({
                        "id": f"call_{uuid.uuid4().hex[:24]}",
                        "type": "function",
                        "function": {
                            "name": func_name,
                            "arguments": json.dumps(arguments, ensure_ascii=False),
                        },
                    })

        return tool_calls if tool_calls else None

    def _build_messages(
        self, phone_number: str, message: str, context: dict | None = None
    ) -> list[dict]:
        """Construye la lista de mensajes para la API."""
        messages = [
            {"role": "system", "content": SYSTEM_MESSAGE},
        ]

        # Agregar contexto previo si existe
        if context and context.get("history"):
            for msg in context["history"]:
                role = msg.get("role", "user")
                text = msg.get("text", "")
                messages.append({"role": role, "content": text})

        # Agregar mensaje actual con contexto del número
        prefixed_message = (
            f"[Numero: {phone_number}] {message}" if phone_number else message
        )
        messages.append({"role": "user", "content": prefixed_message})

        return messages

    # Tipos esperados por cada función: campo → tipo Python
    _ARG_TYPES: dict[str, dict[str, type]] = {
        "abrir_caja": {"saldo_inicial": float, "vendedor_id": int},
        "cerrar_caja": {"diferencia": float},
        "consultar_stock": {"codigo": str},
        "consultar_precio": {"codigo": str, "lista": str},
        "buscar_clientes": {"query": str},
        "generar_cotizacion": {"cliente_id": int},
        "convertir_cotizacion": {"cotizacion_id": int, "tipo_factura": str},
        "bloquear_articulo": {"codigo": str},
        "desbloquear_articulo": {"codigo": str},
        "ver_comprobante": {"comprobante_id": int},
        "listar_comprobantes": {"caja_id": int},
    }

    @classmethod
    def _coerce_tool_arguments(cls, function_name: str, arguments: dict) -> dict:
        """Coerción de tipos para argumentos de tool calls.

        Algunos modelos (Llama) mandan strings donde el schema indica numbers.
        Este método convierte los tipos según lo esperado por cada función.
        """
        expected_types = cls._ARG_TYPES.get(function_name, {})
        for key, expected_type in expected_types.items():
            if key in arguments and arguments[key] is not None:
                try:
                    if expected_type == int:
                        # int() de float-string ("3.0") → primero float, luego int
                        arguments[key] = int(float(arguments[key]))
                    elif expected_type == float:
                        arguments[key] = float(arguments[key])
                except (ValueError, TypeError):
                    logger.warning(
                        "No se pudo coercer %s[%s]=%r a %s",
                        function_name, key, arguments[key], expected_type.__name__,
                    )
        return arguments

    def _execute_function(self, function_name: str, args: dict) -> dict:
        """Ejecuta una función del sistema basada en la llamada de la IA.

        Cada función crea su propia sesión de BD para garantizar
        transacciones independientes.
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

    def _dispatch_function(self, function_name: str, args: dict | None, db) -> dict:
        """Despacha la ejecución de la función correspondiente."""
        # Garantizar que args nunca sea None (modelos Llama pueden no enviar args)
        args = args or {}
        dispatchers = {
            "saludar": self._saludar,
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
            "abrir_caja": self._abrir_caja,
            "cerrar_caja": self._cerrar_caja,
            "listar_comprobantes": self._listar_comprobantes,
            "ver_comprobante": self._ver_comprobante,
            "listar_facturas_caja": self._listar_facturas_caja,
        }

        handler = dispatchers.get(function_name)
        if not handler:
            return {"error": True, "mensaje": f"Función desconocida: {function_name}"}

        return handler(args, db)

    # ─── Implementaciones de funciones ─────────────────────────────

    def _saludar(self, args: dict, db) -> dict:
        """Saluda al usuario y lista las funciones disponibles."""
        return {
            "mensaje": (
                "¡Hola! 👋 Soy el asistente de PosONE. Podés consultarme por:\n"
                "• Stock y precios de artículos\n"
                "• Buscar clientes\n"
                "• Cotizaciones pendientes y generar cotizaciones\n"
                "• Abrir y cerrar caja\n"
                "• Estado de caja\n"
                "• Facturas y comprobantes\n"
                "• Bloquear/desbloquear artículos\n\n"
                "¿En qué te puedo ayudar?"
            ),
        }

    def _buscar_articulos(self, args: dict, db) -> dict:
        uc = ArticuloUseCase(
            SqlAlchemyArticuloRepository(db), SqlAlchemyRubroRepository(db)
        )
        query = args.get("query", "")
        articulos = uc.search(query)

        if not articulos:
            return {"resultados": [], "mensaje": f"No encontré artículos para '{query}'."}

        resultados = []
        for a in articulos[:10]:
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
        cotizacion_id = args.get("cotizacion_id")
        tipo_factura_str = args.get("tipo_factura", "FACTURA_B")

        if not cotizacion_id:
            return {"error": True, "mensaje": "Se requiere cotizacion_id."}

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

        detalles = []
        for item in items:
            detalles.append(DetalleComprobante(
                articulo_codigo=item.get("codigo", ""),
                cantidad=int(item.get("cantidad", 1)),
            ))

        cotizacion = Comprobante(
            tipo=TipoComprobante.COTIZACION,
            cliente_id=int(cliente_id),
            vendedor_id=1,
            lista_mayorista=False,
            consumidor_final=(int(cliente_id) == 1),
            canal="WHATSAPP",
            detalles=detalles,
            formas_pago=[],
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
            return {"abierta": False, "mensaje": "No hay ninguna caja abierta."}

    def _abrir_caja(self, args: dict, db) -> dict:
        """Abre una nueva caja para facturación."""
        saldo_inicial = args.get("saldo_inicial", 0.0)
        vendedor_id = args.get("vendedor_id", 1)

        uc = CajaUseCase(
            SqlAlchemyCajaRepository(db), SqlAlchemyVendedorRepository(db)
        )

        try:
            caja = uc.abrir(vendedor_id=vendedor_id, saldo_inicial=float(saldo_inicial))
            vendedor = SqlAlchemyVendedorRepository(db).get_by_id(caja.vendedor_id)
            return {
                "abierta": True,
                "caja_id": caja.id,
                "vendedor": vendedor.nombre if vendedor else "Desconocido",
                "fecha_apertura": (
                    caja.fecha_apertura.isoformat() if caja.fecha_apertura else None
                ),
                "saldo_inicial": caja.saldo_inicial,
                "mensaje": (
                    f"Caja {caja.id} abierta exitosamente por "
                    f"{vendedor.nombre if vendedor else 'Desconocido'}. "
                    f"Saldo inicial: ${caja.saldo_inicial:,.2f}"
                ),
            }
        except Exception as e:
            error_msg = str(e)
            if "ya abierta" in error_msg.lower() or "ya existe" in error_msg.lower():
                return {
                    "abierta": False,
                    "error": True,
                    "mensaje": "Ya hay una caja abierta. Cerrá la caja actual antes de abrir una nueva.",
                }
            return {"abierta": False, "error": True, "mensaje": f"Error al abrir caja: {error_msg}"}

    def _cerrar_caja(self, args: dict, db) -> dict:
        """Cierra la caja abierta actual."""
        diferencia = args.get("diferencia", 0.0)

        uc = CajaUseCase(
            SqlAlchemyCajaRepository(db), SqlAlchemyVendedorRepository(db)
        )

        try:
            # Primero obtener la caja abierta para saber su ID
            caja = uc.get_abierta()
            caja_id = caja.id
            total_ventas = caja.saldo_inicial  # se actualizará con el cierre

            caja = uc.cerrar(caja_id=caja_id, diferencia=float(diferencia))
            vendedor = SqlAlchemyVendedorRepository(db).get_by_id(caja.vendedor_id)
            return {
                "abierta": False,
                "caja_id": caja_id,
                "vendedor": vendedor.nombre if vendedor else "Desconocido",
                "fecha_apertura": (
                    caja.fecha_apertura.isoformat() if caja.fecha_apertura else None
                ),
                "fecha_cierre": (
                    caja.fecha_cierre.isoformat() if caja.fecha_cierre else None
                ),
                "saldo_inicial": caja.saldo_inicial,
                "diferencia": caja.diferencia,
                "mensaje": (
                    f"Caja {caja_id} cerrada exitosamente. "
                    f"Saldo inicial: ${caja.saldo_inicial:,.2f}, "
                    f"Diferencia: ${caja.diferencia:,.2f}"
                ),
            }
        except Exception as e:
            error_msg = str(e)
            if "no abierta" in error_msg.lower() or "no hay" in error_msg.lower():
                return {
                    "abierta": False,
                    "error": True,
                    "mensaje": "No hay ninguna caja abierta para cerrar.",
                }
            return {"abierta": False, "error": True, "mensaje": f"Error al cerrar caja: {error_msg}"}

    def _listar_comprobantes(self, args: dict, db) -> dict:
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
        for c in comprobantes[:15]:
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