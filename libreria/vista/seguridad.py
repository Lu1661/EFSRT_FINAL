import secrets
from functools import wraps
from threading import Lock
from time import monotonic

from flask import abort, g, redirect, request, url_for

from ..negocio.consultas import obtener_usuario
from ..negocio.reglas import ROLES, ReglaError


def cargar_usuario(session, instante):
    if "usuario_id" not in session:
        return None
    if instante - session.get("actividad", 0) >= 1800:
        session.clear()
        return None
    usuario = obtener_usuario(g.db, session["usuario_id"])
    if not usuario or not usuario.activo or usuario.rol not in ROLES:
        session.clear()
        return None
    session["actividad"] = instante
    return usuario


def requiere(*roles):
    def decorator(function):
        @wraps(function)
        def wrapper(*args, **kwargs):
            if g.usuario is None:
                if request.is_json or request.path.startswith("/api/"):
                    return {"error": "La sesión venció. Vuelve a iniciar sesión."}, 401
                return redirect(url_for("panel.login"))
            if g.usuario.rol not in roles:
                if request.is_json or request.path.startswith("/api/"):
                    return {"error": "Tu usuario no tiene permiso para esta operación."}, 403
                abort(403)
            return function(*args, **kwargs)
        return wrapper
    return decorator


class TurnosVenta:
    """Un formulario por token. Un reintento devuelve el comprobante ya confirmado."""

    def __init__(self):
        self.lock = Lock()
        self.turnos = {}

    def emitir(self, sesion):
        with self.lock:
            instante = monotonic()
            self.turnos = {k: v for k, v in self.turnos.items() if v[1] > instante or v[2] == "procesando"}
            token = secrets.token_urlsafe(24)
            self.turnos[token] = (sesion, instante + 3600, None)
            return token

    def reservar(self, token, sesion):
        if not isinstance(token, str):
            raise ReglaError("Abre de nuevo el formulario de venta.")
        with self.lock:
            turno = self.turnos.get(token)
            if not turno or turno[0] != sesion or turno[1] <= monotonic():
                raise ReglaError("La venta venció. Abre de nuevo el formulario.")
            if turno[2] == "procesando":
                raise ReglaError("La venta ya se está confirmando.")
            if isinstance(turno[2], int):
                return turno[2]
            self.turnos[token] = (sesion, turno[1], "procesando")
            return None

    def resolver(self, token, resultado):
        with self.lock:
            sesion, vencimiento, _ = self.turnos[token]
            self.turnos[token] = (sesion, vencimiento, resultado)
