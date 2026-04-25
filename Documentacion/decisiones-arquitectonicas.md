# Decisiones Arquitectónicas - PosONE MVP

## Contexto del Proyecto

- **Para quién**: Entrevista laboral en CASE Sistemas Integrados SA (Mendoza)
- **Producto original**: PosONE (Punto de Venta integrado con Bejerman ERP)
- **Diferenciador MVP**: Agente conversacional de WhatsApp con capacidad de ACCIONES (no solo consultas)
- **Timeline**: ~4 días
- **Arquitectura**: Hexagonal Lite (Puertos y Adaptadores)

---

## 1. Por Qué Existe Cada Entidad

### 1.1 Rubro

**¿Por qué?** En el sistema real PosONE, cuando se hace un Pedido de Stock (reposición), la grilla muestra la columna "Rubro". Es la agrupación natural de los artículos: Bicicletas, Repuestos, Indumentaria, Componentes. Sin Rubro, los artículos son una lista plana sin organización, lo cual no refleja cómo funciona un comercio real.

Además, el agente de WhatsApp puede responder "¿qué rubros tenés?" y filtrar búsquedas por categoría, lo que enriquece la experiencia conversacional.

**Atributos**: `id`, `nombre`, `activo`. Simple. El flag `activo` permite desactivar rubros sin eliminarlos (baja lógica).

---

### 1.2 Articulo

**¿Por qué?** Es la entidad central del POS. No hay punto de venta sin productos. En PosONE encontramos que los artículos tienen dos precios (público y mayorista), información de stock (actual, mínimo, estado), y códigos alternativos (barra, rápido).

**¿Por qué `codigo_barra` y `codigo_rapido` separados?** En la demo del sistema, el ingreso de productos se hace de dos formas: por selección en dropdown, o por escaneo/manual de código de barra. El `codigo_rapido` es un atajo para vendedores que se saben los códigos de memoria. Son campos distintos porque sirven a propósitos distintos: el código de barra es universal (EAN), el código rápido es interno del negocio.

**¿Por qué `precio_publico` y `precio_mayorista` en el mismo modelo?** PosONE tiene un flag "Lista P. Mayorista" en la pantalla de emisión. Si está tildado, el precio cambia. En vez de crear una tabla de listas de precios dinámicas (que no vamos a implementar en 4 días), ponemos los dos precios directamente en el artículo. Es simple, refleja el sistema real, y funciona.

**¿Por qué `inventario_estado` como campo y no calculado al vuelo?** En la grilla de Pedidos de Stock del sistema real, el inventario_estado (BAJO en rojo, MEDIO en amarillo, ALTO en verde) aparece como una **columna persistente**. Lo recalculamos cada vez que el stock cambia, pero lo almacenamos para que las consultas sean eficientes sin recalcular cada vez.

**¿Por qué `activo`?** Los artículos se desactivan, no se eliminan. Un artículo inactivo no aparece en búsquedas pero sigue referenciado en facturas pasadas.

---

### 1.3 Cliente

**¿Por qué?** Una factura necesita un comprador. En el sistema real, el vendedor selecciona el cliente de un dropdown que muestra "Denominación", "Condición IVA" y "CUIT". La `condicion_iva` es el campo más importante: determina si la factura es A, B o C. Sin esta distinción, no estamos hechos un POS argentino.

**¿Por qué `cuit` con UNIQUE?** El CUIT es el identificador fiscal único de una persona/empresa en Argentina. No pueden existir dos clientes con el mismo CUIT.

**¿Por qué `condicion_iva` como enum y no string libre?** Porque los 4 valores ( Responsable Inscripto, Consumidor Final, Monotributo, Exento) son los únicos que reconoce AFIP. No tiene sentido permitir valores arbitrarios.

---

### 1.4 Vendedor

**¿Por qué?** En la pantalla de emisión de comprobantes de PosONE, aparece un dropdown "Vendedor". La Caja también referencia al vendedor que la abrió. El comprobante tiene vendedor.

**¿Por qué lo hardcodeamos en el MVP?** Porque gestión de vendedores (CRUD, login, permisos) no suma valor a la entrevista. Pero la entidad EXISTE en el dominio porque si no, habría una FK colgando sin sentido en Comprobante y Caja.

**MVP**: Un único vendedor "Vendedor Default" creado en seed data. Todas las operaciones lo usan automáticamente.

---

### 1.5 Caja

**¿Por qué?** En PosONE, la pantalla de facturación **se bloquea** si no hay caja abierta. El vendedor tiene que ir a "Caja" → "Abrir caja" antes de poder facturar. Es una regla de negocio real: control de turnos y de fondos.

**¿Por qué `saldo_inicial` y `diferencia`?** En la demo, al abrir caja se ingresa un "Saldo Inicial" y opcionalmente una "Diferencia" (para ajustes). Estos campos permiten al fin del día comparar el efectivo que debería haber con lo que hay realmente (cierre de caja ciego o abierto).

**¿Por qué es prerrequisito para facturar?** Porque en Argentina, el punto de venta fiscal requiere un responsable (cajero/vendedor) que se hace cargo de los fondos. Sin caja abierta, no hay quién responda.

