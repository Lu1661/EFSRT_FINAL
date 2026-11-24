import hashlib
import hmac
import sqlite3
from pathlib import Path
from time import time


class IntentosAcceso:
    """Límite persistente de tres intentos por cuenta y dirección IP."""

    def __init__(self, path, secreto, *, reloj=time, ventana=900):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.secreto = secreto.encode()
        self.reloj = reloj
        self.ventana = ventana
        with self.conexion() as db:
            db.execute("CREATE TABLE IF NOT EXISTS intentos (clave TEXT PRIMARY KEY, cantidad INTEGER NOT NULL, vence REAL NOT NULL)")

    def conexion(self):
        return sqlite3.connect(self.path, timeout=5)

    def claves(self, usuario, direccion):
        valores = ("cuenta:" + usuario.strip().casefold(), "ip:" + direccion)
        return [hmac.new(self.secreto, valor.encode(), hashlib.sha256).hexdigest() for valor in valores]

    def reservar(self, usuario, direccion):
        claves = self.claves(usuario, direccion)
        ahora = self.reloj()
        with self.conexion() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("DELETE FROM intentos WHERE vence <= ?", (ahora,))
            registros = {row[0]: (row[1], row[2]) for row in db.execute(
                "SELECT clave, cantidad, vence FROM intentos WHERE clave IN (?, ?)", claves
            )}
            if any(cantidad >= 3 for cantidad, _ in registros.values()):
                return False
            for clave in claves:
                cantidad, vence = registros.get(clave, (0, ahora + self.ventana))
                cantidad += 1
                if cantidad == 3:
                    vence = ahora + self.ventana
                db.execute("INSERT INTO intentos VALUES (?, ?, ?) ON CONFLICT(clave) DO UPDATE SET cantidad=excluded.cantidad, vence=excluded.vence",
                           (clave, cantidad, vence))
        return True

    def exito(self, usuario, direccion):
        with self.conexion() as db:
            db.executemany("DELETE FROM intentos WHERE clave = ?", [(k,) for k in self.claves(usuario, direccion)])
