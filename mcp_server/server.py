import os
import sys
import logging
from datetime import date, timedelta

import httpx
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

load_dotenv()

API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")
MCP_HOST = os.getenv("MCP_HOST", "0.0.0.0")
MCP_PORT = int(os.getenv("MCP_PORT", "8080"))

# Colores para que cada invocación de Claude sea visible en pantalla durante la demo
logging.basicConfig(
    level=logging.INFO,
    format="\033[36m%(asctime)s\033[0m \033[1;33m[AndesTech MCP]\033[0m %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stderr)],
    force=True,
)
logger = logging.getLogger("andestech.mcp")


mcp = FastMCP(
    "AndesTech Negocio",
    host=MCP_HOST,
    port=MCP_PORT,
)


@mcp.custom_route("/health", methods=["GET"])
async def health_endpoint(request: Request) -> JSONResponse:
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{API_BASE}/api/health")
            api_ok = resp.status_code == 200
            api_info = resp.json() if api_ok else {}
    except Exception:
        api_ok = False
        api_info = {}

    return JSONResponse({
        "status": "ok",
        "servidor": "AndesTech MCP Server",
        "version": "1.0",
        "sse_endpoint": f"http://{MCP_HOST}:{MCP_PORT}/sse",
        "api_negocio": {
            "url": API_BASE,
            "status": "ok" if api_ok else "no disponible",
            **api_info,
        },
    })


def _get(path: str, params: dict | None = None) -> dict | list:
    url = f"{API_BASE}{path}"
    try:
        resp = httpx.get(url, params=params or {}, timeout=10.0)
        resp.raise_for_status()
        return resp.json()
    except httpx.ConnectError:
        raise RuntimeError(
            f"No se puede conectar a la API de negocio en {API_BASE}. "
            "Verifica que esté corriendo con: bash scripts/start_api.sh"
        )
    except httpx.HTTPStatusError as e:
        raise RuntimeError(
            f"Error de la API ({e.response.status_code}): {e.response.text}"
        )


def _post(path: str, data: dict) -> dict:
    url = f"{API_BASE}{path}"
    try:
        resp = httpx.post(url, json=data, timeout=10.0)
        resp.raise_for_status()
        return resp.json()
    except httpx.ConnectError:
        raise RuntimeError(
            f"No se puede conectar a la API de negocio en {API_BASE}. "
            "Verifica que esté corriendo con: bash scripts/start_api.sh"
        )
    except httpx.HTTPStatusError as e:
        raise RuntimeError(
            f"Error de la API ({e.response.status_code}): {e.response.text}"
        )


def _patch(path: str, data: dict) -> dict:
    url = f"{API_BASE}{path}"
    try:
        resp = httpx.patch(url, json=data, timeout=10.0)
        resp.raise_for_status()
        return resp.json()
    except httpx.ConnectError:
        raise RuntimeError(
            f"No se puede conectar a la API de negocio en {API_BASE}. "
            "Verifica que esté corriendo con: bash scripts/start_api.sh"
        )
    except httpx.HTTPStatusError as e:
        raise RuntimeError(
            f"Error de la API ({e.response.status_code}): {e.response.text}"
        )


def _log_tool(nombre: str, **params) -> None:
    p = ", ".join(f"{k}={v!r}" for k, v in params.items() if v is not None)
    logger.info("🔧 Claude invocó → \033[1;32m%s\033[0m(%s)", nombre, p)


def _moneda(valor: float) -> str:
    return f"${valor:,.2f}"



@mcp.tool()
def consultar_inventario(categoria: str | None = None) -> str:
    """
    Lista los productos del inventario de AndesTech con precios y stock disponible.
    Úsala cuando el usuario pregunte qué productos hay disponibles, cuánto stock
    queda, precios, o quiera explorar el catálogo por categoría.
    Categorías válidas: Laptops, Monitores, Periféricos, Audio,
    Almacenamiento, Redes, Accesorios.
    Si no se especifica categoría, retorna todos los productos.
    """
    _log_tool("consultar_inventario", categoria=categoria)

    productos = _get("/api/inventario", {"categoria": categoria} if categoria else None)

    if not productos:
        return f"No se encontraron productos en la categoría '{categoria}'."

    titulo = "Inventario AndesTech" + (f" — {categoria}" if categoria else " — Todos los productos")
    lineas = [titulo, "=" * len(titulo)]

    cat_actual = None
    for p in productos:
        if p["categoria"] != cat_actual:
            cat_actual = p["categoria"]
            lineas.append(f"\n[{cat_actual}]")

        estado = "✓ OK" if p["stock_ok"] else f"⚠ BAJO (mín: {p['stock_minimo']})"
        lineas.append(
            f"  • {p['nombre']}\n"
            f"    Precio: {_moneda(p['precio'])} | Stock: {p['stock']} uds {estado}\n"
            f"    Proveedor: {p['proveedor']}"
        )

    lineas.append(f"\nTotal: {len(productos)} producto(s)")
    return "\n".join(lineas)


