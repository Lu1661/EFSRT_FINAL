from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from libreria.negocio.reglas import ReglaError, disponibilidad, entero, importe, limites_periodo
from libreria.negocio.servicios import whatsapp
from libreria.vista.seguridad import TurnosVenta


@pytest.mark.parametrize("stock,clave", [(0, "agotado"), (1, "bajo"), (5, "bajo"), (6, "normal")])
def test_umbral_y_disponibilidad(stock, clave):
    assert disponibilidad(SimpleNamespace(stock=stock, stock_minimo=5))[0] == clave


def test_precio_peruano_y_decimales():
    assert importe("12,40") == Decimal("12.40")
    for value in ("NaN", "Infinity", "-1", "1.001", "999999999", ""):
        with pytest.raises(ReglaError):
            importe(value)


@pytest.mark.parametrize("value", ["-1", "1.5", "9" * 1000, None])
def test_ajuste_sin_cantidades_invalidas(value):
    with pytest.raises(ReglaError):
        entero(value, "cantidad")


def test_periodos_y_cambio_de_ano():
    assert limites_periodo("mes", date(2026, 12, 31)) == (date(2026, 12, 1), date(2027, 1, 1))
    assert limites_periodo("semana", date(2026, 11, 18)) == (date(2026, 11, 16), date(2026, 11, 23))
    assert limites_periodo("campana", date(2027, 2, 20)) == (date(2026, 12, 1), date(2027, 4, 1))


def test_enlace_whatsapp_normaliza_y_codifica_mensaje():
    assert whatsapp("(999) 999-999", "Confirma + 1") == "https://wa.me/51999999999?text=Confirma%20%2B%201"
    assert whatsapp("teléfono inválido") == ""


def test_token_de_venta_reutiliza_resumen_solo_con_misma_sesion():
    servicio = TurnosVenta()
    token = servicio.emitir("sesion-a")
    with pytest.raises(ReglaError):
        servicio.reservar(token, "sesion-b")
    assert servicio.reservar(token, "sesion-a") is None
    with pytest.raises(ReglaError):
        servicio.reservar(token, "sesion-a")
    servicio.resolver(token, 3)
    assert servicio.reservar(token, "sesion-a") == 3
