(() => {
  const panel = document.querySelector('[data-catalogo]');
  const form = panel.querySelector('form');
  const q = form.elements.q;
  const grid = panel.querySelector('[data-productos]');
  const resultados = panel.querySelector('[data-resultados]');
  const paginador = panel.querySelector('[data-paginas]');
  const anterior = paginador.querySelector('[data-anterior]');
  const siguiente = paginador.querySelector('[data-siguiente]');
  const paginaLabel = paginador.querySelector('[data-pagina]');
  const filtros = [...form.querySelectorAll('[data-categoria]')];
  const limite = Number(panel.dataset.limite);
  let categoria = filtros.find(boton => boton.getAttribute('aria-pressed') === 'true')?.dataset.categoria || '';
  let pagina = 1;
  let pending;
  let timer;

  function elemento(tag, texto, clase) {
    const node = document.createElement(tag);
    node.textContent = texto;
    if (clase) node.className = clase;
    return node;
  }

  function tarjeta(producto) {
    const card = elemento('article', '', 'catalog-card');
    card.append(
      elemento('span', producto.codigo + ' · ' + producto.categoria, 'code'),
      elemento('h2', producto.nombre),
      elemento('strong', 'S/ ' + producto.precio),
      elemento('span', producto.disponibilidad, 'status ' + producto.estado),
    );
    return card;
  }

  async function consultar() {
    pending?.abort();
    const controller = new AbortController();
    pending = controller;
    try {
      const params = new URLSearchParams({ q: q.value.trim(), categoria, pagina: String(pagina) });
      const resp = await fetch(panel.dataset.api + '?' + params, { signal: controller.signal });
      if (!resp.ok) throw new Error('Catálogo no disponible.');
      const data = await resp.json();
      if (controller.signal.aborted) return;
      grid.replaceChildren(...data.productos.map(tarjeta));
      resultados.textContent = data.total === 0 ? 'No se encontraron productos.' :
        data.total + (data.total === 1 ? ' producto' : ' productos');
      const paginas = Math.max(1, Math.ceil(data.total / limite));
      paginador.hidden = paginas === 1;
      anterior.disabled = pagina <= 1;
      siguiente.disabled = pagina >= paginas;
      paginaLabel.textContent = 'Página ' + pagina + ' de ' + paginas;
    } catch (error) {
      if (controller.signal.aborted) return;
      grid.replaceChildren();
      resultados.textContent = 'No se pudo cargar el catálogo. Vuelve a intentar.';
      paginador.hidden = true;
    } finally {
      if (pending === controller) pending = null;
    }
  }

  q.addEventListener('input', () => {
    pagina = 1;
    clearTimeout(timer);
    pending?.abort();
    timer = setTimeout(consultar, 160);
  });
  form.addEventListener('submit', event => {
    event.preventDefault();
    clearTimeout(timer);
    pagina = 1;
    consultar();
  });
  filtros.forEach(boton => boton.addEventListener('click', () => {
    categoria = boton.dataset.categoria;
    filtros.forEach(filtro => {
      filtro.classList.toggle('selected', filtro === boton);
      filtro.setAttribute('aria-pressed', String(filtro === boton));
    });
    pagina = 1;
    consultar();
  }));
  anterior.addEventListener('click', () => { pagina -= 1; consultar(); });
  siguiente.addEventListener('click', () => { pagina += 1; consultar(); });
  window.addEventListener('pageshow', () => consultar());
  setInterval(() => {
    if (document.visibilityState === 'visible' && !pending) consultar();
  }, 4000);
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') consultar();
  });
})();
