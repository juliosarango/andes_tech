#!/bin/bash
# Inicia la API de negocio AndesTech en localhost:8000

set -e
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR"

echo "=== AndesTech Business API ==="
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

if [ ! -f "andestech.db" ]; then
    echo "Base de datos no encontrada. Ejecutando setup_db.py..."
    python setup_db.py
fi

echo ""
echo "Iniciando FastAPI en http://0.0.0.0:8000"
echo "Docs: http://localhost:8000/docs"
echo "Presiona Ctrl+C para detener."
echo ""

uvicorn business_api.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --log-level info
