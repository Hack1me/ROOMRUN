/** Tenant dashboard interactions: mobile sidebar toggle and chart initialization. */
(function () {
  'use strict';

  const mobileMenu = document.getElementById('mobile-menu');
  const sidebar = document.getElementById('sidebar');

  if (mobileMenu && sidebar && !mobileMenu.dataset.sidebarBound) {
    mobileMenu.addEventListener('click', (event) => {
      event.stopPropagation();
      sidebar.classList.toggle('open');
    });
    mobileMenu.dataset.sidebarBound = 'true';
  }

  document.querySelectorAll('.nav-item').forEach((item) => {
    item.addEventListener('click', function () {
      document.querySelectorAll('.nav-item').forEach((nav) => nav.classList.remove('active'));
      this.classList.add('active');
      if (window.innerWidth <= 1024 && sidebar) {
        sidebar.classList.remove('open');
      }
    });
  });

  document.addEventListener('click', (event) => {
    if (
      window.innerWidth <= 1024 &&
      sidebar &&
      sidebar.classList.contains('open') &&
      !sidebar.contains(event.target) &&
      (!mobileMenu || !mobileMenu.contains(event.target))
    ) {
      sidebar.classList.remove('open');
    }
  });

  function initCharts() {
    const dataElement = document.getElementById('tenant-dashboard-data');
    if (!dataElement || !window.Chart) return;
    let dashboardData;
    try {
      dashboardData = JSON.parse(dataElement.textContent);
    } catch (error) {
      console.error('Invalid tenant dashboard chart data.', error);
      return;
    }
    const expensesCanvas = document.getElementById('expensesChart');
    const maintenanceCanvas = document.getElementById('maintenanceChart');

    if (expensesCanvas && dashboardData.expenses) {
      const expensesCtx = expensesCanvas.getContext('2d');
      new Chart(expensesCtx, {
        type: 'bar',
        data: {
          labels: dashboardData.expenses.labels,
          datasets: [
            {
              label: 'Payments',
              data: dashboardData.expenses.data,
              backgroundColor: '#1E3A5F',
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
                  return new Intl.NumberFormat(document.documentElement.lang || undefined, {
                    style: 'currency', currency: 'XAF', maximumFractionDigits: 0,
                  }).format(context.parsed.y);
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

    if (maintenanceCanvas && dashboardData.maintenance) {
      const maintenanceCtx = maintenanceCanvas.getContext('2d');
      new Chart(maintenanceCtx, {
        type: 'doughnut',
        data: {
          labels: dashboardData.maintenance.labels,
          datasets: [
            {
              data: dashboardData.maintenance.data,
              backgroundColor: ['#2E9E5B', '#4A90D9', '#B9770E', '#9CA3AF'],
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
