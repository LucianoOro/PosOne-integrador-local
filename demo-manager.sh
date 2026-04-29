#!/bin/bash
# demo-manager.sh — Script para levantar proyectos de demo
# Uso: ./demo-manager.sh [posone|proyecto2|proyecto3]
#
# Ejemplos:
#   ./demo-manager.sh posone     # Levanta PosONE
#   ./demo-manager.sh stop       # Mata todo
#   ./demo-manager.sh status     # Verifica qué está corriendo

set -e

# ─── Configuración ─────────────────────────────────────────────
# Adaptá estos paths a tu notebook
POSONE_BACKEND="$HOME/proyectos/PosONE-Workspace/posone-integrador-local"
POSONE_FRONTEND="$HOME/proyectos/PosONE-Workspace/posone-web-extendida"

# Proyecto 2 (adaptar cuando tengas los paths)
# PROYECTO2_BACKEND="$HOME/proyectos/Proyecto2/backend"
# PROYECTO2_FRONTEND="$HOME/proyectos/Proyecto2/frontend"

# Proyecto 3 (adaptar cuando tengas los paths)
# PROYECTO3_BACKEND="$HOME/proyectos/Proyecto3/backend"
# PROYECTO3_FRONTEND="$HOME/proyectos/Proyecto3/frontend"

# ─── Colores ───────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ─── Funciones ─────────────────────────────────────────────────

kill_port() {
    local port=$1
    local pid
    pid=$(lsof -ti :$port 2>/dev/null || true)
    if [ -n "$pid" ]; then
        echo -e "${YELLOW}  Liberando puerto $port (PID: $pid)...${NC}"
        kill -9 $pid 2>/dev/null || true
        sleep 1
    fi
}

wait_for_port() {
    local port=$1
    local name=$2
    local max_attempts=30
    local attempt=1

    echo -ne "${BLUE}  Esperando $name en puerto $port...${NC}"
    while ! curl -s "http://localhost:$port" > /dev/null 2>&1; do
        if [ $attempt -ge $max_attempts ]; then
            echo -e " ${RED}❌ Timeout${NC}"
            return 1
        fi
        echo -n "."
        sleep 1
        attempt=$((attempt + 1))
    done
    echo -e " ${GREEN}✅ Listo${NC}"
}

