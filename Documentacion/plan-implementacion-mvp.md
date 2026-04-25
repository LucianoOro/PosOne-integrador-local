# Plan de Implementación MVP - PosONE Integrador

## Contexto

- **Proyecto**: PosONE Integrador Local — sistema POS con agente conversacional de WhatsApp
- **Para**: Entrevista laboral en CASE Sistemas Integrados SA (Mendoza)
- **Diferenciador clave**: WhatsApp AI agent que ejecuta ACCIONES (cotizar, facturar, bloquear artículos), no solo consultas
- **Timeline**: ~4 días
- **Arquitectura**: Hexagonal Lite (Domain → Application → Infrastructure)
- **Stack**: Python 3.12, FastAPI, SQLAlchemy, SQLite, Pydantic, FPDF2, Google Gemini, Twilio

---

## Las 9 Fases

### Fase 1: Dominio Puro
**Objetivo**: Modelar el negocio sin ninguna dependencia externa.

| Tarea | Descripción | Archivo(s) |
|-------|-------------|------------|
| 1.1 | Value Objects: 6 enums con lógica de negocio (`TipoComprobante.es_factura()`, `InventarioEstado.calcular()`, `CondicionIVA.tipo_factura_default()`) | `app/domain/value_objects/enums.py` |
| 1.2 | Entidades: 11 dataclasses puras con comportamiento (`Articulo.calcular_precio()`, `Articulo.descontar_stock()`, `Caja.cerrar()`, `Comprobante.calcular_total()`) | `app/domain/entities/entities.py` |
| 1.3 | Excepciones de dominio: 10 errores de negocio con `error_code` y mensaje descriptivo | `app/domain/exceptions.py` |

**Criterio de completitud**: Todas las clases se instancian y sus métodos funcionan SIN base de datos, SIN API, SIN frameworks.

---

### Fase 2: Infraestructura de Datos
**Objetivo**: Persistir las entidades en SQLite con datos iniciales.

| Tarea | Descripción | Archivo(s) |
|-------|-------------|------------|
| 2.1 | Modelos SQLAlchemy: 10 tablas mapeando entidades (con FKs, indexes, unique constraints) | `app/infrastructure/database/models.py` |
| 2.2 | Conexión SQLite: engine, SessionLocal, Base, dependency `get_db()`, `create_tables()` | `app/infrastructure/database/connection.py` |
| 2.3 | Seed Data: 4 rubros, 10 artículos, 3 clientes, 1 vendedor, 6 formas de pago, 1 caja abierta | `app/infrastructure/database/seed.py` |

**Criterio de completitud**: `create_tables()` crea la BD y `seed_database()` la pobla. Las tablas tienen relaciones correctas.

---

### Fase 3: Puertos y Repositorios
**Objetivo**: Definir contratos (puertos) e implementaciones concretas (adaptadores).

| Tarea | Descripción | Archivo(s) |
|-------|-------------|------------|
| 3.1 | Interfaces abstractas: 8 repositorios (Articulo, Cliente, Caja, Comprobante, Vendedor, FormaPago, PedidoStock, Rubro) | `app/application/ports/*.py` |
| 3.2 | Implementaciones SQLAlchemy: mapeo Model↔Entity para cada repositorio | `app/infrastructure/database/repositories/*.py` |

**Criterio de completitud**: Cada repositorio pasa operaciones CRUD básicas contra la BD de test.

---

### Fase 4: Casos de Uso + API REST
**Objetivo**: Orquestar reglas de negocio y exponerlas como endpoints REST.

| Tarea | Descripción | Archivo(s) |
|-------|-------------|------------|
| 4.1 | Schemas Pydantic: DTOs de request/response para todas las entidades | `app/application/schemas.py` |
| 4.2 | Casos de uso: ArticuloUseCase, ClienteUseCase, CajaUseCase, ComprobanteUseCase, CatalogoUseCase, PedidoStockUseCase | `app/application/use_cases/*.py` |
| 4.3 | Routers FastAPI: artículos, clientes, cajas, comprobantes, catálogo, pedidos, health | `app/infrastructure/api/routers/*.py` |
| 4.4 | main.py: CORS, lifespan (seed data), exception handler de dominio | `app/main.py` |

**Criterio de completitud**: El servidor arranca, todos los endpoints responden, seed data funciona, facturación descuenta stock y recalcula inventario.

---

### Fase 5: Generación de PDF
**Objetivo**: Generar PDFs de cotizaciones y facturas para enviar por WhatsApp.

| Tarea | Descripción | Archivo(s) |
|-------|-------------|------------|
| 5.1 | Servicio de generación de PDF con FPDF2: cotización y factura B con datos del negocio, tabla de ítems, totales | `app/infrastructure/pdf/generador_pdf.py` |
| 5.2 | Endpoint `/comprobantes/{id}/pdf` para descargar el PDF | `app/infrastructure/api/routers/comprobantes_router.py` |
| 5.3 | Caso de uso `generar_pdf_cotizacion()` y `generar_pdf_factura()` | `app/application/use_cases/comprobante_use_case.py` |

**Criterio de completitud**: Al hacer GET `/comprobantes/1/pdf` se devuelve un archivo PDF válido con los datos del comprobante.

---

### Fase 6: Agente WhatsApp (Twilio Webhook)
**Objetivo**: Recibir mensajes de WhatsApp y responder con acciones del sistema.

