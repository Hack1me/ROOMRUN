/** Maintenance dashboard interactions: nav active state. */
(function () {
  'use strict';

  const navItems = document.querySelectorAll('.nav-item');
  navItems.forEach((item) => {
    item.addEventListener('click', function () {
      navItems.forEach((nav) => nav.classList.remove('active'));
      this.classList.add('active');
    });
  });
})();
