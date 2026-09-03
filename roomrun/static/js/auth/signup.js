/** Password visibility controls for the registration form. */
document.querySelectorAll("[data-password-toggle]").forEach((button) => {
  const input = document.getElementById(button.dataset.passwordToggle);
  const icon = button.querySelector("i");
  if (!input || !icon) return;
  button.addEventListener("click", () => {
    const visible = input.type === "password";
    input.type = visible ? "text" : "password";
    icon.className = `ti ${visible ? "ti-eye-off" : "ti-eye"} text-lg`;
    const showLabel = button.dataset.i18nShow || "Show password";
    const hideLabel = button.dataset.i18nHide || "Hide password";
    button.setAttribute("aria-label", visible ? hideLabel : showLabel);
  });
});
