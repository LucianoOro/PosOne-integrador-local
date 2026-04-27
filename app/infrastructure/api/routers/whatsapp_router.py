"""Router: Webhook de WhatsApp (Twilio).

Recibe mensajes entrantes de Twilio WhatsApp y los procesa
a través del MessageProcessor con Gemini AI.
"""

import logging

from fastapi import APIRouter, Request
from fastapi.responses import Response

from app.infrastructure.whatsapp.message_processor import MessageProcessor

logger = logging.getLogger(__name__)

router = APIRouter(tags=["WhatsApp Webhook"])


def _get_processor() -> MessageProcessor:
    """Factory para obtener una instancia de MessageProcessor."""
    return MessageProcessor()


@router.post("/webhook")
async def whatsapp_webhook(request: Request):
    """Endpoint que recibe webhooks de Twilio WhatsApp.

    Twilio envía los datos del mensaje como form-data con campos:
    - From: número del remitente (ej: whatsapp:+5491112345678)
    - Body: texto del mensaje

    Para MVP: no se valida la firma de Twilio.
    En producción, agregar validación de firma con TWILIO_AUTH_TOKEN.
    """
    form_data = await request.form()

    # Extraer datos del mensaje
    from_number = str(form_data.get("From", ""))
    body = str(form_data.get("Body", ""))

    # Limpiar el prefijo "whatsapp:" del número
    if from_number.startswith("whatsapp:"):
        from_number = from_number.replace("whatsapp:", "", 1)

    logger.info("WhatsApp webhook: from=%s, body=%s", from_number, body[:100])

    if not from_number or not body:
        logger.warning("Webhook recibido sin From o Body")
        # Retornar TwiML vacío (no respondemos)
        return Response(
            content='<?xml version="1.0" encoding="UTF-8"?><Response />',
            media_type="application/xml",
        )

    # Procesar mensaje a través del MessageProcessor
    try:
        processor = _get_processor()
        response_text = processor.process_incoming(from_number, body)
    except Exception:
        logger.exception("Error procesando webhook de WhatsApp")
        response_text = "Disculpá, hubo un error procesando tu mensaje. Intentá de nuevo."

    # Retornar TwiML vacío (la respuesta se envió vía API de Twilio)
    return Response(
        content='<?xml version="1.0" encoding="UTF-8"?><Response />',
        media_type="application/xml",
    )