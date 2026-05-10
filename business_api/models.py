from sqlalchemy import Column, Integer, String, Float, ForeignKey, Text
from sqlalchemy.orm import relationship
from .database import Base


class Producto(Base):
    __tablename__ = "productos"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(200), nullable=False)
    categoria = Column(String(100), nullable=False)
    precio = Column(Float, nullable=False)
    stock = Column(Integer, nullable=False, default=0)
    stock_minimo = Column(Integer, nullable=False, default=5)
    proveedor = Column(String(200), nullable=False)
    ultima_actualizacion = Column(String(10), nullable=False)

    ventas = relationship("Venta", back_populates="producto")


class Cliente(Base):
    __tablename__ = "clientes"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(200), nullable=False)
    email = Column(String(200))
    telefono = Column(String(20))
    empresa = Column(String(200))
    ciudad = Column(String(100))
    fecha_registro = Column(String(10), nullable=False)

    ventas = relationship("Venta", back_populates="cliente")


class Venta(Base):
    __tablename__ = "ventas"

    id = Column(Integer, primary_key=True, index=True)
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=False)
    producto_id = Column(Integer, ForeignKey("productos.id"), nullable=False)
    cantidad = Column(Integer, nullable=False)
    precio_unitario = Column(Float, nullable=False)
    total = Column(Float, nullable=False)
    fecha = Column(String(10), nullable=False)
    estado = Column(String(50), nullable=False)

    cliente = relationship("Cliente", back_populates="ventas")
    producto = relationship("Producto", back_populates="ventas")


class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True)
    nombre_contacto = Column(String(200), nullable=False)
    empresa = Column(String(200), nullable=False)
    email = Column(String(200))
    telefono = Column(String(20))
    interes = Column(Text)
    valor_estimado = Column(Float)
    estado = Column(String(50), nullable=False)
    fecha_creacion = Column(String(10), nullable=False)
    fecha_seguimiento = Column(String(10), nullable=True)
    notas = Column(Text)