**Relación con Comprobante**: Cada comprobante referencea la caja en la que fue emitido. Esto permite luego saber qué facturas corresponden a cada turno.

---

### 1.6 Comprobante

**¿Por qué?** Es la entidad central del proceso de venta. Unifica Factura, Cotización, Presupuesto y Nota de Crédito porque **todos comparten la misma estructura**: cliente, vendedor, items, totales. La diferencia es el `tipo` y las reglas de negocio asociadas.

**¿Por qué `punto_venta` y `numero`?** En Argentina, los comprobantes fiscales tienen numeración correlativa por punto de venta (ej: Punto de Venta 001, Factura 00000001). Esto es AFIP. En nuestro MVP es manual, pero el campo existe porque tiene que estar.

**¿Por qué `cotizacion_origen_id`?** Cuando una cotización se convierte en factura, necesitamos rastrear el origen. Este campo FK apunta al comprobante original (la cotización). Si es NULL, el comprobante se creó desde cero. Si tiene valor, vino de una conversión.

**¿Por qué `consumidor_final` y `lista_mayorista` como flags?** Porque en la pantalla de emisión de PosONE, hay checkboxes para "Consumidor Final" y "Lista P. Mayorista". El primero autoselecciona el cliente genérico y fuerza Factura B. El segundo cambia los precios a mayorista. Son decisiones de UI que impactan en el dominio.

**¿Por qué `descuento_pie` separado del descuento por ítem?** En la demo, el flujo de facturación tiene "Descuento Pie Factura" como campo aparte. Es un descuento que se aplica AL TOTAL del comprobante, no por ítem. Es una práctica común en comercios argentinos (ej: "10% off en toda la compra").

**¿Por qué `estado_sincronizacion`?** Este sistema es un integrador local que funciona offline. Los comprobantes tienen un estado que indica si ya se sincronizaron con el servidor central. `PENDIENTE` = aún no se envió, `SINCRONIZADO` = ya se envió. En el MVP solo lo creamos con valor `PENDIENTE`.

---

### 1.7 DetalleComprobante

**¿Por qué?** Un comprobante sin ítems no existe. Cada línea del ticket es un DetalleComprobante. Relación clásica maestro-detalle (1-N).

**¿Por qué `imp_int` (impuestos internos)?** En Argentina, algunos productos tienen impuestos internos adicionales al IVA (ej: bebidas alcohólicas, tabaco). La grilla de PosONE tiene esta columna. La incluimos en el modelo.

**¿Por qué `porc_dto` y `descuento` separados?** `porc_dto` es el porcentaje de descuento (ej: 5%), y `descuento` es el monto calculado. Se guardan ambos porque puede haber redondeos. En el sistema real, el vendedor ingresa el porcentaje y el sistema calcula el monto.

**¿Por qué `porc_alicuota` con default 21.0?** El IVA en Argentina es 21% para la mayoría de los productos. Pero existe 10.5% (regalías) y 27% (servicios digitales). El campo permite cualquier alícuota, con default razonable.

**¿Por qué `subtotal` como campo y no calculado al vuelo?** Por rendimiento y auditoría. El subtotal se calcula al momento de la emisión y se guarda. Si después cambian los precios, el comprobante original no se ve alterado.

---

### 1.8 FormaPago y ComprobanteFormaPago

**¿Por qué FormaPago como tabla?** Las formas de pago son configurables. Hoy son 6, mañana pueden ser 8. Con una tabla, el seed data las carga una vez y listo. No hardcodeamos nombres.

**¿Por qué `tiene_recargo` y `recargo_financiero`?** En la demo de PosONE, cuando se selecciona Tarjeta de Crédito, aparece un cartel verde "Recargo financiero" que calcula el recargo según las cuotas. Estos campos modelan esa lógica: la forma de pago "Tarjeta CREDITO" tiene `tiene_recargo=true` y `recargo_financiero` almacena el porcentaje.

**¿Por qué ComprobanteFormaPago como tabla intermedia?** Porque un comprobante puede pagarse con múltiples formas de pago a la vez (ej: $50.000 en efectivo + $30.000 en tarjeta). Es una relación N:M que necesita datos adicionales (cuotas, lote, cupón). No alcanza con una FK simple.

**¿Por qué `cuotas`, `lote`, `nro_cupon`?** Son los campos que PosONE pide al seleccionar tarjeta de crédito. El `lote` y `nro_cupon` son datos de la transacción posnet. En el MVP los aceptamos pero no validamos contra un procesador real.

---

### 1.9 PedidoStock y DetallePedidoStock

**¿Por qué?** El módulo "Pedido Nuevo" de PosONE permite armar un pedido de reposición al proveedor/sucursal central. No es una venta al cliente, es un pedido interno de reabastecimiento.

**¿Por qué `estado` (PENDIENTE/ENVIADO/RECIBIDO)?** El pedido tiene un ciclo de vida: se crea localmente (PENDIENTE), se envía a la central (ENVIADO), la central lo procesa y envía la mercadería (RECIBIDO). Es sincronización.

