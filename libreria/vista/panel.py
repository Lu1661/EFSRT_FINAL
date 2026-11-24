import secrets
from time import time

from flask import (
    Blueprint, abort, current_app, flash, g, redirect, render_template, request, session, url_for,
)

from ..negocio import consultas, servicios
from ..negocio.reglas import ROLES, TIPOS_CLIENTE, ReglaError
from ..negocio.transacciones import escribir
from .comun import LIMITE, filtros_productos, numero_pagina, numero_positivo
from .seguridad import requiere

panel = Blueprint("panel", __name__)


@panel.get("/personal")
def inicio():
    if g.usuario:
        page = "admin.productos" if g.usuario.rol == "Administrador" else "panel.venta"
        return redirect(url_for(page))
    return redirect(url_for("panel.login"))


@panel.route("/login", methods=["GET", "POST"])
def login():
    if g.usuario:
        return redirect(url_for("panel.inicio"))
    if request.method == "POST":
        nombre = request.form.get("usuario", "").strip()[:128]
        direccion = request.remote_addr or "local"
        intentos = current_app.extensions["intentos"]
        if not intentos.reservar(nombre, direccion):
            response = current_app.make_response((render_template(
                "login.html", error="Acceso temporalmente bloqueado. Intenta de nuevo en 15 minutos."
            ), 429))
            response.headers["Retry-After"] = "900"
            return response
        usuario = servicios.autenticar(g.db, nombre, request.form.get("password", ""))
        if usuario:
            intentos.exito(nombre, direccion)
            session.clear()
            session.permanent = True
            session.update(usuario_id=usuario.id, actividad=time(), id_login=secrets.token_urlsafe(24))
            return redirect(url_for("panel.inicio"))
        return render_template("login.html", error="Usuario o contraseña incorrectos."), 401
    return render_template("login.html")


@panel.post("/salir")
def salir():
    session.clear()
    return redirect(url_for("panel.login"))


@panel.get("/vendedor")
@requiere("Vendedor")
def venta():
    token = current_app.extensions["turnos_venta"].emitir(session["id_login"])
    return render_template("venta.html", token=token, clientes=consultas.listar_clientes(g.db))


@panel.get("/api/personal/productos")
@requiere("Vendedor")
def buscar_venta():
    q, categoria = filtros_productos()
    return consultas.catalogo(g.db, q, categoria, numero_pagina(), personal=True)


@panel.post("/vendedor")
@requiere("Vendedor")
def confirmar_venta():
    form = request.get_json(silent=True)
    if not isinstance(form, dict):
        return {"error": "Envío de venta inválido."}, 400
    turnos = current_app.extensions["turnos_venta"]
    token = form.get("token")
    try:
        anterior = turnos.reservar(token, session["id_login"])
        if anterior is not None:
            return {"destino": url_for("panel.detalle_venta", ident=anterior, resumen=1)}
        try:
            registro, alertas = escribir(g.db, lambda: servicios.registrar_venta(
                g.db, form.get("productos"), form.get("cliente"), g.usuario.id,
            ))
        except Exception:
            turnos.resolver(token, None)
            raise
        turnos.resolver(token, registro.id)
    except ReglaError as error:
        return {"error": str(error)}, 400
    if alertas:
        flash("Stock bajo: " + ", ".join(alertas[:5]) + (" y otros productos." if len(alertas) > 5 else "."),
              "warning")
    return {"destino": url_for("panel.detalle_venta", ident=registro.id, resumen=1)}, 201


@panel.get("/ventas")
@requiere(*ROLES)
def historial():
    desde, hasta = request.args.get("desde", ""), request.args.get("hasta", "")
    usuario = numero_positivo(request.args.get("usuario"))
    pagina = numero_pagina()
    try:
        rows, total = consultas.historial(g.db, pagina, desde, hasta, usuario)
    except ReglaError as error:
        flash(str(error), "danger")
        rows, total = [], 0
    return render_template("historial.html", ventas=rows, total=total, desde=desde, hasta=hasta,
                           seleccionado=usuario, usuarios=consultas.listar_usuarios(g.db), pagina=pagina, limite=LIMITE)


@panel.get("/ventas/<int:ident>")
@requiere(*ROLES)
def detalle_venta(ident):
    obj = consultas.detalle_venta(g.db, ident)
    if not obj:
        abort(404)
    return render_template("ticket.html", venta=obj, resumen=request.args.get("resumen") == "1")


@panel.route("/clientes", methods=["GET", "POST"])
@requiere(*ROLES)
def clientes():
    q = request.args.get("q", "").strip()[:100]
    tipo = request.args.get("tipo", "")
    tipo = tipo if tipo in TIPOS_CLIENTE else ""
    error = ""
    if request.method == "POST":
        try:
            cliente, nuevo = escribir(g.db, lambda: servicios.guardar_cliente(g.db, request.form))
            flash("Cliente registrado." if nuevo else "El cliente ya estaba registrado.",
                  "success" if nuevo else "warning")
            return redirect(url_for("panel.cliente", ident=cliente.id))
        except ReglaError as exc:
            error = str(exc)
    lista = consultas.listar_clientes(g.db, q, tipo)
    return render_template("clientes.html", clientes=lista, q=q, tipo=tipo, error=error,
                           form=request.form, whatsapp=servicios.whatsapp), 400 if error else 200


@panel.get("/clientes/<int:ident>")
@requiere(*ROLES)
def cliente(ident):
    obj = consultas.obtener_cliente(g.db, ident)
    if not obj:
        abort(404)
    pagina = numero_pagina()
    ventas, total = consultas.historial(g.db, pagina, cliente=ident)
    return render_template("cliente.html", cliente=obj, ventas=ventas, total=total, pagina=pagina,
                           limite=LIMITE, enlace=servicios.whatsapp(obj.telefono))
