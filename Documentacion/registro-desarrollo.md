# Registro de Desarrollo - PosONE Integrador MVP

> Documento vivo. Se actualiza con cada tarea completada.

---

## Fase 1: Dominio Puro ✅

### Tarea 1.1 — Value Objects (Enums con lógica de negocio)
- **Archivo**: `app/domain/value_objects/enums.py`
- **Qué se hizo**: Se crearon 6 enums que extienden `str, Enum`:
  - `TipoComprobante`: A/B/C/COTIZACION/PRESUPUESTO/NC + métodos `es_factura()`, `desconta_stock()`
  - `InventarioEstado`: BAJO/MEDIO/ALTO/BLOQUEADO + método `calcular(stock_actual, stock_minimo)` con umbrales D5
  - `CondicionIVA`: RI/CF/MONOTRIBUTO/EXENTO + método `tipo_factura_default()` (D3)
  - `EstadoCaja`: ABIERTA/CERRADA
  - `EstadoSincronizacion`: PENDIENTE/SINCRONIZADO
  - `EstadoPedido`: PENDIENTE/ENVIADO/RECIBIDO
- **Por qué**: Los enums encapsulan reglas de negocio que las entidades usan. Al heredar de `str, Enum` se serializan directamente en JSON y Pydantic los acepta como strings.
- **Decisión**: Se eligió `str, Enum` en vez de `IntEnum` porque la API habla JSON y los strings son más legibles. No hubo cambio respecto a lo planificado.

### Tarea 1.2 — Entidades de Dominio (11 dataclasses puras)
- **Archivo**: `app/domain/entities/entities.py`
- **Qué se hizo**: 11 dataclasses con comportamiento:
  - `Articulo`: `calcular_precio()`, `actualizar_inventario_estado()`, `descontar_stock()`, `bloquear()`, `desbloquear()`
  - `Caja`: `cerrar()`
  - `Comprobante`: `calcular_total()`, propiedades `es_factura` y `descuenta_stock`
  - `DetalleComprobante`: `calcular_subtotal()`
  - Las demás entidades (Rubro, Cliente, Vendedor, FormaPago, ComprobanteFormaPago, PedidoStock, DetallePedidoStock) son datacontainers con defaults.
- **Por qué**: Las entidades encapsulan estado + comportamiento. Las reglas de negocio (calcular precio según lista, descontar stock y recalcular estado, cerrar caja con fecha) viven AQUÍ, no en los servicios ni en la BD.
- **Decisión**: Se unificaron todas las entidades en un solo archivo en vez de uno por clase porque el archivo tiene ~210 líneas y es navegable. Si creciera mucho, se separarían.

### Tarea 1.3 — Excepciones de Dominio
- **Archivo**: `app/domain/exceptions.py`
- **Qué se hizo**: Jerarquía de excepciones con `PosOneError` como base, cada una con `error_code` y `message`:
  - `CajaNoAbiertaError`, `CajaYaAbiertaError`
  - `ArticuloBloqueadoError`, `ArticuloNoEncontradoError`, `StockInsuficienteError`
  - `CotizacionYaConvertidaError`, `CotizacionNoEncontradaError`, `ComprobanteNoEncontradoError`, `TipoComprobanteInvalidoError`
  - `ClienteNoEncontradoError`, `PedidoNoEncontradoError`
- **Por qué**: Las excepciones de dominio llevan `error_code` para que el exception handler en `main.py` los mapee a HTTP status codes sin necesidad de `if/elif` por tipo de excepción. Es más mantenible y extensible.
- **Cambio respecto a lo planificado**: Se añadió `error_code` que no estaba en el diseño original. Permite el mapeo automático en el handler.

---

## Fase 2: Infraestructura de Datos ✅

### Tarea 2.1 — Modelos SQLAlchemy (10 tablas)
- **Archivo**: `app/infrastructure/database/models.py`
- **Qué se hizo**: 10 clases que heredan de `Base` (DeclarativeBase):
  - `RubroModel`, `ArticuloModel`, `ClienteModel`, `VendedorModel`, `CajaModel`
  - `ComprobanteModel`, `DetalleComprobanteModel`, `FormaPagoModel`, `ComprobanteFormaPagoModel`
  - `PedidoStockModel`, `DetallePedidoStockModel`
  - Con indexes: `ix_articulos_rubro_id`, `ix_articulos_inventario_estado`, `ix_articulos_codigo_barra`, `ix_articulos_codigo_rapido`, `ix_comprobantes_tipo_estado`, `ix_comprobantes_fecha`, `ix_comprobantes_cotizacion_origen`
  - Con unique constraint: `uq_comprobante_punto_numero_tipo` (punto_venta + numero + tipo)
  - Con cascade delete-orphan en detalles y formas de pago
