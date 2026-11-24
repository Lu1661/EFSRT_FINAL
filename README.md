# Librería Popular

Aplicación para gestionar el inventario y las ventas de mostrador, con un catálogo público para consultar productos. Utiliza Flask, SQLAlchemy y MySQL y organiza el código en las capas de vista, negocio y datos.

## Ver la aplicación

- [Catálogo público](https://libreriapopular.zenpag.com/Catalogo)
- [Ingreso del personal](https://libreriapopular.zenpag.com/login)

El Administrador accede al inventario y la gestión de la tienda. El Vendedor registra las ventas, relaciona clientes y consulta el historial. Las cuentas se entregan por separado.

## Ejecución local en Windows

Con Python y MySQL disponibles, configura tus propias credenciales en un archivo local excluido de Git, credenciales/credenciales_mysql.txt, o utiliza las variables LIBRERIA_DB_HOST, LIBRERIA_DB_PORT, LIBRERIA_DB_NAME, LIBRERIA_DB_USER y LIBRERIA_DB_PASSWORD.

Desde PowerShell, dentro de la carpeta del proyecto, ejecuta:

```powershell
.\iniciar.ps1
```

El script prepara el entorno y verifica el esquema. Si todavía no hay usuarios, crea cuentas de demostración con contraseñas aleatorias y las guarda en instance/acceso_demo.txt. Si el inventario está vacío, carga productos de ejemplo.

- Catálogo local en http://127.0.0.1:5060/Catalogo
- Ingreso local en http://127.0.0.1:5060/login
- Administrador en /administrador y Vendedor en /vendedor tras iniciar sesión.

También se puede iniciar desde el entorno instalado:

```powershell
.\.venv\Scripts\python.exe -m libreria servir
```

El puerto local se puede elegir con -Puerto en el script o --puerto en el comando de Python. La variable opcional LIBRERIA_WHATSAPP permite configurar el contacto público de la tienda.

## Funciones principales

- Gestión de productos e importación de un catálogo desde Excel o CSV.
- Ajustes de stock con registro de usuario, fecha y motivo.
- Ventas con descuento de stock dentro de una transacción y resumen imprimible.
- Historial de ventas, clientes, proveedores y reposición sugerida.
- Reportes por periodo y productos más vendidos.
- Catálogo público con precio y disponibilidad.
- Permisos por rol, protección CSRF, sesión con vencimiento y límite de tres intentos de acceso.

El catálogo consulta la disponibilidad cada cuatro segundos cuando la página está visible. El carrito de solicitudes queda como mejora posterior. La facturación electrónica y la pasarela de pagos están fuera del alcance acordado.

## Organización del código

- libreria/vista/ contiene las rutas, plantillas y recursos de la interfaz.
- libreria/negocio/ contiene las validaciones y las reglas de ventas, inventario y reportes.
- libreria/datos/ contiene los modelos, los repositorios, el SQL del esquema y el respaldo.
- tests/ contiene las pruebas unitarias, de integración y de navegador.
- TRAZABILIDAD.md relaciona requisitos, casos de uso, pantallas, datos y pruebas.
- requirements.txt define las dependencias de la aplicación.
- requirements-dev.txt incorpora las herramientas de pruebas.
- requirements-vps.txt y wsgi.py permiten ejecutar la aplicación con un servidor WSGI.

## Pruebas

Instala requirements-dev.txt dentro del entorno y ejecuta las pruebas unitarias:

```powershell
python -m pytest -q tests/test_reglas.py
```

Las pruebas de integración requieren una instancia independiente de MySQL. Configura su puerto en LIBRERIA_QA_PORT y, cuando corresponda, su contraseña en LIBRERIA_QA_PASSWORD. La cuenta de pruebas debe poder crear y eliminar un esquema temporal.

```powershell
python -m pytest -q -s
```

Las pruebas de navegador utilizan Chrome por defecto. Se puede elegir Edge mediante LIBRERIA_QA_NAVEGADOR=msedge. Las cuentas y los productos definidos en tests/ pertenecen al entorno de prueba.

El repositorio excluye credenciales, claves de sesión, respaldos y archivos de acceso personales.
