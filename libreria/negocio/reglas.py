import re
from datetime import date, datetime, time, timedelta
from decimal import Decimal, DecimalException

from ..config import LIMA

CATEGORIAS = ("Libros", "Útiles")
ROLES = ("Administrador", "Vendedor")
TIPOS_CLIENTE = ("Minorista", "Mayorista")
PERIODOS = {"dia": "Día", "semana": "Semana", "mes": "Mes", "campana": "Campaña escolar"}
MAX_INT = 2_147_483_647
MAX_IMPORTE = Decimal("99999999.99")
CENTIMO = Decimal("0.01")


class ReglaError(ValueError):
    pass


def texto(value, nombre, maximo, *, requerido=True):
    result = str(value if value is not None else "").strip()
    if not result and requerido:
        raise ReglaError(f"Ingresa {nombre}.")
    if len(result) > maximo:
        raise ReglaError(f"{nombre.capitalize()} admite hasta {maximo} caracteres.")
    return result


def entero(value, nombre, *, minimo=0, maximo=MAX_INT):
    raw = str(value if value is not None else "").strip()
    if not re.fullmatch(r"-?[0-9]{1,10}", raw):
        raise ReglaError(f"{nombre.capitalize()} debe ser un número entero.")
    number = int(raw)
    if not minimo <= number <= maximo:
        raise ReglaError(f"{nombre.capitalize()} debe estar entre {minimo} y {maximo}.")
    return number


def importe(value):
    try:
        amount = Decimal(str(value).strip().replace(",", "."))
        if amount.is_finite() and 0 < amount <= MAX_IMPORTE and amount == amount.quantize(CENTIMO):
            return amount.quantize(CENTIMO)
    except DecimalException:
        pass
    raise ReglaError("Ingresa un precio positivo con hasta dos decimales.")


def opcion(value, allowed, nombre):
    if value not in allowed:
        raise ReglaError(f"Selecciona {nombre} válido.")
    return value


def disponibilidad(producto):
    if producto.stock <= 0:
        return "agotado", "Agotado"
    if producto.stock <= producto.stock_minimo:
        return "bajo", "Pocas unidades"
    return "normal", "Disponible"


def hoy():
    return datetime.now(LIMA).date()


def ahora():
    return datetime.now(LIMA).replace(tzinfo=None)


def leer_fecha(value):
    try:
        result = date.fromisoformat(value)
        if date(1000, 1, 1) <= result <= date(9998, 12, 31):
            return result
    except (ValueError, TypeError):
        pass
    raise ReglaError("Ingresa una fecha válida.")


def inicio(dia):
    return datetime.combine(dia, time.min)


def limites_periodo(periodo, referencia):
    opcion(periodo, PERIODOS, "un periodo")
    if periodo == "dia":
        return referencia, referencia + timedelta(days=1)
    if periodo == "semana":
        lunes = referencia - timedelta(days=referencia.weekday())
        return lunes, lunes + timedelta(days=7)
    if periodo == "mes":
        primer_dia = referencia.replace(day=1)
        siguiente = (primer_dia + timedelta(days=32)).replace(day=1)
        return primer_dia, siguiente
    year = referencia.year if referencia.month >= 12 else referencia.year - 1
    return date(max(1000, year), 12, 1), date(max(1000, year) + 1, 4, 1)
