import csv
from io import StringIO

from flask import Response, request

from ..negocio.reglas import CATEGORIAS

LIMITE = 24


def filtros_productos():
    q = request.args.get("q", "").strip()[:120]
    categoria = request.args.get("categoria", "")
    return q, categoria if categoria in CATEGORIAS else ""


def numero_pagina():
    return numero_positivo(request.args.get("pagina")) or 1


def numero_positivo(raw):
    if raw and len(raw) <= 10 and raw.isascii() and raw.isdigit():
        number = int(raw)
        if 0 < number <= 2_147_483_647:
            return number
    return None


def csv_descarga(nombre, filas):
    output = StringIO()
    writer = csv.writer(output)
    for fila in filas:
        writer.writerow([
            "'" + item if isinstance(item, str) and item.lstrip().startswith(("=", "+", "-", "@"))
            else item for item in fila
        ])
    return Response(
        "\ufeff" + output.getvalue(), mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
    )

