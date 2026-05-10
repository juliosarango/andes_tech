# CLAUDE.md — AndesTech MCP Business Demo

## Contexto del proyecto

Demo en vivo para la charla **"Claude no es solo un chatbot: MCP + AWS para que la IA haga cosas reales"**
en AWS GenAI Day Ecuador 2026 (USFQ Cumbayá, sábado 16 de mayo 2026).

Autor: Julio Sarango — AWS Community Builder, desarrollador Python 11+ años.

**Repositorio:** https://github.com/juliosarango/andes_tech.git

**Objetivo de la demo:** mostrar a Claude Desktop conectándose a un MCP Server remoto que expone herramientas
para consultar APIs de negocio (inventario + CRM) en tiempo real sobre una EC2 en AWS.

---

## Arquitectura

```
Claude Desktop (laptop del speaker)
    │
    │  MCP Protocol — SSE (Server-Sent Events) — puerto 8080
    ▼
MCP Server  [mcp_server/server.py]
    │
    │  HTTP requests a localhost:8000 via httpx
    ▼
API de Negocio  [business_api/main.py]  — FastAPI, puerto 8000
    │
    │  SQLAlchemy ORM
    ▼
SQLite  [andestech.db]
```

**Producción:** Todo corre en una sola instancia Amazon EC2 (Ubuntu 24.04 LTS).
**Desarrollo:** Probar todo localmente primero, luego desplegar a EC2 vía `git clone` desde GitHub.

---

## Estructura del proyecto

```
mcp-business-demo/
├── CLAUDE.md
├── README.md
├── requirements.txt
├── .env.example
├── .gitignore
├── setup_db.py                      # Crea y puebla la BD con datos semilla
├── andestech.db                     # SQLite (generado por setup_db.py, en .gitignore)
├── business_api/
│   ├── __init__.py
│   ├── main.py                      # FastAPI — todos los endpoints
│   ├── models.py                    # Modelos SQLAlchemy (Productos, Clientes, Ventas, Leads)
│   ├── database.py                  # Engine, SessionLocal, get_db
│   └── seed_data.py                 # Datos semilla del negocio ecuatoriano
├── mcp_server/
│   ├── __init__.py
│   └── server.py                    # MCP Server con 9 herramientas, transporte SSE
├── config/
│   └── claude_desktop_config.json   # Config ejemplo para Claude Desktop
├── scripts/
│   ├── start_api.sh                 # Inicia FastAPI en puerto 8000
│   ├── start_mcp.sh                 # Inicia MCP Server en puerto 8080
│   └── setup_ec2.sh                 # Setup completo EC2: deps, venv, systemd, firewall
└── docs/
    └── demo_queries.md              # Consultas preparadas para la demo en vivo (4 niveles)
```

---

## Stack técnico

| Componente | Tecnología | Versión mínima |
|---|---|---|
| Lenguaje | Python | 3.12 |
| API de negocio | FastAPI + Uvicorn | latest |
| ORM | SQLAlchemy | 2.x |
| Base de datos | SQLite | builtin |
| MCP SDK | `mcp` (oficial Anthropic/modelcontextprotocol) | 1.x |
| Transporte MCP | SSE (Server-Sent Events) | — |
| HTTP client | httpx | latest |
| Variables entorno | python-dotenv | latest |

---

## Base de datos: AndesTech

Negocio ficticio pero realista: **AndesTech** — tienda de tecnología en Quito, Ecuador.

### Tablas y volumen

| Tabla | Registros mínimos | Descripción |
|---|---|---|
| `productos` | 20 | Laptops, accesorios, periféricos, redes, etc. Precios en USD. Algunos con stock bajo. |
| `clientes` | 15 | Nombres ecuatorianos, empresas ficticias, ciudades de Ecuador. |
| `ventas` | 40 | Distribuidas en mar-may 2026. Estados: completada/pendiente/cancelada. |
| `leads` | 12 | Varios con `fecha_seguimiento` en semana 12-16 mayo 2026 para demo. |

### Convenciones de datos
- Fechas como string ISO: `"2026-05-14"`
- Precios en USD (Ecuador usa dólar)
- Nombres y empresas en español, ciudades reales de Ecuador
- `leads.estado` puede ser: `nuevo`, `contactado`, `en_negociacion`, `cerrado_ganado`, `cerrado_perdido`
- `ventas.estado` puede ser: `completada`, `pendiente`, `cancelada`

---

## API de Negocio (FastAPI)

**Base URL:** `http://localhost:8000`

### Endpoints de inventario
- `GET /api/health` — Healthcheck
- `GET /api/inventario` — Lista productos (query param `?categoria=Laptops`)
- `GET /api/inventario/{producto_id}` — Detalle de producto
- `GET /api/inventario/buscar?q={query}` — Buscar por nombre
- `GET /api/inventario/stock-bajo` — Productos bajo el mínimo
- `GET /api/inventario/categorias` — Categorías con conteo

### Endpoints de CRM
- `GET /api/clientes` — Lista clientes
- `GET /api/clientes/{cliente_id}` — Detalle + historial de compras
- `GET /api/clientes/buscar?q={query}` — Buscar por nombre o empresa
- `GET /api/leads` — Lista leads (query param `?estado=en_negociacion`)
- `GET /api/leads/{lead_id}` — Detalle de lead
- `GET /api/leads/seguimiento?desde={fecha}&hasta={fecha}` — Leads a seguir en rango

