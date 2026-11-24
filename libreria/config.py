import os
import re
import secrets
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import URL

ROOT = Path(__file__).resolve().parent.parent
INSTANCE = Path(os.environ.get("LIBRERIA_INSTANCE", ROOT / "instance"))
LIMA = ZoneInfo("America/Lima")


@dataclass(frozen=True)
class MySQLConfig:
    database: str
    username: str
    password: str
    host: str
    port: int

    def url(self, *, database=True):
        return URL.create(
            "mysql+pymysql", username=self.username, password=self.password,
            host=self.host, port=self.port, database=self.database if database else None,
            query={"charset": "utf8mb4"},
        )


def mysql_config():
    source = Path(os.environ.get(
        "LIBRERIA_CREDENCIALES", ROOT / "credenciales" / "credenciales_mysql.txt"
    ))
    keys = {
        "base de datos": "database", "database": "database", "usuario": "username",
        "user": "username", "password": "password", "contraseña": "password",
        "host": "host", "servidor": "host", "puerto": "port", "port": "port",
    }
    values = {}
    if source.is_file():
        for line in source.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            key, sep, value = line.partition(":")
            if not sep:
                key, sep, value = line.partition("=")
            known = keys.get(key.strip().casefold())
            if sep and known:
                values[known] = value.strip()
            elif re.fullmatch(r"[a-zA-Z0-9.\-]+(?::[0-9]{1,5})?", line):
                host, _, port = line.partition(":")
                values["host"] = host
                if port:
                    values["port"] = port
    database = os.environ.get("LIBRERIA_DB_NAME", values.get("database", "libreria_popular"))
    if not re.fullmatch(r"[A-Za-z0-9_]{1,64}", database):
        raise ValueError("El nombre de la base MySQL debe contener letras, números o guiones bajos.")
    username = os.environ.get("LIBRERIA_DB_USER", values.get("username"))
    password = os.environ.get("LIBRERIA_DB_PASSWORD", values.get("password"))
    if not username or password is None:
        raise ValueError("Configura las credenciales MySQL en el archivo local o en el entorno.")
    return MySQLConfig(
        database, username, password,
        os.environ.get("LIBRERIA_DB_HOST", values.get("host", "127.0.0.1")),
        int(os.environ.get("LIBRERIA_DB_PORT", values.get("port", "3306"))),
    )


def secret_key(instance=INSTANCE):
    if key := os.environ.get("LIBRERIA_SECRET_KEY"):
        return key
    instance.mkdir(parents=True, exist_ok=True)
    path = instance / "session.key"
    try:
        with path.open("x", encoding="ascii") as handle:
            handle.write(secrets.token_hex(32))
    except FileExistsError:
        pass
    return path.read_text(encoding="ascii").strip()
