/** Maintenance dashboard interactions. */
(function () {
  'use strict';

  const sidebar = document.getElementById('sidebar');
  const mobileMenu = document.getElementById('mobileMenu');
  const overlay = document.getElementById('overlay');

  if (mobileMenu && sidebar && overlay) {
    mobileMenu.addEventListener('click', () => {
      sidebar.classList.add('open');
      overlay.classList.add('active');
    });

    overlay.addEventListener('click', () => {
      sidebar.classList.remove('open');
      overlay.classList.remove('active');
    });
  }

  const navItems = document.querySelectorAll('.nav-item');
  navItems.forEach((item) => {
    item.addEventListener('click', function () {
      navItems.forEach((nav) => nav.classList.remove('active'));
      this.classList.add('active');
    });
  });
})();
