(() => {
  const breakpoint = window.matchMedia("(max-width: 1024px)");

  const createQuickActionsPopover = (toggle) => {
    const panel = document.getElementById(toggle.getAttribute("aria-controls"));
    const source = toggle.closest("[data-quick-actions-source]");
    if (!panel || !source) return null;

    const togglePlaceholder = document.createComment("Quick actions toggle");
    const panelPlaceholder = document.createComment("Quick actions panel");
    toggle.before(togglePlaceholder);
    panel.before(panelPlaceholder);

    const popover = document.createElement("div");
    popover.className = "quick-actions-popover";
    popover.setAttribute("role", "region");
    popover.setAttribute("aria-hidden", "true");
    popover.inert = true;

    const heading = document.createElement("h2");
    heading.className = "quick-actions-popover__title";
    heading.id = `${panel.id}-label`;
    heading.textContent = toggle.dataset.modalTitle;
    popover.setAttribute("aria-labelledby", heading.id);

    const body = document.createElement("div");
    body.className = "quick-actions-popover__body";
    popover.append(heading, body);
    body.append(panel);

    let active = false;
    const setOpen = (open) => {
      toggle.setAttribute("aria-expanded", String(open));
      const label = open ? toggle.dataset.labelClose : toggle.dataset.labelOpen;
      toggle.setAttribute("aria-label", label);
      toggle.title = label;
      toggle.classList.toggle("is-open", open);
      popover.setAttribute("aria-hidden", String(!open));
      popover.inert = !open;
      if (open) {
        popover.classList.add("is-open");
      } else {
        popover.classList.remove("is-open");
      }
    };

    const close = (returnFocus = false) => {
      if (toggle.getAttribute("aria-expanded") !== "true") return;
      setOpen(false);
      if (returnFocus) toggle.focus();
    };

    toggle.addEventListener("click", () => {
      const open = toggle.getAttribute("aria-expanded") === "true";
      setOpen(!open);
    });

    document.addEventListener("pointerdown", (event) => {
      if (
        active &&
        !popover.contains(event.target) &&
        !toggle.contains(event.target)
      ) {
        close();
      }
    });
    document.addEventListener("keydown", (event) => {
      if (active && event.key === "Escape") close(true);
    });

    return {
      activate() {
        if (active) return;
        active = true;
        body.append(panel);
        document.body.append(popover, toggle);
        source.hidden = true;
        toggle.classList.add("is-floating");
        setOpen(false);
      },
      restore() {
        if (!active) return;
        close();
        active = false;
        source.hidden = false;
        source.insertBefore(toggle, togglePlaceholder);
        source.insertBefore(panel, panelPlaceholder);
        popover.remove();
        toggle.classList.remove("is-floating", "is-open");
        toggle.setAttribute("aria-expanded", "true");
        toggle.setAttribute("aria-label", toggle.dataset.labelOpen);
        toggle.title = toggle.dataset.labelOpen;
      },
    };
  };

  const controls = Array.from(
    document.querySelectorAll("[data-quick-actions-toggle]"),
  )
    .map(createQuickActionsPopover)
    .filter(Boolean);

  const syncLayout = () => {
    controls.forEach((control) => {
      if (breakpoint.matches) control.activate();
      else control.restore();
    });
  };

  syncLayout();
  if (breakpoint.addEventListener) {
    breakpoint.addEventListener("change", syncLayout);
  } else {
    breakpoint.addListener(syncLayout);
  }
})();
