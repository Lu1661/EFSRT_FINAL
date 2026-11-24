from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Usuario(Base):
    __tablename__ = "usuario"
    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(80))
    usuario: Mapped[str] = mapped_column(String(30), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    rol: Mapped[str] = mapped_column(String(20))
    activo: Mapped[bool] = mapped_column(Boolean, server_default=text("1"))


class Producto(Base):
    __tablename__ = "producto"
    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(20), unique=True)
    nombre: Mapped[str] = mapped_column(String(120))
    categoria: Mapped[str] = mapped_column(String(30))
    precio: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    stock: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    stock_minimo: Mapped[int] = mapped_column(Integer, server_default=text("5"))
    temporada_escolar: Mapped[bool] = mapped_column(Boolean, server_default=text("0"))


class Cliente(Base):
    __tablename__ = "cliente"
    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100))
    tipo: Mapped[str] = mapped_column(String(12))
    telefono: Mapped[str | None] = mapped_column(String(20))


class ProveedorProducto(Base):
    __tablename__ = "proveedor_producto"
    proveedor_id: Mapped[int] = mapped_column(ForeignKey("proveedor.id"), primary_key=True)
    producto_id: Mapped[int] = mapped_column(ForeignKey("producto.id"), primary_key=True)


class Proveedor(Base):
    __tablename__ = "proveedor"
    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100))
    contacto: Mapped[str | None] = mapped_column(String(100))
    productos: Mapped[list[Producto]] = relationship(secondary=ProveedorProducto.__table__)


class Venta(Base):
    __tablename__ = "venta"
    id: Mapped[int] = mapped_column(primary_key=True)
    fecha: Mapped[DateTime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    total: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"))
    cliente_id: Mapped[int | None] = mapped_column(ForeignKey("cliente.id"))
    usuario: Mapped[Usuario] = relationship()
    cliente: Mapped[Cliente | None] = relationship()
    detalles: Mapped[list["DetalleVenta"]] = relationship(order_by="DetalleVenta.id")


class DetalleVenta(Base):
    __tablename__ = "detalle_venta"
    id: Mapped[int] = mapped_column(primary_key=True)
    venta_id: Mapped[int] = mapped_column(ForeignKey("venta.id", ondelete="CASCADE"))
    producto_id: Mapped[int] = mapped_column(ForeignKey("producto.id"))
    cantidad: Mapped[int] = mapped_column(Integer)
    precio_unitario: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    subtotal: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    producto: Mapped[Producto] = relationship()


class MovimientoStock(Base):
    __tablename__ = "movimiento_stock"
    id: Mapped[int] = mapped_column(primary_key=True)
    producto_id: Mapped[int] = mapped_column(ForeignKey("producto.id"))
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"))
    fecha: Mapped[DateTime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    cantidad_anterior: Mapped[int] = mapped_column(Integer)
    cantidad_nueva: Mapped[int] = mapped_column(Integer)
    motivo: Mapped[str] = mapped_column(String(100))
    producto: Mapped[Producto] = relationship()
    usuario: Mapped[Usuario] = relationship()
