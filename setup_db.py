#!/usr/bin/env python3
"""Crea y puebla la base de datos de AndesTech con datos semilla."""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from business_api.database import engine, Base, SessionLocal
from business_api.models import Producto, Cliente, Venta, Lead
from business_api.seed_data import PRODUCTOS, CLIENTES, VENTAS, LEADS


def crear_tablas():
    print("Creando tablas...")
    Base.metadata.create_all(bind=engine)
    print("✓ Tablas creadas")


def poblar_datos(session):
    if session.query(Producto).count() > 0:
        print("⚠  La BD ya tiene datos. Usa --reset para limpiar y recargar.")
        return False

    print(f"Insertando {len(PRODUCTOS)} productos...")
    for data in PRODUCTOS:
        session.add(Producto(**data))
    session.flush()

    print(f"Insertando {len(CLIENTES)} clientes...")
    for data in CLIENTES:
        session.add(Cliente(**data))
    session.flush()

    print(f"Insertando {len(VENTAS)} ventas...")
    for data in VENTAS:
        session.add(Venta(**data))
    session.flush()

    print(f"Insertando {len(LEADS)} leads...")
    for data in LEADS:
        session.add(Lead(**data))

    session.commit()
    return True


def resetear():
    print("⚠  Eliminando tablas existentes...")
    Base.metadata.drop_all(bind=engine)
    crear_tablas()


if __name__ == "__main__":
    reset = "--reset" in sys.argv

    if reset:
        resetear()
    else:
        crear_tablas()

    with SessionLocal() as session:
        ok = poblar_datos(session)

    if ok:
        print("\n✅ Base de datos lista")
        print(f"   Productos : {len(PRODUCTOS):>3}  ({sum(1 for p in PRODUCTOS if p['stock'] < p['stock_minimo'])} con stock bajo)")
        print(f"   Clientes  : {len(CLIENTES):>3}")
        print(f"   Ventas    : {len(VENTAS):>3}")
        semana = sum(1 for l in LEADS if l.get("fecha_seguimiento") and "2026-05-12" <= l["fecha_seguimiento"] <= "2026-05-16")
        print(f"   Leads     : {len(LEADS):>3}  ({semana} con seguimiento semana 12-16 mayo)")
