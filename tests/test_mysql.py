from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from io import BytesIO
import re
from threading import Barrier
from time import perf_counter, time

from openpyxl import Workbook
from sqlalchemy import func, inspect, select
from werkzeug.security import check_password_hash

from libreria.datos.modelos import Base, Cliente, MovimientoStock, Producto, Usuario, Venta
from libreria.negocio.reglas import ReglaError, hoy
from libreria.negocio.servicios import registrar_venta
from conftest import CLAVE


def campo(texto, name):
    matches = re.search(name + r'="([^"]+)"', texto)
    assert matches, name
    return matches[1]


def token_csrf(client, path):
    html = client.get(path).get_data(as_text=True)
    return re.search(r'name="csrf_token" value="([^"]+)"', html)[1]


def login(client, usuario, password=CLAVE):
    url = "/login"
    return client.post(url, data={"csrf_token": token_csrf(client, url),
                                  "usuario": usuario, "password": password}, follow_redirects=True)


def post(client, path, **data):
    return client.post(path, data={"csrf_token": token_csrf(client, path), **data}, follow_redirects=True)


def venta(client, productos, cliente="", llave=None):
    if llave is None:
        texto = client.get("/vendedor").get_data(as_text=True)
        llave = campo(texto, "data-token"), re.search(r'name="csrf-token" content="([^"]+)"', texto)[1]
    turno, csrf = llave
    return client.post("/vendedor", json=dict(token=turno, productos=productos, cliente=cliente),
                       headers={"X-CSRFToken": csrf}), llave


def test_modelo_fisico_mysql(app, mysql_engine):
    inspector = inspect(mysql_engine)
    assert set(inspector.get_table_names()) == set(Base.metadata.tables)
    assert inspector.get_pk_constraint("proveedor_producto")["constrained_columns"] == ["proveedor_id", "producto_id"]
    columnas = {c["name"]: c for c in inspector.get_columns("venta")}
    assert columnas["cliente_id"]["nullable"]
    assert (columnas["total"]["type"].precision, columnas["total"]["type"].scale) == (10, 2)
    fks = inspector.get_foreign_keys("detalle_venta")
    assert any(k["referred_table"] == "venta" and k["options"]["ondelete"] == "CASCADE" for k in fks)


def test_login_y_roles_csrf_cierre_y_expiracion(app):
    client = app.test_client()
    assert client.get("/administrador").status_code == 302
    assert client.post("/login", data={"usuario": "vendedor", "password": CLAVE}).status_code == 400
    assert login(client, "vendedor", "clave-incorrecta").status_code == 401
    resp = login(client, "vendedor")
    assert resp.request.path == "/vendedor"
    assert client.get("/administrador").status_code == 403
    assert client.get("/administrador/reportes").status_code == 403
    actividad = time() - 120
    with client.session_transaction() as sess:
        sess["actividad"] = actividad
    assert client.get("/api/catalogo/productos").status_code == 200
    with client.session_transaction() as sess:
        assert sess["actividad"] == actividad
        sess["actividad"] = time() - 1801
    assert client.get("/api/catalogo/productos").status_code == 200
    assert client.get("/api/personal/productos").status_code == 401
    assert login(client, "admin").request.path == "/administrador"
    assert client.get("/vendedor").status_code == 403
    csrf = token_csrf(client, "/administrador")
    assert client.post("/salir", data={"csrf_token": csrf}).status_code == 302
    assert client.get("/administrador").status_code == 302


def test_gestion_y_restablecimiento_de_usuarios(app):
    admin, usuario = app.test_client(), app.test_client()
    login(admin, "admin")
    resp = post(admin, "/administrador/usuarios", usuario="caja", nombre="Caja 2", password=CLAVE,
                rol="Vendedor", activo="1", accion="guardar")
    assert resp.status_code == 200 and b"Caja 2" in resp.data
    assert post(admin, "/administrador/usuarios", usuario="caja", nombre="Duplicado", password=CLAVE,
                rol="Vendedor", activo="1", accion="guardar").status_code == 400
    with app.extensions["db_sessions"]() as db:
        obj = db.scalar(select(Usuario).where(Usuario.usuario == "caja"))
        assert check_password_hash(obj.password_hash, CLAVE) and obj.password_hash != CLAVE
        ident = obj.id
    assert post(admin, f"/administrador/usuarios/{ident}", accion="clave",
                password="NuevaClave!456").status_code == 200
    assert login(usuario, "caja").status_code == 401
    assert login(usuario, "caja", "NuevaClave!456").status_code == 200
    assert post(admin, f"/administrador/usuarios/{ident}", usuario="caja", nombre="Caja 3",
                rol="Vendedor", accion="guardar").status_code == 200
    assert usuario.get("/api/personal/productos").status_code == 401


