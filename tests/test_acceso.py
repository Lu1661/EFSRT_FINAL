from concurrent.futures import ThreadPoolExecutor

from libreria.negocio.acceso import IntentosAcceso
from test_mysql import CLAVE, login, token_csrf


def test_tres_intentos_persisten_y_expiran(tmp_path):
    clock = [1000.0]
    path = tmp_path / "intentos.sqlite3"
    servicio = IntentosAcceso(path, "llave-de-prueba", reloj=lambda: clock[0])
    for _ in range(3):
        assert servicio.reservar("cuenta", "192.0.2.1")
    assert not servicio.reservar("cuenta", "192.0.2.2")
    assert not servicio.reservar("otra-cuenta", "192.0.2.1")
    reiniciado = IntentosAcceso(path, "llave-de-prueba", reloj=lambda: clock[0])
    assert not reiniciado.reservar("cuenta", "192.0.2.1")
    clock[0] += 901
    assert reiniciado.reservar("cuenta", "192.0.2.1")
    reiniciado.exito("cuenta", "192.0.2.1")
    assert reiniciado.reservar("cuenta", "192.0.2.1")


def test_limite_concurrente_es_atomico(tmp_path):
    servicio = IntentosAcceso(tmp_path / "limite.db", "llave")
    with ThreadPoolExecutor(8) as pool:
        resultados = list(pool.map(lambda _: servicio.reservar("usuario", "192.0.2.1"), range(8)))
    assert resultados.count(True) == 3


def test_login_bloquea_tras_tres_fallos_y_no_filtra_detalles(app):
    client = app.test_client()
    for _ in range(3):
        assert login(client, "vendedor", "erronea").status_code == 401
    response = login(client, "vendedor", CLAVE)
    assert response.status_code == 429
    assert response.headers["Retry-After"] == "900"
    body = response.get_data(as_text=True)
    assert "15 minutos" in body
    assert "mysql" not in body.casefold() and "Traceback" not in body
    assert "default-src 'self'" in response.headers["Content-Security-Policy"]


def test_rutas_por_rol_y_aliases_anteriores(app):
    visitor = app.test_client()
    assert visitor.get("/").location == "/Catalogo"
    assert visitor.get("/personal/login").location == "/login"
    assert visitor.get("/Catalogo").status_code == 200
    assert login(visitor, "admin").request.path == "/administrador"
    assert visitor.get("/vendedor").status_code == 403
    seller = app.test_client()
    assert login(seller, "vendedor").request.path == "/vendedor"
    assert seller.get("/administrador").status_code == 403