**¿Por qué `stock_actual_al_pedido`, `stock_minimo`, `stock_pedido`, `multiplo` en DetallePedidoStock?** En la grilla del sistema real, estos campos aparecen en el detalle del pedido. Son un **snapshot** del estado del artículo al momento del pedido. ¿Por qué snapshot y no FK? Porque el stock cambia constantemente. Si haces un pedido el lunes y lo consultas el viernes, necesitas saber cuánto stock había cuando lo pediste, no cuánto hay ahora.

**¿Por qué `inventario_estado` en el detalle?** En la grilla de PosONE, cada línea del pedido muestra un cartel de color (rojo=BAJO, amarillo=MEDIO, verde=ALTO). Es información visual para el vendedor. Se guarda como snapshot por la misma razón que el stock.

---

## 2. Por Qué Existe Cada Relación

### 2.1 Rubro → Articulo (1:N)

Un rubro clasifica muchos artículos. Un artículo pertenece a un rubro. Es la relación más clásica del catálogo. Sin rubro, no se puede filtrar el pedido de stock ni organizar la búsqueda en WhatsApp.

**Navegabilidad**: Articulo → Rubro (Articulo tiene `rubro_id` como FK). Articulo CONOCE su rubro. Rubro NO tiene una lista de artículos. Para buscar artículos de un rubro, se filtra `Articulo WHERE rubro_id = X`.

### 2.2 Articulo ← DetalleComprobante (N:1, navegabilidad: Detalle → Articulo)

Un artículo puede aparecer en muchos detalles de comprobantes distintos, pero la **navegabilidad** va desde DetalleComprobante hacia Articulo: `DetalleComprobante` tiene `articulo_codigo` como FK. DetalleComprobante CONOCE al artículo que referencia. Articulo NO tiene una lista de detalles.

**¿Por qué el precio se copia y no se referencia?** Si el artículo cambia de precio, los comprobantes anteriores no se ven alterados (porque el precio se copia al momento de la venta como `precio_unitario` en DetalleComprobante).

**Consultas inversas**: Para buscar "todos los comprobantes que incluyen el artículo X", se hace `SELECT comprobante_id FROM detalles_comprobante WHERE articulo_codigo = 'X'`. Esto es una consulta en la BD, no una relación navegable del dominio.

### 2.3 Articulo ← DetallePedidoStock (N:1, navegabilidad: Detalle → Articulo)

Igual que con DetalleComprobante: `DetallePedidoStock` tiene `articulo_codigo` como FK. Los datos del artículo se copian al momento del pedido (snapshot).

### 2.4 Cliente ← Comprobante (N:1, navegabilidad: Comprobante → Cliente)

**Navegabilidad**: Comprobante → Cliente (`cliente_id` como FK). Comprobante CONOCE al cliente. Cliente NO tiene una lista de comprobantes.

**¿Cómo se buscan cotizaciones de un cliente?** No se navega desde el Cliente hacia sus comprobantes. Se filtra directamente en la tabla de Comprobantes: `Comprobante WHERE cliente_id = X AND tipo = COTIZACION`. El Cliente es un **filtro**, no un punto de partida navegable.

Sin esta relación, no se puede hacer "cotizaciones pendientes de cliente X" — que es exactamente lo que hace el botón "Consulta Cotizacion" de PosONE.

**Importante**: Aunque la flecha de navegabilidad va de Comprobante hacia Cliente, la multiplicidad es 1:N — un cliente puede tener muchos comprobantes, pero el modelo no almacena una lista. Es la BD la que resuelve la relación.

### 2.5 Vendedor ← Comprobante (N:1, navegabilidad: Comprobante → Vendedor)

Cada comprobante es emitido por un vendedor. `Comprobante` tiene `vendedor_id` como FK. Comprobante CONOCE al vendedor.

**⚠️ Aclaración importante**: El vendedor que factura puede ser DIFERENTE del vendedor que abrió la caja. En PosONE, el formulario de facturación permite seleccionar el vendedor de un dropdown. `Caja.vendedor_id` = quien abrió la caja (responsable del turno). `Comprobante.vendedor_id` = quien emitió la venta. Son FKs independientes.

En el MVP siempre es "Vendedor Default", pero la arquitectura ya soporta múltiples vendedores.

### 2.6 Vendedor ← Caja (N:1, navegabilidad: Caja → Vendedor)

`Caja` tiene `vendedor_id` como FK. La caja CONOCE al vendedor que la abrió. Un vendedor puede abrir múltiples cajas (en distintos turnos/días).

### 2.7 Vendedor ← PedidoStock (N:1, navegabilidad: PedidoStock → Vendedor)

`PedidoStock` tiene `vendedor_id` como FK. El pedido CONOCE al vendedor que lo generó. Auditoría de quién hizo qué.

### 2.8 Caja ← Comprobante (N:1, navegabilidad: Comprobante → Caja)

**Esta es una de las relaciones más importantes.** `Comprobante` tiene `caja_id` como FK. Todos los comprobantes emitidos durante un turno de caja quedan asociados a esa caja. Si no hay caja abierta, no se puede facturar. Si la caja se cierra, se calcula el total facturado en ese turno.

