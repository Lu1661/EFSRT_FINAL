import secrets

from sqlalchemy import func, select

from ..config import INSTANCE
from ..datos.modelos import Producto, Usuario
from ..datos.repositorios import Productos, Usuarios
from .servicios import guardar_cliente, guardar_producto, guardar_proveedor, guardar_usuario

PRODUCTOS = [
    ("L-0101", "Razonamiento Matemático 5", "Libros", "38.00", 24, 5, True),
    ("L-0102", "Comunicación 4.º grado", "Libros", "32.50", 4, 5, True),
    ("L-0103", "Cien años de soledad", "Libros", "59.90", 11, 5, False),
    ("L-0107", "Libro Ciencia 4", "Libros", "54.00", 2, 5, True),
    ("U-0012", "Cuaderno A4 cuadriculado, 100 hojas", "Útiles", "4.50", 48, 5, True),
    ("U-0045", "Lápiz HB × 12", "Útiles", "8.00", 9, 5, True),
    ("U-0078", "Papel bond A4", "Útiles", "21.00", 0, 5, False),
    ("U-0110", "Témpera × 6", "Útiles", "12.50", 30, 5, True),
]


def preparar_demo(db):
    if db.scalar(select(func.count()).select_from(Usuario)):
        return None
    users = [
        ("Administración de demo", "admin_demo", "Administrador"),
        ("Vendedor de demo", "vendedor_demo", "Vendedor"),
    ]
    claves = []
    for nombre, usuario, rol in users:
        password = secrets.token_urlsafe(14)
        guardar_usuario(db, dict(nombre=nombre, usuario=usuario, rol=rol, password=password, activo="1"))
        claves.append(f"{rol}: {usuario} | {password}")
    if not db.scalar(select(func.count()).select_from(Producto)):
        for codigo, nombre, categoria, precio, stock, minimo, temporada in PRODUCTOS:
            guardar_producto(db, dict(codigo=codigo, nombre=nombre, categoria=categoria, precio=precio,
                                      stock=stock, stock_minimo=minimo, temporada_escolar=temporada))
        nombre = "Distribuidora de ejemplo"
        ids = [str(p.id) for p in Productos(db).opciones() if p.categoria == "Libros"]
        guardar_proveedor(db, dict(nombre=nombre, contacto="Contacto de demostración"), ids)
        guardar_cliente(db, dict(nombre="Mayorista de demostración", tipo="Mayorista", telefono=""))
    return claves


def crear_acceso_demo(session_factory, folder=None):
    folder = folder or INSTANCE
    folder.mkdir(parents=True, exist_ok=True)
    output = folder / "acceso_demo.txt"
    with session_factory() as db:
        claves = preparar_demo(db)
        if not claves:
            return output if output.is_file() else None
        temporal = output.with_suffix(".tmp")
        temporal.write_text("\n".join(claves) + "\n", encoding="utf-8")
        try:
            db.commit()
            temporal.replace(output)
        finally:
            temporal.unlink(missing_ok=True)
    return output
