from fastapi import FastAPI, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, case
from .database import get_db
from .models import Producto, Cliente, Venta, Lead

app = FastAPI(
    title="AndesTech Business API",
    description="API de inventario y CRM — Demo MCP AWS GenAI Day Ecuador 2026",
    version="1.0.0",
)


@app.get("/api/health")
def health():
    return {"status": "ok", "servicio": "AndesTech Business API", "version": "1.0"}


# Inventario — rutas estáticas antes de /{producto_id} para evitar conflictos de routing

@app.get("/api/inventario/stock-bajo")
def stock_bajo(db: Session = Depends(get_db)):
    productos = (
        db.query(Producto)
        .filter(Producto.stock < Producto.stock_minimo)
        .order_by(Producto.categoria, Producto.nombre)
        .all()
    )
    return [
        {
            "id": p.id,
            "nombre": p.nombre,
            "categoria": p.categoria,
            "stock_actual": p.stock,
            "stock_minimo": p.stock_minimo,
            "deficit": p.stock_minimo - p.stock,
            "proveedor": p.proveedor,
            "ultima_actualizacion": p.ultima_actualizacion,
        }
        for p in productos
    ]


@app.get("/api/inventario/categorias")
def categorias(db: Session = Depends(get_db)):
    filas = (
        db.query(
            Producto.categoria,
            func.count(Producto.id).label("total"),
            func.sum(
                case((Producto.stock < Producto.stock_minimo, 1), else_=0)
            ).label("stock_bajo"),
        )
        .group_by(Producto.categoria)
        .order_by(Producto.categoria)
        .all()
    )
    return [
        {
            "categoria": f.categoria,
            "total_productos": f.total,
            "productos_stock_bajo": f.stock_bajo,
        }
        for f in filas
    ]


@app.get("/api/inventario/buscar")
def buscar_productos(
    q: str = Query(..., min_length=2),
    db: Session = Depends(get_db),
):
    productos = (
        db.query(Producto)
        .filter(Producto.nombre.ilike(f"%{q}%"))
        .order_by(Producto.nombre)
        .all()
    )
    return [_producto_dict(p) for p in productos]