**Nota**: Comprobante referencea la caja, pero NO referencea al vendedor de la caja. El vendedor del comprobante es independiente (v. sección 2.5).

### 2.9 Comprobante → DetalleComprobante (1:N, navegabilidad: Comprobante → Detalle)

Un comprobante tiene muchos ítems. Es la relación maestro-detalle clásica. `DetalleComprobante` tiene `comprobante_id` como FK. Comprobante CONOCE sus detalles.

### 2.10 Comprobante → ComprobanteFormaPago (1:N)

`ComprobanteFormaPago` tiene `comprobante_id` como FK. Un comprobante puede tener múltiples formas de pago (ej: mitad efectivo, mitad tarjeta).

### 2.11 Comprobante → Comprobante (auto-referencia, 0..1)

**Relación crucial.** `Comprobante` tiene `cotizacion_origen_id` como FK nullable que apunta a otro Comprobante. Cuando una cotización se convierte en factura, la factura NUEVA referencia a la cotización ORIGINAL. Esto nos permite:
1. Saber cuáles cotizaciones ya se convirtieron (existe una factura con ese `cotizacion_origen_id`)
2. Rastrear el origen de una factura
3. Mostrar "cotizaciones pendientes" = cotizaciones que NO tienen una factura asociada

### 2.12 FormaPago ← ComprobanteFormaPago (N:1, navegabilidad: ComprobanteFormaPago → FormaPago)

`ComprobanteFormaPago` tiene `forma_pago_id` como FK. Cada uso de forma de pago CONOCE a qué forma pertenece.

### 2.13 Rubro ← DetallePedidoStock (N:1, navegabilidad: DetallePedidoStock → Rubro)

`DetallePedidoStock` tiene `rubro_id` como FK. Cada línea del pedido CONOCE su rubro. Esto permite agrupar el pedido por categoría al enviar al proveedor.

---

## 3. Flujos de Trabajo (Happy Path - MVP)

### Flujo 1: Abrir Caja

**Precondición**: No hay caja abierta.

```
1. Vendedor presiona "Abrir Caja"
2. Se ingresa saldo_inicial (default 0)
3. Se crea Caja {vendedor_id=1, fecha_apertura=now, saldo_inicial, estado=ABIERTA}
4. Sistema habilita módulo de facturación

Clases involucradas:
  → Caja (se crea: id, vendedor_id, fecha_apertura, saldo_inicial, estado="ABIERTA")
  → Vendedor (se lee: id=1, hardcoded)
```

**Entidades que cambian**: Se INSERTA una nueva Caja.

---

### Flujo 2: Facturación (Factura B - Consumidor Final)

**Precondición**: Hay caja abierta. Artículos con stock disponible.

```
PASO 0: Verificación de precondición
  - Se verifica que existe una Caja con estado=ABIERTA
  - Si no hay caja abierta → ERROR: "Debe abrir caja antes de facturar"

PASO 1: Carga de datos del encabezado
  - Seleccionar tipo de comprobante "FACTURA"
  - Seleccionar cliente del dropdown (o tildar "Consumidor Final")
    → Si "Consumidor Final" tildado: se autocompleta cliente CF,
      tipo se resuelve a FACTURA_B
    → Si no tildado: se selecciona cliente, y según su condicion_iva
      se determina tipo (RI→A, CF→B, M/E→C)
  - Seleccionar vendedor del dropdown (en MVP: solo "Vendedor Default")
  - [Opcional] Tildar "Lista P. Mayorista" → cambia precios
  - [Opcional] Tildar "Código de barra" → habilita campo de barra

PASO 2: Carga de ítems (se repite por cada producto)
  Forma A — Por nombre o código:
    - Se busca artículo en dropdown por nombre o código
    - Se ingresa cantidad
    - Se presiona "OK" → se agrega al detalle (tabla Items)
  
  Forma B — Por código de barra:
    - Con flag "Código de barra" activado
    - Se ingresa código en campo "Código de barra"
    - Se ingresa cantidad
    - Se presiona "OK" → se agrega al detalle

  Para cada ítem agregado:
  → Se busca Articulo por codigo (o codigo_barra)
  → Se verifica inventario_estado != "BLOQUEADO"
  → Se calcula precio_unitario (precio_publico o precio_mayorista según flag)
  → Se crea DetalleComprobante {articulo_codigo, cantidad,
    precio_unitario, imp_int=0, porc_dto=0, descuento=0,
    porc_alicuota=21.0, subtotal=cantidad*precio_unitario}

PASO 3: Presionar "FACTURAR"
  → Sistema calcula subtotal (suma de todos los detalles)
  → Se abre ventana de confirmación:
    "¿Confirma FACTURA en [forma de pago seleccionada]?"
    Si no se eligió forma de pago → se asume EFECTIVO

PASO 4: Ventana "Descuento, vuelto"
  Ruta A — Efectivo (flujo por defecto):
    - Importe a pagar (calculado del total)
    - Descuento pie de factura (input, default 0)
      → Se recalcula: nuevo_importe = total - descuento_pie
    - Paga con (input: monto con el que paga el cliente)
    - Vuelto (calculado automáticamente = paga_con - nuevo_importe)
    - Botones: "Rechazar" / "Aceptar"
  
  Ruta B — Tarjeta de Crédito (si se seleccionó en pestaña "Pagos"):
    - Se selecciona forma de pago "Tarjeta CREDITO"
    - Se ingresan cuotas, lote, nro_cupon
    - Se calcula recargo_financiero según cuotas
    - Se muestra recargo
    - Se confirma

PASO 5: Ventana "Punto de Venta y Nro Comprobante"
  - Se ingresan punto_venta y numero (en MVP: se puede autoincrementar)
  - Botones: "Rechazar" / "Aceptar"

PASO 6: Confirmación y guardado
  → Ventana "Generado correctamente"
  → Botones: "Imprime" / "Aceptar"

Clases involucradas:
  → Caja       (se lee: verificar estado=ABIERTA; se referencia: caja_id)
  → Comprobante (se crea: tipo, punto_venta, numero, cliente_id, vendedor_id,
                 caja_id, consumidor_final, lista_mayorista, subtotal,
                 descuento_pie, total, estado_sincronizacion="PENDIENTE")
  → DetalleComprobante (se crean N: comprobante_id, articulo_codigo, cantidad,
                         precio_unitario, imp_int, porc_dto, descuento,
                         porc_alicuota, subtotal)
  → Articulo   (se modifica: stock_actual -= cantidad, inventario_estado recalculado)
  → Cliente    (se lee: obtener condicion_iva → determinar tipo factura)
  → Vendedor   (se lee: obtener nombre; se referencia: vendedor_id. Puede ser
                distinto del vendedor que abrió la caja)
  → FormaPago   (se lee: obtener tiene_recargo y recargo_financiero)
  → ComprobanteFormaPago (se crea: comprobante_id, forma_pago_id, monto,
                          cuotas, lote, nro_cupon, recargo_financiero)
```

