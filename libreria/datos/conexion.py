from pathlib import Path

from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

from ..config import mysql_config
from .modelos import Base


def conectar(url):
    return create_engine(
        url, pool_pre_ping=True, pool_size=4, max_overflow=4, hide_parameters=True,
        connect_args={"connect_timeout": 4, "read_timeout": 15, "write_timeout": 15},
    )


def sesiones(engine):
    return sessionmaker(engine, expire_on_commit=False)


def crear_tablas(engine):
    sql = Path(__file__).with_name("modelo_libreria_popular.sql").read_text(encoding="utf-8")
    sql = "\n".join(line for line in sql.splitlines() if not line.startswith("--"))
    with engine.begin() as connection:
        for command in sql.split(";"):
            if command.strip():
                connection.exec_driver_sql(command)
    inspector = inspect(engine)
    for name, table in Base.metadata.tables.items():
        columns = {column["name"] for column in inspector.get_columns(name)}
        key = inspector.get_pk_constraint(name)["constrained_columns"]
        if columns != set(table.columns.keys()) or key != list(table.primary_key.columns.keys()):
            raise ValueError(f"El esquema de {name} difiere del modelo documentado.")


def preparar_mysql():
    config = mysql_config()
    engine = conectar(config.url())
    try:
        with engine.connect():
            pass
    except OperationalError as exc:
        if exc.orig.args[0] != 1049:
            raise
        bootstrap = conectar(config.url(database=False))
        try:
            with bootstrap.begin() as connection:
                connection.exec_driver_sql(
                    f"CREATE DATABASE IF NOT EXISTS `{config.database}` CHARACTER SET utf8mb4"
                )
        finally:
            bootstrap.dispose()
    crear_tablas(engine)
    return engine
