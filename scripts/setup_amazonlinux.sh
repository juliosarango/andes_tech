#!/bin/bash
# =============================================================================
# setup_amazonlinux.sh — Setup de AndesTech en Amazon EC2 Amazon Linux 2023
#
# Diferencias vs setup_ec2.sh (Ubuntu):
#   - Gestor de paquetes: dnf en lugar de apt-get
#   - Usuario por defecto: ec2-user en lugar de ubuntu
#   - Sin ufw: el firewall lo manejan los Security Groups de AWS
#   - Python 3.12 disponible directamente con dnf en AL2023
#
# Uso:
#   git clone https://github.com/juliosarango/andes_tech.git
#   cd andes_tech
#   bash scripts/setup_amazonlinux.sh
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

echo ""
echo "========================================================="
echo "  AndesTech MCP Demo — Setup Amazon Linux 2023"
echo "========================================================="
echo "  Directorio : $REPO_DIR"
echo "  Usuario    : $USUARIO"
echo "  Fecha      : $(date '+%Y-%m-%d %H:%M:%S')"
echo "========================================================="
echo ""

cd "$REPO_DIR"

[ -f "requirements.txt" ] || err "Ejecuta este script desde la raíz del repositorio."

# Verificar que estamos en Amazon Linux
if ! grep -qi "amazon linux" /etc/os-release 2>/dev/null; then
    echo -e "${AMARILLO}ADVERTENCIA: Este script está optimizado para Amazon Linux 2023.${NC}"
    echo "Para Ubuntu usa: bash scripts/setup_ec2.sh"
    read -rp "¿Continuar de todas formas? [s/N] " resp
    [[ "$resp" =~ ^[sS]$ ]] || exit 0
fi

# 1. Actualizar sistema
info "Actualizando paquetes del sistema..."
sudo dnf update -y -q
ok "Sistema actualizado"

# 2. Instalar Python 3.12 y herramientas
info "Instalando Python 3.12, git y curl..."
sudo dnf install -y -q python3.12 python3.12-pip git curl
ok "Python $(python3.12 --version) instalado"

# 3. Crear entorno virtual
info "Creando entorno virtual Python..."
if [ -d "venv" ]; then
    info "venv ya existe, omitiendo."
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
    ok "Archivo .env creado"
else
    info ".env ya existe, omitiendo."
fi

# 5. Crear y poblar base de datos
info "Inicializando base de datos..."
if [ -f "andestech.db" ]; then
    info "BD ya existe. Usa 'python setup_db.py --reset' para recrear."
else
    python setup_db.py
    ok "Base de datos creada y poblada"
fi

# 6. Crear servicios systemd
info "Configurando servicios systemd..."

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
ok "Servicios systemd configurados"

# 7. Nota sobre firewall
echo ""
echo -e "${AMARILLO}FIREWALL: En Amazon Linux el firewall se configura en el${NC}"
echo -e "${AMARILLO}Security Group de la instancia EC2, no en el SO.${NC}"
echo ""
echo "  Asegúrate de tener estas reglas de entrada en tu Security Group:"
echo "  ┌──────────┬──────────┬───────────────────────────────┐"
echo "  │ Puerto   │ Protocolo│ Descripción                   │"
echo "  ├──────────┼──────────┼───────────────────────────────┤"
echo "  │ 22       │ TCP      │ SSH (tu IP o 0.0.0.0/0)       │"
echo "  │ 8000     │ TCP      │ AndesTech API                 │"
echo "  │ 8080     │ TCP      │ AndesTech MCP Server SSE      │"
echo "  └──────────┴──────────┴───────────────────────────────┘"
echo ""

# 8. Iniciar servicios
info "Iniciando servicios..."
sudo systemctl start andestech-api
sleep 3
sudo systemctl start andestech-mcp
sleep 2
ok "Servicios iniciados"

# 9. Verificar healthchecks
info "Verificando healthchecks..."

API_STATUS=$(curl -sf http://localhost:8000/api/health 2>/dev/null \
    | python3 -c "import sys,json; print(json.load(sys.stdin).get('status','error'))" 2>/dev/null || echo "error")
MCP_STATUS=$(curl -sf http://localhost:8080/health 2>/dev/null \
    | python3 -c "import sys,json; print(json.load(sys.stdin).get('status','error'))" 2>/dev/null || echo "error")

echo ""
echo "========================================================="
echo "  Estado de los servicios:"
[ "$API_STATUS" = "ok" ] \
    && echo -e "  API de negocio : ${VERDE}OK${NC}  → http://localhost:8000" \
    || echo -e "  API de negocio : ${ROJO}ERROR${NC} — revisa: sudo journalctl -u andestech-api -n 30"
[ "$MCP_STATUS" = "ok" ] \
    && echo -e "  MCP Server SSE : ${VERDE}OK${NC}  → http://localhost:8080/sse" \
    || echo -e "  MCP Server SSE : ${ROJO}ERROR${NC} — revisa: sudo journalctl -u andestech-mcp -n 30"
echo "========================================================="

# 10. Instrucciones finales
EC2_IP=$(curl -sf http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null \
    || TOKEN=$(curl -sf -X PUT "http://169.254.169.254/latest/api/token" \
         -H "X-aws-ec2-metadata-token-ttl-seconds: 21600" 2>/dev/null) \
    && curl -sf -H "X-aws-ec2-metadata-token: $TOKEN" \
         http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null \
    || echo "<EC2_PUBLIC_IP>")

echo ""
echo "  Config para Claude Desktop:"
echo "  {"
echo '    "mcpServers": {'
echo '      "andestech-negocio": {'
echo "        \"url\": \"http://$EC2_IP:8080/sse\""
echo '      }'
echo '    }'
echo "  }"
echo ""
echo "  Comandos útiles:"
echo "    Logs API  : sudo journalctl -u andestech-api -f"
echo "    Logs MCP  : sudo journalctl -u andestech-mcp -f"
echo "    Reiniciar : sudo systemctl restart andestech-api andestech-mcp"
echo ""
echo "========================================================="
echo "  ¡Setup completo en Amazon Linux 2023!"
echo "========================================================="