show_status() {
    echo ""
    echo -e "${BLUE}══════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}  ESTADO ACTUAL${NC}"
    echo -e "${BLUE}══════════════════════════════════════════════════════════════${NC}"

    echo ""
    echo "  Puertos ocupados:"
    for port in 8000 5173 4040; do
        pid=$(lsof -ti :$port 2>/dev/null || true)
        if [ -n "$pid" ]; then
            name=$(ps -p $pid -o comm= 2>/dev/null || echo "?")
            echo -e "    ${GREEN}:$port${NC} → $name (PID: $pid)"
        else
            echo -e "    ${RED}:$port${NC} → libre"
        fi
    done

    echo ""
    echo "  ngrok:"
    if curl -s http://localhost:4040/api/tunnels > /dev/null 2>&1; then
        ngrok_url=$(curl -s http://localhost:4040/api/tunnels | grep -o '"public_url":"[^"]*"' | head -1 | cut -d'"' -f4)
        if [ -n "$ngrok_url" ]; then
            echo -e "    ${GREEN}🌐 $ngrok_url${NC}"
        else
            echo -e "    ${YELLOW}⚠️  ngrok corriendo pero sin URL pública${NC}"
        fi
    else
        echo -e "    ${RED}❌ No está corriendo${NC}"
    fi

    echo ""
}

stop_all() {
    echo -e "${YELLOW}🛑 Matando todos los procesos de demo...${NC}"
    kill_port 8000
    kill_port 5173
    kill_port 4040

    # Matar procesos específicos
    pkill -f "uvicorn app.main:app" 2>/dev/null || true
    pkill -f "vite" 2>/dev/null || true
    pkill -f "ngrok http" 2>/dev/null || true

    echo -e "${GREEN}✅ Todo detenido${NC}"
}

# ─── PosONE ────────────────────────────────────────────────────

start_posone() {
    echo ""
    echo -e "${BLUE}══════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}  🚀 PosONE Integrador${NC}"
    echo -e "${BLUE}══════════════════════════════════════════════════════════════${NC}"
    echo ""

    # 1. Verificar paths
    if [ ! -d "$POSONE_BACKEND" ]; then
        echo -e "${RED}❌ No existe: $POSONE_BACKEND${NC}"
        echo "   Editá la variable POSONE_BACKEND en este script"
        exit 1
    fi
    if [ ! -d "$POSONE_FRONTEND" ]; then
        echo -e "${RED}❌ No existe: $POSONE_FRONTEND${NC}"
        echo "   Editá la variable POSONE_FRONTEND en este script"
        exit 1
    fi

    # 2. Liberar puertos
    echo -e "${YELLOW}🔧 Liberando puertos...${NC}"
    kill_port 8000
    kill_port 5173
    kill_port 4040
    echo ""

    # 3. Backend
    echo -e "${BLUE}📦 Backend (FastAPI + SQLite + IA)${NC}"
    cd "$POSONE_BACKEND"
    source venv/bin/activate
    echo -e "  ${GREEN}→${NC} uvicorn app.main:app --reload --port 8000"
    nohup uvicorn app.main:app --reload --port 8000 > /tmp/posone-backend.log 2>&1 &
    BACKEND_PID=$!
    echo -e "  PID: ${YELLOW}$BACKEND_PID${NC}"
    wait_for_port 8000 "backend"

    # 4. Frontend
    echo ""
    echo -e "${BLUE}🎨 Frontend (React + Vite)${NC}"
    cd "$POSONE_FRONTEND"
    echo -e "  ${GREEN}→${NC} npm run dev"
    nohup npm run dev > /tmp/posone-frontend.log 2>&1 &
    FRONTEND_PID=$!
    echo -e "  PID: ${YELLOW}$FRONTEND_PID${NC}"
    wait_for_port 5173 "frontend"

    # 5. ngrok
    echo ""
    echo -e "${BLUE}🌐 ngrok (túnel público para WhatsApp)${NC}"
    echo -e "  ${GREEN}→${NC} ngrok http 8000"
    nohup ngrok http 8000 > /tmp/posone-ngrok.log 2>&1 &
    NGROK_PID=$!
    echo -e "  PID: ${YELLOW}$NGROK_PID${NC}"

    # Esperar a que ngrok tenga URL
    sleep 3
    NGROK_URL=$(curl -s http://localhost:4040/api/tunnels | grep -o '"public_url":"https://[^"]*"' | head -1 | cut -d'"' -f4 || true)

    echo ""
    echo -e "${GREEN}══════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  ✅ PosONE está corriendo${NC}"
    echo -e "${GREEN}══════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "  🏥 Health:     ${BLUE}http://localhost:8000/health${NC}"
    echo -e "  📚 API Docs:   ${BLUE}http://localhost:8000/docs${NC}"
    echo -e "  🎨 Web App:    ${BLUE}http://localhost:5173${NC}"
    if [ -n "$NGROK_URL" ]; then
        echo -e "  🌐 WhatsApp:   ${BLUE}$NGROK_URL/webhook${NC}"
        echo -e "  📄 PDFs:       ${BLUE}$NGROK_URL/comprobantes/{id}/pdf${NC}"
    else
        echo -e "  🌐 WhatsApp:   ${YELLOW}Esperando ngrok...${NC}"
        echo "                 Verificá en http://localhost:4040/status"
    fi
    echo ""
    echo -e "  ${YELLOW}⚠️  IMPORTANTE: actualizá APP_BASE_URL en .env con la URL de ngrok${NC}"
    echo -e "  ${YELLOW}   y reiniciá el backend si cambió.${NC}"
    echo ""
    echo -e "  ${YELLOW}📋 Para ver logs:${NC}"
    echo -e "     Backend:  tail -f /tmp/posone-backend.log"
    echo -e "     Frontend: tail -f /tmp/posone-frontend.log"
    echo -e "     ngrok:    tail -f /tmp/posone-ngrok.log"
    echo ""
}

# ─── Proyecto 2 (plantilla) ────────────────────────────────────

# start_proyecto2() {
#     echo "🚀 Proyecto 2"
#     kill_port 8000
#     kill_port 5173
#     # ...adaptar según el stack del proyecto
# }

# ─── Proyecto 3 (plantilla) ────────────────────────────────────

# start_proyecto3() {
#     echo "🚀 Proyecto 3"
#     kill_port 8000
#     kill_port 5173
#     # ...adaptar según el stack del proyecto
# }

# ─── Main ──────────────────────────────────────────────────────

case "${1:-posone}" in
    posone|1)
        start_posone
        ;;
    # proyecto2|2)
    #     start_proyecto2
    #     ;;
    # proyecto3|3)
    #     start_proyecto3
    #     ;;
    stop|kill|down)
        stop_all
        ;;
    status|st)
        show_status
        ;;
    logs|log)
        echo "📋 Logs recientes:"
        echo ""
        echo "Backend:"
        tail -20 /tmp/posone-backend.log 2>/dev/null || echo "  (no hay log)"
        echo ""
        echo "Frontend:"
        tail -20 /tmp/posone-frontend.log 2>/dev/null || echo "  (no hay log)"
        echo ""
        echo "ngrok:"
        tail -20 /tmp/posone-ngrok.log 2>/dev/null || echo "  (no hay log)"
        ;;
    help|--help|-h)
        echo ""
        echo "Uso: ./demo-manager.sh [comando]"
        echo ""
        echo "Comandos:"
        echo "  posone | 1      Levanta PosONE (backend + frontend + ngrok)"
        echo "  stop | kill     Mata todos los procesos"
        echo "  status | st     Muestra estado de puertos y ngrok"
        echo "  logs | log      Muestra logs recientes"
        echo "  help            Esta ayuda"
        echo ""
        echo "Ejemplo:"
        echo "  ./demo-manager.sh posone"
        echo ""
        ;;
    *)
        echo -e "${RED}❌ Comando desconocido: $1${NC}"
        echo "   Usá: ./demo-manager.sh help"
        exit 1
        ;;
esac
