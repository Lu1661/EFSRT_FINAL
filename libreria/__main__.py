import argparse
import threading

from sqlalchemy.exc import SQLAlchemyError

from . import create_app
from .config import mysql_config
from .datos.conexion import preparar_mysql, sesiones
from .datos.respaldo import respaldo_diario
from .negocio.demostracion import crear_acceso_demo


def main():
    parser = argparse.ArgumentParser(prog="python -m libreria", description="Sistema Librería Popular")
    comandos = parser.add_subparsers(dest="comando", required=True)
    preparar = comandos.add_parser("preparar", help="Verificar el esquema MySQL")
    preparar.add_argument("--demo", action="store_true", help="Crear datos ficticios y cuentas iniciales")
    comandos.add_parser("respaldo", help="Guardar el respaldo local del día")
    servidor = comandos.add_parser("servir", help="Abrir la aplicación local")
    servidor.add_argument("--host", default="127.0.0.1")
    servidor.add_argument("--puerto", type=int, default=5062)
    servidor.add_argument("--https", action="store_true", help="Usar un certificado temporal para una prueba local")
    servidor.add_argument("--certificado")
    servidor.add_argument("--llave")
    args = parser.parse_args()
    if args.comando == "servir" and bool(args.certificado) != bool(args.llave):
        parser.error("Indica tanto --certificado como --llave.")

    try:
        if args.comando == "respaldo":
            print(f"Respaldo disponible: {respaldo_diario()}")
            return
        if args.comando == "preparar":
            engine = preparar_mysql()
            print("Esquema MySQL verificado.")
            if args.demo:
                acceso = crear_acceso_demo(sesiones(engine))
                print(f"Cuentas de demostración: {acceso}" if acceso
                      else "Se conservaron los usuarios existentes.")
            engine.dispose()
            return
        config = mysql_config()
        ssl = (args.certificado, args.llave) if args.certificado else ("adhoc" if args.https else None)
        app = create_app(https=bool(ssl))
        protocol = "https" if ssl else "http"
        print(f"Catálogo: {protocol}://{args.host}:{args.puerto}/Catalogo", flush=True)
        print(f"Panel:    {protocol}://{args.host}:{args.puerto}/login", flush=True)
        stop = threading.Event()

        def respaldar():
            while not stop.is_set():
                try:
                    respaldo_diario(config)
                except (RuntimeError, TimeoutError, OSError) as exc:
                    app.logger.warning("El respaldo diario quedó pendiente: %s", type(exc).__name__)
                stop.wait(900)

        thread = threading.Thread(target=respaldar, daemon=True, name="respaldo-mysql")
        thread.start()
        try:
            app.run(host=args.host, port=args.puerto, debug=False, use_reloader=False, ssl_context=ssl)
        finally:
            stop.set()
    except (SQLAlchemyError, RuntimeError, ValueError) as exc:
        if isinstance(exc, SQLAlchemyError):
            print("MySQL rechazó la operación. Comprueba el servicio, las credenciales y los permisos.")
        else:
            print(str(exc))
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