**Entidades que cambian**: Se INSERTA Comprobante + N Detalles + N ComprobanteFormaPago. Se UPDATE Articulo (stock_actual e inventario_estado).

**Atributos que cambian**:
- `Articulo.stock_actual`: decrementa en la cantidad vendida
- `Articulo.inventario_estado`: se recalcula según umbrales
- `Comprobante.estado_sincronizacion`: siempre "PENDIENTE" al crear

**Responsabilidad Back vs Front**:

| Responsabilidad | Back (API) | Front (UI) |
|----------------|------------|------------|
| Buscar artículo por nombre/código/barra | ✅ Endpoint de búsqueda | Muestra dropdown |
| Calcular subtotal por ítem | ✅ Caso de uso | Muestra en tabla |
| Calcular total del comprobante | ✅ Caso de uso | Muestra |
| Aplicar descuento pie | ✅ Caso de uso (recibe input del front) | Input del vendedor |
| Calcular vuelto | ✅ Caso de uso (devuelve en response) | Muestra resultado |
| Calcular recargo financiero TC | ✅ Caso de uso | Muestra en carte verde |
| Validar stock / artículo bloqueado | ✅ Caso de uso (lanza excepción) | Muestra error |
| Validar caja abierta | ✅ Caso de uso (lanza excepción) | Bloquea módulo |
| Determinar tipo de factura | ✅ Caso de uso (según condicion_iva) | — |
| Generar comprobante en BD | ✅ Caso de uso | Confirmación |
| Descontar stock | ✅ Caso de uso (transacción) | — |
| Mostrar pantalla de pago | — | ✅ Front |
| Pantalla "Pto Vta y Nro" | — | ✅ Front (envía datos al back) |
| Confirmar impresión | — | ✅ Front |

---

### Flujo 3: Cotización (sin afectar stock)

**Precondición**: Ninguna (no requiere caja abierta para cotizar).

```
1. Vendedor (o agente WhatsApp) solicita cotización
2. Se agregan ítems al carrito (mismo paso que facturación)
3. Se confirma cotización:
   - Se crea Comprobante {tipo=COTIZACION, cliente_id, subtotal, total,
     estado_sincronizacion=PENDIENTE}
   - NO se descuenta stock (es una cotización, no una venta)
   - Si es WhatsApp: se genera PDF y se devuelve

Clases involucradas:
  → Comprobante (se crea: tipo="COTIZACION", cliente_id, vendedor_id,
                 subtotal, total, estado_sincronizacion="PENDIENTE")
  → DetalleComprobante (se crean N: ítems con precios)
  → Cliente    (se lee: para obtener datos del PDF)
  → Articulo   (se lee: precios y descripciones, NO se modifica stock)
```

**Entidades que cambian**: Se INSERTA Comprobante + N Detalles. **NO se toca Articulo.**

