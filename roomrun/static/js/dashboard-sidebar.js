/** Responsive sidebar toggle shared by dashboard pages. */
(function () {
  'use strict';

  const sidebar = document.getElementById('sidebar');
  if (!sidebar) return;
  if (sidebar.dataset.responsiveBound) return;
  sidebar.dataset.responsiveBound = 'true';

  let mobileMenu =
    document.getElementById('mobile-menu') ||
    document.getElementById('mobileMenu') ||
    document.querySelector('[data-sidebar-toggle], .menu-button, .mobile-menu, .payments-mobile-toggle');
  if (!mobileMenu) {
    const main = document.querySelector('.main');
    if (!main) return;

    const topbar = main.querySelector('.topbar, .profile-topbar');
    if (topbar) {
      mobileMenu = document.createElement('button');
      mobileMenu.className = 'menu-button dashboard-auto-menu';
      mobileMenu.type = 'button';
      mobileMenu.setAttribute('aria-label', gettext('Open menu'));
      mobileMenu.innerHTML = '<i class="ti ti-menu-2" aria-hidden="true"></i>';
      topbar.prepend(mobileMenu);
    } else {
      const bar = document.createElement('header');
      bar.className = 'dashboard-mobile-bar';
      mobileMenu = document.createElement('button');
      mobileMenu.className = 'menu-button';
      mobileMenu.type = 'button';
      mobileMenu.setAttribute('aria-label', gettext('Open menu'));
      mobileMenu.innerHTML = '<i class="ti ti-menu-2" aria-hidden="true"></i>';
      bar.append(mobileMenu);
      main.prepend(bar);
    }
    mobileMenu.id = 'mobile-menu';
  }

  const breakpoint = parseInt(mobileMenu.dataset.sidebarBreakpoint || '1024', 10);
  if (!mobileMenu.hasAttribute('aria-expanded')) {
    mobileMenu.setAttribute('aria-expanded', 'false');
  }
  if (!mobileMenu.dataset.sidebarBound) {
    mobileMenu.addEventListener('click', (event) => {
      event.stopPropagation();
      sidebar.classList.toggle('open');
      mobileMenu.setAttribute('aria-expanded', String(sidebar.classList.contains('open')));
    });
    mobileMenu.dataset.sidebarBound = 'true';
  }

  document.querySelectorAll('.nav-item').forEach((item) => {
    item.addEventListener('click', function () {
      document.querySelectorAll('.nav-item').forEach((nav) => nav.classList.remove('active'));
      this.classList.add('active');
      if (window.innerWidth <= breakpoint) sidebar.classList.remove('open');
    });
  });

  document.addEventListener('click', (event) => {
    if (
      window.innerWidth <= breakpoint &&
      sidebar.classList.contains('open') &&
      !sidebar.contains(event.target) &&
      !mobileMenu.contains(event.target)
    ) {
      sidebar.classList.remove('open');
      mobileMenu.setAttribute('aria-expanded', 'false');
    }
  });
})();
