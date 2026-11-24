import csv
import re
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP
from io import StringIO
from urllib.parse import quote
from zipfile import BadZipFile

from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from ..datos.modelos import Cliente, DetalleVenta, MovimientoStock, Producto, Proveedor, Usuario, Venta
from ..datos.repositorios import Clientes, Productos, Proveedores, Usuarios, Ventas
from .reglas import (
    CATEGORIAS, CENTIMO, MAX_IMPORTE, MAX_INT, ROLES, TIPOS_CLIENTE, ReglaError,
    ahora, disponibilidad, entero, importe, inicio, leer_fecha, limites_periodo, opcion, texto,
)


def autenticar(db, nombre, password):
    if not (0 < len(nombre) <= 30 and 0 < len(password) <= 128):
        return None
    usuario = Usuarios(db).por_usuario(nombre)
    if usuario and usuario.activo and check_password_hash(usuario.password_hash, password):
        return usuario
    return None


def clave_segura(value):
    if not 8 <= len(value) <= 128:
        raise ReglaError("La contraseña debe tener entre 8 y 128 caracteres.")
    return generate_password_hash(value)


def guardar_usuario(db, form, ident=None):
    repo = Usuarios(db)
    nombre = texto(form.get("nombre"), "el nombre", 80)
    login = texto(form.get("usuario"), "el usuario", 30)
    rol = opcion(form.get("rol"), ROLES, "un rol")
    activo = form.get("activo") == "1"
    if ident is not None:
        admins = repo.admins_activos()
        obj = repo.obtener(ident)
        if obj is None:
            raise ReglaError("No se encontró el usuario.")
        if len(admins) == 1 and admins[0].id == ident and (rol != "Administrador" or not activo):
            raise ReglaError("Debe quedar un administrador activo.")
    else:
        obj = Usuario(password_hash=clave_segura(str(form.get("password", ""))))
    previo = repo.por_usuario(login)
    if previo and previo.id != ident:
        raise ReglaError("Ese nombre de usuario ya existe.")
    obj.nombre, obj.usuario, obj.rol, obj.activo = nombre, login, rol, activo
    db.add(obj)
    try:
        db.flush()
    except IntegrityError as exc:
        raise ReglaError("Ese nombre de usuario ya existe.") from exc
    return obj


def restablecer_clave(usuario, password):
    usuario.password_hash = clave_segura(password)


def datos_producto(form, *, nuevo=True):
    data = {
        "codigo": texto(form.get("codigo"), "el código", 20),
        "nombre": texto(form.get("nombre"), "el nombre", 120),
        "categoria": opcion(form.get("categoria"), CATEGORIAS, "una categoría"),
        "precio": importe(form.get("precio")),
        "stock_minimo": entero(form.get("stock_minimo", 5), "stock mínimo", minimo=1),
        "temporada_escolar": form.get("temporada_escolar") in (True, "1", "sí", "Si", "Sí", "si"),
    }
    if nuevo:
        data["stock"] = entero(form.get("stock", 0), "stock inicial")
    return data


def guardar_producto(db, form, ident=None):
    repo = Productos(db)
    data = datos_producto(form, nuevo=ident is None)
    obj = repo.obtener(ident) if ident is not None else Producto()
    if obj is None:
        raise ReglaError("No se encontró el producto.")
    existing = repo.por_codigo(data["codigo"])
    if existing and existing.id != ident:
        raise ReglaError("El código del producto ya está registrado.")
    for key, value in data.items():
        setattr(obj, key, value)
    db.add(obj)
    try:
        db.flush()
    except IntegrityError as exc:
        raise ReglaError("El código del producto ya está registrado.") from exc
    return obj


COLUMNAS_IMPORTACION = (
    "codigo", "nombre", "categoria", "precio", "stock", "stock_minimo", "temporada_escolar",
)


def filas_de_archivo(file):
    nombre = (file.filename or "").lower()
    if nombre.endswith(".xlsx"):
        workbook = load_workbook(file, read_only=True, data_only=True)
        try:
            yield from workbook.active.iter_rows(values_only=True)
        finally:
            workbook.close()
    elif nombre.endswith(".csv"):
        raw = file.read()
        try:
            body = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            body = raw.decode("cp1252")
        try:
            dialect = csv.Sniffer().sniff(body.splitlines()[0], delimiters=",;\t")
        except (csv.Error, IndexError):
            dialect = "excel"
        yield from csv.reader(StringIO(body), dialect=dialect)
    else:
        raise ReglaError("Selecciona un archivo CSV o Excel (.xlsx).")