**Generación de PDF** (KILLER FEATURE WhatsApp):
```
El caso de uso CotizacionUseCase.generar_pdf(id_comprobante):
1. Busca el Comprobante por ID
2. Busca los DetalleComprobante asociados
3. Busca el Cliente
4. Busca los Articulo de cada detalle
5. Genera un PDF con:
   - Encabezado: PosONE, datos del negocio
   - Número de cotización
   - Fecha
   - Datos del cliente
   - Tabla de ítems: código, descripción, cantidad, precio unitario, subtotal
   - Total
   - Pie: "Cotización válida por X días"
6. Devuelve el PDF como bytes
```

---

### Flujo 4: Convertir Cotización en Factura

**Precondición**: Hay al menos una cotización pendiente (tipo=COTIZACION que no fue convertida). Hay caja abierta.

```
PASO 1: El vendedor ingresa al módulo de Facturación (habiéndose abierto caja antes)
PASO 2: En la pestaña "EMISIÓN" del menú superior, presiona el botón "Consulta Cotización"
PASO 3: Se muestra una ventana con la lista de cotizaciones pendientes, con columnas:
    - Fecha
    - Número
    - Cliente
    - Vendedor
    - Estado (PENDIENTE)
    - Total
PASO 4: El vendedor selecciona una cotización de la lista
PASO 5: Se presiona "Confirmar" → se cargan automáticamente todos los datos en el
    formulario de facturación (cliente, vendedor, ítems, totales)
PASO 6: A partir de acá, el flujo continúa igual que el Flujo 2 (Facturación):
    - Se verifica caja abierta (ya está abierta)
    - Se presiona "FACTURAR"
    - Se selecciona forma de pago
    - Se confirman descuento y vuelto
    - Se ingresa punto de venta y número
    - Se genera la factura

Lo que hace el back al convertir:
  a) Se busca la cotización original (Comprobante tipo=COTIZACION, id=X)
  b) Se verifica que no fue ya convertida (no existe otra Comprobante con cotizacion_origen_id=X)
  c) Se crea nueva Factura:
     - Se copian los DetalleComprobante de la cotización
     - tipo = FACTURA_B (o según condicion_iva del cliente)
     - cotizacion_origen_id = X
     - caja_id = caja abierta actual
     - vendedor_id = vendedor seleccionado
  d) Se descuenta stock para cada ítem (ahora SÍ, porque es una venta)
  e) Se recalcula inventario_estado de los artículos

Clases involucradas:
  → Comprobante (se leen: lista de cotizaciones pendientes; se lee: la cotización original; se crea: la factura nueva)
  → Comprobante (se lee: verificar que no existe factura con cotizacion_origen_id=X)
  → DetalleComprobante (se leen: detalles de la cotización; se crean: detalles de la factura)
  → Caja       (se lee: verificar estado=ABIERTA)
  → Articulo   (se modifican: stock_actual -= cantidad, inventario_estado recalculado)
  → Cliente    (se lee: nombre para la lista + condicion_iva para tipo de factura)
  → Vendedor   (se lee: nombre para la lista + id para crear factura)
```

**Entidades que cambian**: Se INSERTA nuevo Comprobante + N Detalles + N ComprobanteFormaPago. Se UPDATE Articulo (stock e inventario).

**Atributos que cambian**:
- `Articulo.stock_actual`: decrementa
- `Articulo.inventario_estado`: se recalcula
- `Comprobante.estado_sincronizacion`: "PENDIENTE" en la nueva factura

**Nota importante**: La cotización original NO se modifica ni se elimina. Permanece en la BD con sus datos originales para auditoría. La nueva factura referencia a la cotización mediante `cotizacion_origen_id`.

---

### Flujo 5: Pedido de Stock (Reposición)

**Precondición**: Ninguna.

```
1. Vendedor selecciona "Pedido Nuevo"
2. Se buscan artículos (opcionalmente filtrados por "Stock COMPLETO", "Stock MINIMO",
   o "Vendidos en últimos N días")
3. Para cada artículo se ingresa cantidad
4. Se confirma pedido:
   - Se crea PedidoStock {vendedor_id, fecha, estado=PENDIENTE,
     estado_sincronizacion=PENDIENTE}
   - Para cada DetallePedidoStock:
     - Se hace snapshot de stock_actual, stock_minimo, inventario_estado al momento
     - Se calcula total = cantidad * precio_unitario

Clases involucradas:
  → PedidoStock (se crea: vendedor_id, fecha, estado="PENDIENTE",
                 estado_sincronizacion="PENDIENTE")
  → DetallePedidoStock (se crean N: pedido_id, articulo_codigo, rubro_id, cantidad,
                         precio_unitario, total, stock_actual_al_pedido, stock_minimo,
                         inventario_estado)
  → Articulo   (se leen: precio, stock, estado para el snapshot)
  → Vendedor   (se lee: id=1, hardcoded)
```

**Entidades que cambian**: Se INSERTA PedidoStock + N Detalles. **NO se modifica stock** (es un pedido de reposición, no una venta).

---

### Flujo 6: Emergencia - Bloquear Artículo (WhatsApp)

**Precondición**: Ninguna (el agente puede bloquear en cualquier momento).

