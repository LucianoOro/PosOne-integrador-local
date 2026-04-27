# PosONE Integrador — Backend

Backend del sistema POS (Point of Sale) con arquitectura hexagonal, bot de WhatsApp con IA y function calling, y API REST.

## Arquitectura

```
posone-integrador-local/
├── app/
│   ├── domain/                  # Capa de dominio (pura, sin dependencias)
│   │   ├── entities.py          # Entidades: Articulo, Cliente, Caja, Comprobante...
│   │   ├── value_objects/       # Enums: TipoComprobante, EstadoCaja, InventarioEstado
│   │   └── exceptions.py        # Excepciones de dominio
│   ├── application/             # Casos de uso (orquesta dominio + infra)
│   │   ├── use_cases/           # ArticuloUseCase, CajaUseCase, ComprobanteUseCase...
│   │   ├── ports/               # Interfaces de repositorios (CajaRepository, etc.)
│   │   └── schemas.py          # Pydantic schemas para request/response
│   └── infrastructure/         # Adaptadores externos
│       ├── ai/                  # Servicio de IA multi-provider
│       │   ├── ai_service.py    # AIService: OpenAI/GitHub Models/Groq con fallback
│       │   └── ai_functions.py  # 16 tool declarations + system prompt
│       ├── api/                 # FastAPI routers
│       │   └── routers/         # Articulos, Clientes, Cajas, Comprobantes, WhatsApp
│       ├── database/            # SQLAlchemy models, repos, seed data, connection
│       ├── pdf/                 # Generación de PDFs con FPDF2
│       └── whatsapp/            # Twilio webhook + FallbackProcessor
├── requirements.txt
└── main.py                      # FastAPI app entrypoint
```

## Stack

- **Python 3.12** + **FastAPI** + **Uvicorn**
- **SQLAlchemy** + **SQLite** (migrable a PostgreSQL)
- **OpenAI SDK** (compatible con GitHub Models y Groq)
- **Twilio** (WhatsApp Business API)
- **FPDF2** (generación de PDFs)

## Funcionalidades

### Bot de WhatsApp con IA

16 funciones que el modelo de IA selecciona dinámicamente vía function calling:

| Función | Descripción |
|---------|-------------|
| `saludar` | Saludo y lista de funciones |
| `buscar_articulos` | Buscar por nombre, código, barra o rápido |
| `consultar_stock` | Stock y estado de un artículo |
| `consultar_precio` | Precio público o mayorista |
| `buscar_clientes` | Buscar por razón social o CUIT |
| `cotizaciones_pendientes` | Lista de cotizaciones pendientes |
| `generar_cotizacion` | Crear cotización con items |
| `convertir_cotizacion` | Convertir cotización a factura |
| `consultar_caja` | Estado de la caja abierta |
| `abrir_caja` | Abrir caja con saldo inicial |
| `cerrar_caja` | Cerrar la caja actual |
| `listar_comprobantes` | Lista por tipo o por caja |
| `ver_comprobante` | Detalle completo de un comprobante |
| `listar_facturas_caja` | Facturas de la caja abierta |
| `bloquear_articulo` | Bloqueo de emergencia |
| `desbloquear_articulo` | Restaurar artículo |

### Anti-manipulación

Triple capa de seguridad:
1. **System prompt** con límites estrictos
2. **FallbackProcessor** con pattern matching (filtra antes de la IA)
3. **Azure/GitHub content filter** (rechaza jailbreaks a nivel de API)

### Multi-provider con fallback automático

```env
AI_PROVIDER=github   # o "groq"
```

- **GitHub Models**: gpt-4o-mini → gpt-4o (fallback)
- **Groq**: qwen3-32b → llama-3.3-70b-versatile (fallback)
- Si la IA falla → FallbackProcessor rule-based (cero dependencia externa)

### API REST

Endpoints completos para artículos, clientes, cajas, comprobantes, pedidos de stock y WhatsApp directo.

## Inicio Rápido

```bash
# 1. Clonar e instalar
git clone https://github.com/lucianoEstevez/posone-integrador-local.git
cd posone-integrador-local
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 2. Configurar .env
cp .env.example .env
# Editar .env con tus credenciales:
#   AI_PROVIDER=github
#   AI_API_KEY=ghp_tu_key_aqui
#   GROQ_API_KEY=gsk_tu_key_aqui
#   TWILIO_ACCOUNT_SID=...
#   TWILIO_AUTH_TOKEN=...
#   TWILIO_PHONE_NUMBER=+14155238886
#   APP_BASE_URL=https://tu-ngrok-url.ngrok-free.dev

# 3. Levantar (la BD se crea con seed data automáticamente)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Datos de Demo

El seed genera automáticamente:
- **20 artículos** en 4 rubros (bicicletas, repuestos, indumentaria, componentes)
- **6 clientes** (incluyendo Consumidor Final)
- **3 vendedores**
- **6 formas de pago**
- **5 comprobantes** históricos (3 facturas B, 2 cotizaciones WhatsApp)
- **1 caja abierta** con $50,000 de saldo inicial
- Artículos REP-001 y REP-004 en estado BLOQUEADO

## Testing

```bash
# Tests unitarios (sin backend)
python3 test_caja_functions.py unit

# Tests de integración (necesita backend corriendo)
python3 test_caja_functions.py integration

# Tests completos de API
python3 test_completo.py
```

## Variables de Entorno

| Variable | Descripción | Default |
|----------|-------------|---------|
| `AI_PROVIDER` | Proveedor de IA: `github` / `groq` / `openai` | `openai` |
| `AI_API_KEY` | API key (GitHub token o Groq key) | — |
| `GROQ_API_KEY` | API key específica de Groq | — |
| `AI_MODEL` | Modelo a usar (override del default) | Auto según provider |
| `TWILIO_ACCOUNT_SID` | SID de Twilio | — |
| `TWILIO_AUTH_TOKEN` | Token de Twilio | — |
| `TWILIO_PHONE_NUMBER` | Número de WhatsApp | — |
| `APP_BASE_URL` | URL pública (ngrok) para PDFs | — |

## Diseño

- **Hexagonal Architecture Lite**: Domain → Application → Infrastructure
- **Domain puro**: Sin dependencias externas, dataclasses Python
- **Repositorios por interfaz**: SqlAlchemyRepos implementan interfaces del dominio
- **Seed data auto-mático**: Se ejecuta al levantar si la BD está vacía