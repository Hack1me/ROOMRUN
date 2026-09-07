/** Dashboard interactions: mobile sidebar toggle and outside click close. */
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
    item.addEventListener('click', () => {
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
      !sidebar.contains(event.target)
    ) {
      sidebar.classList.remove('open');
    }
  });
})();