| Tarea | Descripción | Archivo(s) |
|-------|-------------|------------|
| 6.1 | Webhook endpoint `/api/whatsapp/webhook` que recibe mensajes de Twilio | `app/infrastructure/api/routers/whatsapp_router.py` |
| 6.2 | Servicio de procesamiento de mensajes: parsear intención → mapear a acción → ejecutar caso de uso → formatear respuesta | `app/infrastructure/whatsapp/message_processor.py` |
| 6.3 | Respuestas con texto formateado (stock, precio, cotizaciones pendientes) | Ídem anterior |
| 6.4 | Envío de PDF de cotización por WhatsApp (Twilio Media) | `app/infrastructure/whatsapp/twilio_service.py` |

**Flujos del agente**:
- "¿qué stock tenés de bicicletas?" → búsqueda de artículos → respuesta formateada
- "cotizame 2 Mountain Bike Ranger" → crea cotización → genera PDF → envía por WhatsApp
- "bloqueá el artículo REP-004" → bloquea artículo → confirmación
- "cotizaciones pendientes de Juan Pérez" → lista cotizaciones → respuesta
- "convertí la cotización 5 en factura" → convierte → confirmación

**Criterio de completitud**: Enviando un mensaje de WhatsApp al sandbox de Twilio, se recibe una respuesta coherente del sistema.

---

### Fase 7: Agente Inteligente (Gemini Function Calling)
**Objetivo**: Reemplazar el parser manual de intenciones con Gemini como cerebro del agente.

| Tarea | Descripción | Archivo(s) |
|-------|-------------|------------|
| 7.1 |	Configurar Google AI Studio (Gemini) con API key | `.env` |
| 7.2 | Definir function declarations para las acciones del sistema (buscar artículos, crear cotización, bloquear, convertir, etc.) | `app/infrastructure/ai/gemini_functions.py` |
| 7.3 | Servicio Gemini: enviar mensaje → recibir función a ejecutar → ejecutar caso de uso → devolver resultado a Gemini → respuesta natural | `app/infrastructure/ai/gemini_service.py` |
| 7.4 | Integrar Gemini en el message_processor reemplazando el parser manual | `app/infrastructure/whatsapp/message_processor.py` |

**Criterio de completitud**: El usuario escribe lenguaje natural por WhatsApp y Gemini decide qué función ejecutar. Ej: "necesito 2 mountain bike, cotizame" → Gemini llama `crear_cotizacion` → se genera PDF → se envía.

---

### Fase 8: Chat Web
**Objetivo**: Interfaz web minimalista como canal alternativo a WhatsApp para la demo.

| Tarea | Descripción | Archivo(s) |
|-------|-------------|------------|
| 8.1 | Endpoint `/api/chat/message` (POST) que recibe mensaje y devuelve respuesta del agente | `app/infrastructure/api/routers/chat_router.py` |
| 8.2 | Frontend HTML/JS mínimo con interfaz de chat (input + historial) | `app/static/index.html` |
| 8.3 | Servir archivos estáticos desde FastAPI | `app/main.py` (montar /static) |

**Criterio de completitud**: El usuario abre `http://localhost:8000/`, escribe un mensaje en el chat web, y recibe respuesta del agente (usa el mismo message_processor que WhatsApp).

---

### Fase 9: Testing, Deploy y Pulido
**Objetivo**: Verificar que todo funciona end-to-end, corregir bugs y preparar la demo.

| Tarea | Descripción | Archivo(s) |
|-------|-------------|------------|
| 9.1 | Tests de integración: probar los 8 flujos felices del documento de decisiones | `tests/test_flujos.py` |
| 9.2 | Tests de errores: caja no abierta, artículo bloqueado, cotización ya convertida | `tests/test_errores.py` |
| 9.3 | Configurar ngrok para exponer el servidor local a Twilio | Documentación |
| 9.4 | Probar flujo completo WhatsApp → Gemini → Acción → PDF → Respuesta | Manual |
| 9.5 | Script de demo: reset BD + seed data + abrir caja + secuencia de demostración | `scripts/demo.sh` |
| 9.6 | Limpiar código, comments, type hints | Todos los archivos |
| 9.7 | Documentación final: README con instrucciones de setup | `README.md` |

**Criterio de completitud**: El evaluador puede clonar el repo, correr `pip install -r requirements.txt && uvicorn app.main:app`, y probar los endpoints + WhatsApp + chat web.

---

## Priorización

Las fases 1-4 son **obligatorias** (sin ellas no hay nada que demostrar).
Las fases 5-7 son el **diferenciador** (WhatsApp con acciones es lo que impresiona en la entrevista).
Las fases 8-9 son **valor agregado** (chat web y pulido).

```
Obligatorias:  F1 → F2 → F3 → F4
Diferenciador: F5 → F6 → F7
Valor agregado: F8 → F9
```

Si el tiempo aprieta, F7 (Gemini) se puede simplificar con un parser manual en F6, y F8 (chat web) se puede omitir.

---

## Estado Actual

| Fase | Estado | Notas |
|------|--------|-------|
| Fase 1: Dominio Puro | ✅ Completada | enums, entidades, excepciones |
| Fase 2: Infraestructura de Datos | ✅ Completada | models, connection, seed |
| Fase 3: Puertos y Repositorios | ✅ Completada | 8 puertos + 8 implementaciones |
| Fase 4: Casos de Uso + API | ✅ Completada | 6 use cases, 6 routers, main.py |
| Fase 5: Generación de PDF | 🔲 Pendiente | Próxima fase |
| Fase 6: WhatsApp Webhook | 🔲 Pendiente | |
| Fase 7: Gemini Integration | 🔲 Pendiente | |
| Fase 8: Chat Web | 🔲 Pendiente | |
| Fase 9: Testing y Deploy | 🔲 Pendiente | |