@mcp.tool()
def buscar_producto(query: str) -> str:
    """
    Busca productos en el inventario por nombre (búsqueda parcial, sin distinción
    de mayúsculas). Úsala cuando el usuario mencione un producto específico por
    nombre o marca, por ejemplo: 'ASUS', 'SSD Samsung', 'Logitech', 'monitor LG'.
    Retorna todos los detalles del producto incluyendo precio, stock y proveedor.
    """
    _log_tool("buscar_producto", query=query)

    productos = _get("/api/inventario/buscar", {"q": query})

    if not productos:
        return f"No se encontraron productos que coincidan con '{query}'."

    lineas = [f"Resultados para '{query}': {len(productos)} producto(s)", ""]
    for p in productos:
        estado = "✓ En stock" if p["stock_ok"] else f"⚠ Stock bajo ({p['stock']} uds, mín {p['stock_minimo']})"
        lineas.append(
            f"ID {p['id']} — {p['nombre']}\n"
            f"  Categoría: {p['categoria']} | Precio: {_moneda(p['precio'])}\n"
            f"  Stock: {p['stock']} unidades | {estado}\n"
            f"  Proveedor: {p['proveedor']} | Actualizado: {p['ultima_actualizacion']}"
        )
    return "\n".join(lineas)


@mcp.tool()
def productos_stock_bajo() -> str:
    """
    Lista todos los productos cuyo stock actual está por debajo del mínimo
    configurado. Úsala cuando el usuario pregunte sobre alertas de inventario,
    qué productos necesitan reabastecimiento o cuáles están agotándose.
    Incluye el nombre del proveedor para facilitar el pedido.
    """
    _log_tool("productos_stock_bajo")

    productos = _get("/api/inventario/stock-bajo")

    if not productos:
        return "¡Excelente! Todos los productos están sobre el stock mínimo. No hay alertas."

    total_deficit = sum(p["deficit"] for p in productos)
    lineas = [
        f"⚠  ALERTA DE INVENTARIO — {len(productos)} producto(s) con stock bajo",
        f"   Déficit total acumulado: {total_deficit} unidades",
        "",
    ]
    for p in productos:
        lineas.append(
            f"• {p['nombre']}  [{p['categoria']}]\n"
            f"  Stock actual: {p['stock_actual']} | Mínimo: {p['stock_minimo']} | Déficit: {p['deficit']}\n"
            f"  Proveedor: {p['proveedor']}"
        )
    return "\n".join(lineas)



@mcp.tool()
def listar_leads(estado: str | None = None) -> str:
    """
    Lista los leads (prospectos) del CRM de AndesTech con su valor estimado
    y próximo seguimiento. Úsala cuando el usuario pregunte sobre oportunidades
    de negocio, prospectos, el pipeline de ventas o clientes potenciales.
    Estados válidos: nuevo, contactado, en_negociacion,
    cerrado_ganado, cerrado_perdido.
    Sin filtro de estado retorna todos los leads ordenados por seguimiento.
    """
    _log_tool("listar_leads", estado=estado)

    leads = _get("/api/leads", {"estado": estado} if estado else None)

    if not leads:
        msg = f"No hay leads con estado '{estado}'." if estado else "No hay leads en el CRM."
        return msg

    titulo = "Pipeline CRM AndesTech" + (f" — Estado: {estado}" if estado else "")
    valor_total = sum(l.get("valor_estimado") or 0 for l in leads)
    lineas = [titulo, "=" * len(titulo), ""]

    for l in leads:
        seg = f" | Seguimiento: {l['fecha_seguimiento']}" if l.get("fecha_seguimiento") else ""
        lineas.append(
            f"ID {l['id']} — {l['nombre_contacto']} ({l['empresa']})\n"
            f"  Estado: {l['estado']}{seg}\n"
            f"  Interés: {l['interes']}\n"
            f"  Valor estimado: {_moneda(l.get('valor_estimado') or 0)}"
        )

    lineas.append(f"\nTotal: {len(leads)} lead(s) | Valor pipeline: {_moneda(valor_total)}")
    return "\n".join(lineas)