```
1. Agente WhatsApp recibe solicitud de bloquear artículo X
2. Se busca Articulo por codigo
3. Se verifica que existe y que inventario_estado != BLOQUEADO
4. Se actualiza:
   - stock_actual = 0
   - inventario_estado = BLOQUEADO

Clases involucradas:
  → Articulo (se modifica: stock_actual=0, inventario_estado="BLOQUEADO")
```

**Entidades que cambian**: Se UPDATE Articulo. Dos campos cambian: `stock_actual` y `inventario_estado`.

---

### Flujo 7: Emergencia - Desbloquear Artículo (WhatsApp)

```
1. Agente WhatsApp recibe solicitud de desbloquear artículo X
2. Se busca Articulo por codigo
3. Se verifica que inventario_estado = BLOQUEADO
4. Se recalcula inventario_estado según stock_mínimo y un stock de reposición razonable
5. Se actualiza inventario_estado al valor correspondiente

Clases involucradas:
  → Articulo (se modifica: inventario_estado recalculado)
```

**Nota**: Al desbloquear, no restauramos el stock (no sabemos cuánto era). Solo cambiamos el estado para que el artículo vuelva a estar disponible para venta si tiene stock > 0, o en estado BAJO si stock_minimo > 0.

---

### Flujo 8: Consultas WhatsApp (solo lectura)

Todas las consultas son de solo lectura y no modifican entidades:

```
Consultar stock:
  → Articulo (se lee: descripcion, stock_actual, inventario_estado)

Consultar precio:
  → Articulo (se lee: descripcion, precio_publico, precio_mayorista)

Consultar cliente:
  → Cliente (se lee: razon_social, cuit, condicion_iva)

Cotizaciones pendientes de un cliente:
  → Comprobante (se leen: tipo=COTIZACION, cliente_id=X, sin factura asociada)
  → DetalleComprobante (se leen: detalles de cada cotización)
```

---

## 4. Decisiones de Modelo (resumen)

### D1: Tipos de Comprobante
Modelamos A/B/C + Cotización + Presupuesto + NC. MVP ejecuta solo B, Cotización y Presupuesto.

### D2: Cotización → Factura
Campo `cotizacion_origen_id` para rastrear conversión. KILLER FEATURE para WhatsApp.

### D3: Caja = Prerrequisito
Sin caja ABIERTA, no se puede facturar. Regla de negocio real del POS argentino.

### D4: Dos precios
`precio_publico` y `precio_mayorista`. Se selecciona con flag `lista_mayorista`.

### D5: Umbral de inventario
- `stock_actual == 0` → BLOQUEADO
- `stock_actual <= stock_minimo` → BAJO
- `stock_actual <= stock_minimo * 2` → MEDIO
- `stock_actual > stock_minimo * 2` → ALTO

### D6: Formas de pago
6 modeladas, 2 implementadas (Efectivo + TC con cuotas).

### D7: Vendedor — Independiente del Cajero
La entidad Vendedor existe en el modelo. En el MVP se hardcodea un único vendedor, pero la arquitectura soporta múltiples. El `vendedor_id` del Comprobante es **independiente** del `vendedor_id` de la Caja: Caja.vendedor_id = quién abrió la caja (responsable del turno), Comprobante.vendedor_id = quién hizo la venta. Pueden ser personas distintas.

### D8: Rubro como entidad
Agrupa artículos. Esencial para pedidos de stock y para búsquedas WhatsApp.

### D9: Seed data
4 rubros, 10 artículos, 3 clientes, 1 vendedor, 6 formas de pago.

### D10: WhatsApp - PDF de cotización primero
Generar PDF de cotización es el KILLER FEATURE. Links de pago emulados quedan como bonus si hay tiempo.

### D11: Búsqueda de artículos flexible
Los artículos se pueden buscar por nombre, código, o código de barra. La API tiene un endpoint de búsqueda (`/api/articulos?search=...`) que filtra por `descripcion`, `codigo`, o `codigo_barra`. Esto refleja el sistema real donde existen dos modos de ingreso: dropdown y campo de código de barra.

### D12: Responsabilidad Back vs Front
La lógica de negocio SIEMPRE vive en el back (casos de uso). El front es una capa fina que: (1) muestra lo que el back calcula (subtotales, totales, vuelto, recargo), (2) envía lo que el usuario ingresa (cantidades, selección de cliente, forma de pago), (3) gestiona la UI (pantallas de confirmación, transiciones). El back valida todo y lanza excepciones si hay errores (stock insuficiente, artículo bloqueado, sin caja abierta).

---

## 5. Estructura Hexagonal del Proyecto