def importar_productos(db, file):
    rows = iter(filas_de_archivo(file))
    try:
        header = [str(value or "").strip().lower() for value in next(rows, ())]
        if not set(COLUMNAS_IMPORTACION[:5]) <= set(header) or len(set(header)) != len(header):
            raise ReglaError("El archivo debe usar las columnas de la plantilla.")
        errores, guardados = [], 0
        for numero, row in enumerate(rows, 2):
            if numero > 5001:
                raise ReglaError("La plantilla admite hasta 5,000 productos por carga.")
            if all(value is None or value == "" for value in row):
                continue
            values = dict(zip(header, row))
            categoria = str(values.get("categoria") or "").strip().casefold()
            values["categoria"] = {"libro": "Libros", "libros": "Libros", "util": "Útiles",
                                  "útil": "Útiles", "útiles": "Útiles", "utiles": "Útiles"}.get(categoria)
            if values.get("stock_minimo") in (None, ""):
                values["stock_minimo"] = 5
            try:
                with db.begin_nested():
                    guardar_producto(db, values)
                guardados += 1
            except ReglaError as exc:
                errores.append((numero, str(exc)))
        return guardados, errores
    except ReglaError:
        raise
    except (ValueError, OSError, csv.Error, KeyError, SyntaxError, BadZipFile, InvalidFileException) as exc:
        raise ReglaError("No se pudo leer la plantilla.") from exc
    finally:
        rows.close()


def ajustar_stock(db, producto_id, cantidad, motivo, usuario_id):
    ident = entero(producto_id, "producto", minimo=1)
    cantidad = entero(cantidad, "cantidad nueva")
    motivo = texto(motivo, "el motivo", 100)
    producto = Productos(db).bloquear([ident]).get(ident)
    if producto is None:
        raise ReglaError("No se encontró el producto.")
    if producto.stock == cantidad:
        raise ReglaError("La cantidad nueva debe ser distinta del stock actual.")
    db.add(MovimientoStock(
        producto_id=ident, usuario_id=usuario_id, fecha=ahora(), cantidad_anterior=producto.stock,
        cantidad_nueva=cantidad, motivo=motivo,
    ))
    producto.stock = cantidad
    return producto


def registrar_venta(db, lineas, cliente_id, usuario_id):
    if not isinstance(lineas, list) or not 1 <= len(lineas) <= 100:
        raise ReglaError("Agrega entre 1 y 100 productos antes de confirmar.")
    cantidades = defaultdict(int)
    for item in lineas:
        if not isinstance(item, dict):
            raise ReglaError("Hay un producto inválido en la venta.")
        ident = entero(item.get("id"), "producto", minimo=1)
        cantidades[ident] += entero(item.get("cantidad"), "cantidad", minimo=1)
        if cantidades[ident] > MAX_INT:
            raise ReglaError("La cantidad supera el máximo permitido.")
    cliente = None
    if cliente_id not in ("", None):
        cliente = Clientes(db).obtener(entero(cliente_id, "cliente", minimo=1))
        if cliente is None:
            raise ReglaError("No se encontró el cliente seleccionado.")
    productos = Productos(db).bloquear(list(cantidades))
    venta = Venta(usuario_id=usuario_id, cliente=cliente, fecha=ahora(), total=Decimal(0))
    alertas = []
    for ident, cantidad in cantidades.items():
        producto = productos.get(ident)
        if producto is None:
            raise ReglaError("Uno de los productos no se encontró.")
        if cantidad > producto.stock:
            raise ReglaError(f"Stock insuficiente para {producto.nombre}. Disponible: {producto.stock}.")
        subtotal = producto.precio * cantidad
        venta.total += subtotal
        if venta.total > MAX_IMPORTE:
            raise ReglaError("El total de la venta supera el importe permitido.")
        venta.detalles.append(DetalleVenta(
            producto=producto, cantidad=cantidad, precio_unitario=producto.precio, subtotal=subtotal,
        ))
        producto.stock -= cantidad
        if producto.stock <= producto.stock_minimo:
            alertas.append(producto.nombre)
    db.add(venta)
    db.flush()
    return venta, alertas


