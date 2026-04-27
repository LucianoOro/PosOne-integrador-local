"""Procesador de mensajes WhatsApp.

Orquesta el flujo completo:
WhatsApp → MessageProcessor → AIService → (function call) → UseCase → Response → Twilio
"""

import logging
import os

from app.infrastructure.ai.ai_service import AIService, AIResult
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
from app.infrastructure.pdf.comprobante_pdf import ComprobantePDFService
from app.infrastructure.whatsapp.twilio_service import TwilioService
from app.infrastructure.whatsapp.fallback_processor import FallbackProcessor

logger = logging.getLogger(__name__)


class MessageProcessor:
    """Procesador de mensajes entrantes de WhatsApp.

    Recibe el mensaje crudo de Twilio, lo procesa a través de Gemini AI,
    y envía la respuesta vía Twilio. Si se generó una cotización,
    también envía el PDF correspondiente.
    """

    def __init__(self):
        self.ai = AIService()
        self.twilio = TwilioService()
        self.fallback = FallbackProcessor()

    def process_incoming(self, from_number: str, message_body: str) -> str:
        """Procesa un mensaje entrante de WhatsApp.

        1. Envía el mensaje a la IA para procesamiento con function calling
        2. Envía la respuesta de texto vía Twilio
        3. Si se generó una cotización, genera y envía el PDF

        Args:
            from_number: Número de WhatsApp del remitente (sin prefijo 'whatsapp:').
            message_body: Texto del mensaje recibido.

        Returns:
            Texto de la respuesta (para debugging o TwiML fallback).
        """
        logger.info("Procesando mensaje de %s: %s", from_number, message_body[:100])

        # 1. Procesar mensaje con IA (con fallback si falla)
        if not self.ai.is_configured:
            # IA no configurada → usar fallback rule-based
            logger.info("IA no configurada — usando fallback rule-based")
            response_text = self.fallback.process(message_body)
            self._send_text(from_number, response_text)
            return response_text

        try:
            result = self.ai.process_message(from_number, message_body)
        except Exception as e:
            error_msg = str(e)
            logger.warning("Error en IA, usando fallback: %s", error_msg[:100])
            response_text = self.fallback.process(message_body)
            self._send_text(from_number, response_text)
            return response_text

        # 2. Enviar respuesta de texto
        self._send_text(from_number, result.text)

        # 3. Si se generó una cotización, enviar PDF
        if result.cotizacion_id:
            self._send_cotizacion_pdf(from_number, result.cotizacion_id)

        return result.text

    def _send_text(self, to: str, text: str) -> None:
        """Envía un mensaje de texto vía Twilio."""
        self.twilio.send_message(to, text)

    def _send_cotizacion_pdf(self, to: str, cotizacion_id: int) -> None:
        """Genera y envía el PDF de una cotización vía Twilio."""
        db = SessionLocal()
        try:
            uc = self._get_comprobante_use_case(db)
            comp = uc.get_by_id(cotizacion_id)
            nombres = self._resolve_nombres(comp, db)

            # Generar PDF
            pdf_service = ComprobantePDFService()
            pdf_bytes = pdf_service.generar_pdf(comp, nombres)

            filename = f"COTIZACION_{comp.punto_venta:04d}-{comp.numero:08d}.pdf"
            caption = f"Cotización N° {comp.punto_venta:04d}-{comp.numero:08d}"

            # Construir URL del PDF si APP_BASE_URL está configurado
            base_url = os.environ.get("APP_BASE_URL", "")
            media_url = None
            if base_url:
                media_url = f"{base_url}/comprobantes/{comp.id}/pdf"

            self.twilio.send_pdf(
                to=to,
                pdf_bytes=pdf_bytes,
                filename=filename,
                caption=caption,
                media_url=media_url,
            )
        except Exception:
            logger.exception("Error generando/enviando PDF de cotización %s", cotizacion_id)

    def _get_comprobante_use_case(self, db):
        """Factory method para ComprobanteUseCase."""
        from app.application.use_cases.comprobante_use_case import ComprobanteUseCase
        return ComprobanteUseCase(
            repo=SqlAlchemyComprobanteRepository(db),
            caja_repo=SqlAlchemyCajaRepository(db),
            articulo_repo=SqlAlchemyArticuloRepository(db),
            cliente_repo=SqlAlchemyClienteRepository(db),
            vendedor_repo=SqlAlchemyVendedorRepository(db),
            forma_pago_repo=SqlAlchemyFormaPagoRepository(db),
        )

    def _resolve_nombres(self, comprobante, db) -> dict:
        """Resuelve nombres relacionados a un comprobante (cliente, vendedor, artículos)."""
        cliente_repo = SqlAlchemyClienteRepository(db)
        vendedor_repo = SqlAlchemyVendedorRepository(db)
        articulo_repo = SqlAlchemyArticuloRepository(db)
        forma_pago_repo = SqlAlchemyFormaPagoRepository(db)

        cliente = cliente_repo.get_by_id(comprobante.cliente_id)
        vendedor = vendedor_repo.get_by_id(comprobante.vendedor_id)

        codigos = {d.articulo_codigo for d in comprobante.detalles}
        articulos_map = {}
        for codigo in codigos:
            art = articulo_repo.get_by_codigo(codigo)
            if art:
                articulos_map[codigo] = art.descripcion

        fp_ids = {fp.forma_pago_id for fp in comprobante.formas_pago}
        formas_pago_map = {}
        for fp_id in fp_ids:
            fp = forma_pago_repo.get_by_id(fp_id)
            if fp:
                formas_pago_map[fp_id] = fp.nombre

        return {
            "cliente_razon_social": cliente.razon_social if cliente else None,
            "cliente_cuit": cliente.cuit if cliente else None,
            "cliente_condicion_iva": cliente.condicion_iva.value if cliente else None,
            "vendedor_nombre": vendedor.nombre if vendedor else None,
            "articulos_map": articulos_map,
            "formas_pago_map": formas_pago_map,
        }