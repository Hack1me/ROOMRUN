/** Guard dashboard interactions: mobile sidebar toggle. */
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
})();
