# AndesTech MCP Business Demo

Demo en vivo para la charla **"Claude no es solo un chatbot: MCP + AWS para que la IA haga cosas reales"**
— AWS GenAI Day Ecuador 2026, USFQ Cumbayá, 16 de mayo 2026.

Demuestra cómo Claude Desktop se conecta a un MCP Server remoto en EC2 que expone herramientas
para consultar APIs de inventario y CRM en tiempo real.

## Arquitectura

```
Claude Desktop (Windows/Mac)
    │
    │  MCP Protocol — SSE — puerto 8080
    ▼
MCP Server  [mcp_server/server.py]   ← 10 herramientas de negocio
    │
    │  HTTP — localhost
    ▼
API de Negocio  [business_api/main.py]   ← FastAPI, puerto 8000
    │
    │  SQLAlchemy ORM
    ▼
SQLite  [andestech.db]   ← negocio ficticio: tienda tecnología Quito
```

Todo corre en una sola instancia Amazon EC2 Ubuntu 24.04.

---

## Requisitos

- Python 3.12+
- Claude Desktop instalado (Windows o macOS)
- Git

---

## Opción A — Desarrollo local

### 1. Clonar y preparar el entorno

```bash
git clone https://github.com/juliosarango/andes_tech.git
cd andes_tech

python3 -m venv venv
source venv/bin/activate          # Linux/macOS
# venv\Scripts\activate           # Windows

pip install -r requirements.txt
cp .env.example .env
```

### 2. Crear y poblar la base de datos

```bash
python setup_db.py
```

Salida esperada:
```
✅ Base de datos lista
   Productos :  23  (5 con stock bajo)
   Clientes  :  15
   Ventas    :  43
   Leads     :  13  (5 con seguimiento semana 12-16 mayo)
```

Para resetear y recargar desde cero:
```bash
python setup_db.py --reset
```

### 3. Iniciar la API de negocio (Terminal 1)

```bash
bash scripts/start_api.sh
```

Verifica: `curl http://localhost:8000/api/health`

### 4. Iniciar el MCP Server (Terminal 2)

```bash
bash scripts/start_mcp.sh
```

Verifica: `curl http://localhost:8080/health`

### 5. Configurar Claude Desktop

Copia el archivo de configuración local a la ubicación correcta:

**Windows:**
```
%APPDATA%\Claude\claude_desktop_config.json
```

**macOS:**
```
~/Library/Application Support/Claude/claude_desktop_config.json
```

Contenido para pruebas locales:
```json
{
  "mcpServers": {
    "andestech-negocio": {
      "url": "http://localhost:8080/sse"
    }
  }
}
```

El archivo listo está en `config/claude_desktop_config.local.json`.

**Reinicia Claude Desktop** después de copiar la configuración.

### 6. Probar en Claude Desktop

Escribe en Claude Desktop:
```
¿Qué productos de AndesTech tienen stock bajo?
```

Deberías ver en la terminal del MCP Server:
```
🔧 Claude invocó → productos_stock_bajo()
```

---

## Opción B — Despliegue en Amazon EC2

### Prerrequisitos en AWS

1. Lanzar instancia EC2: **Ubuntu 24.04 LTS**, tipo `t3.small` o superior
2. En el Security Group, abrir puertos de entrada:
   - `22` (SSH)
   - `8000` (API de negocio)
   - `8080` (MCP Server SSE)

### Setup en la instancia

```bash
# Conectarse por SSH
ssh -i tu-key.pem ubuntu@<EC2_PUBLIC_IP>

# Clonar el repositorio
git clone https://github.com/juliosarango/andes_tech.git
cd andes_tech

# Ejecutar el setup completo (instala deps, crea BD, configura systemd)
bash scripts/setup_ec2.sh
```

El script al terminar imprime automáticamente la configuración para Claude Desktop con la IP pública de tu instancia.

### Verificar que todo funciona

```bash
# Estado de los servicios
sudo systemctl status andestech-api andestech-mcp

# Healthcheck
curl http://localhost:8080/health

# Logs en tiempo real (para la demo)
sudo journalctl -u andestech-mcp -f
```

### Configurar Claude Desktop para EC2

```json
{
  "mcpServers": {
    "andestech-negocio": {
      "url": "http://<EC2_PUBLIC_IP>:8080/sse"
    }
  }
}
```

Reemplaza `<EC2_PUBLIC_IP>` con la IP pública de tu instancia.

---

## Estructura del proyecto

```
andes_tech/
├── setup_db.py              # Crea y puebla la BD
├── requirements.txt
├── .env.example
├── business_api/
│   ├── main.py              # FastAPI — 15 endpoints
│   ├── models.py            # Modelos SQLAlchemy
│   ├── database.py          # Sesión de BD
│   └── seed_data.py         # Datos semilla ecuatorianos
├── mcp_server/
│   └── server.py            # MCP Server — 10 herramientas
├── config/
│   ├── claude_desktop_config.json        # Para EC2
│   └── claude_desktop_config.local.json  # Para localhost
├── scripts/
│   ├── start_api.sh         # Inicia FastAPI
│   ├── start_mcp.sh         # Inicia MCP Server
│   └── setup_ec2.sh         # Setup completo EC2
└── docs/
    └── demo_queries.md      # Consultas preparadas (4 niveles)
```

---

## Herramientas MCP disponibles

| Herramienta | Descripción |
|---|---|
| `consultar_inventario(categoria?)` | Lista productos, filtrando por categoría |
| `buscar_producto(query)` | Busca producto por nombre |
| `productos_stock_bajo()` | Alerta de productos bajo el mínimo |
| `listar_clientes(busqueda?)` | Lista o busca clientes por nombre/empresa |
| `historial_cliente(cliente_id)` | Perfil completo + historial de compras |
| `listar_leads(estado?)` | Pipeline CRM con filtro por estado |
| `detalle_lead(lead_id)` | Ficha completa de un lead con notas |
| `leads_por_seguir(dias=7)` | Seguimientos pendientes en los próximos N días |
| `ventas_recientes(limite=10)` | Últimas N ventas |
| `ventas_por_categoria(inicio, fin)` | Resumen de ventas por categoría en un período |

---

## API de negocio — Endpoints principales

```
GET /api/health
GET /api/inventario?categoria=Laptops
GET /api/inventario/stock-bajo
GET /api/inventario/buscar?q=asus
GET /api/clientes
GET /api/clientes/buscar?q=maria
GET /api/clientes/{id}
GET /api/leads?estado=en_negociacion
GET /api/leads/seguimiento?desde=2026-05-12&hasta=2026-05-16
GET /api/ventas/recientes?limite=10
GET /api/ventas/por-categoria?desde=2026-04-01&hasta=2026-04-30
```

Documentación interactiva (Swagger): `http://localhost:8000/docs`

---

## Comandos útiles durante la demo

```bash
# Ver logs del MCP Server en tiempo real
sudo journalctl -u andestech-mcp -f

# Ver logs de la API
sudo journalctl -u andestech-api -f

# Reiniciar servicios si algo falla
sudo systemctl restart andestech-api andestech-mcp

# Resetear BD (si necesitas datos limpios)
cd /home/ubuntu/andes_tech
source venv/bin/activate
python setup_db.py --reset
sudo systemctl restart andestech-api
```

---

## Consultas de demo

Ver `docs/demo_queries.md` para las consultas preparadas organizadas en 4 niveles de complejidad,
con el logging esperado, la respuesta aproximada y los puntos de charla para cada una.
