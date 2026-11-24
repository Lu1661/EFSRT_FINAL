# Trazabilidad de la construcción

Referencia: informe de Fase 1 y Fase 2 de Librería Popular, Tablas 7, 8, 12–24, 26 y 27, y Figuras 19–33. Los archivos académicos originales se conservan como fuente.

## Casos de uso y requisitos funcionales

| Caso de uso | Requisitos y resultado verificable | Pantalla, flujo y datos |
|---|---|---|
| CU01 Autenticar | RF01 inicia sesión, distingue Administrador y Vendedor y rechaza credenciales inválidas o usuarios inactivos. | `/login`. Campos usuario y contraseña. El Administrador va a Inventario y el Vendedor a Registrar venta. Figura 20/32. Tabla `usuario`. |
| CU02 Gestionar usuarios | RF19 crea, edita, desactiva, reactiva y restablece la contraseña de un usuario. | `/administrador/usuarios`. Nombre, usuario, contraseña, rol y estado. Figura 21/32. Tabla `usuario`; el hash es interno. |
| CU03 Gestionar inventario | RF02 registra productos, RF18 admite la marca de temporada escolar y RF24 importa Excel/CSV. Las filas inválidas se muestran y quedan sin cargar. | `/administrador` y `/administrador/importar`. Código, nombre, categoría, precio, stock, mínimo y temporada escolar. Figura 22/32. Tabla `producto`. |
| CU04 Ajustar stock | RF05 valida la cantidad, registra el motivo y conserva usuario, fecha y cantidades anterior y nueva. | `/administrador/ajuste`. Figura 23/32. Tablas `producto`, `usuario`, `movimiento_stock`. |
| CU05 Registrar venta | RF03 descuenta stock, RF06 guarda fecha, productos, cantidades y total, RF07 genera un resumen imprimible y RF21 permite asociar un cliente. | `/vendedor` y detalle de venta. Búsqueda, cantidad, precio, subtotal, total y cliente opcional. Figuras 24/32. Tablas `venta`, `detalle_venta`, `producto`, `usuario`, `cliente`. |
| CU06 Buscar productos | RF20 busca por nombre, código y categoría en los dos canales. El personal ve stock exacto y el público ve el estado calculado. | Buscador de Registrar venta y Catálogo. Figuras 25/32. API privada `/api/personal/productos` y pública `/api/catalogo/productos`. Tabla `producto`. |
| CU07 Historial de ventas | RF08 consulta ventas por fechas, con filtro de usuario y acceso al detalle de solo lectura. | `/ventas`. Número, fecha, usuario, cliente y total. Figura 26/33. Tablas `venta`, `detalle_venta`, `usuario`, `cliente`, `producto`. |
| CU08 Alertas y reposición | RF04 alerta al alcanzar o bajar del mínimo. RF10 calcula cantidades sugeridas por proveedor y permite exportarlas. | `/administrador/alertas`. Figura 27/33. Tablas `producto`, `proveedor`, `proveedor_producto`. |
| CU09 Gestionar proveedores | RF09 registra y edita proveedores con nombre, contacto y productos que suministran. | `/administrador/proveedores`. Figura 28/33. Tablas `proveedor`, `proveedor_producto`, `producto`. |
| CU10 Generar reportes | RF16 muestra productos más vendidos, RF17 resume ventas por periodo. La ficha del CU especifica día, semana, mes y campaña escolar, con gráfico y exportación. | `/administrador/reportes`. Figura 29/33. Tablas `venta`, `detalle_venta`, `producto`. |
| CU11 Gestionar clientes | RF11 registra nombre, tipo y teléfono, RF22 lista mayoristas con historial de compras y RF23 abre WhatsApp desde la ficha. | `/clientes` y ficha del cliente. Figura 30/33. Tablas `cliente` y `venta`. |
| CU12 Consultar catálogo | RF12 publica precio y disponibilidad, RF13 vuelve a leer el stock, RF14 permite búsqueda y filtro sin sesión y RF15 facilita consultar por cuenta propia. | `/Catalogo` y API de catálogo. Figuras 31/33. Tabla `producto`. La consulta por WhatsApp requiere el número configurado de la tienda. La reducción de llamadas requiere observación con la librería. |