def guardar_cliente(db, form):
    nombre = texto(form.get("nombre"), "el nombre", 100)
    tipo = opcion(form.get("tipo"), TIPOS_CLIENTE, "un tipo de cliente")
    telefono = texto(form.get("telefono"), "el teléfono", 20, requerido=False) or None
    if telefono:
        number = re.sub(r"[\s().-]", "", telefono)
        if not re.fullmatch(r"\+?[0-9]{7,15}", number):
            raise ReglaError("Ingresa un número de teléfono válido.")
        telefono = number[3:] if number.startswith("+51") and len(number) == 12 else number
    existing = Clientes(db).duplicado(nombre, telefono)
    if existing:
        return existing, False
    obj = Cliente(nombre=nombre, tipo=tipo, telefono=telefono)
    db.add(obj)
    db.flush()
    return obj, True


def whatsapp(telefono, mensaje=""):
    clean = re.sub(r"\D", "", telefono or "")
    if len(clean) == 9:
        clean = "51" + clean
    if not 8 <= len(clean) <= 15:
        return ""
    return "https://wa.me/" + clean + ("?text=" + quote(mensaje) if mensaje else "")


def guardar_proveedor(db, form, producto_ids, ident=None):
    repo = Proveedores(db)
    nombre = texto(form.get("nombre"), "el nombre", 100)
    contacto = texto(form.get("contacto"), "el contacto", 100, requerido=False) or None
    if repo.duplicado(nombre, ident):
        raise ReglaError("Ya hay un proveedor registrado con ese nombre.")
    obj = repo.obtener(ident) if ident is not None else Proveedor()
    if obj is None:
        raise ReglaError("No se encontró el proveedor.")
    ids = {entero(value, "producto", minimo=1) for value in producto_ids}
    productos = Productos(db).opciones(ids) if ids else []
    if len(productos) != len(ids):
        raise ReglaError("Uno de los productos no se encontró.")
    obj.nombre, obj.contacto, obj.productos = nombre, contacto, productos
    db.add(obj)
    return obj


def reposicion(db):
    productos = Productos(db).bajos()
    por_producto = defaultdict(list)
    for prov in Proveedores(db).listar():
        for prod in prov.productos:
            por_producto[prod.id].append(prov)
    grupos = {}
    for prod in productos:
        for prov in por_producto[prod.id] or [None]:
            grupo = grupos.setdefault(prov.id if prov else None, (prov, []))
            grupo[1].append((prod, max(prod.stock_minimo * 4 - prod.stock, 0)))
    return productos, por_producto, grupos.values()


def reporte(db, periodo, referencia):
    desde, hasta = limites_periodo(periodo, referencia)
    repo = Ventas(db)
    dias = repo.totales_por_dia(inicio(desde), inicio(hasta))
    productos = repo.mas_vendidos(inicio(desde), inicio(hasta))
    total = sum((fila[2] for fila in dias), Decimal(0))
    numero = sum(fila[1] for fila in dias)
    promedio = (total / numero).quantize(CENTIMO, rounding=ROUND_HALF_UP) if numero else Decimal(0)
    return {
        "desde": desde, "hasta": hasta - timedelta(days=1), "dias": dias,
        "productos": productos, "total": total, "numero": numero, "promedio": promedio,
    }


def producto_publico(producto):
    estado, etiqueta = disponibilidad(producto)
    return dict(codigo=producto.codigo, nombre=producto.nombre, categoria=producto.categoria,
                precio=f"{producto.precio:.2f}", estado=estado, disponibilidad=etiqueta)


def filtros_fechas(desde, hasta):
    start = leer_fecha(desde) if desde else None
    end = leer_fecha(hasta) if hasta else None
    if start and end and end < start:
        raise ReglaError("La fecha final debe ser igual o posterior a la inicial.")
    return inicio(start) if start else None, inicio(end + timedelta(days=1)) if end else None
