#!/bin/bash
# =============================================================================
# setup_ec2.sh — Setup completo de AndesTech en Amazon EC2 Ubuntu 24.04 LTS
#
# Uso:
#   git clone https://github.com/juliosarango/andes_tech.git
#   cd andes_tech
#   bash scripts/setup_ec2.sh
#
# El script debe ejecutarse desde el directorio raíz del repositorio.
# Se recomienda correrlo como usuario ubuntu (no como root).
# =============================================================================

set -e

VERDE='\033[0;32m'
AMARILLO='\033[1;33m'
ROJO='\033[0;31m'
NC='\033[0m'

ok()   { echo -e "${VERDE}✓ $1${NC}"; }
info() { echo -e "${AMARILLO}→ $1${NC}"; }
err()  { echo -e "${ROJO}✗ $1${NC}" >&2; exit 1; }

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
USUARIO="$(whoami)"
PYTHON_MIN="3.12"

echo ""
echo "========================================================="
echo "  AndesTech MCP Demo — Setup EC2 Ubuntu 24.04"
echo "========================================================="
echo "  Directorio : $REPO_DIR"
echo "  Usuario    : $USUARIO"
echo "  Fecha      : $(date '+%Y-%m-%d %H:%M:%S')"
echo "========================================================="
echo ""

cd "$REPO_DIR"

[ -f "requirements.txt" ] || err "Ejecuta este script desde la raíz del repositorio."

# 1. Actualizar sistema
info "Actualizando paquetes del sistema..."
sudo apt-get update -qq
sudo apt-get upgrade -y -qq
ok "Sistema actualizado"

# 2. Instalar dependencias del sistema
info "Instalando Python 3.12, pip y herramientas..."
sudo apt-get install -y -qq \
    python3.12 \
    python3.12-venv \
    python3-pip \
    python3.12-dev \
    curl \
    git \
    ufw
ok "Dependencias del sistema instaladas"

# 3. Crear entorno virtual Python
info "Creando entorno virtual Python..."
if [ -d "venv" ]; then
    info "venv ya existe, omitiendo creación."
else
    python3.12 -m venv venv
    ok "Entorno virtual creado"
fi

source venv/bin/activate
info "Instalando dependencias Python..."
pip install --upgrade pip -q
pip install -r requirements.txt -q
ok "Dependencias Python instaladas"

# 4. Crear archivo .env
info "Configurando variables de entorno..."
if [ ! -f ".env" ]; then
    cp .env.example .env
    ok "Archivo .env creado desde .env.example"
else
    info ".env ya existe, omitiendo."
fi

# 5. Crear y poblar base de datos
info "Inicializando base de datos..."
if [ -f "andestech.db" ]; then
    info "Base de datos ya existe. Usar 'python setup_db.py --reset' para recrear."
else
    python setup_db.py
    ok "Base de datos creada y poblada"
fi

# 6. Crear servicios systemd
info "Configurando servicios systemd..."

# Servicio: API de negocio (FastAPI)
sudo tee /etc/systemd/system/andestech-api.service > /dev/null << EOF
[Unit]
Description=AndesTech Business API (FastAPI)
After=network.target
StartLimitIntervalSec=0

[Service]
Type=simple
User=$USUARIO
WorkingDirectory=$REPO_DIR
EnvironmentFile=$REPO_DIR/.env
ExecStart=$REPO_DIR/venv/bin/uvicorn business_api.main:app --host 0.0.0.0 --port 8000 --log-level info
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=andestech-api

[Install]
WantedBy=multi-user.target
EOF

# Servicio: MCP Server
sudo tee /etc/systemd/system/andestech-mcp.service > /dev/null << EOF
[Unit]
Description=AndesTech MCP Server (SSE)
After=network.target andestech-api.service
Requires=andestech-api.service
StartLimitIntervalSec=0

[Service]
Type=simple
User=$USUARIO
WorkingDirectory=$REPO_DIR
EnvironmentFile=$REPO_DIR/.env
ExecStart=$REPO_DIR/venv/bin/python -m mcp_server.server
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=andestech-mcp

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable andestech-api andestech-mcp
ok "Servicios systemd configurados y habilitados"

# 7. Configurar firewall
info "Configurando firewall (ufw)..."
sudo ufw allow ssh
sudo ufw allow 8000/tcp comment "AndesTech API"
sudo ufw allow 8080/tcp comment "AndesTech MCP Server"
# Habilitar ufw si no está activo
if sudo ufw status | grep -q "inactive"; then
    sudo ufw --force enable
fi
ok "Firewall configurado (puertos 22, 8000, 8080 abiertos)"

# 8. Iniciar servicios
info "Iniciando servicios..."
sudo systemctl start andestech-api
sleep 3
sudo systemctl start andestech-mcp
sleep 2
ok "Servicios iniciados"

# 9. Verificar que todo funcione
info "Verificando healthchecks..."

API_STATUS=$(curl -sf http://localhost:8000/api/health 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('status','error'))" 2>/dev/null || echo "error")
MCP_STATUS=$(curl -sf http://localhost:8080/health 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('status','error'))" 2>/dev/null || echo "error")

echo ""
echo "========================================================="
echo "  Estado de los servicios:"
[ "$API_STATUS" = "ok" ] && echo -e "  API de negocio  : ${VERDE}OK${NC}  → http://localhost:8000" \
                          || echo -e "  API de negocio  : ${ROJO}ERROR${NC}"
[ "$MCP_STATUS" = "ok" ] && echo -e "  MCP Server SSE  : ${VERDE}OK${NC}  → http://localhost:8080/sse" \
                          || echo -e "  MCP Server SSE  : ${ROJO}ERROR${NC}"
echo "========================================================="
echo ""

# 10. Instrucciones finales
EC2_IP=$(curl -sf http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || echo "<EC2_PUBLIC_IP>")

echo "  SIGUIENTE PASO — Configura Claude Desktop:"
echo ""
echo "  Windows : %APPDATA%\\Claude\\claude_desktop_config.json"
echo "  macOS   : ~/Library/Application Support/Claude/claude_desktop_config.json"
echo ""
echo '  Contenido:'
echo "  {"
echo '    "mcpServers": {'
echo '      "andestech-negocio": {'
echo "        \"url\": \"http://$EC2_IP:8080/sse\""
echo '      }'
echo '    }'
echo "  }"
echo ""
echo "  Comandos útiles:"
echo "    Ver logs API : sudo journalctl -u andestech-api -f"
echo "    Ver logs MCP : sudo journalctl -u andestech-mcp -f"
echo "    Reiniciar API: sudo systemctl restart andestech-api"
echo "    Reiniciar MCP: sudo systemctl restart andestech-mcp"
echo ""
echo "========================================================="
echo "  ¡Setup completo! Listo para la demo."
echo "========================================================="
