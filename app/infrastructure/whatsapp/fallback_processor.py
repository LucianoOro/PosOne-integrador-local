"""Fallback rule-based processor para cuando Gemini no está disponible.

Procesa mensajes sin IA usando pattern matching directo.
Se activa cuando:
- Gemini no está configurado (sin API key)
- Se agota la cuota (429 RESOURCE_EXHAUSTED)
- Error temporal de Gemini

Responde las mismas funciones que el agente de IA, pero con
respuestas más estructuradas y sin conversación libre.
"""

import re
import logging
from typing import Optional

from app.application.use_cases.articulo_use_case import ArticuloUseCase
from app.application.use_cases.caja_use_case import CajaUseCase
from app.application.use_cases.cliente_use_case import ClienteUseCase
from app.application.use_cases.comprobante_use_case import ComprobanteUseCase
from app.domain.entities.entities import Comprobante, DetalleComprobante, ComprobanteFormaPago
from app.domain.value_objects.enums import TipoComprobante
from app.infrastructure.database.connection import SessionLocal
from app.infrastructure.database.repositories.articulo_repo import SqlAlchemyArticuloRepository
from app.infrastructure.database.repositories.caja_repo import SqlAlchemyCajaRepository
from app.infrastructure.database.repositories.cliente_repo import SqlAlchemyClienteRepository
from app.infrastructure.database.repositories.comprobante_repo import SqlAlchemyComprobanteRepository
from app.infrastructure.database.repositories.forma_pago_repo import SqlAlchemyFormaPagoRepository
from app.infrastructure.database.repositories.rubro_repo import SqlAlchemyRubroRepository
from app.infrastructure.database.repositories.vendedor_repo import SqlAlchemyVendedorRepository

logger = logging.getLogger(__name__)