@mcp.tool()
def detalle_lead(lead_id: int) -> str:
    """
    Obtiene la ficha completa de un lead específico: datos de contacto,
    interés declarado, valor estimado, estado actual y notas internas.
    Úsala cuando el usuario quiera ver todos los detalles de un prospecto
    o necesite las notas de seguimiento de un lead en particular.
    """
    _log_tool("detalle_lead", lead_id=lead_id)

    l = _get(f"/api/leads/{lead_id}")

    seguimiento = l.get("fecha_seguimiento") or "Sin fecha agendada"
    notas = l.get("notas") or "Sin notas registradas"

    return (
        f"LEAD #{l['id']} — {l['nombre_contacto']}\n"
        f"{'=' * 50}\n"
        f"Empresa:             {l['empresa']}\n"
        f"Email:               {l.get('email') or 'N/D'}\n"
        f"Teléfono:            {l.get('telefono') or 'N/D'}\n"
        f"Estado:              {l['estado']}\n"
        f"Valor estimado:      {_moneda(l.get('valor_estimado') or 0)}\n"
        f"Fecha creación:      {l['fecha_creacion']}\n"
        f"Próximo seguimiento: {seguimiento}\n"
        f"\nInterés del cliente:\n  {l.get('interes') or 'N/D'}\n"
        f"\nNotas internas:\n  {notas}"
    )


@mcp.tool()
def leads_por_seguir(dias: int = 7) -> str:
    """
    Lista los leads que necesitan seguimiento en los próximos N días (por defecto 7).
    Úsala cuando el usuario pregunte qué prospectos hay que contactar esta semana,
    cuáles son los seguimientos pendientes o cuál es la agenda de ventas próxima.
    Retorna nombre, empresa, fecha de seguimiento, valor y notas de cada lead.
    """
    _log_tool("leads_por_seguir", dias=dias)

    hoy = date.today()
    hasta = hoy + timedelta(days=dias)

    leads = _get("/api/leads/seguimiento", {
        "desde": hoy.isoformat(),
        "hasta": hasta.isoformat(),
    })

    rango = f"{hoy.isoformat()} → {hasta.isoformat()}"

    if not leads:
        return f"No hay leads con seguimiento agendado entre {rango}."

    valor_total = sum(l.get("valor_estimado") or 0 for l in leads)
    lineas = [
        f"📅  SEGUIMIENTOS PENDIENTES — {rango}",
        f"    {len(leads)} lead(s) | Valor en juego: {_moneda(valor_total)}",
        "",
    ]

    for l in leads:
        dias_rest = (date.fromisoformat(l["fecha_seguimiento"]) - hoy).days
        urgencia = "¡HOY!" if dias_rest == 0 else f"en {dias_rest} día(s)"
        lineas.append(
            f"• [{l['fecha_seguimiento']}] {urgencia}\n"
            f"  {l['nombre_contacto']} — {l['empresa']}\n"
            f"  Estado: {l['estado']} | Valor: {_moneda(l.get('valor_estimado') or 0)}\n"
            f"  Notas: {l.get('notas') or 'Sin notas'}"
        )

    return "\n".join(lineas)



@mcp.tool()
def listar_clientes(busqueda: str | None = None) -> str:
    """
    Lista los clientes de AndesTech, con opción de buscar por nombre o empresa.
    Úsala cuando necesites encontrar el ID de un cliente para luego obtener su
    historial con historial_cliente, o cuando el usuario pregunte por la base
    de clientes. El parámetro busqueda filtra por nombre o empresa (parcial).
    """
    _log_tool("listar_clientes", busqueda=busqueda)

    if busqueda:
        clientes = _get("/api/clientes/buscar", {"q": busqueda})
    else:
        clientes = _get("/api/clientes")

    if not clientes:
        sufijo = f' que coincidan con "{busqueda}"' if busqueda else ""
        return f"No se encontraron clientes{sufijo}."

    lineas = [f"Clientes AndesTech — {len(clientes)} encontrado(s)", ""]
    for c in clientes:
        lineas.append(
            f"ID {c['id']:>2} — {c['nombre']}\n"
            f"         {c['empresa']} | {c['ciudad']}"
        )
    return "\n".join(lineas)