def test_producto_y_ajuste_con_auditoria(app):
    admin = app.test_client()
    login(admin, "admin")
    path = "/administrador"
    assert post(admin, path, codigo="C101", nombre="Cuento", categoria="Libros",
                precio="6.10", stock="5", stock_minimo="5", temporada_escolar="1").status_code == 200
    assert post(admin, path, codigo="C101", nombre="Duplicado", categoria="Libros",
                precio="9.10", stock="5", stock_minimo="5").status_code == 400
    path = "/administrador/productos/1"
    assert post(admin, path, codigo="L-TEST", nombre="Matemática revisada",
                categoria="Libros", precio="13.00", stock="100", stock_minimo="5").status_code == 200
    path = "/administrador/ajuste"
    assert post(admin, path, producto_id="1", cantidad="-1", motivo="Conteo físico").status_code == 400
    assert post(admin, path, producto_id="1", cantidad="5", motivo="Conteo físico").status_code == 200
    with app.extensions["db_sessions"]() as db:
        assert db.get(Producto, 1).stock == 5
        mov = db.scalar(select(MovimientoStock))
        assert (mov.producto_id, mov.usuario_id, mov.cantidad_anterior, mov.cantidad_nueva) == (1, 1, 6, 5)


def test_importar_csv_y_excel_con_filas_invalidas(app):
    client = app.test_client()
    login(client, "admin")
    url = "/administrador/importar"
    source = "codigo;nombre;categoria;precio;stock\nCSV1;Cuaderno CSV;Útiles;3,50;90\nCSV2;Fila inválida;Libros;-1;5\n"
    data = post(client, url, archivo=(BytesIO(source.encode()), "inventario.csv"))
    assert data.status_code == 200 and b"1 productos registrados" in data.data and b"Fila 3." in data.data
    book = Workbook()
    book.active.append(["codigo", "nombre", "categoria", "precio", "stock"])
    book.active.append(["XL1", "Libro Excel", "Libros", 2.1, 12])
    file = BytesIO()
    book.save(file)
    file.seek(0)
    assert post(client, url, archivo=(file, "inventario.xlsx")).status_code == 200
    assert post(client, url, archivo=(BytesIO(b"archivo invalido"), "inventario.xlsx")).status_code == 400
    with app.extensions["db_sessions"]() as db:
        assert set(db.scalars(select(Producto.codigo))) == {"L-TEST", "U-TEST", "CSV1", "XL1"}


def test_venta_con_cliente_catalogo_historial_reporte_y_reintento(app, monkeypatch):
    monkeypatch.setenv("LIBRERIA_WHATSAPP", "999999999")
    visitante, caja, admin = (app.test_client() for _ in range(3))
    assert b"wa.me/51999999999" in visitante.get("/Catalogo").data
    url = "/api/catalogo/productos?q=L-TEST"
    inicial = visitante.get(url).json["productos"][0]
    assert inicial["disponibilidad"] == "Disponible"
    assert set(inicial) == {"nombre", "codigo", "precio", "categoria", "estado", "disponibilidad"}
    assert visitante.get("/api/catalogo/productos?categoria=Útiles").json["total"] == 1
    assert visitante.get("/api/catalogo/productos?q=sincoincidencia").json["total"] == 0
    login(caja, "vendedor")
    assert caja.get("/api/personal/productos?q=L-TEST").json["productos"][0]["stock"] == 6
    assert post(caja, "/clientes", nombre="Mayorista Prueba", telefono="999999999",
                tipo="Mayorista").status_code == 200
    post(caja, "/clientes", nombre="Mayorista Prueba", telefono="+51999999999", tipo="Mayorista")
    with app.extensions["db_sessions"]() as db:
        cliente = db.scalar(select(Cliente))
        assert db.scalar(select(func.count(Cliente.id))) == 1
        ident = cliente.id
    lineas = [{"id": 1, "cantidad": 6}]
    respuesta, llave = venta(caja, lineas, str(ident))
    assert respuesta.status_code == 201, respuesta.json
    repetida, _ = venta(caja, lineas, str(ident), llave=llave)
    assert repetida.status_code == 200 and repetida.json == respuesta.json
    assert visitante.get(url).json["productos"][0]["disponibilidad"] == "Agotado"
    ticket = caja.get(respuesta.json["destino"])
    assert b"S/ 74.70" in ticket.data and b"Imprimir resumen" in ticket.data
    assert b"Mayorista Prueba" in caja.get("/ventas").data
    assert b"wa.me/51999999999" in caja.get(f"/clientes/{ident}").data
    login(admin, "admin")
    assert b"Agotado" in admin.get("/administrador/alertas").data
    report = admin.get(f"/administrador/reportes?periodo=mes&fecha={hoy().isoformat()}")
    assert report.status_code == 200 and b"S/ 74.70" in report.data
    assert b"74.70" in admin.get("/administrador/reportes?exportar=1").data
    with app.extensions["db_sessions"]() as db:
        assert db.scalar(select(func.count(Venta.id))) == 1
        obj = db.scalar(select(Venta))
        assert obj.total == Decimal("74.70") and obj.cliente_id == ident
        assert obj.detalles[0].precio_unitario == Decimal("12.45")


