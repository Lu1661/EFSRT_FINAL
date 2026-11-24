import os

from flask import Blueprint, g, redirect, render_template, url_for

from ..negocio.consultas import catalogo as consultar_catalogo
from ..negocio.servicios import whatsapp
from .comun import LIMITE, filtros_productos, numero_pagina

publico = Blueprint("publico", __name__)


@publico.get("/")
def inicio():
    return redirect(url_for("publico.catalogo"))


@publico.get("/Catalogo")
def catalogo():
    q, categoria = filtros_productos()
    telefono = os.environ.get("LIBRERIA_WHATSAPP", "")
    return render_template("catalogo.html", q=q, categoria=categoria, limite=LIMITE,
                           contacto=whatsapp(telefono, "Hola, quisiera consultar por un producto de Librería Popular."))


@publico.get("/api/catalogo/productos")
def buscar():
    q, categoria = filtros_productos()
    pagina = numero_pagina()
    return consultar_catalogo(g.db, q, categoria, pagina)
