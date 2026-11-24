from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from time import time
from urllib.parse import urlencode

from flask import Flask, flash, g, redirect, render_template, request, session, url_for
from flask_wtf.csrf import CSRFError, CSRFProtect
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.middleware.proxy_fix import ProxyFix
from .negocio.acceso import IntentosAcceso

from .config import INSTANCE, mysql_config, secret_key
from .datos.conexion import conectar, sesiones
from .negocio.reglas import CATEGORIAS, PERIODOS, ROLES, TIPOS_CLIENTE, disponibilidad
from .vista.admin import admin
from .vista.panel import panel
from .vista.publica import publico
from .vista.seguridad import TurnosVenta, cargar_usuario


def create_app(*, engine=None, testing=False, https=False, key=None, proxy=False, instance=None):
    instance = Path(instance or INSTANCE)
    app = Flask(
        __name__, template_folder="vista/templates", static_folder="vista/static",
        static_url_path="/static", instance_path=str(instance),
    )
    app.config.update(
        TESTING=testing, SECRET_KEY=key or secret_key(instance), SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax", SESSION_COOKIE_SECURE=https, SESSION_REFRESH_EACH_REQUEST=False,
        PERMANENT_SESSION_LIFETIME=timedelta(minutes=30),
        WTF_CSRF_TIME_LIMIT=1800, MAX_CONTENT_LENGTH=5 * 1024 * 1024,
        MAX_FORM_PARTS=6000,
    )
    app.extensions["engine"] = engine or conectar(mysql_config().url())
    app.extensions["db_sessions"] = sesiones(app.extensions["engine"])
    app.extensions["turnos_venta"] = TurnosVenta()
    app.extensions["intentos"] = IntentosAcceso(instance / "acceso.sqlite3", app.config["SECRET_KEY"])
    if proxy:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
        app.config["TRUSTED_HOSTS"] = ["libreriapopular.zenpag.com", "127.0.0.1", "localhost"]
    CSRFProtect(app)

    @app.before_request
    def antes():
        if request.endpoint == "static":
            return
        g.db = app.extensions["db_sessions"]()
        g.usuario = None if request.blueprint == 'publico' else cargar_usuario(session, time())

    @app.teardown_request
    def cerrar_db(_error):
        if db := g.pop("db", None):
            db.close()

    @app.after_request
    def cabeceras(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "font-src 'self'; img-src 'self' data:; connect-src 'self'; "
            "object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'"
        )
        if https:
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        if request.endpoint != "static":
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.context_processor
    def helpers():
        def pagina_url(number):
            params = request.args.to_dict()
            params["pagina"] = number
            return request.path + "?" + urlencode(params)

        return dict(
            categorias=CATEGORIAS, roles=ROLES, tipos_cliente=TIPOS_CLIENTE,
            periodos=PERIODOS, disponibilidad=disponibilidad, pagina_url=pagina_url,
        )

    @app.template_filter("soles")
    def moneda(value):
        return f"S/ {Decimal(value):,.2f}"

    @app.errorhandler(CSRFError)
    def csrf_invalido(_error):
        if request.is_json:
            return {"error": "El formulario venció. Recarga la página e intenta otra vez."}, 400
        return render_template("error.html", titulo="Formulario vencido",
                               mensaje="Recarga la pantalla e intenta otra vez."), 400

    @app.errorhandler(403)
    @app.errorhandler(404)
    @app.errorhandler(413)
    def error_http(error):
        messages = {
            403: ("Acceso restringido", "Tu usuario no tiene permiso para abrir esta opción."),
            404: ("Página no encontrada", "Verifica la dirección o vuelve al inicio."),
            413: ("Archivo demasiado grande", "La importación admite archivos de hasta 5 MB."),
        }
        titulo, mensaje = messages[error.code]
        return render_template("error.html", titulo=titulo, mensaje=mensaje), error.code

    @app.errorhandler(SQLAlchemyError)
    def error_db(_error):
        if db := g.get("db"):
            db.rollback()
        app.logger.error("MySQL no pudo completar una operación.")
        mensaje = "No se pudo completar la operación. Intenta otra vez en unos minutos."
        if request.is_json or request.path.startswith("/api/"):
            return {"error": mensaje}, 503
        return render_template("error.html", titulo="Operación no disponible", mensaje=mensaje), 503

    @app.errorhandler(500)
    def error_interno(_error):
        if request.is_json:
            return {"error": "No se pudo completar la operación."}, 500
        return render_template("error.html", titulo="Operación no disponible",
                               mensaje="Intenta de nuevo en unos minutos."), 500

    app.register_blueprint(publico)
    app.register_blueprint(panel)
    app.register_blueprint(admin)
    @app.route("/personal/<path:anterior>", methods=["GET", "POST"])
    def enlace_anterior(anterior):
        rutas = {
            "login": "/login", "ventas/nueva": "/vendedor", "ventas": "/ventas",
            "clientes": "/clientes", "salir": "/salir", "inventario": "/administrador",
            "usuarios": "/administrador/usuarios", "proveedores": "/administrador/proveedores",
            "reportes": "/administrador/reportes",
        }
        destino = rutas.get(anterior)
        if destino is None and anterior.startswith("inventario/"):
            destino = "/administrador/" + anterior.removeprefix("inventario/")
        if destino is None and anterior.startswith(("ventas/", "clientes/")):
            destino = "/" + anterior
        if destino is None and anterior.startswith(("usuarios/", "proveedores/")):
            destino = "/administrador/" + anterior
        if destino is None:
            from flask import abort
            abort(404)
        if request.query_string:
            destino += "?" + request.query_string.decode("ascii", errors="ignore")
        return redirect(destino, code=307)

    return app
