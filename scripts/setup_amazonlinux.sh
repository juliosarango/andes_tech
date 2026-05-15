#!/bin/bash
# =============================================================================
# setup_amazonlinux.sh — Setup completo de AndesTech en Amazon Linux 2023
#
# Levanta 3 servicios systemd:
#   - andestech-api     : FastAPI en puerto 8000
#   - andestech-mcp     : MCP Server en puerto 8080
#   - andestech-tunnel  : Cloudflare Tunnel HTTPS → localhost:8080
#
# Uso:
#   git clone https://github.com/juliosarango/andes_tech.git
#   cd andes_tech
#   bash scripts/setup_amazonlinux.sh
#
# Ejecutar como usuario ec2-user (no como root).
# Solo necesitas el puerto 22 abierto en el Security Group (SSH).
# Cloudflare Tunnel maneja el acceso HTTPS sin abrir puertos adicionales.
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
[ "$USUARIO" != "root" ]  || err "No ejecutes como root. Usa ec2-user."

# Verificar que estamos en Amazon Linux
if ! grep -qi "amazon linux" /etc/os-release 2>/dev/null; then
    echo -e "${AMARILLO}ADVERTENCIA: Este script está optimizado para Amazon Linux 2023.${NC}"
    read -rp "¿Continuar de todas formas? [s/N] " resp
    [[ "$resp" =~ ^[sS]$ ]] || exit 0
fi

# -----------------------------------------------------------------------------
# 1. Actualizar sistema
# -----------------------------------------------------------------------------
info "Actualizando paquetes del sistema..."
sudo dnf update -y -q
ok "Sistema actualizado"

# -----------------------------------------------------------------------------
# 2. Instalar dependencias del sistema
# -----------------------------------------------------------------------------
info "Instalando Python 3.12, git y curl..."
sudo dnf install -y -q python3.12 git curl
ok "Python $(python3.12 --version) instalado"

# -----------------------------------------------------------------------------
# 3. Instalar cloudflared
# -----------------------------------------------------------------------------
info "Instalando cloudflared..."
if command -v cloudflared &>/dev/null; then
    info "cloudflared ya instalado ($(cloudflared --version 2>&1 | head -1))"
else
    curl -fsSL https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 \
        -o /tmp/cloudflared
    sudo install -m 755 /tmp/cloudflared /usr/local/bin/cloudflared
    rm /tmp/cloudflared
    ok "cloudflared instalado ($(cloudflared --version 2>&1 | head -1))"
fi

# -----------------------------------------------------------------------------
# 4. Entorno virtual Python
# -----------------------------------------------------------------------------
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

# -----------------------------------------------------------------------------
# 5. Variables de entorno
# -----------------------------------------------------------------------------
info "Configurando variables de entorno..."
if [ ! -f ".env" ]; then
    cp .env.example .env
    ok "Archivo .env creado"
else
    info ".env ya existe, omitiendo."
fi

# -----------------------------------------------------------------------------
# 6. Base de datos
# -----------------------------------------------------------------------------
info "Inicializando base de datos..."
if [ -f "andestech.db" ]; then
    info "BD ya existe. Para recrear: source venv/bin/activate && python setup_db.py --reset"
else
    python setup_db.py
    ok "Base de datos creada y poblada"
fi

# -----------------------------------------------------------------------------
# 7. Servicios systemd
# -----------------------------------------------------------------------------
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
Description=AndesTech MCP Server
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

sudo tee /etc/systemd/system/andestech-tunnel.service > /dev/null << EOF
[Unit]
Description=Cloudflare Tunnel — AndesTech MCP HTTPS
After=network.target andestech-mcp.service
Requires=andestech-mcp.service
StartLimitIntervalSec=0

[Service]
Type=simple
User=$USUARIO
ExecStart=/usr/local/bin/cloudflared tunnel --url http://localhost:8080 --no-autoupdate
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=andestech-tunnel

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable andestech-api andestech-mcp andestech-tunnel
ok "3 servicios systemd configurados y habilitados"

