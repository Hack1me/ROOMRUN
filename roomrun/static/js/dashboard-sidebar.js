/** Shared dashboard sidebar interactions: mobile toggle, nav active state, outside click close. */
(function () {
  'use strict';

  const mobileMenu = document.getElementById('mobile-menu');
  const sidebar = document.getElementById('sidebar');
  const breakpoint = parseInt(mobileMenu?.dataset?.sidebarBreakpoint || '768', 10);

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
      if (window.innerWidth <= breakpoint && sidebar) {
        sidebar.classList.remove('open');
      }
    });
  });

  document.addEventListener('click', (event) => {
    if (
      window.innerWidth <= breakpoint &&
      sidebar &&
      sidebar.classList.contains('open') &&
      !sidebar.contains(event.target) &&
      (!mobileMenu || !mobileMenu.contains(event.target))
    ) {
      sidebar.classList.remove('open');
    }
  });
})();