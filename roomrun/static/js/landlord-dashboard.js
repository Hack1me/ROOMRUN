/** Landlord dashboard interactions: mobile sidebar toggle and chart initialization. */
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
      if (window.innerWidth <= 768 && sidebar) {
        sidebar.classList.remove('open');
      }
    });
  });

  document.addEventListener('click', (event) => {
    if (
      window.innerWidth <= 768 &&
      sidebar &&
      sidebar.classList.contains('open') &&
      !sidebar.contains(event.target) &&
      (!mobileMenu || !mobileMenu.contains(event.target))
    ) {
      sidebar.classList.remove('open');
    }
  });

  function initCharts() {
    const revenueCanvas = document.getElementById('revenueChart');
    const occupancyCanvas = document.getElementById('occupancyChart');
    const maintenanceCanvas = document.getElementById('maintenanceChart');

    if (revenueCanvas && window.LANDLORD_DASHBOARD) {
      const ctx = revenueCanvas.getContext('2d');
      new Chart(ctx, {
        type: 'line',
        data: {
          labels: window.LANDLORD_DASHBOARD.revenue.labels,
          datasets: [
            {
              label: 'Revenus',
              data: window.LANDLORD_DASHBOARD.revenue.data,
              borderColor: '#4A90D9',
              backgroundColor: 'rgba(74,144,217,.10)',
              borderWidth: 2,
              fill: true,
              tension: 0.35,
              pointRadius: 3,
              pointHoverRadius: 5,
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

    if (occupancyCanvas && window.LANDLORD_DASHBOARD) {
      const ctx = occupancyCanvas.getContext('2d');
      new Chart(ctx, {
        type: 'doughnut',
        data: {
          labels: window.LANDLORD_DASHBOARD.occupancy.labels,
          datasets: [
            {
              data: window.LANDLORD_DASHBOARD.occupancy.data,
              backgroundColor: window.LANDLORD_DASHBOARD.occupancy.backgroundColor,
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
                padding: 15,
                font: { size: 10 },
              },
            },
          },
        },
      });
    }

    if (maintenanceCanvas && window.LANDLORD_DASHBOARD) {
      const ctx = maintenanceCanvas.getContext('2d');
      new Chart(ctx, {
        type: 'bar',
        data: {
          labels: window.LANDLORD_DASHBOARD.maintenance.labels,
          datasets: [
            {
              label: 'Nouvelles',
              data: window.LANDLORD_DASHBOARD.maintenance.new,
              backgroundColor: '#4A90D9',
              borderRadius: 4,
              barPercentage: 0.65,
            },
            {
              label: 'En cours',
              data: window.LANDLORD_DASHBOARD.maintenance.inProgress,
              backgroundColor: '#B9770E',
              borderRadius: 4,
              barPercentage: 0.65,
            },
            {
              label: 'Terminées',
              data: window.LANDLORD_DASHBOARD.maintenance.completed,
              backgroundColor: '#2E9E5B',
              borderRadius: 4,
              barPercentage: 0.65,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: {
              position: 'top',
              align: 'end',
              labels: {
                usePointStyle: true,
                pointStyle: 'circle',
                boxWidth: 7,
                padding: 15,
              },
            },
          },
          scales: {
            y: {
              beginAtZero: true,
              ticks: { stepSize: 1 },
              grid: { color: '#EEF0F3' },
            },
            x: { grid: { display: false } },
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