@mcp.tool()
def ventas_recientes(limite: int = 10) -> str:
    """
    Muestra las últimas ventas registradas en el sistema, con nombre del cliente,
    empresa, producto y estado de cada transacción.
    Úsala cuando el usuario pregunte por ventas recientes, actividad comercial
    reciente o quiera saber qué se ha vendido últimamente.
    El parámetro limite controla cuántas ventas mostrar (1-100, por defecto 10).
    """
    _log_tool("ventas_recientes", limite=limite)

    ventas = _get("/api/ventas/recientes", {"limite": limite})

    if not ventas:
        return "No hay ventas registradas."

    ICONO = {"completada": "✅", "pendiente": "⏳", "cancelada": "❌"}
    total_completado = sum(v["total"] for v in ventas if v["estado"] == "completada")

    lineas = [f"Últimas {len(ventas)} venta(s) — AndesTech", ""]
    for v in ventas:
        icono = ICONO.get(v["estado"], "•")
        lineas.append(
            f"{icono} [{v['fecha']}] {v['cliente']} ({v['empresa']})\n"
            f"   Producto: {v['producto']} ({v['categoria']})\n"
            f"   Cantidad: {v['cantidad']} uds | Total: {_moneda(v['total'])} | {v['estado']}"
        )

    lineas.append(f"\nTotal completadas (mostradas): {_moneda(total_completado)}")
    return "\n".join(lineas)


@mcp.tool()
def ventas_por_categoria(fecha_inicio: str, fecha_fin: str) -> str:
    """
    Resumen de ventas completadas agrupado por categoría de producto en un período.
    Úsala cuando el usuario quiera analizar qué categorías vendieron más,
    comparar períodos (ej: abril vs marzo) o ver el desempeño por línea de producto.
    Los parámetros deben estar en formato YYYY-MM-DD.
    Ejemplo: ventas_por_categoria('2026-04-01', '2026-04-30')
    """
    _log_tool("ventas_por_categoria", fecha_inicio=fecha_inicio, fecha_fin=fecha_fin)

    data = _get("/api/ventas/por-categoria", {"desde": fecha_inicio, "hasta": fecha_fin})

    categorias = data.get("por_categoria", [])
    if not categorias:
        return f"No hay ventas completadas entre {fecha_inicio} y {fecha_fin}."

    lineas = [
        f"Ventas por categoría — {fecha_inicio} al {fecha_fin}",
        f"Gran total: {_moneda(data['gran_total'])}",
        "",
    ]
    for cat in categorias:
        barra = "█" * max(1, int(cat["porcentaje"] / 5))
        lineas.append(
            f"  {cat['categoria']:<15} {_moneda(cat['total_vendido']):>10}"
            f"  ({cat['porcentaje']:>5}%)  {cat['num_ventas']} venta(s)  {barra}"
        )

    return "\n".join(lineas)


@mcp.tool()
def historial_cliente(cliente_id: int) -> str:
    """
    Muestra el perfil completo de un cliente y su historial de compras:
    datos de contacto, empresa, totales acumulados y cada transacción realizada.
    Úsala cuando el usuario pregunte sobre un cliente en particular, quiera
    saber qué ha comprado, cuánto ha gastado o necesite su perfil de comprador.
    Usa el ID numérico del cliente (usa listar_clientes si no lo conoces).
    """
    _log_tool("historial_cliente", cliente_id=cliente_id)

    c = _get(f"/api/clientes/{cliente_id}")

    lineas = [
        f"CLIENTE #{c['id']} — {c['nombre']}",
        "=" * 50,
        f"Empresa:       {c.get('empresa') or 'N/D'}",
        f"Ciudad:        {c.get('ciudad') or 'N/D'}",
        f"Email:         {c.get('email') or 'N/D'}",
        f"Teléfono:      {c.get('telefono') or 'N/D'}",
        f"Cliente desde: {c.get('fecha_registro') or 'N/D'}",
        "",
        "Resumen de compras:",
        f"  Total pedidos:       {c['total_pedidos']}",
        f"  Completados:         {c['pedidos_completados']}",
        f"  Monto total:         {_moneda(c['monto_total'])}",
        f"  Monto completado:    {_moneda(c['monto_completado'])}",
        "",
        "Historial de compras:",
    ]

    ICONO = {"completada": "✅", "pendiente": "⏳", "cancelada": "❌"}
    for v in c.get("historial_compras", []):
        icono = ICONO.get(v["estado"], "•")
        lineas.append(
            f"  {icono} [{v['fecha']}] {v['producto']}  [{v['categoria']}]\n"
            f"      {v['cantidad']} × {_moneda(v['precio_unitario'])} = {_moneda(v['total'])}  |  {v['estado']}"
        )

    return "\n".join(lineas)