- **Por qué**: Los modelos SON adaptadores de infraestructura. La capa de dominio NUNCA los ve. Los mappers Model↔Entity viven en los repositorios, no en los modelos.
- **Decisión**: Se usó `server_default=func.now()` para `fecha_apertura` y `fecha` en Comprobante. Esto permite que SQLite asigne la fecha automáticamente sin necesidad de setearla en el código.

### Tarea 2.2 — Conexión SQLite
- **Archivo**: `app/infrastructure/database/connection.py`
- **Qué se hizo**: `engine`, `SessionLocal`, `Base` (DeclarativeBase), `get_db()` dependency para FastAPI, `create_tables()`.
- **Por qué**: SQLite es perfecto para un MVP local. `check_same_thread=False` es necesario porque FastAPI usa async y múltiples threads pueden acceder a la misma conexión.

### Tarea 2.3 — Seed Data
- **Archivo**: `app/infrastructure/database/seed.py`
- **Qué se hizo**: `seed_database()` que verifica si ya hay datos (idempotente) y si no:
  - 4 rubros (Bicicletas y Rodados, Repuestos y Accesorios, Indumentaria, Componentes)
  - 10 artículos variados con datos realistas (Bicicleta MB Ranger 29, Casco ProRider, Grupo Shimano Deore 12V, etc.)
  - 3 clientes (CF genérico, Distribuidora Mendocina SRL RI, Bicicleteras Juan Pérez Monotributo)
  - 1 vendedor default
  - 6 formas de pago (Efectivo, TC, TD, Cta Cte, Cheque, Transferencia)
  - 1 caja abierta (para poder facturar inmediatamente)
- **Por qué**: Los datos son representativos de una bicicletería real, que es el nicho de CASE SA. Incluyen artículos con distintos estados de inventario (ALTO, MEDIO, BAJO) para probar todos los flujos.
- **Decisión**: La semilla se ejecuta en el lifespan de FastAPI, no en un script separado. Esto significa que al levantar el servidor, la BD ya está lista. Si la BD ya tiene datos, no hace nada (idempotente).

---

## Fase 3: Puertos y Repositorios ✅

### Tarea 3.1 — Interfaces abstractas (8 puertos)
- **Archivos**: `app/application/ports/*.py`
- **Qué se hizo**: 8 clases abstractas (ABC) que definen QUÉ se puede hacer sin CÓMO:
  - `ArticuloRepository`: get_by_codigo, get_by_codigo_barra, get_by_codigo_rapido, search_by_descripcion, search (flexible), list_all, list_by_rubro, list_by_inventario_estado, save
  - `ClienteRepository`: get_by_id, get_by_cuit, search_by_razon_social, list_all, save
  - `CajaRepository`: get_by_id, find_abierta, save
  - `ComprobanteRepository`: get_by_id, save, get_next_numero, list_by_tipo, list_cotizaciones_pendientes, list_by_caja
  - `VendedorRepository`: get_by_id, list_all
  - `FormaPagoRepository`: get_by_id, list_all
  - `PedidoStockRepository`: get_by_id, save, list_by_estado
  - `RubroRepository`: get_by_id, list_all
- **Por qué**: Los puertos son el contratoHexagonal. Si mañana queremos cambiar SQLite por PostgreSQL, solo creamos nuevas implementaciones. Los casos de uso NO cambian.

### Tarea 3.2 — Implementaciones SQLAlchemy (8 repos)
- **Archivos**: `app/infrastructure/database/repositories/*.py`
- **Qué se hizo**: 8 clases que implementan los puertos usando SQLAlchemy ORM:
  - Cada una tiene funciones `_model_to_entity()` y (donde aplica) `_entity_to_model()` para hacer el mapeo.
  - `ArticuloRepository.search()`: usa `OR` con `ilike` para buscar por código, descripción, código barra y código rápido — todos en una sola query (D11).
  - `ComprobanteRepository.save()`: maneja la persistencia en cascada manualmente (detalles + formas de pago) porque SQLAlchemy cascade no se lleva bien con nuestra lógica de dominio.
  - `ComprobanteRepository.list_cotizaciones_pendientes()`: usa subquery para encontrar cotizaciones cuyo ID NO aparece como `cotizacion_origen_id` en otra factura (D2).
  - `ComprobanteRepository.get_next_numero()`: usa `func.max()` para obtener el próximo número correlativo.
- **Decisión**: Los mappers están en cada archivo de repo y no en un archivo central porque cada repositorio sabe mejor cómo mapear su propio modelo. Si un campo cambia, se cambia en un solo lugar.

---

## Fase 4: Casos de Uso + API REST ✅

