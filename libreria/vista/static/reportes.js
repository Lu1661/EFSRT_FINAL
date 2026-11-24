(() => {
  const canvas = document.querySelector('#ventas-chart');
  if (!canvas || !window.Chart) return;
  const data = JSON.parse(document.querySelector('#ventas-datos').textContent);
  new Chart(canvas, {
    type: 'bar',
    data: {
      labels: data.map(row => row.fecha.split('-').slice(1).reverse().join('/')),
      datasets: [{ label: 'Ventas (S/)', data: data.map(row => row.total), backgroundColor: '#c50049', borderRadius: 4, maxBarThickness: 52 }],
    },
    options: {
      responsive: true, maintainAspectRatio: false, animation: false,
      scales: { y: { beginAtZero: true, ticks: { callback: value => 'S/ ' + value } } },
      plugins: { legend: { display: false } },
    },
  });
})();
