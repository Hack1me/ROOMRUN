document.addEventListener("DOMContentLoaded", () => {
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ============================== MOBILE MENU ============================== */
  const burger = $("#nav-burger");
  const mobileMenu = $("#mobile-menu");

  if (burger && mobileMenu) {
    burger.addEventListener("click", () => {
      const isOpen = burger.getAttribute("aria-expanded") === "true";
      burger.setAttribute("aria-expanded", String(!isOpen));
      mobileMenu.hidden = isOpen;
      mobileMenu.classList.toggle("is-open", !isOpen);
    });

    $$("a", mobileMenu).forEach(link => {
      link.addEventListener("click", () => {
        burger.setAttribute("aria-expanded", "false");
        mobileMenu.hidden = true;
        mobileMenu.classList.remove("is-open");
      });
    });
  }

  /* ============================== FAQ ============================== */
  $$(".faq-item__q").forEach(button => {
    button.addEventListener("click", () => {
      const item = button.closest(".faq-item");
      const answer = $(".faq-item__a", item);
      const isOpen = item.classList.contains("is-open");

      $$(".faq-item").forEach(otherItem => {
        otherItem.classList.remove("is-open");

        const otherButton = $(".faq-item__q", otherItem);
        const otherAnswer = $(".faq-item__a", otherItem);

        if (otherButton) {
          otherButton.setAttribute("aria-expanded", "false");
        }

        if (otherAnswer) {
          otherAnswer.style.maxHeight = "0px";
        }
      });

      if (!isOpen) {
        item.classList.add("is-open");
        button.setAttribute("aria-expanded", "true");
        answer.style.maxHeight = answer.scrollHeight + "px";
      }
    });
  });

  /* ============================== SCROLL REVEAL ============================== */
  const revealElements = $$(".rr-reveal");

  if ("IntersectionObserver" in window && !reduceMotion) {
    const revealObserver = new IntersectionObserver(
      entries => {
        entries.forEach(entry => {
          if (!entry.isIntersecting) return;

          entry.target.classList.add("is-visible");
          revealObserver.unobserve(entry.target);
        });
      },
      {
        threshold: 0.12,
        rootMargin: "0px 0px -8% 0px"
      }
    );

    revealElements.forEach(el => revealObserver.observe(el));
  } else {
    revealElements.forEach(el => el.classList.add("is-visible"));
  }

  /* ============================== SCROLL PROGRESS ============================== */
  const progress = $(".rr-scroll-progress");

  const updateProgress = () => {
    if (!progress) return;

    const scrollable =
      document.documentElement.scrollHeight - window.innerHeight;

    const ratio = scrollable > 0 ? window.scrollY / scrollable : 0;

    progress.style.transform =
      `scaleX(${Math.min(1, Math.max(0, ratio))})`;
  };

  window.addEventListener("scroll", updateProgress, {
    passive: true
  });

  updateProgress();

  /* ============================== PARALLAX ============================== */
  const parallaxImages = $$(".rr-parallax");

  const updateParallax = () => {
    if (reduceMotion) return;

    parallaxImages.forEach(image => {
      const parent = image.parentElement;
      const rect = parent.getBoundingClientRect();

      if (
        rect.bottom < 0 ||
        rect.top > window.innerHeight
      ) {
        return;
      }

      const viewportCenter = window.innerHeight / 2;
      const elementCenter = rect.top + rect.height / 2;

      const distance =
        (elementCenter - viewportCenter) /
        window.innerHeight;

      image.style.transform =
        `translateY(${distance * -24}px) scale(1.04)`;
    });
  };

  window.addEventListener("scroll", updateParallax, {
    passive: true
  });

  updateParallax();

  /* ============================== COUNTERS ============================== */
  const counters = $$("[data-count]");

  if (
    "IntersectionObserver" in window &&
    counters.length
  ) {
    const counterObserver = new IntersectionObserver(
      entries => {
        entries.forEach(entry => {
          if (!entry.isIntersecting) return;

          const el = entry.target;
          const target = Number(
            el.dataset.count || 0
          );

          if (reduceMotion) {
            el.textContent = target;
            counterObserver.unobserve(el);
            return;
          }

          const duration = 900;
          const start = performance.now();

          const animate = now => {
            const progress = Math.min(
              1,
              (now - start) / duration
            );

            const eased =
              1 - Math.pow(1 - progress, 3);

            el.textContent =
              Math.round(target * eased);

            if (progress < 1) {
              requestAnimationFrame(animate);
            }
          };

          requestAnimationFrame(animate);

          counterObserver.unobserve(el);
        });
      },
      {
        threshold: 0.65
      }
    );

    counters.forEach(counter =>
      counterObserver.observe(counter)
    );
  }

  /* ============================== MAGNETIC BUTTONS ============================== */
  if (
    !reduceMotion &&
    window.matchMedia("(pointer:fine)").matches
  ) {
    $$(".rr-magnetic").forEach(button => {
      button.addEventListener("mousemove", event => {
        const rect =
          button.getBoundingClientRect();

        const x =
          (event.clientX -
            rect.left -
            rect.width / 2) *
          0.12;

        const y =
          (event.clientY -
            rect.top -
            rect.height / 2) *
          0.12;

        button.style.transform =
          `translate(${x}px, ${y}px)`;
      });

      button.addEventListener("mouseleave", () => {
        button.style.transform = "";
      });
    });
  }

  /* ============================== RAIL SCROLL SPY ============================== */
  const railItems = $$(".rail__item");

  const sections = railItems
    .map(item =>
      document.getElementById(
        item.dataset.target
      )
    )
    .filter(Boolean);

  if (
    "IntersectionObserver" in window &&
    sections.length
  ) {
    const railObserver =
      new IntersectionObserver(
        entries => {
          entries.forEach(entry => {
            if (!entry.isIntersecting) return;

            railItems.forEach(item => {
              item.classList.toggle(
                "is-active",
                item.dataset.target ===
                  entry.target.id
              );
            });
          });
        },
        {
          threshold: 0.2,
          rootMargin:
            "-35% 0px -50% 0px"
        }
      );

    sections.forEach(section =>
      railObserver.observe(section)
    );
  }

  /* ============================== SMOOTH ANCHORS ============================== */
  $$('a[href^="#"]').forEach(link => {
    link.addEventListener("click", event => {
      const href =
        link.getAttribute("href");

      if (!href || href === "#") return;

      const target =
        document.querySelector(href);

      if (!target) return;

      event.preventDefault();

      target.scrollIntoView({
        behavior: reduceMotion
          ? "auto"
          : "smooth",
        block: "start"
      });
    });
  });
});
