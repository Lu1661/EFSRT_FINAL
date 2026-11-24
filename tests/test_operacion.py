from dataclasses import replace
from datetime import datetime
from threading import Thread
from urllib.request import Request, urlopen
import re
import ssl

from sqlalchemy import insert
from werkzeug.serving import make_server

from libreria import create_app
from libreria.config import mysql_config
from libreria.datos.modelos import Venta
from libreria.datos.respaldo import respaldo_diario
from libreria.negocio import consultas, servicios
from test_mysql import login


def test_https_local_y_cookie_segura(mysql_engine, tmp_path):
    app = create_app(engine=mysql_engine, testing=True, https=True, key="prueba-https", instance=tmp_path)
    server = make_server("127.0.0.1", 0, app, threaded=True, ssl_context="adhoc")
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        origin = f"https://127.0.0.1:{server.server_port}"
        request = Request(origin + "/login")
        # The locally generated certificate is self-signed.
        with urlopen(request, context=ssl._create_unverified_context(), timeout=10) as reply:
            assert reply.status == 200
            header = reply.headers.get("Set-Cookie")
            assert "Secure" in header and "HttpOnly" in header and "SameSite=Lax" in header
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def test_respaldo_contiene_el_modelo_y_se_reutiliza_en_el_dia(app, mysql_engine, tmp_path):
    url = mysql_engine.url
    config = replace(mysql_config(), username=url.username, password=url.password, database=url.database,
                     host=url.host, port=url.port)
    file = respaldo_diario(config, tmp_path)
    assert file == respaldo_diario(config, tmp_path)
    sql = file.read_text(encoding="utf-8")
    assert len(re.findall(r"^CREATE TABLE ", sql, re.MULTILINE)) == 8
    assert "INSERT INTO `producto`" in sql


def test_historial_de_distintos_anos_y_tres_mil_ventas_por_mes(app):
    make_session = app.extensions["db_sessions"]
    with make_session.begin() as db:
        for year in (2024, 2025, 2026):
            db.execute(insert(Venta), [
                dict(usuario_id=2, total="8.00", fecha=datetime(year, 11, index % 28 + 1, 10))
                for index in range(3000)
            ])
    with make_session() as db:
        rows, total = consultas.historial(db, 1, "2024-11-01", "2026-11-30")
        assert len(rows) == 24 and total == 9000
        assert servicios.reporte(db, "mes", datetime(2025, 11, 30).date())["numero"] == 3000

    admin = app.test_client()
    login(admin, "admin")
    assert admin.get("/ventas?desde=2024-11-01&hasta=2024-11-30&pagina=2").status_code == 200
