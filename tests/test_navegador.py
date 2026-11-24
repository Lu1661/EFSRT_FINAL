import os
from pathlib import Path
from threading import Thread
from time import perf_counter

from playwright.sync_api import expect, sync_playwright
from werkzeug.serving import make_server

from conftest import CLAVE


def entrar(page, origin, usuario):
    page.goto(origin + "/login")
    page.get_by_label("Usuario", exact=True).fill(usuario)
    page.get_by_label("Contraseña", exact=True).fill(CLAVE)
    page.get_by_role("button", name="Ingresar").click()


def cabe_en_pantalla(page):
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")


def captura(page, nombre):
    if carpeta := os.environ.get("LIBRERIA_QA_CAPTURAS"):
        Path(carpeta).mkdir(exist_ok=True, parents=True)
        page.screenshot(path=Path(carpeta) / f"{nombre}.png")


def test_caja_catalogo_y_administracion_en_escritorio_y_celular(app):
    server = make_server("127.0.0.1", 0, app, threaded=True)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f"http://127.0.0.1:{server.server_port}"
    try:
        with sync_playwright() as tool:
            browser = tool.chromium.launch(channel=os.environ.get("LIBRERIA_QA_NAVEGADOR", "chrome"))
            desktop = browser.new_context(viewport={"width": 1366, "height": 850})
            mobile = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
            adminctx = browser.new_context(viewport={"width": 1366, "height": 850})
            catalogo, caja, admin = mobile.new_page(), desktop.new_page(), adminctx.new_page()
            errors = []
            for page in (catalogo, caja, admin):
                page.on("pageerror", lambda e: errors.append(str(e)))
            catalogo.goto(origin)
            expect(catalogo.get_by_role("heading", name="Matemática del colegio")).to_be_visible()
            expect(catalogo.get_by_text("Disponible", exact=True)).to_be_visible()
            cabe_en_pantalla(catalogo)
            captura(catalogo, "catalogo-movil")
            entrar(caja, origin, "vendedor")
            inicio = perf_counter()
            expect(caja.get_by_role("heading", name="Registrar venta")).to_be_visible()
            caja.get_by_label("Producto", exact=True).fill("L-TEST")
            caja.get_by_role("button", name="Matemática del colegio", exact=False).click()
            caja.get_by_label("Cantidad", exact=True).fill("6")
            caja.get_by_role("button", name="Agregar", exact=True).click()
            expect(caja.get_by_text("S/ 74.70", exact=True).last).to_be_visible()
            captura(caja, "venta-escritorio")
            caja.get_by_role("button", name="Confirmar venta", exact=True).click()
            caja.locator(".swal2-confirm").click()
            expect(caja.get_by_role("heading", name="Resumen de venta")).to_be_visible()
            print(f"Venta completa en Chrome (recorrido automatizado): {perf_counter() - inicio:.2f} s")
            expect(caja.get_by_role("button", name="Imprimir resumen")).to_be_visible()
            caja.emulate_media(media="print")
            expect(caja.locator(".sidebar")).to_be_hidden()
            expect(caja.locator(".ticket")).to_be_visible()
            caja.emulate_media(media="screen")

            card = catalogo.locator("article").filter(has_text="Matemática del colegio")
            expect(card.get_by_text("Agotado", exact=True)).to_be_visible(timeout=10000)
            expect(card).not_to_contain_text("Stock 0")
            entrar(admin, origin, "admin")
            expect(admin.get_by_role("heading", name="Inventario de productos")).to_be_visible()
            captura(admin, "inventario-escritorio")
            admin.get_by_role("link", name="Alertas y reposición").click()
            expect(admin.get_by_text("Matemática del colegio").first).to_be_visible()
            admin.get_by_role("link", name="Reportes", exact=True).click()
            expect(admin.get_by_role("heading", name="Reportes de ventas")).to_be_visible()
            admin.wait_for_function("!!window.Chart?.getChart(document.querySelector('canvas'))")
            captura(admin, "reportes-escritorio")
            admin.set_viewport_size({"width": 390, "height": 844})
            for path in ("inventario", "inventario/ajuste", "inventario/alertas", "usuarios",
                         "proveedores", "reportes", "ventas", "clientes"):
                assert admin.goto(origin + ("/administrador" if path == "inventario" else "/administrador/" + path.removeprefix("inventario/") if path in ("inventario/ajuste", "inventario/alertas", "usuarios", "proveedores", "reportes") else "/" + path)).ok
                cabe_en_pantalla(admin)
            admin.get_by_role("button", name="Menú del personal").click()
            expect(admin.get_by_role("link", name="Proveedores")).to_be_visible()
            admin.keyboard.press("Escape")
            expect(admin.get_by_role("link", name="Proveedores")).to_be_hidden()
            admin.goto(origin + "/administrador")
            captura(admin, "inventario-movil")
            caja.set_viewport_size({"width": 390, "height": 844})
            caja.goto(origin + "/vendedor")
            cabe_en_pantalla(caja)
            expect(caja.get_by_role("navigation", name="Accesos del personal")).to_be_visible()
            expect(caja.get_by_role("button", name="Confirmar venta", exact=True)).to_be_in_viewport()
            captura(caja, "venta-movil")
            assert not errors, errors
            browser.close()
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()