@app.get("/api/inventario")
def listar_inventario(
    categoria: str | None = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(Producto)
    if categoria:
        query = query.filter(Producto.categoria.ilike(f"%{categoria}%"))
    return [_producto_dict(p) for p in query.order_by(Producto.categoria, Producto.nombre).all()]


@app.get("/api/inventario/{producto_id}")
def detalle_producto(producto_id: int, db: Session = Depends(get_db)):
    p = db.get(Producto, producto_id)
    if not p:
        raise HTTPException(status_code=404, detail=f"Producto con ID {producto_id} no encontrado")
    return _producto_dict(p)


# Clientes — /buscar antes de /{cliente_id}

@app.get("/api/clientes/buscar")
def buscar_clientes(
    q: str = Query(..., min_length=2),
    db: Session = Depends(get_db),
):
    clientes = (
        db.query(Cliente)
        .filter(Cliente.nombre.ilike(f"%{q}%") | Cliente.empresa.ilike(f"%{q}%"))
        .order_by(Cliente.nombre)
        .all()
    )
    return [_cliente_resumen(c) for c in clientes]


@app.get("/api/clientes")
def listar_clientes(db: Session = Depends(get_db)):
    return [_cliente_resumen(c) for c in db.query(Cliente).order_by(Cliente.nombre).all()]


@app.get("/api/clientes/{cliente_id}")
def detalle_cliente(cliente_id: int, db: Session = Depends(get_db)):
    c = db.get(Cliente, cliente_id)
    if not c:
        raise HTTPException(status_code=404, detail=f"Cliente con ID {cliente_id} no encontrado")

    rows = (
        db.query(
            Venta,
            Producto.nombre.label("producto_nombre"),
            Producto.categoria.label("categoria"),
        )
        .join(Producto, Venta.producto_id == Producto.id)
        .filter(Venta.cliente_id == cliente_id)
        .order_by(Venta.fecha.desc())
        .all()
    )

    historial = [
        {
            "venta_id": r.Venta.id,
            "producto": r.producto_nombre,
            "categoria": r.categoria,
            "cantidad": r.Venta.cantidad,
            "precio_unitario": r.Venta.precio_unitario,
            "total": r.Venta.total,
            "fecha": r.Venta.fecha,
            "estado": r.Venta.estado,
        }
        for r in rows
    ]

    completadas = [v for v in historial if v["estado"] == "completada"]

    return {
        **_cliente_resumen(c),
        "historial_compras": historial,
        "total_pedidos": len(historial),
        "pedidos_completados": len(completadas),
        "monto_total": round(sum(v["total"] for v in historial), 2),
        "monto_completado": round(sum(v["total"] for v in completadas), 2),
    }


# Leads — /seguimiento antes de /{lead_id}

@app.get("/api/leads/seguimiento")
def leads_seguimiento(
    desde: str = Query(..., description="YYYY-MM-DD"),
    hasta: str = Query(..., description="YYYY-MM-DD"),
    db: Session = Depends(get_db),
):
    leads = (
        db.query(Lead)
        .filter(Lead.fecha_seguimiento >= desde, Lead.fecha_seguimiento <= hasta)
        .order_by(Lead.fecha_seguimiento)
        .all()
    )
    return [_lead_completo(l) for l in leads]


@app.get("/api/leads")
def listar_leads(
    estado: str | None = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(Lead)
    if estado:
        query = query.filter(Lead.estado == estado)
    # CASE pone los leads sin fecha_seguimiento al final
    leads = query.order_by(
        case((Lead.fecha_seguimiento.is_(None), 1), else_=0),
        Lead.fecha_seguimiento,
        Lead.nombre_contacto,
    ).all()
    return [_lead_resumen(l) for l in leads]


@app.get("/api/leads/{lead_id}")
def detalle_lead(lead_id: int, db: Session = Depends(get_db)):
    l = db.get(Lead, lead_id)
    if not l:
        raise HTTPException(status_code=404, detail=f"Lead con ID {lead_id} no encontrado")
    return _lead_completo(l)


@app.get("/api/ventas/recientes")
def ventas_recientes(
    limite: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(
            Venta,
            Cliente.nombre.label("cliente_nombre"),
            Cliente.empresa.label("empresa"),
            Producto.nombre.label("producto_nombre"),
            Producto.categoria.label("categoria"),
        )
        .join(Cliente, Venta.cliente_id == Cliente.id)
        .join(Producto, Venta.producto_id == Producto.id)
        .order_by(Venta.fecha.desc(), Venta.id.desc())
        .limit(limite)
        .all()
    )
    return [
        {
            "id": r.Venta.id,
            "cliente": r.cliente_nombre,
            "empresa": r.empresa,
            "producto": r.producto_nombre,
            "categoria": r.categoria,
            "cantidad": r.Venta.cantidad,
            "precio_unitario": r.Venta.precio_unitario,
            "total": r.Venta.total,
            "fecha": r.Venta.fecha,
            "estado": r.Venta.estado,
        }
        for r in rows
    ]


@app.get("/api/ventas/por-categoria")
def ventas_por_categoria(
    desde: str = Query(..., description="YYYY-MM-DD"),
    hasta: str = Query(..., description="YYYY-MM-DD"),
    db: Session = Depends(get_db),
):
    filas = (
        db.query(
            Producto.categoria,
            func.count(Venta.id).label("num_ventas"),
            func.sum(Venta.total).label("total_vendido"),
        )
        .join(Producto, Venta.producto_id == Producto.id)
        .filter(Venta.fecha >= desde, Venta.fecha <= hasta, Venta.estado == "completada")
        .group_by(Producto.categoria)
        .order_by(func.sum(Venta.total).desc())
        .all()
    )

    gran_total = sum(f.total_vendido or 0 for f in filas)

    return {
        "periodo": {"desde": desde, "hasta": hasta},
        "gran_total": round(gran_total, 2),
        "por_categoria": [
            {
                "categoria": f.categoria,
                "num_ventas": f.num_ventas,
                "total_vendido": round(f.total_vendido or 0, 2),
                "porcentaje": round((f.total_vendido or 0) / gran_total * 100, 1) if gran_total else 0,
            }
            for f in filas
        ],
    }


@app.get("/api/ventas/por-cliente/{cliente_id}")
def ventas_por_cliente(cliente_id: int, db: Session = Depends(get_db)):
    c = db.get(Cliente, cliente_id)
    if not c:
        raise HTTPException(status_code=404, detail=f"Cliente con ID {cliente_id} no encontrado")

    rows = (
        db.query(
            Venta,
            Producto.nombre.label("producto_nombre"),
            Producto.categoria.label("categoria"),
        )
        .join(Producto, Venta.producto_id == Producto.id)
        .filter(Venta.cliente_id == cliente_id)
        .order_by(Venta.fecha.desc())
        .all()
    )

    compras = [
        {
            "id": r.Venta.id,
            "producto": r.producto_nombre,
            "categoria": r.categoria,
            "cantidad": r.Venta.cantidad,
            "precio_unitario": r.Venta.precio_unitario,
            "total": r.Venta.total,
            "fecha": r.Venta.fecha,
            "estado": r.Venta.estado,
        }
        for r in rows
    ]

    completadas = [x for x in compras if x["estado"] == "completada"]

    return {
        "cliente_id": c.id,
        "cliente_nombre": c.nombre,
        "empresa": c.empresa,
        "ciudad": c.ciudad,
        "email": c.email,
        "total_pedidos": len(compras),
        "pedidos_completados": len(completadas),
        "monto_total": round(sum(x["total"] for x in compras), 2),
        "monto_completado": round(sum(x["total"] for x in completadas), 2),
        "compras": compras,
    }


def _producto_dict(p: Producto) -> dict:
    return {
        "id": p.id,
        "nombre": p.nombre,
        "categoria": p.categoria,
        "precio": p.precio,
        "stock": p.stock,
        "stock_minimo": p.stock_minimo,
        "stock_ok": p.stock >= p.stock_minimo,
        "proveedor": p.proveedor,
        "ultima_actualizacion": p.ultima_actualizacion,
    }


def _cliente_resumen(c: Cliente) -> dict:
    return {
        "id": c.id,
        "nombre": c.nombre,
        "email": c.email,
        "telefono": c.telefono,
        "empresa": c.empresa,
        "ciudad": c.ciudad,
        "fecha_registro": c.fecha_registro,
    }


def _lead_resumen(l: Lead) -> dict:
    return {
        "id": l.id,
        "nombre_contacto": l.nombre_contacto,
        "empresa": l.empresa,
        "interes": l.interes,
        "valor_estimado": l.valor_estimado,
        "estado": l.estado,
        "fecha_seguimiento": l.fecha_seguimiento,
    }


def _lead_completo(l: Lead) -> dict:
    return {
        "id": l.id,
        "nombre_contacto": l.nombre_contacto,
        "empresa": l.empresa,
        "email": l.email,
        "telefono": l.telefono,
        "interes": l.interes,
        "valor_estimado": l.valor_estimado,
        "estado": l.estado,
        "fecha_creacion": l.fecha_creacion,
        "fecha_seguimiento": l.fecha_seguimiento,
        "notas": l.notas,
    }
