#!/bin/bash
# Inicia el MCP Server AndesTech en 0.0.0.0:8080 con transporte SSE

set -e
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR"

echo "=== AndesTech MCP Server ==="
echo "Directorio: $REPO_DIR"

if [ ! -d "venv" ]; then
    echo "Creando entorno virtual..."
    python3 -m venv venv
fi

source venv/bin/activate

pip install -q -r requirements.txt

if [ ! -f ".env" ]; then
    echo "Creando .env desde .env.example..."
    cp .env.example .env
fi

API_URL="${API_BASE_URL:-http://localhost:8000}"
echo "Verificando API de negocio en $API_URL..."
if ! curl -sf "$API_URL/api/health" > /dev/null 2>&1; then
    echo ""
    echo "ADVERTENCIA: La API de negocio no responde en $API_URL"
    echo "Asegúrate de iniciarla primero con: bash scripts/start_api.sh"
    echo "Continuando de todos modos en 3 segundos..."
    sleep 3
fi

echo ""
echo "Iniciando MCP Server SSE en http://0.0.0.0:8080/sse"
echo "Healthcheck: http://localhost:8080/health"
echo "Presiona Ctrl+C para detener."
echo ""

python -m mcp_server.server