# -----------------------------------------------------------------------------
# 8. Iniciar servicios
# -----------------------------------------------------------------------------
info "Iniciando servicios..."
sudo systemctl start andestech-api
sleep 3
sudo systemctl start andestech-mcp
sleep 2
sudo systemctl start andestech-tunnel
sleep 5
ok "Servicios iniciados"

# -----------------------------------------------------------------------------
# 9. Healthchecks
# -----------------------------------------------------------------------------
info "Verificando servicios..."

API_OK=$(curl -sf http://localhost:8000/api/health 2>/dev/null \
    | python3 -c "import sys,json; print(json.load(sys.stdin).get('status',''))" 2>/dev/null || echo "error")
MCP_OK=$(curl -sf http://localhost:8080/health 2>/dev/null \
    | python3 -c "import sys,json; print(json.load(sys.stdin).get('status',''))" 2>/dev/null || echo "error")

# Extraer URL del tunnel desde los logs de systemd
TUNNEL_URL=$(sudo journalctl -u andestech-tunnel --no-pager -n 50 2>/dev/null \
    | grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' | tail -1 || echo "")

echo ""
echo "========================================================="
echo "  Estado de los servicios:"
if [ "$API_OK" = "ok" ]; then
    echo -e "  API de negocio    : ${VERDE}OK${NC}  → http://localhost:8000"
else
    echo -e "  API de negocio    : ${ROJO}ERROR${NC}"
    echo    "    → sudo journalctl -u andestech-api -n 30 --no-pager"
fi
if [ "$MCP_OK" = "ok" ]; then
    echo -e "  MCP Server        : ${VERDE}OK${NC}  → http://localhost:8080/mcp"
else
    echo -e "  MCP Server        : ${ROJO}ERROR${NC}"
    echo    "    → sudo journalctl -u andestech-mcp -n 30 --no-pager"
fi
if [ -n "$TUNNEL_URL" ]; then
    echo -e "  Cloudflare Tunnel : ${VERDE}OK${NC}  → $TUNNEL_URL"
else
    echo -e "  Cloudflare Tunnel : ${AMARILLO}iniciando...${NC}"
    echo    "    → sudo journalctl -u andestech-tunnel -f"
fi
echo "========================================================="

# -----------------------------------------------------------------------------
# 10. Instrucciones finales
# -----------------------------------------------------------------------------
echo ""
if [ -n "$TUNNEL_URL" ]; then
    echo -e "  ${VERDE}Config para Claude Desktop (copia esto):${NC}"
    echo ""
    echo '  {'
    echo '    "mcpServers": {'
    echo '      "andestech-negocio": {'
    echo "        \"url\": \"$TUNNEL_URL/mcp\""
    echo '      }'
    echo '    }'
    echo '  }'
else
    echo -e "  ${AMARILLO}El tunnel aún no tiene URL. Espera unos segundos y ejecuta:${NC}"
    echo ""
    echo "    sudo journalctl -u andestech-tunnel -f | grep trycloudflare"
    echo ""
    echo "  Luego usa la URL en Claude Desktop:"
    echo '  { "mcpServers": { "andestech-negocio": { "url": "https://<url>.trycloudflare.com/mcp" } } }'
fi
echo ""
echo "  Rutas del config en Claude Desktop:"
echo "    Windows (Store) : %LOCALAPPDATA%\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Roaming\Claude\claude_desktop_config.json"
echo "    Windows (exe)   : %APPDATA%\Claude\claude_desktop_config.json"
echo "    macOS           : ~/Library/Application Support/Claude/claude_desktop_config.json"
echo ""
echo "  Comandos útiles:"
echo "    URL del tunnel   : sudo journalctl -u andestech-tunnel --no-pager | grep trycloudflare | tail -1"
echo "    Logs MCP en vivo : sudo journalctl -u andestech-mcp -f -o cat"
echo "    Logs API en vivo : sudo journalctl -u andestech-api -f"
echo "    Reiniciar todo   : sudo systemctl restart andestech-api andestech-mcp andestech-tunnel"
echo "    Reset base datos : source venv/bin/activate && python setup_db.py --reset"
echo ""
echo "========================================================="
echo "  ¡Setup completo! Listo para la demo."
echo "========================================================="
