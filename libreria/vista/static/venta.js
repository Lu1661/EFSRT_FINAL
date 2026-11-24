(() => {
  const vista = document.querySelector('[data-venta]');
  const form = vista.querySelector('[data-buscador]');
  const q = form.elements.q;
  const categoria = form.elements.categoria;
  const cantidad = form.elements.cantidad;
  const resultados = form.querySelector('[data-resultados]');
  const contenedor = vista.querySelector('[data-lineas]');
  const aviso = vista.querySelector('[data-error]');
  const confirmar = vista.querySelector('[data-confirmar-venta]');
  const csrf = document.querySelector('meta[name=csrf-token]').content;
  const lineas = new Map();
  let lista = [];
  let actual;
  let solicitud;
  let timer;
  let pagina = 1;
  let enviando = false;

  function nodo(tag, text, cls) {
    const result = document.createElement(tag);
    if (text !== undefined) result.textContent = text;
    if (cls) result.className = cls;
    return result;
  }

  const centimos = precio => Math.round(Number(precio) * 100);
  const moneda = monto => 'S/ ' + (monto / 100).toFixed(2);

  function error(mensaje) {
    aviso.hidden = !mensaje;
    aviso.textContent = mensaje;
    if (mensaje) aviso.scrollIntoView({ block: 'nearest' });
  }

  function fila(linea) {
    const row = nodo('tr');
    const subtotal = centimos(linea.precio) * linea.cantidad;
    const valores = [
      ['Producto', linea.nombre], ['Cantidad', linea.cantidad],
      ['Precio unitario', moneda(centimos(linea.precio))], ['Subtotal', moneda(subtotal)],
    ];
    valores.forEach(([label, value]) => {
      const cell = nodo('td', value);
      cell.dataset.label = label;
      row.append(cell);
    });
    const action = nodo('td', '', 'actions-cell');
    const quitar = nodo('button', 'Quitar', 'btn btn-light btn-sm');
    quitar.type = 'button';
    quitar.setAttribute('aria-label', 'Quitar ' + linea.nombre);
    quitar.addEventListener('click', () => {
      lineas.delete(linea.id);
      dibujarVenta();
    });
    action.append(quitar);
    row.append(action);
    return row;
  }

  function dibujarVenta() {
    const total = [...lineas.values()].reduce((sum, linea) => sum + centimos(linea.precio) * linea.cantidad, 0);
    vista.querySelector('[data-total]').textContent = moneda(total);
    confirmar.disabled = lineas.size === 0 || enviando;
    if (lineas.size === 0) {
      contenedor.replaceChildren(nodo('p', 'Aún no hay productos en la venta.', 'empty-state'));
      return;
    }
    const table = nodo('table', '', 'stack-table');
    const thead = table.createTHead().insertRow();
    ['Producto', 'Cantidad', 'Precio unitario', 'Subtotal', ''].forEach(label => {
      thead.append(nodo('th', label));
    });
    table.createTBody().append(...[...lineas.values()].map(fila));
    contenedor.replaceChildren(table);
  }

  function seleccionar(producto) {
    actual = producto;
    q.value = producto.codigo + ' · ' + producto.nombre;
    resultados.hidden = true;
    cantidad.focus();
    cantidad.select();
  }

  async function buscar() {
    solicitud?.abort();
    const controller = new AbortController();
    solicitud = controller;
    const params = new URLSearchParams({ q: q.value.trim(), categoria: categoria.value, pagina: String(pagina) });
    try {
      const resp = await fetch(vista.dataset.buscar + '?' + params, { signal: controller.signal });
      if (!resp.ok) throw new Error(resp.status === 401 ? 'La sesión venció.' : 'No se pudo buscar el producto.');
      const data = await resp.json();
      if (controller.signal.aborted) return;
      lista = data.productos;
      const botones = lista.map(item => {
        const btn = nodo('button', '', 'search-option');
        btn.type = 'button';
        btn.append(nodo('strong', item.nombre), nodo('small',
          item.codigo + ' · S/ ' + item.precio + ' · ' + item.disponibilidad + ' · Stock ' + item.stock));
        btn.addEventListener('click', () => seleccionar(item));
        return btn;
      });
      if (data.total > 24) {
        const nav = nodo('div', '', 'pager');
        if (pagina > 1) {
          const btn = nodo('button', 'Anterior', 'btn btn-light btn-sm');
          btn.type = 'button';
          btn.addEventListener('click', () => { pagina -= 1; buscar(); });
          nav.append(btn);
        }
        if (pagina * 24 < data.total) {
          const btn = nodo('button', 'Siguiente', 'btn btn-light btn-sm');
          btn.type = 'button';
          btn.addEventListener('click', () => { pagina += 1; buscar(); });
          nav.append(btn);
        }
        botones.push(nav);
      }
      resultados.replaceChildren(...(botones.length ? botones : [nodo('p', 'No se encontraron productos.')]));
      resultados.hidden = false;
    } catch (exc) {
      if (!controller.signal.aborted) error(exc.message);
    }
  }

  function cambiarBusqueda() {
    actual = undefined;
    lista = [];
    pagina = 1;
    clearTimeout(timer);
    solicitud?.abort();
    resultados.hidden = true;
    timer = setTimeout(buscar, 120);
  }
  q.addEventListener('input', cambiarBusqueda);
  q.addEventListener('focus', () => { if (!actual && resultados.hidden) cambiarBusqueda(); });
  q.addEventListener('keydown', event => {
    if (event.key === 'ArrowDown' && !resultados.hidden) resultados.querySelector('button')?.focus();
  });
  categoria.addEventListener('change', () => {
    if (actual) q.value = '';
    cambiarBusqueda();
  });
  form.addEventListener('keydown', event => { if (event.key === 'Escape') resultados.hidden = true; });
  document.addEventListener('click', event => { if (!form.contains(event.target)) resultados.hidden = true; });

  form.addEventListener('submit', async event => {
    event.preventDefault();
    error('');
    const item = actual || (lista.length === 1 ? lista[0] : undefined);
    if (!item) {
      clearTimeout(timer);
      await buscar();
      error('Selecciona un producto de la lista.');
      return;
    }
    const unidades = Number(cantidad.value);
    const acumuladas = unidades + (lineas.get(item.id)?.cantidad || 0);
    if (!Number.isInteger(unidades) || unidades < 1) {
      error('Ingresa una cantidad entera mayor que cero.');
      return;
    }
    if (acumuladas > item.stock) {
      error('Stock insuficiente para ' + item.nombre + '. Disponible: ' + item.stock + '.');
      return;
    }
    if (lineas.size >= 100 && !lineas.has(item.id)) {
      error('Una venta admite un máximo de 100 productos.');
      return;
    }
    lineas.set(item.id, { ...item, cantidad: acumuladas });
    actual = undefined;
    lista = [];
    clearTimeout(timer);
    solicitud?.abort();
    resultados.hidden = true;
    q.value = '';
    cantidad.value = 1;
    dibujarVenta();
  });

  confirmar.addEventListener('click', async () => {
    if (enviando || !lineas.size) return;
    enviando = true;
    confirmar.disabled = true;
    error('');
    try {
      if (window.Swal) {
        const dialogo = await Swal.fire({
          title: '¿Confirmar venta?',
          text: 'Total: ' + vista.querySelector('[data-total]').textContent,
          icon: 'question', showCancelButton: true, cancelButtonText: 'Revisar',
          confirmButtonText: 'Confirmar venta', confirmButtonColor: '#c50049',
        });
        if (!dialogo.isConfirmed) return;
      }
      const resp = await fetch(vista.dataset.confirmar, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
        body: JSON.stringify({
          token: vista.dataset.token, cliente: vista.querySelector('[data-cliente]').value,
          productos: [...lineas.values()].map(({ id, cantidad }) => ({ id, cantidad })),
        }),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.error || 'La venta no se pudo confirmar.');
      window.location.assign(data.destino);
    } catch (exc) {
      error(exc instanceof SyntaxError ? 'No se pudo confirmar la venta. Vuelve a intentar.' : exc.message);
    } finally {
      enviando = false;
      dibujarVenta();
    }
  });
  dibujarVenta();
})();
