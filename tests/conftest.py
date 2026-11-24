import os
import secrets
from dataclasses import replace

import pytest
from sqlalchemy import delete
from werkzeug.security import generate_password_hash

from libreria import create_app
from libreria.config import mysql_config
from libreria.datos.conexion import conectar, crear_tablas, sesiones
from libreria.datos.modelos import Base, Producto, Usuario


@pytest.fixture(scope="session")
def mysql_engine():
    raw_port = os.environ.get("LIBRERIA_QA_PORT")
    if not raw_port:
        pytest.skip("Configura LIBRERIA_QA_PORT para ejecutar contra una instancia MySQL de pruebas.")
    config = replace(mysql_config(), host="127.0.0.1", port=int(raw_port), username="root",
                     password=os.environ.get("LIBRERIA_QA_PASSWORD", ""))
    assert config.port != mysql_config().port, "La instancia de pruebas debe estar en otro puerto."
    name = "libreria_test_" + secrets.token_hex(6)
    host = conectar(config.url(database=False))
    engine = conectar(replace(config, database=name).url())
    with host.begin() as cn:
        cn.exec_driver_sql(f"CREATE DATABASE `{name}` CHARACTER SET utf8mb4")
    try:
        crear_tablas(engine)
        yield engine
    finally:
        engine.dispose()
        with host.begin() as cn:
            cn.exec_driver_sql(f"DROP DATABASE `{name}`")
        host.dispose()


CLAVE = "ClavePruebas!123"
HASH = generate_password_hash(CLAVE)


@pytest.fixture
def app(mysql_engine, tmp_path):
    app = create_app(engine=mysql_engine, testing=True, key="llave-de-pruebas-no-usar-en-la-app", instance=tmp_path)
    with sesiones(mysql_engine).begin() as db:
        for table in reversed(Base.metadata.sorted_tables):
            db.execute(delete(table))
        db.add_all([
            Usuario(id=1, nombre="Admin de prueba", usuario="admin", rol="Administrador", activo=True, password_hash=HASH),
            Usuario(id=2, nombre="Vendedor de prueba", usuario="vendedor", rol="Vendedor", activo=True, password_hash=HASH),
            Producto(id=1, codigo="L-TEST", nombre="Matemática del colegio", categoria="Libros",
                     precio="12.45", stock=6, stock_minimo=5, temporada_escolar=True),
            Producto(id=2, codigo="U-TEST", nombre="Lápiz escolar", categoria="Útiles",
                     precio="2.70", stock=1, stock_minimo=5),
        ])
    return app