@mcp.tool()
def crear_lead(
    nombre_contacto: str,
    empresa: str,
    email: str | None = None,
    telefono: str | None = None,
    interes: str | None = None,
    valor_estimado: float | None = None,
    estado: str = "nuevo",
    fecha_seguimiento: str | None = None,
    notas: str | None = None,
) -> str:
    """
    Registra un nuevo lead (prospecto) en el CRM de AndesTech.
    Úsala cuando el usuario quiera agregar un cliente potencial, anotar un
    contacto que mostró interés, o registrar un prospecto nuevo.
    El estado por defecto es 'nuevo'. Estados válidos: nuevo, contactado,
    en_negociacion, cerrado_ganado, cerrado_perdido.
    fecha_seguimiento en formato YYYY-MM-DD. valor_estimado en USD.
    """
    _log_tool("crear_lead", nombre_contacto=nombre_contacto, empresa=empresa)

    lead = _post("/api/leads", {
        "nombre_contacto": nombre_contacto,
        "empresa": empresa,
        "email": email,
        "telefono": telefono,
        "interes": interes,
        "valor_estimado": valor_estimado,
        "estado": estado,
        "fecha_seguimiento": fecha_seguimiento,
        "notas": notas,
    })

    return (
        f"✅ Lead creado exitosamente (ID: {lead['id']})\n\n"
        f"Contacto:   {lead['nombre_contacto']}\n"
        f"Empresa:    {lead['empresa']}\n"
        f"Estado:     {lead['estado']}\n"
        f"Interés:    {lead.get('interes') or 'No especificado'}\n"
        f"Valor est.: {_moneda(lead['valor_estimado']) if lead.get('valor_estimado') else 'No especificado'}\n"
        f"Seguim.:    {lead.get('fecha_seguimiento') or 'No agendado'}\n"
        f"Creado:     {lead['fecha_creacion']}"
    )


@mcp.tool()
def ingresar_stock(producto_id: int, cantidad: int) -> str:
    """
    Registra el ingreso de nuevas unidades al inventario de un producto.
    Úsala cuando el usuario indique que llegó mercadería, que se reabastecieron
    productos, o que quiere actualizar el stock de un artículo específico.
    Requiere el ID del producto (obtenible con consultar_inventario o
    buscar_producto) y la cantidad de unidades a agregar al stock actual.
    """
    _log_tool("ingresar_stock", producto_id=producto_id, cantidad=cantidad)

    p = _patch(f"/api/inventario/{producto_id}/stock", {"cantidad": cantidad})

    alerta = (
        ""
        if p["stock_ok"]
        else f"\n⚠  Aún bajo el mínimo — faltan {p['stock_minimo'] - p['stock']} uds más"
    )

    return (
        f"✅ Stock actualizado — {p['nombre']}\n\n"
        f"Stock anterior:    {p['stock_anterior']} unidades\n"
        f"Unidades ingres.:  +{p['unidades_ingresadas']}\n"
        f"Stock actual:      {p['stock']} unidades\n"
        f"Stock mínimo:      {p['stock_minimo']} unidades\n"
        f"Estado:            {'✓ OK' if p['stock_ok'] else '⚠ Bajo mínimo'}{alerta}\n"
        f"Actualizado:       {p['ultima_actualizacion']}"
    )


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--stdio", action="store_true", help="Modo stdio para Claude Desktop local")
    args = parser.parse_args()

    if args.stdio:
        mcp.run(transport="stdio")
    else:
        logger.info("=" * 55)
        logger.info("  AndesTech MCP Server — Demo AWS GenAI Day Ecuador 2026")
        logger.info("=" * 55)
        logger.info("API de negocio : %s", API_BASE)
        logger.info("MCP endpoint   : http://%s:%s/mcp", MCP_HOST, MCP_PORT)
        logger.info("Healthcheck    : http://%s:%s/health", MCP_HOST, MCP_PORT)
        logger.info("Herramientas   : 12 disponibles para Claude")
        logger.info("-" * 55)
        logger.info("Esperando conexión de Claude Desktop...")
        mcp.run(transport="streamable-http")