## Requisitos no funcionales

| Código | Implementación y alcance de la verificación |
|---|---|
| RNF01 | Hash de Werkzeug, cookies HttpOnly/SameSite, sesión de 30 minutos de inactividad, CSRF y permisos del servidor. HTTPS en la publicación y activación opcional en local. Las credenciales se configuran por separado. |
| RNF02 | Búsqueda, cantidades y resumen fijo con confirmación. El flujo se puede recorrer en Chrome. La medición con vendedores nuevos tras una inducción queda para validación con usuarios. |
| RNF03 | Consulta paginada en ambas APIs. La suite mide la latencia en MySQL local incluyendo filtrado y serialización. Meta del Word: menos de 3 segundos. |
| RNF04 | Respaldo lógico diario y comando manual de respaldo. La disponibilidad sostenida requiere observación durante un periodo definido. |
| RNF05 | Pantallas web para laptop y una interfaz adaptada al ancho de un celular. La navegación por rol conserva el menú lateral en escritorio y las opciones inferiores en celular. |
| RNF06 | Vista, negocio y datos en directorios separados. La vista llama a servicios y los servicios usan repositorios. Los pasos de ejecución y pruebas quedan en el README. |
| RNF07 | Una transacción guarda venta, detalle y stock. InnoDB bloquea los productos involucrados durante la operación. Hay cobertura para stock insuficiente, duplicados por reintento, dos ventas concurrentes y auditoría del ajuste manual. |
| RNF08 | Prueba de cuatro sesiones internas más una pública concurrente, usando MySQL local. |
| RNF09 | MySQL 8, ocho tablas relacionales con claves foráneas y capas de vista, negocio y datos. |
| RNF10 | Consulta y paginación con 5.000 productos y registros con fechas históricas. La retención de años de operación dependerá de la base, la política de copias y el entorno. |
| RNF11 | La lógica de confirmar una venta y la impresión del resumen viven en componentes separados. Incorporar la facturación electrónica en el futuro requerirá especificar y modelar sus datos. |

## Diferencias entre las fuentes del diseño

- El texto del SQL del Word omite la clave compuesta de `proveedor_producto`. El esquema usa la clave compuesta de las Figuras 18 y 19.
- Las secuencias de CU04 y CU05 dibujan un guardado de alerta. Las pantallas usan el cálculo descrito en el diseño de la base. El mínimo inicial es cinco; se aplica el mínimo configurado por producto.
- Algunos bocetos incluyen método de pago de mostrador, marca, fotos, categorías distintas o la desactivación de productos. Esas pantallas se construyeron con los datos de las ocho tablas y los campos de los casos de uso. El estado visible del producto se deriva del stock.
- El wireframe de catálogo de escritorio muestra el menú del personal. El catálogo implementa el acceso público del CU12 y del boceto móvil.
- El informe deja por precisar el intervalo de campaña escolar. La implementación usa diciembre a marzo y muestra las fechas exactas del intervalo al generar el reporte. La reposición apunta a cuatro veces el mínimo según la Figura 27.

## Actualización de la construcción

La interfaz renovada conserva las funciones y los datos relacionados con los requisitos. Las entradas son /Catalogo, /login, /administrador y /vendedor. Los enlaces anteriores redirigen a sus pantallas equivalentes.

La protección de tres intentos desarrolla RNF01 y el flujo alternativo de CU01. La publicación HTTPS y el respaldo diario se relacionan con RNF01 y RNF04. Las pruebas de integración verifican el uso de MySQL conforme a RNF09. El informe académico debe incorporar estas decisiones y los resultados de validación.