### Endpoints de ventas
- `GET /api/ventas/recientes?limite={n}` — Últimas N ventas (default: 10)
- `GET /api/ventas/por-categoria?desde={fecha}&hasta={fecha}` — Resumen por categoría
- `GET /api/ventas/por-cliente/{cliente_id}` — Historial de compras de un cliente

### Convenciones de API
- Respuestas JSON limpio y estructurado
- 404 para recursos no encontrados, 400 para parámetros inválidos
- Sin autenticación (es una demo local/EC2 cerrada)

---

## MCP Server

**Puerto:** 8080
**Transporte:** SSE (`/sse`) — compatible con Claude Desktop actual
**Endpoint SSE:** `http://<HOST>:8080/sse`

El MCP Server actúa como proxy: recibe llamadas de Claude Desktop y las traduce a requests HTTP a la API de negocio en `localhost:8000`. No accede directamente a la BD.

### 9 Herramientas definidas

#### Inventario
| Herramienta | Parámetros | Qué hace |
|---|---|---|
| `consultar_inventario` | `categoria: str \| None` | Lista productos, filtrando por categoría si se especifica |
| `buscar_producto` | `query: str` | Busca productos por nombre, retorna coincidencias con detalles |
| `productos_stock_bajo` | — | Lista productos con stock por debajo del mínimo |

#### CRM
| Herramienta | Parámetros | Qué hace |
|---|---|---|
| `listar_leads` | `estado: str \| None` | Lista leads, filtrando por estado si se especifica |
| `detalle_lead` | `lead_id: int` | Información completa de un lead incluyendo notas |
| `leads_por_seguir` | `dias: int = 7` | Leads con seguimiento en los próximos N días |

#### Ventas
| Herramienta | Parámetros | Qué hace |
|---|---|---|
| `ventas_recientes` | `limite: int = 10` | Últimas N ventas con nombre de cliente y producto |
| `ventas_por_categoria` | `fecha_inicio: str, fecha_fin: str` | Resumen de ventas agrupado por categoría |
| `historial_cliente` | `cliente_id: int` | Historial completo de compras con totales acumulados |

### Requisitos de cada herramienta
- Descripción en español que ayude a Claude a decidir cuándo usarla
- Esquema de parámetros tipado con anotaciones Python
- Manejo de errores con mensajes descriptivos
- Logging en consola de cada llamada (para mostrar en pantalla durante la charla)

---

## Configuración Claude Desktop

Archivo: `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS)

```json
{
  "mcpServers": {
    "andestech-negocio": {
      "url": "http://<EC2_PUBLIC_IP>:8080/sse"
    }
  }
}
```

Para desarrollo local, reemplazar `<EC2_PUBLIC_IP>` con `localhost`.

---

## Flujo de desarrollo

### 1. Setup local

```bash
cd mcp-business-demo/
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python setup_db.py          # Crea andestech.db con datos semilla
```

### 2. Levantar componentes (dos terminales)

```bash
# Terminal 1 — API de negocio
bash scripts/start_api.sh   # Corre en localhost:8000

# Terminal 2 — MCP Server
bash scripts/start_mcp.sh   # Corre en localhost:8080
```

### 3. Verificar healthchecks

```bash
curl http://localhost:8000/api/health
curl http://localhost:8080/health
```

### 4. Configurar Claude Desktop (local)

Apuntar `url` a `http://localhost:8080/sse` en `claude_desktop_config.json`.

---

## Despliegue en EC2

**Método:** `git clone` desde GitHub.

```bash
# En EC2 (Ubuntu 24.04)
git clone https://github.com/juliosarango/andes_tech.git
cd andes_tech
bash scripts/setup_ec2.sh   # Instala deps, crea venv, puebla BD, configura systemd
```

El script `setup_ec2.sh` configura dos servicios systemd:
- `andestech-api.service` — FastAPI en puerto 8000
- `andestech-mcp.service` — MCP Server en puerto 8080

Puertos a abrir en Security Group EC2: **8000** y **8080** (TCP, desde cualquier IP para demo).

---

## Convenciones de código

- **Idioma:** Todo en español — docstrings, comentarios, nombres de variables descriptivos
- **Prioridad:** Funciona > elegante (es una demo en vivo con deadline duro)
- **Logging:** El MCP Server debe imprimir en consola qué herramienta se está llamando (visible en pantalla durante la charla)
- **Sin autenticación:** La demo corre en entorno controlado, no se necesita auth
- **Errores:** Mensajes claros y descriptivos; no silenciar excepciones

---

## Demo en vivo — Flujo narrativo

La demo está organizada en 4 niveles de complejidad (ver `docs/demo_queries.md`):

1. **Nivel 1 — Herramienta simple:** consulta directa a inventario o leads
2. **Nivel 2 — Filtrado y búsqueda:** con parámetros y rangos de fecha
3. **Nivel 3 — Encadenamiento:** Claude usa 2-3 herramientas en secuencia
4. **Nivel 4 — Razonamiento:** Claude analiza y compara datos de múltiples herramientas

---

## Fechas clave

| Fecha | Hito |
|---|---|
| 2026-05-14 (aprox.) | Demo funcionando en EC2, ensayo completo |
| 2026-05-16 | Charla en vivo — AWS GenAI Day Ecuador, USFQ Cumbayá |
