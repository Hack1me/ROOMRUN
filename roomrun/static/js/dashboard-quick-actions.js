(() => {
  const breakpoint = window.matchMedia("(max-width: 1024px)");

  const createQuickActionsModal = (toggle) => {
    const panel = document.getElementById(toggle.getAttribute("aria-controls"));
    const source = toggle.closest("[data-quick-actions-source]");
    if (!panel || !source) return null;

    const togglePlaceholder = document.createComment("Quick actions toggle");
    const panelPlaceholder = document.createComment("Quick actions panel");
    toggle.before(togglePlaceholder);
    panel.before(panelPlaceholder);

    const dialog = document.createElement("dialog");
    dialog.className = "quick-actions-dialog";
    source.closest(".app")?.classList.forEach((className) => {
      dialog.classList.add(className);
    });
    dialog.setAttribute("aria-labelledby", `${panel.id}-title`);

    const header = document.createElement("header");
    header.className = "quick-actions-dialog__header";
    const title = document.createElement("h2");
    title.className = "quick-actions-dialog__title";
    title.id = `${panel.id}-title`;
    title.textContent = toggle.dataset.modalTitle;

    const close = document.createElement("button");
    close.className = "quick-actions-dialog__close";
    close.type = "button";
    close.setAttribute("aria-label", toggle.dataset.labelClose);
    close.title = toggle.dataset.labelClose;
    close.innerHTML = '<i class="ti ti-x" aria-hidden="true"></i>';
    header.append(title, close);

    const body = document.createElement("div");
    body.className = "quick-actions-dialog__body";
    dialog.append(header, body);

    let active = false;
    const setExpanded = (expanded) => {
      toggle.setAttribute("aria-expanded", String(expanded));
      const label = expanded ? toggle.dataset.labelClose : toggle.dataset.labelOpen;
      toggle.setAttribute("aria-label", label);
      toggle.title = label;
      toggle.classList.toggle("is-open", expanded);
    };

    const open = () => {
      if (!dialog.open) dialog.showModal();
      setExpanded(true);
    };
    const dismiss = () => {
      if (dialog.open) dialog.close();
    };

    toggle.addEventListener("click", () => {
      if (dialog.open) dismiss();
      else open();
    });
    close.addEventListener("click", dismiss);
    dialog.addEventListener("click", (event) => {
      if (event.target === dialog) dismiss();
    });
    dialog.addEventListener("close", () => setExpanded(false));

    return {
      activate() {
        if (active) return;
        active = true;
        body.append(panel);
        document.body.append(dialog, toggle);
        source.hidden = true;
        toggle.classList.add("is-floating");
        setExpanded(false);
      },
      restore() {
        if (!active) return;
        dismiss();
        active = false;
        source.hidden = false;
        source.insertBefore(toggle, togglePlaceholder);
        source.insertBefore(panel, panelPlaceholder);
        dialog.remove();
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
    .map(createQuickActionsModal)
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
