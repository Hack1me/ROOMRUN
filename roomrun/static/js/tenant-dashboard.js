/** Tenant dashboard interactions: mobile sidebar toggle and chart initialization. */
(function () {
  'use strict';

  const mobileMenu = document.getElementById('mobile-menu');
  const sidebar = document.getElementById('sidebar');

  if (mobileMenu && sidebar) {
    mobileMenu.addEventListener('click', (event) => {
      event.stopPropagation();
      sidebar.classList.toggle('open');
    });
  }

  document.querySelectorAll('.nav-item').forEach((item) => {
    item.addEventListener('click', function () {
      document.querySelectorAll('.nav-item').forEach((nav) => nav.classList.remove('active'));
      this.classList.add('active');
      if (window.innerWidth <= 700 && sidebar) {
        sidebar.classList.remove('open');
      }
    });
  });

  document.addEventListener('click', (event) => {
    if (
      window.innerWidth <= 700 &&
      sidebar &&
      sidebar.classList.contains('open') &&
      !sidebar.contains(event.target) &&
      (!mobileMenu || !mobileMenu.contains(event.target))
    ) {
      sidebar.classList.remove('open');
    }
  });

  function initCharts() {
    const expensesCanvas = document.getElementById('expensesChart');
    const maintenanceCanvas = document.getElementById('maintenanceChart');

    if (expensesCanvas && window.TENANT_DASHBOARD) {
      const expensesCtx = expensesCanvas.getContext('2d');
      new Chart(expensesCtx, {
        type: 'bar',
        data: {
          labels: window.TENANT_DASHBOARD.expenses.labels,
          datasets: [
            {
              label: 'Dépenses',
              data: window.TENANT_DASHBOARD.expenses.data,
              backgroundColor: window.TENANT_DASHBOARD.expenses.backgroundColor,
              borderRadius: 5,
              borderWidth: 0,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: {
                label: function (context) {
                  return context.parsed.y.toLocaleString('fr-FR') + ' FCFA';
                },
              },
            },
          },
          scales: {
            y: {
              beginAtZero: true,
              grid: { color: '#EEF0F3' },
              ticks: {
                callback: function (value) {
                  return (value / 1000) + 'k';
                },
              },
            },
            x: { grid: { display: false } },
          },
        },
      });
    }

    if (maintenanceCanvas && window.TENANT_DASHBOARD) {
      const maintenanceCtx = maintenanceCanvas.getContext('2d');
      new Chart(maintenanceCtx, {
        type: 'doughnut',
        data: {
          labels: window.TENANT_DASHBOARD.maintenance.labels,
          datasets: [
            {
              data: window.TENANT_DASHBOARD.maintenance.data,
              backgroundColor: window.TENANT_DASHBOARD.maintenance.backgroundColor,
              borderWidth: 0,
              hoverOffset: 5,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          cutout: '68%',
          plugins: {
            legend: {
              position: 'bottom',
              labels: {
                usePointStyle: true,
                pointStyle: 'circle',
                padding: 14,
                font: { size: 9 },
              },
            },
          },
        },
      });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initCharts);
  } else {
    initCharts();
  }
})();