def test_reposicion_y_relacion_proveedor_producto(app):
    admin = app.test_client()
    login(admin, "admin")
    path = "/administrador/proveedores"
    assert post(admin, path, nombre="Proveedor QA", contacto="Contacto QA", producto_id="2").status_code == 200
    assert post(admin, path, nombre="Proveedor QA", contacto="Repetido", producto_id="2").status_code == 400
    data = admin.get("/administrador/alertas?exportar=1").get_data(as_text=True)
    assert "Proveedor QA,Contacto QA,U-TEST,Lápiz escolar,1,19" in data


def test_stock_insuficiente_revierte_todas_las_lineas(app):
    caja = app.test_client()
    login(caja, "vendedor")
    resp, _ = venta(caja, [{"id": 1, "cantidad": 2}, {"id": 2, "cantidad": 2}])
    assert resp.status_code == 400 and "Stock insuficiente" in resp.json["error"]
    with app.extensions["db_sessions"]() as db:
        assert db.get(Producto, 1).stock == 6
        assert db.get(Producto, 2).stock == 1
        assert db.scalar(select(func.count(Venta.id))) == 0


def test_dos_vendedores_no_venden_la_misma_ultima_unidad(app):
    barrier = Barrier(2)
    make_session = app.extensions["db_sessions"]

    def confirmar():
        barrier.wait(timeout=5)
        try:
            with make_session.begin() as db:
                registrar_venta(db, [{"id": 2, "cantidad": 1}], None, 2)
                return "venta"
        except ReglaError:
            return "rechazada"

    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(lambda _: confirmar(), range(2))) == ["rechazada", "venta"]
    with make_session() as db:
        assert db.get(Producto, 2).stock == 0
        assert db.scalar(select(func.count(Venta.id))) == 1
        assert db.scalar(select(Venta)).cliente_id is None


def test_rendimiento_y_capacidad_con_catalogo_de_5000_y_cuatro_sesiones(app):
    make_session = app.extensions["db_sessions"]
    with make_session.begin() as db:
        db.add_all(Producto(codigo=f"PERF{i:05}", nombre=f"Artículo de prueba {i}", categoria="Libros",
                            precio="3.10", stock=25, stock_minimo=5) for i in range(4998))
    with make_session.begin() as db:
        original = db.get(Usuario, 2)
        db.add_all(Usuario(nombre=f"Caja {i}", usuario=f"caja{i}", rol="Vendedor",
                           activo=True, password_hash=original.password_hash) for i in range(1,4))
    barrier = Barrier(5)

    def ejecutar(index):
        client = app.test_client()
        client.environ_base["REMOTE_ADDR"] = f"192.0.2.{index + 1}"
        if index < 4:
            assert login(client, "vendedor" if index == 0 else f"caja{index}").status_code == 200
            url = "/api/personal/productos?categoria=Libros"
        else:
            url = "/api/catalogo/productos?categoria=Libros"
        barrier.wait(timeout=10)
        tiempos = []
        for intento in range(5):
            start = perf_counter()
            response = client.get(url)
            tiempos.append(perf_counter() - start)
            assert response.status_code == 200 and response.json["total"] == 4999
            assert len(response.json["productos"]) == 24
        return tiempos

    with ThreadPoolExecutor(5) as pool:
        tiempos = sorted(t for consultas in pool.map(ejecutar, range(5)) for t in consultas)
    print(f"5.000 productos / 25 consultas / 4 sesiones de personal + 1 pública: máxima {tiempos[-1] * 1000:.1f} ms")
    assert tiempos[-1] < 3
