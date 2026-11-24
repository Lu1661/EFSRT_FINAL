(() => {
  const menu = document.querySelector('#menu-personal');
  const botones = [...document.querySelectorAll('[data-menu]')];
  function menuAbierto(abierto) {
    menu.classList.toggle('open', abierto);
    botones.forEach(boton => boton.setAttribute('aria-expanded', String(abierto)));
  }
  if (menu) {
    botones.forEach(boton => boton.addEventListener('click', () => menuAbierto(!menu.classList.contains('open'))));
    document.addEventListener('keydown', event => {
      if (event.key === 'Escape' && menu.classList.contains('open')) {
        menuAbierto(false);
        botones[0].focus();
      }
    });
    document.addEventListener('click', event => {
      if (!menu.contains(event.target) && !event.target.closest('[data-menu]')) menuAbierto(false);
    });
  }

  document.querySelector('[data-imprimir]')?.addEventListener('click', () => window.print());
  const producto = document.querySelector('[data-producto-ajuste]');
  if (producto) {
    const cantidad = document.querySelector('[data-stock-actual]');
    const mostrar = () => { cantidad.value = producto.selectedOptions[0]?.dataset.stock || '—'; };
    producto.addEventListener('change', mostrar);
    mostrar();
  }

  function normalizar(value) {
    return value.toLocaleLowerCase('es').normalize('NFD').replace(/[\u0300-\u036f]/g, '');
  }
  const buscador = document.querySelector('[data-filtrar-opciones]');
  if (buscador) {
    const opciones = Array.from(document.querySelectorAll('[data-opcion]'), etiqueta => ({
      etiqueta, texto: normalizar(etiqueta.textContent),
    }));
    buscador.addEventListener('input', () => {
      const filtro = normalizar(buscador.value.trim());
      opciones.forEach(({ etiqueta, texto }) => { etiqueta.hidden = !texto.includes(filtro); });
    });
  }
})();