```
app/
├── domain/                    # MODELOS PUROS - CERO dependencias
│   ├── entities/
│   │   ├── articulo.py
│   │   ├── cliente.py
│   │   ├── comprobante.py
│   │   ├── detalle_comprobante.py
│   │   ├── rubro.py
│   │   ├── vendedor.py
│   │   ├── caja.py
│   │   ├── forma_pago.py
│   │   ├── comprobante_forma_pago.py
│   │   ├── pedido_stock.py
│   │   └── detalle_pedido_stock.py
│   ├── value_objects/
│   │   ├── tipo_comprobante.py
│   │   ├── inventario_estado.py
│   │   ├── condicion_iva.py
│   │   └── estado_caja.py
│   └── exceptions.py
├── application/               # CASOS DE USO + PUERTOS
│   ├── ports/
│   │   ├── repositorio_articulo.py
│   │   ├── repositorio_cliente.py
│   │   ├── repositorio_comprobante.py
│   │   ├── repositorio_pedido.py
│   │   └── repositorio_caja.py
│   └── use_cases/
│       ├── facturacion.py
│       ├── cotizacion.py
│       ├── pedido_stock.py
│       ├── caja.py
│       └── emergencia.py
├── infrastructure/             # ADAPTADORES
│   ├── database/
│   │   ├── connection.py
│   │   ├── models.py           # SQLAlchemy ORM models
│   │   └── repositories.py     # Implementación de puertos
│   ├── api/
│   │   ├── routers/
│   │   │   ├── articulos.py
│   │   │   ├── clientes.py
│   │   │   ├── comprobantes.py
│   │   │   ├── pedidos.py
│   │   │   ├── caja.py
│   │   │   └── emergencia.py
│   │   ├── schemas.py          # Pydantic DTOs
│   │   └── dependencies.py     # Inyección de dependencias
│   └── pdf/
│       └── generador_pdf.py    # Generación de PDFs de cotización
└── main.py                     # ASSEMBLER + CORS + lifespan + seed
```

---

## 6. APIs del MVP

### REST API (frontend web)

| Método | Endpoint | Descripción | MVP |
|--------|----------|-------------|-----|
| GET | /api/articulos | Catálogo completo | ✅ |
| GET | /api/articulos?search=... | Búsqueda por nombre, código o barra | ✅ |
| GET | /api/articulos/{codigo} | Artículo por código exacto | ✅ |
| GET | /api/clientes | Lista de clientes | ✅ |
| GET | /api/clientes/{id} | Cliente por ID | ✅ |
| GET | /api/vendedores | Lista de vendedores | ✅ |
| GET | /api/rubros | Lista de rubros | ✅ |
| POST | /api/cajas/abrir | Abrir caja | ✅ |
| POST | /api/cajas/{id}/cerrar | Cerrar caja | ✅ |
| GET | /api/cajas/abierta | ¿Hay caja abierta? | ✅ |
| POST | /api/comprobantes | Crear factura/cotización/presupuesto | ✅ |
| GET | /api/comprobantes | Listar comprobantes | ✅ |
| GET | /api/comprobantes/{id} | Detalle de comprobante | ✅ |
| GET | /api/cotizaciones/pendientes | Cotizaciones pendientes (fecha, número, cliente, vendedor, estado, total) | ✅ |
| POST | /api/cotizaciones/{id}/convertir | Convertir cotización a factura | ✅ |
| POST | /api/pedidos-stock | Crear pedido de stock | ✅ |
| GET | /api/pedidos-stock | Listar pedidos | ✅ |
| POST | /api/emergencia/bloquear-articulo | Bloquear artículo | ✅ |
| POST | /api/emergencia/desbloquear-articulo | Desbloquear artículo | ✅ |

### WhatsApp Agent API

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | /api/whatsapp/consultar-stock | Consultar stock de artículo |
| POST | /api/whatsapp/consultar-precio | Consultar precio |
| POST | /api/whatsapp/consultar-cliente | Buscar cliente por nombre/CUIT |
| POST | /api/whatsapp/generar-cotizacion | Generar cotización y devolver PDF |
| POST | /api/whatsapp/bloquear-articulo | Emergencia: bloquear artículo |
| POST | /api/whatsapp/cotizaciones-pendientes | Cotizaciones pendientes de cliente |
| POST | /api/whatsapp/convertir-cotizacion | Convertir cotización a factura |

---

## 7. Reglas de Negocio Clave (para la entrevista)

1. **No se puede facturar sin caja abierta** — precondición obligatoria
2. **Artículo BLOQUEADO no se puede incluir en factura** — validar antes de agregar
3. **El tipo de factura se determina por condición IVA del cliente** — A para RI, B para CF, C para M/E
4. **Facturación descuenta stock** — Cotización y Presupuesto NO descuentan
5. **El inventario_estado se recalcula automáticamente** al modificar stock
6. **Cotización puede convertirse en Factura** — se copian los detalles y se descuenta stock
7. **Pagos con TC tienen recargo financiero** por cuotas — se calcula automáticamente
8. **Punto de venta + número = comprobante único** — numeración correlativa

---

## 8. Plan de Implementación (4 días)

| Día | Qué | Detalle |
|-----|-----|---------|
| 1 | Dominio + DB + Repos | Entidades puras, SQLAlchemy models, SQLite, seed data, repositorios completos |
| 2 | Casos de Uso + API | Facturación, Cotización, Pedido, Caja, Emergencia + endpoints REST |
| 3 | WhatsApp + PDF | Endpoints WhatsApp, generación de PDF de cotización, integración |
| 4 | Pulir + Frontend | Probar todo, corregir bugs, conectar frontend |