class FallbackProcessor:
    """Procesador rule-based que responde sin IA cuando Gemini no está disponible."""

    def process(self, message: str) -> str:
        """Procesa un mensaje usando reglas simples sin IA.

        Args:
            message: Texto del mensaje del usuario.

        Returns:
            Respuesta en texto formateado.
        """
        msg = message.lower().strip()

        # Detectar intención por palabras clave
        # IMPORTANTE: orden de prioridad — los patrones más específicos van primero

        # ---- Anti-manipulación: intentos de jailbreak o off-topic ----
        if any(w in msg for w in ["ignorá", "ignora", "ignorar", "olvidá", "olvida",
                                    "actúa como", "actua como", "pretendé", "finge",
                                    "system prompt", "instrucciones", "jailbreak",
                                    "sos un", "you are", "etcétera", "receta", "chiste",
                                    "poema", "canción", "cancion", "chisme", "broma"]):
            return (
                "No puedo ayudarte con eso. Soy el asistente de PosONE y solo atiendo "
                "consultas sobre stock, precios, clientes, facturas, cotizaciones y caja. "
                "¿En qué te puedo ayudar?"
            )

        if any(w in msg for w in ["hola", "buenas", "buen día", "hey", "ey"]):
            return self._saludo()

        if any(w in msg for w in ["ayuda", "qué podés", "que podes", "funciones", "qué hacés", "que haces"]):
            return self._lista_funciones()

        # ---- Comprobantes y caja (ANTES que "cotiz" o "factur" genérico) ----
        # Facturas de la caja / qué se vendió hoy — patrones específicos
        if any(w in msg for w in [
            "facturas de la caja", "factura de la caja",
            "qué se vendió", "que se vendió", "se vendió hoy", "se vendio",
            "ventas de la caja", "ventas del día", "ventas de hoy",
            "facturado hoy", "facturación de hoy", "facturación del día",
            "caja facturas", "caja ventas",
        ]):
            return self._listar_facturas_caja()

        if any(w in msg for w in ["ver factura", "ver comprobante", "ver cotización", "detalle"]):
            return self._ver_comprobante(msg)

        if any(w in msg for w in ["factura", "comprobantes", "facturas", "ventas"]):
            return self._listar_comprobantes(msg)

        # ---- Stock y precios ----
        if any(w in msg for w in ["stock", "hay de", "cuánto hay", "disponib"]):
            return self._buscar_articulos(msg)

        if any(w in msg for w in ["precio", "cuánto sale", "cuanto sale", "cuánto cuesta", "cuanto cuesta", "valuación", "valor", "mayorista"]):
            return self._consultar_precio(msg)

        # ---- Clientes ----
        if any(w in msg for w in ["cliente", "razón social", "razon social", "cuit", "datos de"]):
            return self._buscar_clientes(msg)

        # ---- Cotizaciones ----
        if any(w in msg for w in ["cotización pendiente", "cotizaciones pendientes", "pendiente"]):
            return self._cotizaciones_pendientes()

        if any(w in msg for w in ["cotiz", "presupuesto", "presup"]):
            return self._generar_cotizacion(msg)

        if any(w in msg for w in ["convertir", "conviert"]):
            return self._convertir_cotizacion(msg)

        # ---- Bloquear/desbloquear ----
        if any(w in msg for w in ["bloquear", "bloqueá", "bloqueo"]):
            return self._bloquear_articulo(msg)

        if any(w in msg for w in ["desbloquear", "desbloqueá", "desbloqueo"]):
            return self._desbloquear_articulo(msg)

        # ---- Abrir y cerrar caja (ANTES del genérico "caja") ----
        if any(w in msg for w in [
            "abrir caja", "abrí caja", "abreme caja", "abrír caja",
            "abrir la caja", "iniciar caja", "iniciá caja", "inicio caja",
            "empezar caja", "nueva caja", "apertura caja", "apertura de caja",
            "abrir turno", "iniciar turno", "abrir turno",
        ]):
            return self._abrir_caja(msg)

        if any(w in msg for w in [
            "cerrar caja", "cerrá caja", "cerrar la caja", "cierren caja",
            "cierre de caja", "cierre caja", "cerrar turno", "cierra caja",
            "cerrando caja", "fin de caja", "finalizar caja", "terminar caja",
        ]):
            return self._cerrar_caja(msg)

        # ---- Caja (genérico, después de los específicos arriba) ----
        if any(w in msg for w in ["caja"]):
            return self._consultar_caja()

        # ---- Cotizaciones (sin "pendiente") ----
        if any(w in msg for w in ["cotizacion", "cotización"]):
            return self._cotizaciones_pendientes()

        # Si no coincide ningún patrón, intentar buscar artículos como fallback
        if len(msg) > 3:
            return self._buscar_articulos(msg)

        return (
            "No entendí tu consulta. Podés preguntarme por:\n"
            "• Stock y precios de artículos\n"
            "• Buscar clientes\n"
            "• Cotizaciones pendientes\n"
            "• Generar cotizaciones\n"
            "• Abrir, cerrar y consultar caja\n"
            "• Bloquear/desbloquear artículos\n\n"
            "Ejemplo: '¿qué stock hay de bicicletas?'"
        )

    # ─── Respuestas predefinidas ──────────────────────────────────────

    def _saludo(self) -> str:
        return (
            "¡Hola! 👋 Soy el asistente de PosONE. ¿En qué te puedo ayudar?\n\n"
            "Podés consultarme por:\n"
            "• Stock y precios\n"
            "• Buscar clientes\n"
            "• Cotizaciones\n"
            "• Abrir, cerrar y consultar caja\n"
            "• Bloquear/desbloquear artículos"
        )

    def _lista_funciones(self) -> str:
        return (
            "Soy el asistente de PosONE. Puedo ayudarte con:\n\n"
            "📊 **Stock y precios** — '¿qué stock hay de bicicletas?'\n"
            "🔍 **Buscar clientes** — 'buscá cliente Juan'\n"
            "📋 **Cotizaciones** — 'cotizame 2 Mountain Bike para Consumidor Final'\n"
            "📃 **Cotizaciones pendientes** — 'cotizaciones pendientes'\n"
            "🔄 **Convertir cotización** — 'convertí cotización 5 en factura B'\n"
            "🔓 **Abrir caja** — 'abrir caja con 50000'\n"
            "🔒 **Cerrar caja** — 'cerrar caja'\n"
            "💰 **Estado de caja** — '¿hay caja abierta?'"
        )

    # ─── Funciones con BD ──────────────────────────────────────────────

    def _buscar_articulos(self, msg: str) -> str:
        db = SessionLocal()
        try:
            # Extraer término de búsqueda
            query = self._extraer_termino(msg, [
                "stock", "hay", "de", "qué", "que", "cuánto", "buscá", "search",
                "buscar", "artículo", "articulo", "del", "la", "el", "los", "las",
                "hay de", "tenés", "tenes", "mostrá", "mostra", "ver", "quiero",
            ])
            if not query:
                return "Decime qué artículo buscás y te paso la info."

            uc = ArticuloUseCase(SqlAlchemyArticuloRepository(db), SqlAlchemyRubroRepository(db))
            articulos = uc.search(query)

            # Si no encuentra, probar sin la 's' final (singularización simple)
            if not articulos and query.endswith("s") and len(query) > 3:
                singular = query[:-1]  # bicicletas → bicicleta
                articulos = uc.search(singular)
            
            # Segundo intento: probar sin las últimas 2 letras (capacetes → capacitor)
            if not articulos and len(query) > 4:
                articulos = uc.search(query[:4])

            if not articulos:
                return f"No encontré artículos para '{query}'. Probá con otro término o código."

            lines = [f"📋 **Resultados para '{query}':**\n"]
            for a in articulos[:8]:
                estado = "✅" if a.inventario_estado.value == "ALTO" else "⚠️" if a.inventario_estado.value == "BAJO" else "🔒"
                lines.append(
                    f"  {estado} **{a.descripcion}** ({a.codigo})\n"
                    f"     Público: ${a.precio_publico:,.0f} | Mayorista: ${a.precio_mayorista:,.0f} | Stock: {a.stock_actual}"
                )

            if len(articulos) > 8:
                lines.append(f"\n  ...y {len(articulos) - 8} más.")

            return "\n".join(lines)
        except Exception as e:
            logger.exception("Error en buscar_articulos fallback")
            return f"Error al buscar artículos: {str(e)}"
        finally:
            db.close()

    def _consultar_precio(self, msg: str) -> str:
        db = SessionLocal()
        try:
            query = self._extraer_termino(msg, [
                "precio", "cuánto", "cuanto", "sale", "cuesta", "valen",
                "la", "el", "del", "de", "es", "del", "mayorista", "publico", "lista",
            ])
            if not query:
                return "Decime qué artículo buscás y te paso el precio."

            uc = ArticuloUseCase(SqlAlchemyArticuloRepository(db), SqlAlchemyRubroRepository(db))
            articulos = uc.search(query)
            
            # Fallback: singularizar
            if not articulos and query.endswith("s") and len(query) > 3:
                articulos = uc.search(query[:-1])

            if not articulos:
                return f"No encontré '{query}'. Probá con otro nombre o código."

            a = articulos[0]
            return (
                f"💰 **{a.descripcion}** ({a.codigo})\n"
                f"   Público: ${a.precio_publico:,.2f}\n"
                f"   Mayorista: ${a.precio_mayorista:,.2f}\n"
                f"   Stock: {a.stock_actual} unidades"
            )
        except Exception as e:
            return f"Error: {str(e)}"
        finally:
            db.close()

    def _buscar_clientes(self, msg: str) -> str:
        db = SessionLocal()
        try:
            query = self._extraer_termino(msg, [
                "cliente", "buscar", "buscá", "razón", "razon", "con", "el",
                "la", "del", "de", "nombre", "cuit", "datos",
            ])
            if not query:
                return "Decime qué cliente buscás."

            uc = ClienteUseCase(SqlAlchemyClienteRepository(db))
            clientes = uc.search(query)

            if not clientes:
                return f"No encontré clientes para '{query}'."

            lines = [f"👥 **Clientes para '{query}':**\n"]
            for c in clientes[:5]:
                lines.append(f"  • **{c.razon_social}** — CUIT: {c.cuit} — ID: {c.id}")

            return "\n".join(lines)
        except Exception as e:
            return f"Error: {str(e)}"
        finally:
            db.close()

    def _cotizaciones_pendientes(self) -> str:
        db = SessionLocal()
        try:
            uc = ComprobanteUseCase(
                repo=SqlAlchemyComprobanteRepository(db),
                caja_repo=SqlAlchemyCajaRepository(db),
                articulo_repo=SqlAlchemyArticuloRepository(db),
                cliente_repo=SqlAlchemyClienteRepository(db),
                vendedor_repo=SqlAlchemyVendedorRepository(db),
                forma_pago_repo=SqlAlchemyFormaPagoRepository(db),
            )
            cotizaciones = uc.listar_cotizaciones_pendientes()

            if not cotizaciones:
                return "📋 No hay cotizaciones pendientes."

            lines = ["📋 **Cotizaciones pendientes:**\n"]
            for c in cotizaciones[:10]:
                cliente_repo = SqlAlchemyClienteRepository(db)
                cliente = cliente_repo.get_by_id(c.cliente_id)
                nombre = cliente.razon_social if cliente else f"Cliente #{c.cliente_id}"
                numero = f"{c.punto_venta:04d}-{c.numero:08d}"
                lines.append(f"  • #{numero} — {nombre} — ${c.total:,.2f}")

            return "\n".join(lines)
        except Exception as e:
            return f"Error: {str(e)}"
        finally:
            db.close()

    def _generar_cotizacion(self, msg: str) -> str:
        return (
            "Para generar una cotización por WhatsApp, necesito que me indiques:\n\n"
            "1️⃣ **Cliente** — nombre o número de ID\n"
            "2️⃣ **Artículos** — código y cantidad\n\n"
            "Ejemplo: *cotizame 2 BIC-001 para el cliente 1*\n\n"
            "También podés crear cotizaciones desde el sistema POS web."
        )

    def _convertir_cotizacion(self, msg: str) -> str:
        # Extraer número de cotización
        num = self._extraer_numero(msg)
        if num:
            db = SessionLocal()
            try:
                uc = ComprobanteUseCase(
                    repo=SqlAlchemyComprobanteRepository(db),
                    caja_repo=SqlAlchemyCajaRepository(db),
                    articulo_repo=SqlAlchemyArticuloRepository(db),
                    cliente_repo=SqlAlchemyClienteRepository(db),
                    vendedor_repo=SqlAlchemyVendedorRepository(db),
                    forma_pago_repo=SqlAlchemyFormaPagoRepository(db),
                )
                factura = uc.convertir_cotizacion_a_factura(num, tipo_factura=TipoComprobante.FACTURA_B)
                db.commit()
                cliente = SqlAlchemyClienteRepository(db).get_by_id(factura.cliente_id)
                nombre = cliente.razon_social if cliente else "Desconocido"
                numero = f"{factura.punto_venta:04d}-{factura.numero:08d}"
                return (
                    f"✅ **Cotización #{num} convertida a Factura B**\n"
                    f"   Número: {numero}\n"
                    f"   Cliente: {nombre}\n"
                    f"   Total: ${factura.total:,.2f}"
                )
            except Exception as e:
                db.rollback()
                return f"Error al convertir: {str(e)}"
            finally:
                db.close()
        return "Decime el número de cotización que querés convertir. Ejemplo: 'convertí cotización 5'"

    def _bloquear_articulo(self, msg: str) -> str:
        codigo = self._extraer_codigo(msg)
        if not codigo:
            return "Decime el código del artículo a bloquear. Ejemplo: 'bloqueá REP-004'"

        db = SessionLocal()
        try:
            uc = ArticuloUseCase(SqlAlchemyArticuloRepository(db), SqlAlchemyRubroRepository(db))
            articulo = uc.bloquear(codigo)
            db.commit()
            return f"🔒 **{articulo.descripcion}** ({codigo}) bloqueado exitosamente."
        except Exception as e:
            db.rollback()
            return f"Error: {str(e)}"
        finally:
            db.close()

    def _desbloquear_articulo(self, msg: str) -> str:
        codigo = self._extraer_codigo(msg)
        if not codigo:
            return "Decime el código del artículo a desbloquear. Ejemplo: 'desbloqueá BIC-001'"

        db = SessionLocal()
        try:
            uc = ArticuloUseCase(SqlAlchemyArticuloRepository(db), SqlAlchemyRubroRepository(db))
            articulo = uc.desbloquear(codigo)
            db.commit()
            return f"🔓 **{articulo.descripcion}** ({codigo}) desbloqueado. Stock: {articulo.stock_actual}"
        except Exception as e:
            db.rollback()
            return f"Error: {str(e)}"
        finally:
            db.close()

    def _consultar_caja(self) -> str:
        db = SessionLocal()
        try:
            uc = CajaUseCase(SqlAlchemyCajaRepository(db), SqlAlchemyVendedorRepository(db))
            caja = uc.get_abierta()
            if caja:
                vendedor = SqlAlchemyVendedorRepository(db).get_by_id(caja.vendedor_id)
                return (
                    f"✅ **Caja abierta**\n"
                    f"   Número: {caja.id}\n"
                    f"   Vendedor: {vendedor.nombre if vendedor else 'N/A'}\n"
                    f"   Apertura: {caja.fecha_apertura}\n"
                    f"   Saldo inicial: ${caja.saldo_inicial:,.2f}"
                )
            return "❌ No hay ninguna caja abierta."
        except Exception:
            return "❌ No hay ninguna caja abierta."
        finally:
            db.close()

    def _abrir_caja(self, msg: str) -> str:
        """Abre una nueva caja. Extrae saldo_inicial del mensaje si está presente."""
        db = SessionLocal()
        try:
            # Extraer saldo inicial del mensaje (ej: "abrir caja con 50000")
            saldo_inicial = 0.0
            num = self._extraer_numero(msg)
            if num and any(w in msg for w in ["con", "saldo", "$", "pesos", "inicial"]):
                saldo_inicial = float(num)

            uc = CajaUseCase(SqlAlchemyCajaRepository(db), SqlAlchemyVendedorRepository(db))
            caja = uc.abrir(vendedor_id=1, saldo_inicial=saldo_inicial)
            db.commit()
            vendedor = SqlAlchemyVendedorRepository(db).get_by_id(caja.vendedor_id)
            return (
                f"✅ **Caja {caja.id} abierta exitosamente**\n"
                f"   Vendedor: {vendedor.nombre if vendedor else 'N/A'}\n"
                f"   Saldo inicial: ${caja.saldo_inicial:,.2f}\n\n"
                f"Ya podés facturar. ¿Qué más necesitás?"
            )
        except Exception as e:
            db.rollback()
            error_msg = str(e)
            if "ya abierta" in error_msg.lower() or "ya existe" in error_msg.lower():
                # Si ya hay caja abierta, mostrar su estado
                try:
                    caja_abierta = uc.get_abierta()
                    vendedor = SqlAlchemyVendedorRepository(db).get_by_id(caja_abierta.vendedor_id)
                    return (
                        f"⚠️ Ya hay una caja abierta (#{caja_abierta.id}).\n"
                        f"   Vendedor: {vendedor.nombre if vendedor else 'N/A'}\n"
                        f"   Cerrá la caja actual antes de abrir una nueva."
                    )
                except Exception:
                    return "⚠️ Ya hay una caja abierta. Cerrala antes de abrir una nueva."
            return f"❌ Error al abrir caja: {error_msg}"
        finally:
            db.close()

    def _cerrar_caja(self, msg: str) -> str:
        """Cierra la caja abierta actual."""
        db = SessionLocal()
        try:
            uc = CajaUseCase(SqlAlchemyCajaRepository(db), SqlAlchemyVendedorRepository(db))
            caja = uc.get_abierta()
            caja_id = caja.id
            # Extraer diferencia del mensaje si está presente
            diferencia = 0.0
            num = self._extraer_numero(msg)
            if num and any(w in msg for w in ["diferencia", "diferen"]):
                diferencia = float(num)

            caja = uc.cerrar(caja_id=caja_id, diferencia=diferencia)
            db.commit()
            vendedor = SqlAlchemyVendedorRepository(db).get_by_id(caja.vendedor_id)
            return (
                f"✅ **Caja {caja_id} cerrada exitosamente**\n"
                f"   Vendedor: {vendedor.nombre if vendedor else 'N/A'}\n"
                f"   Saldo inicial: ${caja.saldo_inicial:,.2f}\n"
                f"   Diferencia: ${caja.diferencia:,.2f}\n\n"
                f"Para volver a operar, abrí una nueva caja."
            )
        except Exception as e:
            db.rollback()
            error_msg = str(e)
            if "no abierta" in error_msg.lower() or "no hay" in error_msg.lower():
                return "❌ No hay ninguna caja abierta para cerrar."
            return f"❌ Error al cerrar caja: {error_msg}"
        finally:
            db.close()

    def _listar_comprobantes(self, msg: str) -> str:
        db = SessionLocal()
        try:
            # Determine type from message
            tipo_str = "FACTURA_B"
            if "cotización" in msg or "cotizacion" in msg:
                tipo_str = "COTIZACION"
            elif "factura a" in msg:
                tipo_str = "FACTURA_A"
            elif "factura c" in msg:
                tipo_str = "FACTURA_C"

            tipo = TipoComprobante(tipo_str)
            uc = ComprobanteUseCase(
                repo=SqlAlchemyComprobanteRepository(db),
                caja_repo=SqlAlchemyCajaRepository(db),
                articulo_repo=SqlAlchemyArticuloRepository(db),
                cliente_repo=SqlAlchemyClienteRepository(db),
                vendedor_repo=SqlAlchemyVendedorRepository(db),
                forma_pago_repo=SqlAlchemyFormaPagoRepository(db),
            )
            comprobantes = uc.listar_por_tipo(tipo)

            if not comprobantes:
                return f"No hay {tipo_str.lower()}s registradas."

            lines = [f"📋 **{tipo_str}s:**\n"]
            for c in comprobantes[:10]:
                cliente_repo = SqlAlchemyClienteRepository(db)
                cliente = cliente_repo.get_by_id(c.cliente_id)
                nombre = cliente.razon_social if cliente else "Desconocido"
                numero = f"{c.punto_venta:04d}-{c.numero:08d}"
                lines.append(f"  • #{c.id} — {numero} — {nombre} — ${c.total:,.2f}")

            if len(comprobantes) > 10:
                lines.append(f"\n  ...y {len(comprobantes) - 10} más.")

            return "\n".join(lines)
        except Exception as e:
            return f"Error al listar comprobantes: {str(e)}"
        finally:
            db.close()

    def _ver_comprobante(self, msg: str) -> str:
        num = self._extraer_numero(msg)
        if not num:
            return "Decime el ID o número del comprobante que querés ver. Ejemplo: 'ver factura 1'"

        db = SessionLocal()
        try:
            uc = ComprobanteUseCase(
                repo=SqlAlchemyComprobanteRepository(db),
                caja_repo=SqlAlchemyCajaRepository(db),
                articulo_repo=SqlAlchemyArticuloRepository(db),
                cliente_repo=SqlAlchemyClienteRepository(db),
                vendedor_repo=SqlAlchemyVendedorRepository(db),
                forma_pago_repo=SqlAlchemyFormaPagoRepository(db),
            )
            c = uc.get_by_id(num)
            cliente = SqlAlchemyClienteRepository(db).get_by_id(c.cliente_id)

            lines = [
                f"📄 **{c.tipo.value} N° {c.punto_venta:04d}-{c.numero:08d}**",
                f"   Cliente: {cliente.razon_social if cliente else 'Desconocido'}",
                f"   Fecha: {c.fecha.strftime('%d/%m/%Y %H:%M') if c.fecha else 'N/A'}",
                f"   Total: ${c.total:,.2f}",
                f"   Estado: {c.estado_sincronizacion.value}",
            ]

            if c.detalles:
                lines.append("   **Items:**")
                for d in c.detalles:
                    art = SqlAlchemyArticuloRepository(db).get_by_codigo(d.articulo_codigo)
                    desc = art.descripcion if art else d.articulo_codigo
                    lines.append(f"     - {desc} ({d.articulo_codigo}) × {d.cantidad} = ${d.subtotal:,.2f}")

            if c.formas_pago:
                lines.append("   **Pago:**")
                for fp in c.formas_pago:
                    fp_obj = SqlAlchemyFormaPagoRepository(db).get_by_id(fp.forma_pago_id)
                    nombre = fp_obj.nombre if fp_obj else f"ID {fp.forma_pago_id}"
                    lines.append(f"     - {nombre}: ${fp.monto:,.2f}")

            return "\n".join(lines)
        except Exception as e:
            return f"Error: {str(e)}"
        finally:
            db.close()

    def _listar_facturas_caja(self) -> str:
        db = SessionLocal()
        try:
            caja_uc = CajaUseCase(
                SqlAlchemyCajaRepository(db), SqlAlchemyVendedorRepository(db)
            )
            try:
                caja = caja_uc.get_abierta()
            except Exception:
                return "❌ No hay ninguna caja abierta."

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

            if not facturas:
                return f"📋 Caja #{caja.id} — No hay facturas en esta caja."

            total = sum(f.total for f in facturas)
            lines = [f"📋 **Caja #{caja.id} — {len(facturas)} factura(s), Total: ${total:,.2f}**\n"]

            for c in facturas[:10]:
                cliente = SqlAlchemyClienteRepository(db).get_by_id(c.cliente_id)
                nombre = cliente.razon_social if cliente else "Desconocido"
                lines.append(f"  • {c.tipo.value} {c.punto_venta:04d}-{c.numero:08d} — {nombre} — ${c.total:,.2f}")

            return "\n".join(lines)
        except Exception as e:
            return f"Error: {str(e)}"
        finally:
            db.close()

    # ─── Helpers ────────────────────────────────────────────────────────

    def _extraer_termino(self, msg: str, stopwords: list[str]) -> str:
        """Extrae el término de búsqueda relevante del mensaje."""
        # Primero limpiar signos de puntuación y acentos exóticos
        import unicodedata
        cleaned = msg.lower()
        # Remover signos de puntuación comunes en español
        for ch in "¿?¡!.,;:()[]{}\"'":
            cleaned = cleaned.replace(ch, " ")
        # Normalizar espacios
        words = cleaned.split()
        significant = [w for w in words if w not in stopwords and len(w) > 2]
        return " ".join(significant) if significant else msg.strip()

    def _extraer_numero(self, msg: str) -> Optional[int]:
        """Extrae un número del mensaje."""
        match = re.search(r'\b(\d+)\b', msg)
        return int(match.group(1)) if match else None

    def _extraer_codigo(self, msg: str) -> Optional[str]:
        """Extrae un código de artículo del mensaje (formato XXX-NNN)."""
        match = re.search(r'[A-Z]{2,}-\d{3}', msg.upper())
        if match:
            return match.group(0)
        return None