### Tarea 4.1 — Schemas Pydantic
- **Archivo**: `app/application/schemas.py`
- **Qué se hizo**: DTOs de entrada/salida para todos los endpoints:
  - Response schemas: `ArticuloResponse`, `ClienteResponse`, `CajaResponse`, `ComprobanteResponse`, `DetalleComprobanteResponse`, `FormaPagoResponse`, `RubroResponse`, `VendedorResponse`, `PedidoStockResponse`, etc.
  - Request schemas: `ComprobanteRequest` (con detalles y formas de pago anidados), `CotizacionConvertRequest`, `CajaOpenRequest`, `CajaCloseRequest`, `ArticuloSearchRequest`, `PedidoStockRequest`
  - `ErrorResponse` con `error_code` y `message`
- **Por qué**: Los schemas son la API contract. Separan lo que la API recibe/devuelve de las entidades de dominio. Las entidades NUNCA se exponen directamente.

### Tarea 4.2 — Casos de Uso (6)
- **Archivos**: `app/application/use_cases/*.py`
- **Qué se hizo**:
  - `ArticuloUseCase`: get_by_codigo, search, list_all, list_by_rubro, list_bajo_stock, bloquear, desbloquear
  - `ClienteUseCase`: get_by_id, search, list_all
  - `CajaUseCase`: get_abierta, abrir, cerrar, require_caja_abierta (lanza CajaNoAbiertaError)
  - `ComprobanteUseCase`: crear_comprobante (valida caja, artículos, calcula precios, descuenta stock si es factura, asigna número), get_by_id, listar_cotizaciones_pendientes, listar_por_tipo, listar_por_caja, convertir_cotizacion_a_factura
  - `CatalogoUseCase`: listar_rubros, get_rubro, listar_formas_pago, get_forma_pago, listar_vendedores, get_vendedor
  - `PedidoStockUseCase`: crear_pedido (snapshot de stock), get_by_id, listar_pendientes, listar_por_estado
- **Por qué**: Los casos de uso ORQUESTAN las reglas de negocio. No hacen SQL, no saben de HTTP. Reciben repositorios por inyección y coordinan entidades + excepciones.
- **Reglas de negocio implementadas**:
  - (D3) No se puede facturar sin caja abierta → `CajaUseCase.require_caja_abierta()`
  - No se puede facturar artículo bloqueado → `ComprobanteUseCase.crear_comprobante()` valida
  - (D4) Precio público o mayorista según flag → `Articulo.calcular_precio(lista_mayorista)`
  - (D5) Inventario se recalcula automáticamente → `Articulo.descontar_stock()` llama a `actualizar_inventario_estado()`
  - (D2) Cotización → Factura: crea NUEVO comprobante, no modifica original → `ComprobanteUseCase.convertir_cotizacion_a_factura()`

### Tarea 4.3 — Routers FastAPI (6)
- **Archivos**: `app/infrastructure/api/routers/*.py`
- **Qué se hizo**:
  - `health_router`: GET `/health`
  - `articulos_router`: GET `/articulos/`, GET `/articulos/buscar?q=`, GET `/articulos/bajo-stock`, GET `/articulos/rubro/{id}`, GET `/articulos/{codigo}`, POST `/articulos/{codigo}/bloquear`, POST `/articulos/{codigo}/desbloquear`
  - `clientes_router`: GET `/clientes/`, GET `/clientes/buscar?q=`, GET `/clientes/{id}`
  - `cajas_router`: GET `/cajas/abierta`, POST `/cajas/abrir`, POST `/cajas/{id}/cerrar`
  - `comprobantes_router`: POST `/comprobantes/`, GET `/comprobantes/{id}`, GET `/comprobantes/cotizaciones/pendientes`, GET `/comprobantes/tipo/{tipo}`, GET `/comprobantes/caja/{caja_id}`, POST `/comprobantes/cotizacion/{id}/convertir`
  - `catalogo_router`: GET `/catalogo/rubros`, GET `/catalogo/rubros/{id}`, GET `/catalogo/formas-pago`, GET `/catalogo/formas-pago/{id}`, GET `/catalogo/vendedores`, GET `/catalogo/vendedores/{id}`
  - `pedidos_stock_router`: POST `/pedidos-stock/`, GET `/pedidos-stock/{id}`, GET `/pedidos-stock/`
- **Decisión**: Los routers instancian repositorios y casos de uso inline (sin DI container). Para un MVP esto es suficiente y explícito. Si el proyecto creciera, se usaría un contenedor de DI.

### Tarea 4.4 — main.py
- **Archivo**: `app/main.py`
- **Qué se hizo**:
  - `lifespan`: crea tablas + ejecuta seed data al arrancar
  - CORS configurado con `allow_origins=["*"]` (para MVP, en prod se restringe)
  - Exception handler para `PosOneError` que mapea `error_code` → HTTP status:
    - `CAJA_NO_ABIERTA` → 409, `ARTICULO_BLOQUEADO` → 403, `ARTICULO_NO_ENCONTRADO` → 404, etc.
  - Todos los routers montados en la app

