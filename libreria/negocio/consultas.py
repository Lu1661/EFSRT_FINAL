from ..datos.repositorios import Clientes, Productos, Proveedores, Usuarios, Ventas
from .servicios import filtros_fechas, producto_publico


def buscar_productos(db, q, categoria, estado="", *, pagina=1):
    return Productos(db).buscar(q, categoria, estado, pagina=pagina)


def catalogo(db, q, categoria, pagina, *, personal=False):
    productos, total = buscar_productos(db, q, categoria, pagina=pagina)
    data = []
    for prod in productos:
        fila = producto_publico(prod)
        if personal:
            fila.update(id=prod.id, stock=prod.stock)
        data.append(fila)
    return dict(productos=data, total=total, pagina=pagina)


def listar_usuarios(db, q=""):
    return Usuarios(db).listar(q)


def obtener_usuario(db, ident):
    return Usuarios(db).obtener(ident)


def obtener_producto(db, ident):
    return Productos(db).obtener(ident)


def opciones_productos(db):
    return Productos(db).opciones()


def listar_movimientos(db, pagina):
    return Productos(db).movimientos(pagina)


def obtener_proveedor(db, ident):
    return Proveedores(db).obtener(ident)


def listar_proveedores(db, q):
    return Proveedores(db).listar(q)


def listar_clientes(db, q="", tipo=""):
    return Clientes(db).listar(q, tipo)


def obtener_cliente(db, ident):
    return Clientes(db).obtener(ident)


def historial(db, pagina, desde="", hasta="", usuario=None, *, cliente=None):
    inicio, fin = filtros_fechas(desde, hasta)
    return Ventas(db).historial(inicio, fin, usuario, cliente, pagina=pagina)


def detalle_venta(db, ident):
    return Ventas(db).detalle(ident)
