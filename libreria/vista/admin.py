from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from ..negocio import consultas, servicios
from ..negocio.reglas import PERIODOS, ReglaError, hoy, leer_fecha
from ..negocio.transacciones import escribir
from .comun import LIMITE, csv_descarga, filtros_productos, numero_pagina, numero_positivo
from .seguridad import requiere

admin = Blueprint("admin", __name__, url_prefix="/administrador")


@admin.route("/usuarios", methods=["GET", "POST"])
@admin.route("/usuarios/<int:ident>", methods=["GET", "POST"])
@requiere("Administrador")
def usuarios(ident=None):
    obj = consultas.obtener_usuario(g.db, ident) if ident is not None else None
    if ident is not None and obj is None:
        abort(404)
    error = ""
    if request.method == "POST":
        try:
            if request.form.get("accion") == "clave" and obj is not None:
                escribir(g.db, lambda: servicios.restablecer_clave(obj, request.form.get("password", "")))
                flash("Contraseña restablecida.", "success")
            else:
                escribir(g.db, lambda: servicios.guardar_usuario(g.db, request.form, ident))
                flash("Usuario guardado.", "success")
            return redirect(url_for("admin.usuarios"))
        except ReglaError as exc:
            error = str(exc)
    q = request.args.get("q", "").strip()[:80]
    return render_template("usuarios.html", usuarios=consultas.listar_usuarios(g.db, q),
                           usuario=obj, q=q, form=request.form, error=error), 400 if error else 200


@admin.route("", methods=["GET", "POST"])
@admin.route("/productos/<int:ident>", methods=["GET", "POST"])
@requiere("Administrador")
def productos(ident=None):
    obj = consultas.obtener_producto(g.db, ident) if ident is not None else None
    if ident is not None and obj is None:
        abort(404)
    error = ""
    if request.method == "POST":
        try:
            escribir(g.db, lambda: servicios.guardar_producto(g.db, request.form, ident))
            flash("Producto guardado.", "success")
            return redirect(url_for("admin.productos"))
        except ReglaError as exc:
            error = str(exc)
    q, categoria = filtros_productos()
    estado = request.args.get("estado", "")
    pagina = numero_pagina()
    lista, total = consultas.buscar_productos(g.db, q, categoria, estado, pagina=pagina)
    return render_template("inventario.html", productos=lista, total=total, producto=obj, q=q,
                           categoria=categoria, estado=estado, pagina=pagina, limite=LIMITE,
                           error=error, form=request.form), 400 if error else 200


@admin.route("/importar", methods=["GET", "POST"])
@requiere("Administrador")
def importar():
    guardados, errores, error = None, [], ""
    if request.method == "POST":
        file = request.files.get("archivo")
        if not file or not file.filename:
            error = "Selecciona una plantilla CSV o Excel."
        else:
            try:
                guardados, errores = escribir(g.db, lambda: servicios.importar_productos(g.db, file))
            except ReglaError as exc:
                error = str(exc)
    return render_template("importar.html", guardados=guardados, errores=errores,
                           error=error), 400 if error else 200


@admin.get("/plantilla.csv")
@requiere("Administrador")
def plantilla():
    return csv_descarga("plantilla_productos.csv", [servicios.COLUMNAS_IMPORTACION,
                            ("L-0107", "Libro Ciencia 4", "Libros", "54.00", 6, 5, 1)])


@admin.route("/ajuste", methods=["GET", "POST"])
@requiere("Administrador")
def ajuste():
    error = ""
    if request.method == "POST":
        form = request.form
        try:
            producto = escribir(g.db, lambda: servicios.ajustar_stock(
                g.db, form.get("producto_id"), form.get("cantidad"), form.get("motivo"), g.usuario.id,
            ))
            mensaje = "Stock actualizado."
            if producto.stock <= producto.stock_minimo:
                mensaje += f" Stock bajo: {producto.nombre}."
            flash(mensaje, "success")
            return redirect(url_for("admin.ajuste"))
        except ReglaError as exc:
            error = str(exc)
    seleccionado = numero_positivo(request.values.get("producto_id"))
    pagina = numero_pagina()
    movimientos, total = consultas.listar_movimientos(g.db, pagina)
    return render_template("ajuste.html", movimientos=movimientos, total=total, pagina=pagina, limite=LIMITE,
                           productos=consultas.opciones_productos(g.db), seleccionado=seleccionado,
                           error=error, form=request.form), 400 if error else 200


@admin.get("/alertas")
@requiere("Administrador")
def alertas():
    productos, proveedores, grupos = servicios.reposicion(g.db)
    if request.args.get("exportar") == "1":
        filas = [("Proveedor", "Contacto", "Código", "Producto", "Stock", "Cantidad sugerida")]
        filas.extend((prov.nombre if prov else "Sin proveedor", prov.contacto if prov else "",
                      prod.codigo, prod.nombre, prod.stock, cantidad)
                     for prov, items in grupos for prod, cantidad in items)
        return csv_descarga("reposicion_sugerida.csv", filas)
    return render_template("alertas.html", productos=productos, proveedores=proveedores, grupos=grupos,
                           agotados=sum(p.stock == 0 for p in productos))


@admin.route("/proveedores", methods=["GET", "POST"])
@admin.route("/proveedores/<int:ident>", methods=["GET", "POST"])
@requiere("Administrador")
def proveedores(ident=None):
    obj = consultas.obtener_proveedor(g.db, ident) if ident is not None else None
    if ident is not None and obj is None:
        abort(404)
    q = request.args.get("q", "").strip()[:100]
    error = ""
    seleccion = {item.id for item in obj.productos} if obj else set()
    if request.method == "POST":
        raw_ids = request.form.getlist("producto_id")
        seleccion = {numero_positivo(raw) for raw in raw_ids}
        try:
            escribir(g.db, lambda: servicios.guardar_proveedor(g.db, request.form, raw_ids, ident))
            flash("Proveedor guardado.", "success")
            return redirect(url_for("admin.proveedores"))
        except ReglaError as exc:
            error = str(exc)
    return render_template("proveedores.html", proveedores=consultas.listar_proveedores(g.db, q),
                           opciones=consultas.opciones_productos(g.db), proveedor=obj,
                           seleccion=seleccion, q=q, error=error, form=request.form), 400 if error else 200


@admin.get("/reportes")
@requiere("Administrador")
def reportes():
    periodo = request.args.get("periodo", "dia")
    raw = request.args.get("fecha", hoy().isoformat())
    error = ""
    try:
        data = servicios.reporte(g.db, periodo, leer_fecha(raw))
    except ReglaError as exc:
        error = str(exc)
        data = None
    if data and request.args.get("exportar") == "1":
        filas = [("Periodo", PERIODOS[periodo], data["desde"], data["hasta"]),
                 ("Fecha", "Número de ventas", "Total")]
        filas += list(data["dias"])
        filas += [(), ("Producto", "Categoría", "Unidades", "Total")]
        filas += list(data["productos"])
        return csv_descarga("reporte_ventas.csv", filas)
    grafico = [{"fecha": str(dia), "total": float(total)} for dia, _, total in data["dias"]] if data else []
    return render_template("reportes.html", data=data, periodo=periodo, fecha=raw,
                           grafico=grafico, error=error), 400 if error else 200
