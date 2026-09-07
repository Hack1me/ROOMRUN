/** Password visibility controls for the registration form. */
document.querySelectorAll("[data-password-toggle]").forEach((button) => {
  const input = document.getElementById(button.dataset.passwordToggle);
  const icon = button.querySelector("i");
  if (!input || !icon) return;
  button.addEventListener("click", () => {
    const visible = input.type === "password";
    input.type = visible ? "text" : "password";
    icon.className = `ti ${visible ? "ti-eye-off" : "ti-eye"} text-lg`;
    const showLabel = button.dataset.i18nShow || gettext("Show password");
    const hideLabel = button.dataset.i18nHide || gettext("Hide password");
    button.setAttribute("aria-label", visible ? hideLabel : showLabel);
  });
});

/** Signup step navigation and role selection. */
document.addEventListener("DOMContentLoaded", function () {
  const nextButton = document.getElementById("next-button");
  const backButton = document.getElementById("back-button");
  const step1 = document.getElementById("signup-step-1");
  const step2 = document.getElementById("signup-step-2");
  const step1Indicator = document.getElementById("step-1-indicator");
  const step2Indicator = document.getElementById("step-2-indicator");
  const roleCards = document.querySelectorAll(".role-card");

  function updateStepIndicator(activeStep) {
    if (activeStep === 1) {
      if (step1Indicator) {
        step1Indicator.querySelector('span:first-child').className = 'flex h-7 w-7 items-center justify-center rounded-full bg-primary text-xs font-semibold text-white';
        step1Indicator.querySelector('span:last-child').className = 'text-xs font-semibold text-primary';
      }
      if (step2Indicator) {
        step2Indicator.querySelector('span:first-child').className = 'flex h-7 w-7 items-center justify-center rounded-full bg-border text-xs font-semibold text-muted';
        step2Indicator.querySelector('span:last-child').className = 'text-xs font-medium text-muted';
      }
    } else {
      if (step1Indicator) {
        step1Indicator.querySelector('span:first-child').className = 'flex h-7 w-7 items-center justify-center rounded-full bg-success text-xs font-semibold text-white';
        step1Indicator.querySelector('span:last-child').className = 'text-xs font-semibold text-success';
      }
      if (step2Indicator) {
        step2Indicator.querySelector('span:first-child').className = 'flex h-7 w-7 items-center justify-center rounded-full bg-primary text-xs font-semibold text-white';
        step2Indicator.querySelector('span:last-child').className = 'text-xs font-semibold text-primary';
      }
    }
  }

  function hasStep2Errors() {
    return Boolean(
      step2?.querySelector(".text-danger, .text-red-500")
    );
  }

  function showStep(stepNumber) {
    const currentStepInput = document.getElementById("current_step");
    if (currentStepInput) currentStepInput.value = String(stepNumber);
    if (stepNumber === 1) {
      if (step1) step1.classList.remove("hidden");
      if (step2) step2.classList.add("hidden");
      updateStepIndicator(1);
    } else {
      if (step1) step1.classList.add("hidden");
      if (step2) step2.classList.remove("hidden");
      updateStepIndicator(2);
    }
  }

  if (hasStep2Errors()) {
    showStep(2);
  } else {
    showStep(1);
  }

  roleCards.forEach((card) => {
    const inner = card.querySelector(".role-card-inner");
    const radio = card.querySelector('input[type="radio"]');

    function selectCard(cardToSelect) {
      roleCards.forEach((item) => {
        const itemInner = item.querySelector(".role-card-inner");
        if (!itemInner) return;
        itemInner.classList.remove("border-2", "border-secondary", "bg-primary-soft", "shadow-sm");
        itemInner.classList.add("border", "border-line", "bg-white");
        const itemRadio = item.querySelector('input[type="radio"]');
        if (itemRadio) itemRadio.checked = false;
      });

      if (!cardToSelect) return;
      if (inner) {
        inner.classList.remove("border", "border-line", "bg-white");
        inner.classList.add("border-2", "border-secondary", "bg-primary-soft", "shadow-sm");
      }
      const selectedRadio = cardToSelect.querySelector('input[type="radio"]');
      if (selectedRadio) selectedRadio.checked = true;
    }

    card.addEventListener("click", () => selectCard(card));

    radio?.addEventListener("change", () => selectCard(card));

    card.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        selectCard(card);
      }
    });

    if (radio?.checked) selectCard(card);
  });

  if (nextButton) {
    nextButton.addEventListener("click", () => {
      const selectedRole = document.querySelector('input[name="role"]:checked');
      if (!selectedRole) {
        alert(gettext("Please select your profile type."));
        return;
      }
      showStep(2);
    });
  }

  if (backButton) {
    backButton.addEventListener("click", () => {
      showStep(1);
    });
  }
});
