from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import joinedload, selectinload

from .modelos import Cliente, DetalleVenta, MovimientoStock, Producto, Proveedor, Usuario, Venta


def paginar(db, stmt, pagina, limite):
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    return db.scalars(stmt.offset((pagina - 1) * limite).limit(limite)).all(), total


class Usuarios:
    def __init__(self, db):
        self.db = db

    def obtener(self, ident):
        return self.db.get(Usuario, ident)

    def por_usuario(self, usuario):
        return self.db.scalar(select(Usuario).where(Usuario.usuario == usuario))

    def listar(self, q=""):
        stmt = select(Usuario).order_by(Usuario.nombre, Usuario.id)
        if q:
            stmt = stmt.where(or_(Usuario.nombre.contains(q, autoescape=True),
                                  Usuario.usuario.contains(q, autoescape=True)))
        return self.db.scalars(stmt).all()

    def admins_activos(self):
        stmt = select(Usuario).where(Usuario.rol == "Administrador", Usuario.activo.is_(True))
        return self.db.scalars(stmt.order_by(Usuario.id).with_for_update()).all()


class Productos:
    def __init__(self, db):
        self.db = db

    def obtener(self, ident):
        return self.db.get(Producto, ident)

    def por_codigo(self, codigo):
        return self.db.scalar(select(Producto).where(Producto.codigo == codigo))

    def buscar(self, q="", categoria="", estado="", *, pagina=1, limite=24):
        stmt = select(Producto)
        if q:
            stmt = stmt.where(or_(Producto.nombre.contains(q, autoescape=True),
                                  Producto.codigo.contains(q, autoescape=True)))
        if categoria:
            stmt = stmt.where(Producto.categoria == categoria)
        estados = {
            "agotado": Producto.stock == 0,
            "bajo": (Producto.stock > 0) & (Producto.stock <= Producto.stock_minimo),
            "normal": Producto.stock > Producto.stock_minimo,
        }
        if estado in estados:
            stmt = stmt.where(estados[estado])
        orden = [Producto.nombre, Producto.id]
        if q:
            orden.insert(0, case((Producto.codigo == q, 0), else_=1))
        return paginar(self.db, stmt.order_by(*orden), pagina, limite)

    def opciones(self, ids=None):
        stmt = select(Producto).order_by(Producto.nombre, Producto.id)
        if ids is not None:
            stmt = stmt.where(Producto.id.in_(ids))
        return self.db.scalars(stmt).all()

    def bloquear(self, ids):
        stmt = select(Producto).where(Producto.id.in_(ids)).order_by(Producto.id).with_for_update()
        return {obj.id: obj for obj in self.db.scalars(stmt)}

    def bajos(self):
        stmt = select(Producto).where(Producto.stock <= Producto.stock_minimo)
        return self.db.scalars(stmt.order_by(Producto.stock, Producto.nombre, Producto.id)).all()

    def movimientos(self, pagina=1):
        stmt = select(MovimientoStock).options(
            joinedload(MovimientoStock.producto), joinedload(MovimientoStock.usuario)
        ).order_by(MovimientoStock.fecha.desc(), MovimientoStock.id.desc())
        return paginar(self.db, stmt, pagina, 24)


class Clientes:
    def __init__(self, db):
        self.db = db

    def obtener(self, ident):
        return self.db.get(Cliente, ident)

    def duplicado(self, nombre, telefono):
        criteria = [Cliente.nombre == nombre]
        if telefono:
            criteria.append(Cliente.telefono == telefono)
        return self.db.scalar(select(Cliente).where(or_(*criteria)).order_by(Cliente.id))

    def listar(self, q="", tipo=""):
        stmt = select(Cliente)
        if q:
            stmt = stmt.where(or_(Cliente.nombre.contains(q, autoescape=True),
                                  Cliente.telefono.contains(q, autoescape=True)))
        if tipo:
            stmt = stmt.where(Cliente.tipo == tipo)
        return self.db.scalars(stmt.order_by(Cliente.nombre, Cliente.id)).all()


class Proveedores:
    def __init__(self, db):
        self.db = db

    def obtener(self, ident):
        return self.db.get(Proveedor, ident)

    def duplicado(self, nombre, ident=None):
        stmt = select(Proveedor).where(Proveedor.nombre == nombre)
        if ident is not None:
            stmt = stmt.where(Proveedor.id != ident)
        return self.db.scalar(stmt.order_by(Proveedor.id))

    def listar(self, q=""):
        stmt = select(Proveedor).options(selectinload(Proveedor.productos))
        if q:
            stmt = stmt.where(Proveedor.nombre.contains(q, autoescape=True))
        return self.db.scalars(stmt.order_by(Proveedor.nombre, Proveedor.id)).all()


class Ventas:
    def __init__(self, db):
        self.db = db

    def detalle(self, ident):
        stmt = select(Venta).where(Venta.id == ident).options(
            joinedload(Venta.usuario), joinedload(Venta.cliente),
            selectinload(Venta.detalles).joinedload(DetalleVenta.producto),
        )
        return self.db.scalar(stmt)

    def historial(self, desde=None, hasta=None, usuario=None, cliente=None, *, pagina=1):
        stmt = select(Venta)
        if desde is not None:
            stmt = stmt.where(Venta.fecha >= desde)
        if hasta is not None:
            stmt = stmt.where(Venta.fecha < hasta)
        if usuario is not None:
            stmt = stmt.where(Venta.usuario_id == usuario)
        if cliente is not None:
            stmt = stmt.where(Venta.cliente_id == cliente)
        stmt = stmt.options(joinedload(Venta.usuario), joinedload(Venta.cliente))
        return paginar(self.db, stmt.order_by(Venta.fecha.desc(), Venta.id.desc()), pagina, 24)

    def totales_por_dia(self, desde, hasta):
        dia = func.date(Venta.fecha)
        stmt = select(dia, func.count(), func.sum(Venta.total)).where(
            Venta.fecha >= desde, Venta.fecha < hasta
        ).group_by(dia).order_by(dia)
        return self.db.execute(stmt).all()

    def mas_vendidos(self, desde, hasta):
        unidades = func.sum(DetalleVenta.cantidad)
        stmt = select(Producto.nombre, Producto.categoria, unidades, func.sum(DetalleVenta.subtotal))
        stmt = stmt.join(DetalleVenta, DetalleVenta.producto_id == Producto.id).join(Venta)
        stmt = stmt.where(Venta.fecha >= desde, Venta.fecha < hasta)
        stmt = stmt.group_by(Producto.id, Producto.nombre, Producto.categoria)
        return self.db.execute(stmt.order_by(unidades.desc(), Producto.nombre, Producto.id)).all()