---

## Verificación End-to-End (post Fase 4) ✅

Se probaron TODOS los endpoints principales:

| Endpoint | Resultado |
|----------|-----------|
| GET `/health` | ✅ `{"status": "ok"}` |
| GET `/articulos/` | ✅ Lista de 10 artículos con seed data |
| GET `/articulos/buscar?q=bici` | ✅ Búsqueda flexible (3 resultados) |
| GET `/articulos/BIC-001` | ✅ Artículo por código |
| GET `/cajas/abierta` | ✅ Caja abierta con fecha |
| GET `/catalogo/rubros` | ✅ 4 rubros |
| GET `/catalogo/formas-pago` | ✅ 6 formas de pago |
| GET `/clientes/` | ✅ 3 clientes con condición IVA |
| POST `/comprobantes/` (Factura B) | ✅ Se crea con número correlativo, descuenta stock, recalcula inventario |

**Hallazgo importante**: La facturación descuenta stock correctamente (BIC-001: 8→6) y el estado de inventario se recalcula automáticamente (ALTO→MEDIO). Esto valida las decisiones D5 y la lógica en `Articulo.descontar_stock()`.

---

## Fase 5: Generación de PDF 🔲

**Estado**: Pendiente. Próxima fase a implementar.

**Plan**:
- 5.1: Servicio FPDF2 para generar PDF de cotización y factura
- 5.2: Endpoint `/comprobantes/{id}/pdf`
- 5.3: Integrar en caso de uso `ComprobanteUseCase`

---

## Fase 6: WhatsApp Webhook 🔲

**Estado**: Pendiente.

**Plan**:
- 6.1: Webhook endpoint para recibir mensajes de Twilio
- 6.2: Message processor para parsear intenciones
- 6.3: Respuestas formateadas
- 6.4: Envío de PDF por WhatsApp (Twilio Media)

---

## Fase 7: Gemini Function Calling 🔲

**Estado**: Pendiente.

**Plan**:
- 7.1: Configurar API key de Google AI Studio
- 7.2: Definir function declarations
- 7.3: Servicio Gemini que orquesta: mensaje → Gemini → función → caso de uso → respuesta
- 7.4: Integrar en message_processor reemplazando parser manual

---

## Fase 8: Chat Web 🔲

**Estado**: Pendiente.

**Plan**:
- 8.1: Endpoint POST `/api/chat/message`
- 8.2: Frontend HTML/JS mínimo con interfaz de chat
- 8.3: Servir estáticos desde FastAPI

---

## Fase 9: Testing, Deploy y Pulido 🔲

**Estado**: Pendiente.

**Plan**:
- 9.1: Tests de integración de los 8 flujos felices
- 9.2: Tests de errores
- 9.3: Configurar ngrok para Twilio
- 9.4: Probar flujo completo WhatsApp
- 9.5: Script de demo
- 9.6: Limpiar código
- 9.7: README con instrucciones

---

## Cambios Respecto a lo Planificado

| # | Qué cambió | Motivo | Fase |
|---|----------- |-------|------|
| 1 | Se añadió `error_code` a las excepciones de dominio | Permitir mapeo automático a HTTP status en el exception handler sin if/elif por tipo | F1 |
| 2 | Se unificaron entidades en un solo archivo | 210 líneas es navegable; se separarían si crece | F1 |
| 3 | Se usó `server_default=func.now()` en SQLAlchemy | SQLite asigna la fecha automáticamente, simplifica los casos de uso | F2 |
| 4 | Seed data se ejecuta en lifespan, no en script separado | Al levantar el servidor la BD ya está lista para la demo | F2 |
| 5 | Detalles y formas de pago se persisten manualmente en ComprobanteRepository.save() | SQLAlchemy cascade delete-orphan no se lleva bien con nuestra lógica de dominio | F3 |
| 6 | Router instancian repos y use cases inline (sin DI container) | MVP: explícito y simple. Si crece, se agrega DI | F4 |
| 7 | Se creó `ArticuloRepository.search()` con OR + ilike | Búsqueda flexible por código, descripción, barra y rápido en una sola query (D11) | F3 |

---

## Decisiones Técnicas Pendientes (para Fases 5-9)

| # | Decisión | Opciones | Inclinación |
|---|----------|----------|-------------|
| D1-PDF | Formato del PDF | Tabla simple vs diseño profesional | Tabla simple primero, iterar si hay tiempo |
| D2-WA | Procesamiento de mensajes | Parser manual vs Gemini directo | Gemini con function calling (F7), parser simple como fallback (F6) |
| D3-Chat | Frontend | HTML/JS mínimo vs React vs Vercel AI | HTML/JS servido por FastAPI (más simple) |
| D4-Deploy | Hospedaje | Local + ngrok vs Railway/Render | Local + ngrok para la demo |