"""Servicio de integración con Twilio WhatsApp.

Encapsula el envío de mensajes de texto y documentos PDF
a través de la API de Twilio para WhatsApp Business.
"""

import logging
import os

from twilio.rest import Client

logger = logging.getLogger(__name__)


class TwilioService:
    """Servicio para enviar mensajes WhatsApp vía Twilio."""

    def __init__(self):
        self.account_sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
        self.auth_token = os.environ.get("TWILIO_AUTH_TOKEN", "")
        self.phone_number = os.environ.get("TWILIO_PHONE_NUMBER", "")
        self.base_url = os.environ.get("APP_BASE_URL", "")
        self._client: Client | None = None

    @property
    def client(self) -> Client:
        """Lazy initialization del cliente Twilio."""
        if self._client is None:
            if not self.account_sid or not self.auth_token:
                raise ValueError(
                    "TWILIO_ACCOUNT_SID y TWILIO_AUTH_TOKEN deben estar configurados"
                )
            self._client = Client(self.account_sid, self.auth_token)
        return self._client

    @property
    def is_configured(self) -> bool:
        """Verifica si las credenciales de Twilio están configuradas."""
        return bool(self.account_sid and self.auth_token and self.phone_number)

    def send_message(self, to: str, body: str) -> None:
        """Envía un mensaje de texto WhatsApp.

        Args:
            to: Número de destino (ej: +5491112345678).
            body: Texto del mensaje.
        """
        if not self.is_configured:
            logger.warning("Twilio no configurado — mensaje no enviado a %s: %s", to, body[:80])
            return

        try:
            self.client.messages.create(
                from_=f"whatsapp:{self.phone_number}",
                body=body,
                to=f"whatsapp:{to}",
            )
            logger.info("Mensaje enviado a %s", to)
        except Exception:
            logger.exception("Error enviando mensaje WhatsApp a %s", to)

    def send_pdf(
        self,
        to: str,
        pdf_bytes: bytes,
        filename: str,
        caption: str,
        media_url: str | None = None,
    ) -> None:
        """Envía un documento PDF vía WhatsApp.

        Twilio requiere una URL pública para enviar medios.
        Si se proporciona media_url, se usa directamente.
        Si no, se construye desde APP_BASE_URL + /api/comprobantes/{id}/pdf.
        Si no hay URL disponible, se envía solo el caption como texto.

        Args:
            to: Número de destino (ej: +5491112345678).
            pdf_bytes: Bytes del PDF (reservado para uso futuro).
            filename: Nombre del archivo PDF.
            caption: Texto descriptivo que acompaña al PDF.
            media_url: URL pública del PDF. Si es None, intenta construirse
                       desde APP_BASE_URL (requiere que el archivo ya esté
                       servido por la API REST).
        """
        if not self.is_configured:
            logger.warning("Twilio no configurado — PDF no enviado a %s", to)
            return

        if not media_url:
            # Sin URL pública, no podemos enviar medios por Twilio
            # En su lugar, enviamos un mensaje de texto informativo
            logger.warning(
                "No hay URL pública para el PDF — enviando texto alternativo a %s", to
            )
            self.send_message(to, f"📄 {caption}\n\nEl documento PDF está disponible en el sistema.")
            return

        try:
            self.client.messages.create(
                from_=f"whatsapp:{self.phone_number}",
                body=caption,
                to=f"whatsapp:{to}",
                media_url=[media_url],
            )
            logger.info("PDF enviado a %s: %s", to, filename)
        except Exception:
            logger.exception("Error enviando PDF WhatsApp a %s", to)
            # Fallback: enviar solo el caption como texto
            self.send_message(to, f"📄 {caption}\n\n(No se pudo enviar el PDF)")